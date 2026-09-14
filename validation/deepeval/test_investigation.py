import json
import os
import time
from pathlib import Path

import pytest

from validation.datasets.golden import cases
from validation.deepeval.metrics.aml_correctness import aml_correctness

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "reports" / "gemini_agreement.json"


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


def _gemini_live_ready() -> bool:
    return bool(os.getenv("CW_GEMINI_LIVE"))


def test_aml_correctness_metric():
    assert aml_correctness("monitor", "monitor") == 1.0
    assert aml_correctness("freeze_account", "monitor") == 0.0


@pytest.mark.skipif(not _gemini_live_ready(), reason="live Gemini agreement needs GEMINI_API_KEY or CW_GEMINI_LIVE")
def test_gemini_deterministic_agreement(isolated_db, monkeypatch):
    _load_dotenv()
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", os.getenv("GOOGLE_CLOUD_PROJECT") or "corridor-watch-508420")
    if not (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")):
        monkeypatch.setenv("GEMINI_BACKEND", "vertex")
        monkeypatch.setenv("VERTEX_LOCATION", os.getenv("VERTEX_LOCATION") or "global")
    monkeypatch.setenv("GEMINI_MODEL", os.getenv("GEMINI_MODEL") or "gemini-2.5-flash")
    import agent
    agent._client = None
    agent.MODEL = os.environ["GEMINI_MODEL"]

    from pubsub.ingestion import ingest_transaction
    from investigations.service import build_investigation
    from validation.reliability.test_idempotency import _event

    golden = cases()
    n = int(os.getenv("CW_GEMINI_N") or min(100, len(golden)))
    selected = golden[:n]
    rows = []
    for row in selected:
        txn_id = row["txn_id"]
        kwargs = {k: row[k] for k in ("txn_id", "source_event_id", "amount", "account_age_days", "fraud_scenario") if k in row}
        ingest_transaction(_event(**kwargs), message_id=f"m-{txn_id}")
        det = build_investigation(txn_id, use_gemini=False)
        started = time.perf_counter()
        gem = build_investigation(txn_id, use_gemini=True)
        latency_ms = round((time.perf_counter() - started) * 1000.0, 1)
        usage = agent.last_usage()
        det_d = det["report"]["recommended_disposition"]
        gem_d = gem["report"]["recommended_disposition"]
        used = bool(gem["report"].get("gemini_used"))
        rows.append({
            "txn_id": txn_id,
            "deterministic": det_d,
            "gemini": gem_d,
            "agree": used and det_d == gem_d,
            "gemini_used": used,
            "grounded": gem["report"].get("grounded"),
            "uncertainty": gem["report"].get("uncertainty"),
            "gemini_error": gem.get("gemini_error"),
            "latency_ms": latency_ms,
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
            "cost_usd": usage.get("cost_usd"),
            "parse_error": usage.get("parse_error"),
            "finish_reason": usage.get("finish_reason"),
        })
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps({"partial": True, "n": len(rows), "cases": rows}, indent=2))

    invoked = [r for r in rows if r["gemini_error"] is None]
    scored = [r for r in invoked if r["gemini_used"]]
    agreement = (sum(1 for r in scored if r["agree"]) / len(scored)) if scored else 0.0
    latencies = sorted(r["latency_ms"] for r in invoked)
    p95 = latencies[int(0.95 * (len(latencies) - 1))] if latencies else None
    costs = [r.get("cost_usd") for r in scored if r.get("cost_usd") is not None]
    cost_per = round(sum(costs) / len(costs), 6) if costs else None
    toks = [(r.get("prompt_tokens") or 0) + (r.get("completion_tokens") or 0) for r in scored]
    tokens_per = round(sum(toks) / len(toks), 1) if toks else None
    k = sum(1 for r in scored if r["agree"])
    n_scored = len(scored)
    z = 1.96
    ci = None
    if n_scored:
        p = k / n_scored
        denom = 1 + z ** 2 / n_scored
        centre = (p + z ** 2 / (2 * n_scored)) / denom
        spread = z * ((p * (1 - p) / n_scored + z ** 2 / (4 * n_scored * n_scored)) ** 0.5) / denom
        ci = [round(max(0.0, centre - spread), 4), round(min(1.0, centre + spread), 4)]
    payload = {
        "cases": rows,
        "invoked_n": len(invoked),
        "schema_valid_n": len(scored),
        "agreement": round(agreement, 4) if scored else None,
        "agreement_ci": ci,
        "p95_latency_ms": p95,
        "cost_per_case_usd": cost_per,
        "tokens_per_case": tokens_per,
        "model": os.getenv("GEMINI_MODEL"),
        "note": (
            f"Agreement is schema-valid Gemini vs deterministic. "
            f"invoked={len(invoked)} schema_valid={len(scored)}. "
            "p95 is over all invoked latencies. Cost from usage_metadata."
        ),
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(payload, indent=2))
    assert invoked, f"Gemini was not invoked: {rows}"
    assert scored, (
        "Gemini responded but no report passed InvestigationReport schema; "
        f"see {REPORT}"
    )
    assert agreement >= 0.85, f"agreement {agreement} < 0.85"
    assert p95 is not None and p95 <= 8000, f"p95 {p95} ms > 8000"
    assert cost_per is not None and cost_per <= 0.05, f"cost/case {cost_per} > 0.05"
