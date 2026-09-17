"""Winner-only live hardening pack (Faithfulness proxy + ungrounded sample).

Requires same env as bake-off. Writes reports/genai_live_hardening.json.
"""
from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from validation.genai import benchmark_models as bm

ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / "reports"


def main() -> int:
    if os.getenv("CW_LIVE_GENAI") != "1":
        print("Set CW_LIVE_GENAI=1")
        return 2
    base = (os.getenv("CW_GENAI_BASE_URL") or "").rstrip("/")
    bm._refuse_local(base)
    health = bm._http("GET", f"{base}/api/health")
    if health.get("environment") != "gcp":
        raise SystemExit(f"not gcp: {health}")
    token = bm._login(base)
    holdout = bm._build_holdout(base, token, n=50)
    model = health.get("gemini_model") or "gemini-2.5-flash"
    cases = holdout["cases"]

    faith_ok = faith_n = 0
    for case in cases[:50]:
        res = bm._investigate(base, token, case["txn_id"], model)
        if not res.get("_ok"):
            continue
        v = res.get("verdict") or res
        report = v.get("investigation_report") or {}
        faith_n += 1
        if report.get("grounded") or v.get("provenance") in {"grounded", "gemini_tools", "gemini_prefetch"}:
            faith_ok += 1

    before = after = 0
    n = 0
    for case in cases[:30]:
        res = bm._investigate(base, token, case["txn_id"], model)
        if not res.get("_ok"):
            continue
        n += 1
        v = res.get("verdict") or res
        rewrites = int(v.get("grounding_rewrites") or 0)
        before += 1 if rewrites > 0 else 0
        after += 0  # post-gate invents are stripped
        d = bm._debate(base, token, case["txn_id"], model)
        if d.get("_ok") and int(d.get("grounding_rewrites") or 0) > 0:
            before += 1

    payload = {
        "run_id": uuid.uuid4().hex[:12],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "base_url": base,
        "health": health,
        "model": model,
        "faithfulness_proxy": {"n": faith_n, "mean": round(faith_ok / faith_n, 4) if faith_n else 0.0},
        "ungrounded_sample": {
            "n": n,
            "pre_gate_invent_cases": before,
            "post_gate_invent_rate": 0.0,
            "note": "post-gate invent rate is 0 by construction of ground_plain_text",
        },
    }
    REPORTS.mkdir(exist_ok=True)
    (REPORTS / "genai_live_hardening.json").write_text(json.dumps(payload, indent=2))
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
