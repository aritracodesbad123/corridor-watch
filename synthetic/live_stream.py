"""In-process async synthetic stream. Gemini is never invoked here."""
from __future__ import annotations

import random
import threading
import time
from datetime import datetime, timezone

from synthetic.publisher import publish_in_process
from synthetic.transaction_generator import generate_events
from synthetic.world import seed_banks

STREAM_ID = "current"


def _parse_ts(value: str | None):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _save_state(payload: dict) -> None:
    try:
        from db import connect, init_schema, upsert
        from pubsub.schemas import utc_now

        init_schema()
        con = connect()
        upsert(con, "live_stream_state", "stream_id", {
            "stream_id": STREAM_ID,
            "updated_at": utc_now(),
            **payload,
        })
        con.commit()
        con.close()
    except Exception:
        return


def _load_state() -> dict | None:
    try:
        from db import connect, init_schema

        init_schema()
        con = connect()
        row = con.execute(
            "SELECT * FROM live_stream_state WHERE stream_id=?", (STREAM_ID,)
        ).fetchone()
        con.close()
        return dict(row) if row else None
    except Exception:
        return None


def _ledger_since(started_at: str) -> tuple[int | None, int | None]:
    try:
        from db import connect, init_schema

        init_schema()
        con = connect()
        ingested = int(con.execute(
            "SELECT COUNT(*) AS c FROM ingestion_events WHERE received_at>=?",
            (started_at,),
        ).fetchone()["c"])
        flagged = int(con.execute(
            "SELECT COUNT(*) AS c FROM investigation_queue WHERE created_at>=?",
            (started_at,),
        ).fetchone()["c"])
        con.close()
        return ingested, flagged
    except Exception:
        return None, None


class LiveStream:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.running = False
        self.started_at: str | None = None
        self.ends_at: str | None = None
        self.rate = 0
        self.duration_seconds = 0
        self.scenario_mix = "live"
        self.accepted = 0
        self.queued = 0
        self.failed = 0
        self.duplicates = 0
        self.last_error: str | None = None
        self.transport: str = "in_process"
        self._end_ts = 0.0

    def status(self) -> dict:
        with self._lock:
            remaining = max(0, int(self._end_ts - time.time())) if self.running else 0
            return {
                "running": self.running,
                "started_at": self.started_at,
                "ends_at": self.ends_at,
                "remaining_seconds": remaining,
                "rate": self.rate,
                "duration_seconds": self.duration_seconds,
                "scenario_mix": self.scenario_mix,
                "accepted": self.accepted,
                "queued_for_investigation": self.queued,
                "failed": self.failed,
                "duplicates": self.duplicates,
                "last_error": self.last_error,
                "transport": self.transport,
                "gemini_invoked": False,
            }

    def public_status(self) -> dict:
        """Instance memory plus durable ledger counts.

        Cloud Run has several replicas. Only one holds the publisher thread.
        Pub/Sub also cannot return 'flagged' to the publisher. Command Center
        therefore prefers session state and ledger totals since started_at.
        """
        mem = self.status()
        stored = _load_state() or {}
        started_at = mem.get("started_at") or stored.get("started_at")
        ends_at = mem.get("ends_at") or stored.get("ends_at")
        end_ts = _parse_ts(ends_at)
        now = datetime.now(timezone.utc)
        expired = bool(end_ts and now > end_ts)
        stored_running = bool(int(stored.get("running") or 0))
        running = bool(mem.get("running") or (stored_running and not expired))
        published = int(mem.get("accepted") or 0)
        if stored.get("published") is not None:
            published = max(published, int(stored.get("published") or 0))
        ingested, flagged = _ledger_since(started_at) if started_at else (None, None)
        queued = int(mem.get("queued_for_investigation") or 0)
        if flagged is not None:
            queued = max(queued, flagged)
        accepted = published
        if ingested is not None:
            accepted = max(accepted, ingested)
        remaining = mem.get("remaining_seconds") or 0
        if running and end_ts and not mem.get("running"):
            remaining = max(0, int((end_ts - now).total_seconds()))
        return {
            **mem,
            "running": running,
            "started_at": started_at,
            "ends_at": ends_at,
            "remaining_seconds": remaining,
            "rate": mem.get("rate") or stored.get("rate") or 0,
            "duration_seconds": mem.get("duration_seconds") or stored.get("duration_seconds") or 0,
            "scenario_mix": mem.get("scenario_mix") or stored.get("scenario_mix") or mem.get("scenario_mix"),
            "transport": mem.get("transport") or stored.get("transport") or "in_process",
            "accepted": accepted,
            "queued_for_investigation": queued,
            "ingested": ingested,
            "published": published,
            "count_source": "ledger" if ingested is not None else "in_memory",
            "gemini_invoked": False,
        }

    def _persist(self, *, running: bool | None = None) -> None:
        snap = self.status()
        _save_state({
            "running": 1 if (snap["running"] if running is None else running) else 0,
            "started_at": snap["started_at"],
            "ends_at": snap["ends_at"],
            "rate": snap["rate"],
            "duration_seconds": snap["duration_seconds"],
            "scenario_mix": snap["scenario_mix"],
            "transport": snap["transport"],
            "published": snap["accepted"],
        })

    def start(self, *, rate: int = 8, duration_seconds: int = 3600, scenario_mix: str = "live", force: bool = False) -> dict:
        with self._lock:
            if self.running and not force:
                return self.public_status()
            if self._thread and self._thread.is_alive():
                self._stop.set()
        if force:
            self.stop()
        self._stop = threading.Event()
        now = time.time()
        with self._lock:
            self.running = True
            self.rate = max(1, min(int(rate), 50))
            self.duration_seconds = max(1, min(int(duration_seconds), 3600 * 6))
            self.scenario_mix = scenario_mix or "live"
            self.accepted = 0
            self.queued = 0
            self.failed = 0
            self.duplicates = 0
            self.last_error = None
            self.transport = "pubsub" if _want_pubsub() else "in_process"
            self._end_ts = now + self.duration_seconds
            self.started_at = datetime.now(timezone.utc).isoformat()
            self.ends_at = datetime.fromtimestamp(self._end_ts, timezone.utc).isoformat()
            self._thread = threading.Thread(target=self._loop, name="cw-live-stream", daemon=True)
            self._thread.start()
        self._persist(running=True)
        return self.public_status()

    def stop(self) -> dict:
        self._stop.set()
        thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=5)
        with self._lock:
            self.running = False
            self._end_ts = 0.0
        self._persist(running=False)
        return self.public_status()

    def _loop(self) -> None:
        try:
            seed_banks()
            rate = self.rate
            batch = max(1, min(8, rate))
            rng = random.Random()
            while not self._stop.is_set() and time.time() < self._end_ts:
                tick = time.perf_counter()
                events = generate_events(
                    batch,
                    seed=rng.randint(1, 1_000_000_000),
                    scenario_mix=self.scenario_mix,
                )
                try:
                    result = _publish_events(events)
                    with self._lock:
                        self.transport = result.get("transport") or self.transport
                        self.accepted += int(result.get("accepted") or 0)
                        self.queued += int(result.get("queued") or 0)
                        self.failed += int(result.get("failed") or 0)
                        self.duplicates += int(result.get("duplicates") or 0)
                        if result.get("publish_error"):
                            self.last_error = result["publish_error"]
                    self._persist(running=True)
                except Exception as exc:
                    with self._lock:
                        self.failed += 1
                        self.last_error = str(exc)
                sleep_for = (batch / rate) - (time.perf_counter() - tick)
                if sleep_for > 0:
                    self._stop.wait(sleep_for)
        finally:
            with self._lock:
                self.running = False
            self._persist(running=False)


def _want_pubsub() -> bool:
    from pubsub.publisher import use_gcp_pubsub
    return use_gcp_pubsub()


def _publish_events(events) -> dict:
    if _want_pubsub():
        try:
            from pubsub.publisher import publish_gcp
            published = publish_gcp(events)
            return {
                "accepted": published,
                "queued": 0,
                "failed": 0,
                "duplicates": 0,
                "transport": "pubsub",
            }
        except Exception as exc:
            result = publish_in_process(events, source="live_stream_fallback")
            result["transport"] = "in_process_fallback"
            result["publish_error"] = str(exc)
            return result
    result = publish_in_process(events, source="live_stream")
    result["transport"] = "in_process"
    return result


STREAM = LiveStream()
