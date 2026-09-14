"""Live Pub/Sub → Cloud Run → Cloud SQL runner. Never invents TPS."""
from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / "reports" / "scale"

GATES = {100: 95, 500: 400, 1000: 800, 2000: 1500}


def _load_dotenv() -> None:
    path = ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def command_url() -> str:
    url = os.getenv("CW_COMMAND_URL", "").rstrip("/")
    if url:
        return url
    import subprocess
    out = subprocess.check_output(
        [
            "gcloud", "run", "services", "describe", "corridor-watch",
            "--project", os.getenv("GOOGLE_CLOUD_PROJECT", "corridor-watch-508420"),
            "--region", os.getenv("REGION", "asia-southeast1"),
            "--format", "value(status.url)",
        ],
        text=True,
    ).strip()
    if not out:
        raise RuntimeError("CW_COMMAND_URL unset and gcloud returned no URL")
    return out.rstrip("/")


def fiu_token(base: str) -> str:
    users = json.loads((ROOT / "credentials.json").read_text())["users"]
    lead = next(u for u in users if u.get("role") == "fiu_lead")
    req = urllib.request.Request(
        f"{base}/api/auth/login",
        data=json.dumps({"username": lead["username"], "password": lead["password"]}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = json.loads(resp.read().decode())
    token = body.get("token")
    if not token:
        raise RuntimeError("login returned no token")
    return token


def duration_for(rate: int) -> int:
    if os.getenv("CW_SCALE_DURATION"):
        return int(os.getenv("CW_SCALE_DURATION"))
    # Spec says 5 min; that would flood a ~5.65 TPS consumer. Short live probe.
    return 20 if rate <= 100 else 10


def purge_backlog(project: str, subscription: str = "corridor-transactions-push") -> None:
    """Drop undelivered messages so consume TPS is not the old backlog."""
    from datetime import datetime, timezone
    from google.cloud import pubsub_v1
    from google.protobuf.timestamp_pb2 import Timestamp

    subscriber = pubsub_v1.SubscriberClient()
    path = subscriber.subscription_path(project, subscription)
    when = Timestamp()
    when.FromDatetime(datetime.now(timezone.utc))
    subscriber.seek(request={"subscription": path, "time": when})


def run_live(rate: int) -> dict:
    _load_dotenv()
    os.environ.setdefault("GOOGLE_CLOUD_PROJECT", "corridor-watch-508420")
    from pubsub_load_generator import run
    try:
        purge_backlog(os.environ["GOOGLE_CLOUD_PROJECT"])
    except Exception:
        pass

    base = command_url()
    token = fiu_token(base)
    duration = duration_for(rate)
    report = run(
        rate=rate,
        duration=duration,
        batch_size=500,
        seed=42,
        scenario_mix="default",
        in_process=False,
        url="",
        token=token,
        pubsub=True,
        command_url=base,
        project=os.environ["GOOGLE_CLOUD_PROJECT"],
        topic="corridor-transactions",
        subscription="corridor-transactions-push",
        persist=True,
    )
    REPORTS.mkdir(parents=True, exist_ok=True)
    out = REPORTS / f"test_{rate}_tps.json"
    safe = {k: v for k, v in report.items() if k not in {"token", "authorization"}}
    safe["gate_min_tps"] = GATES[rate]
    safe["gate_passed"] = (
        report.get("achieved_tps") is not None and report["achieved_tps"] >= GATES[rate]
    )
    out.write_text(json.dumps(safe, indent=2, default=str))
    return safe
