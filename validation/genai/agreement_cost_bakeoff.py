"""
Replicate gemini_agreement protocol across models with real USD $/case.

Same golden set + build_investigation path as validation/deepeval/test_investigation.py,
but once per model. Does not overwrite frozen reports/gemini_agreement.json.

Requires CW_GEMINI_LIVE=1 and Vertex/API credentials (same as agreement test).

  CW_GEMINI_LIVE=1 CW_GEMINI_N=100 python -m validation.genai.agreement_cost_bakeoff
"""
from __future__ import annotations

import json
import os
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / "reports"
OUT_JSON = REPORTS / "genai_agreement_cost_bakeoff.json"
OUT_MD = REPORTS / "genai_agreement_cost_bakeoff.md"

DEFAULT_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.5-pro",
    "gemini-3.6-flash",
    "gemini-3.8-flash",
    "gemini-3.1-pro-preview",
]
ALERT = {"hold_payment", "escalate_fiu", "freeze_account"}


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


def _wilson_ci(k: int, n: int) -> list[float] | None:
    if not n:
        return None
    z = 1.96
    p = k / n
    denom = 1 + z**2 / n
    centre = (p + z**2 / (2 * n)) / denom
    spread = z * ((p * (1 - p) / n + z**2 / (4 * n * n)) ** 0.5) / denom
    return [round(max(0.0, centre - spread), 4), round(min(1.0, centre + spread), 4)]


def _prf1(y_true: list[bool], y_pred: list[bool]) -> dict:
    tp = fp = tn = fn = 0
    for t, p in zip(y_true, y_pred):
        if t and p:
            tp += 1
        elif not t and p:
            fp += 1
        elif not t and not p:
            tn += 1
        else:
            fn += 1
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    fpr = fp / (fp + tn) if (fp + tn) else 0.0
    return {
        "tp": tp, "fp": fp, "tn": tn, "fn": fn,
        "precision": round(prec, 4), "recall": round(rec, 4),
        "f1": round(f1, 4), "fpr": round(fpr, 4),
    }


def _setup_db(tmp: Path) -> None:
    import db
    from config import reset_settings_cache
    from db import init_schema
    from patterns.repository import seed_library

    os.environ["ENVIRONMENT"] = "local"
    os.environ.pop("DATABASE_URL", None)
    db.DB_PATH = tmp / "agreement_bakeoff.db"
    reset_settings_cache()
    init_schema()
    seed_library()


def _run_model(model: str, selected: list[dict]) -> dict:
    import agent
    from pubsub.ingestion import ingest_transaction
    from investigations.service import build_investigation
    from validation.reliability.test_idempotency import _event

    agent._client = None
    agent.MODEL = model
    os.environ["GEMINI_MODEL"] = model
    tok = agent.push_model_override(model)
    rows = []
    try:
        for row in selected:
            txn_id = f"{row['txn_id']}-{model[-12:]}-{uuid.uuid4().hex[:6]}"
            kwargs = {
                k: row[k]
                for k in ("source_event_id", "amount", "account_age_days", "fraud_scenario", "purpose")
                if k in row
            }
            kwargs["txn_id"] = txn_id
            kwargs["source_event_id"] = f"E-{txn_id}"
            ingest_transaction(_event(**kwargs), message_id=f"m-{txn_id}")
            det = build_investigation(txn_id, use_gemini=False)
            started = time.perf_counter()
            gem = build_investigation(txn_id, use_gemini=True)
            latency_ms = round((time.perf_counter() - started) * 1000.0, 1)
            usage = agent.last_usage()
            det_d = det["report"]["recommended_disposition"]
            gem_d = gem["report"]["recommended_disposition"]
            used = bool(gem["report"].get("gemini_used"))
            expected = row.get("expected_disposition")
            rows.append({
                "txn_id": txn_id,
                "kind": row.get("kind"),
                "expected_disposition": expected,
                "deterministic": det_d,
                "gemini": gem_d,
                "agree": used and det_d == gem_d,
                "gemini_used": used,
                "grounded": gem["report"].get("grounded"),
                "gemini_error": gem.get("gemini_error"),
                "latency_ms": latency_ms,
                "prompt_tokens": usage.get("prompt_tokens"),
                "completion_tokens": usage.get("completion_tokens"),
                "thoughts_tokens": usage.get("thoughts_tokens"),
                "cost_usd": usage.get("cost_usd"),
            })
    finally:
        agent.reset_model_override(tok)

    invoked = [r for r in rows if r["gemini_error"] is None]
    scored = [r for r in invoked if r["gemini_used"]]
    agreement = (sum(1 for r in scored if r["agree"]) / len(scored)) if scored else 0.0
    latencies = sorted(r["latency_ms"] for r in invoked)
    p95 = latencies[int(0.95 * (len(latencies) - 1))] if latencies else None
    costs = [r["cost_usd"] for r in scored if r.get("cost_usd") is not None]
    cost_per = round(sum(costs) / len(costs), 6) if costs else None
    toks = [(r.get("prompt_tokens") or 0) + (r.get("completion_tokens") or 0) + (r.get("thoughts_tokens") or 0) for r in scored]
    tokens_per = round(sum(toks) / len(toks), 1) if toks else None
    ungrounded = round(sum(1 for r in scored if r.get("grounded") is False) / len(scored), 4) if scored else None

    # Binary alert quality vs golden expected (mixed set includes benign)
    y_true = [r.get("expected_disposition") in ALERT for r in scored]
    y_pred = [r.get("gemini") in ALERT for r in scored]
    alert_metrics = _prf1(y_true, y_pred) if scored else None

    k = sum(1 for r in scored if r["agree"])
    err_sample = next((r.get("gemini_error") for r in rows if r.get("gemini_error")), None)
    return {
        "model": model,
        "status": "ok" if scored else "failed",
        "error": (err_sample[:400] if err_sample and not scored else None),
        "invoked_n": len(invoked),
        "schema_valid_n": len(scored),
        "agreement": round(agreement, 4) if scored else None,
        "agreement_ci": _wilson_ci(k, len(scored)) if scored else None,
        "p95_latency_ms": p95,
        "cost_per_case_usd": cost_per,
        "tokens_per_case": tokens_per,
        "ungrounded_rate": ungrounded,
        "alert_vs_expected": alert_metrics,
        "cases": rows,
    }


def _select_winner(rows: list[dict]) -> tuple[str | None, str]:
    """Prefer agreement≥0.85, p95≤8s, then lowest USD, then highest agreement, then lowest FPR."""
    gated = [
        r for r in rows
        if r.get("status") == "ok"
        and (r.get("agreement") or 0) >= 0.85
        and r.get("p95_latency_ms") is not None
        and r["p95_latency_ms"] <= 8000
        and r.get("cost_per_case_usd") is not None
    ]
    if not gated:
        gated = [r for r in rows if r.get("status") == "ok" and r.get("cost_per_case_usd") is not None]
    if not gated:
        return None, "No model produced measurable USD cost."
    gated.sort(key=lambda r: (
        r.get("cost_per_case_usd", 9e9),
        -(r.get("agreement") or 0),
        (r.get("alert_vs_expected") or {}).get("fpr", 1),
        r.get("p95_latency_ms") or 9e9,
    ))
    w = gated[0]
    return w["model"], (
        f"Selected {w['model']}: agreement={w.get('agreement')} "
        f"cost/case=${w.get('cost_per_case_usd')} p95={w.get('p95_latency_ms')}ms "
        f"alert_FPR={(w.get('alert_vs_expected') or {}).get('fpr')}"
    )


def main() -> int:
    if os.getenv("CW_GEMINI_LIVE") != "1":
        print("Set CW_GEMINI_LIVE=1 to run the agreement+USD bake-off.")
        return 2
    _load_dotenv()
    if not (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")):
        os.environ.setdefault("GEMINI_BACKEND", "vertex")
        os.environ.setdefault("VERTEX_LOCATION", os.getenv("VERTEX_LOCATION") or "global")
    os.environ.setdefault("GOOGLE_CLOUD_PROJECT", os.getenv("GOOGLE_CLOUD_PROJECT") or "corridor-watch-508420")

    from validation.datasets.golden import cases

    models = [m.strip() for m in (os.getenv("CW_GEMINI_MODELS") or ",".join(DEFAULT_MODELS)).split(",") if m.strip()]
    golden = cases()
    n = int(os.getenv("CW_GEMINI_N") or min(100, len(golden)))
    selected = golden[:n]

    prior: dict[str, dict] = {}
    if os.getenv("CW_GEMINI_MERGE") == "1" and OUT_JSON.exists():
        prev = json.loads(OUT_JSON.read_text())
        for r in prev.get("models") or []:
            if r.get("status") == "ok" and r.get("model"):
                prior[r["model"]] = r
                print(f"merge: keep {r['model']} (agreement={r.get('agreement')} $/case={r.get('cost_per_case_usd')})")

    results = []
    with tempfile.TemporaryDirectory(prefix="cw-agree-") as td:
        _setup_db(Path(td))
        for model in models:
            if model in prior:
                results.append(prior[model])
                continue
            print(f"\n=== {model} (n={n}) ===", flush=True)
            try:
                row = _run_model(model, selected)
            except Exception as e:
                row = {"model": model, "status": "error", "error": str(e)[:400]}
            results.append(row)
            # Incremental write so a kill mid-run still leaves evidence
            partial = {
                "partial": True,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "n_per_model": n,
                "models": [
                    {k: v for k, v in r.items() if k != "cases"} | {"cases_n": len(r.get("cases") or [])}
                    for r in results
                ],
            }
            REPORTS.mkdir(parents=True, exist_ok=True)
            OUT_JSON.write_text(json.dumps(partial, indent=2))
            print(
                f"  agreement={row.get('agreement')} cost/case=${row.get('cost_per_case_usd')} "
                f"p95={row.get('p95_latency_ms')} ungrounded={row.get('ungrounded_rate')} "
                f"err={(row.get('error') or '')[:80]}",
                flush=True,
            )

    selected_model, rationale = _select_winner(results)
    payload = {
        "run_id": uuid.uuid4().hex[:12],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "protocol": "gemini_agreement_replica",
        "n_per_model": n,
        "pricing_note": "USD from usage_metadata tokens × Vertex standard rates in agent.estimate_cost_usd",
        "models": results,
        "selected_model": selected_model,
        "selection_rationale": rationale,
        "note": (
            "Same golden[:n] + build_investigation path as reports/gemini_agreement.json. "
            "cost_per_case_usd is real USD (not latency proxy). "
            "alert_vs_expected uses golden expected_disposition (benign included)."
        ),
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2))

    lines = [
        "# GenAI agreement + USD cost bake-off",
        "",
        f"- run_id: `{payload['run_id']}`",
        f"- protocol: gemini_agreement replica (n={n} per model)",
        f"- selected_model: **{selected_model}**",
        f"- rationale: {rationale}",
        "",
        "| Model | Status | Agreement | Cost $/case | Tokens/case | p95 ms | Ungrounded | P | R | F1 | FPR |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in results:
        a = r.get("alert_vs_expected") or {}
        lines.append(
            f"| `{r.get('model')}` | {r.get('status')} | {r.get('agreement')} | "
            f"{r.get('cost_per_case_usd')} | {r.get('tokens_per_case')} | {r.get('p95_latency_ms')} | "
            f"{r.get('ungrounded_rate')} | {a.get('precision')} | {a.get('recall')} | "
            f"{a.get('f1')} | {a.get('fpr')} |"
        )
    OUT_MD.write_text("\n".join(lines) + "\n")
    print(f"\nWrote {OUT_JSON} and {OUT_MD} — selected={selected_model}")
    return 0 if selected_model else 1


if __name__ == "__main__":
    raise SystemExit(main())
