"""
Dist G GenAI unknown bake-off — novel seed-53 ledger × 5 Gemini models.

Not golden[:n]. Dataset: validation/external/generator_g.py (held-out names).
Writes freeze first, then one-shot GenAI metrics (P/R/F1/FPR + USD $/case).

  CW_GEMINI_LIVE=1 python -m validation.genai.dist_g_bakeoff
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from validation.genai.agreement_cost_bakeoff import (
    ALERT,
    DEFAULT_MODELS,
    _load_dotenv,
    _prf1,
    _select_winner,
    _wilson_ci,
)
from validation.external.generator_b import write_db
from validation.external.generator_g import KNOWN_A_TO_F, POSITIVE_G, SEED, build
from validation.oracle import extract, is_positive

ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / "reports"
OUT_JSON = REPORTS / "genai_dist_g_bakeoff.json"
OUT_MD = REPORTS / "genai_dist_g_bakeoff.md"
DIST_JSON = REPORTS / "dist_g.json"
FREEZE_JSON = REPORTS / "dist_g_freeze.json"


def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip()
    except Exception:
        return "unknown"


def _is_alert(disp: str | None, risk_level: str | None = None) -> bool:
    if (disp or "").lower() in ALERT:
        return True
    return (risk_level or "").lower() == "high"


def _write_freeze(accounts: list[dict], txns: list[dict]) -> dict:
    labels = extract(txns, POSITIVE_G)
    n_pos = sum(1 for t in txns if is_positive(t["txn_id"], labels))
    n_ben = len(txns) - n_pos
    freeze = {
        "run_id": uuid.uuid4().hex[:12],
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": _git_commit(),
        "environment": "local",
        "dataset": "dist_g_freeze",
        "dataset_version": f"generator_g.seed{SEED}",
        "generator": "validation/external/generator_g.py",
        "result_artifact": "reports/genai_dist_g_bakeoff.json",
        "model": None,
        "prompt_version": "investigator-v10",
        "tool_schema_version": "investigation-report-v1",
        "case_count": len(txns),
        "account_count": len(accounts),
        "fraud_count": n_pos,
        "benign_count": n_ben,
        "random_seed": SEED,
        "frozen_before_run": True,
        "one_shot": True,
        "do_not_tune": True,
        "frozen_seed": SEED,
        "positive_scenarios": sorted(POSITIVE_G),
        "known_prior_families": sorted(KNOWN_A_TO_F),
        "note": (
            "GenAI unknown holdout. Novel names disjoint from Dist A–F. "
            "Benign included so FPR is non-vacuous. Runtime ignores fraud_scenario. "
            "Do not overwrite Dist A–F or gemini_agreement.json."
        ),
    }
    REPORTS.mkdir(parents=True, exist_ok=True)
    FREEZE_JSON.write_text(json.dumps(freeze, indent=2) + "\n")
    return freeze


def _setup_dist_db(tmp: Path, accounts: list[dict], txns: list[dict]) -> None:
    import db
    from config import reset_settings_cache
    from graph_features import score_all, write_scores
    from patterns.repository import seed_library

    os.environ["ENVIRONMENT"] = "local"
    os.environ.pop("DATABASE_URL", None)
    db.DB_PATH = tmp / "dist_g.db"
    reset_settings_cache()
    write_db(accounts, txns)
    seed_library()
    con = db.connect()
    scores, scored_txns, _ = score_all(con)
    write_scores(con, scores, scored_txns)
    con.commit()
    con.close()


def _run_model(model: str, txns: list[dict], labels: dict) -> dict:
    import agent
    from investigations.service import build_investigation

    agent._client = None
    agent.MODEL = model
    os.environ["GEMINI_MODEL"] = model
    tok = agent.push_model_override(model)
    rows = []
    try:
        for t in txns:
            txn_id = t["txn_id"]
            started = time.perf_counter()
            det = build_investigation(txn_id, use_gemini=False)
            gem = build_investigation(txn_id, use_gemini=True)
            latency_ms = round((time.perf_counter() - started) * 1000.0, 1)
            usage = agent.last_usage()
            det_d = det["report"]["recommended_disposition"]
            gem_d = gem["report"]["recommended_disposition"]
            risk_level = gem["report"].get("risk_level")
            used = bool(gem["report"].get("gemini_used"))
            oracle = is_positive(txn_id, labels)
            rows.append({
                "txn_id": txn_id,
                "fraud_scenario": t.get("fraud_scenario"),
                "oracle_fraud": oracle,
                "expected_disposition": "hold_payment" if oracle else "clear",
                "deterministic": det_d,
                "gemini": gem_d,
                "risk_level": risk_level,
                "agree": used and det_d == gem_d,
                "gemini_used": used,
                "grounded": gem["report"].get("grounded"),
                "gemini_error": gem.get("gemini_error"),
                "latency_ms": latency_ms,
                "prompt_tokens": usage.get("prompt_tokens"),
                "completion_tokens": usage.get("completion_tokens"),
                "thoughts_tokens": usage.get("thoughts_tokens"),
                "cost_usd": usage.get("cost_usd"),
                "alert_pred": _is_alert(gem_d, risk_level),
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
    toks = [
        (r.get("prompt_tokens") or 0)
        + (r.get("completion_tokens") or 0)
        + (r.get("thoughts_tokens") or 0)
        for r in scored
    ]
    tokens_per = round(sum(toks) / len(toks), 1) if toks else None
    ungrounded = (
        round(sum(1 for r in scored if r.get("grounded") is False) / len(scored), 4)
        if scored else None
    )
    y_true = [r["oracle_fraud"] for r in scored]
    y_pred = [r["alert_pred"] for r in scored]
    alert_metrics = _prf1(y_true, y_pred) if scored else None
    benign_n = sum(1 for r in scored if not r["oracle_fraud"])
    if alert_metrics is not None and benign_n == 0:
        alert_metrics["fpr"] = None
        alert_metrics["fpr_note"] = "vacuous: no benign cases"

    k = sum(1 for r in scored if r["agree"])
    err_sample = next((r.get("gemini_error") for r in rows if r.get("gemini_error")), None)
    return {
        "model": model,
        "status": "ok" if scored else "failed",
        "error": (err_sample[:400] if err_sample and not scored else None),
        "invoked_n": len(invoked),
        "schema_valid_n": len(scored),
        "benign_n": benign_n,
        "fraud_n": sum(1 for r in scored if r["oracle_fraud"]),
        "agreement": round(agreement, 4) if scored else None,
        "agreement_ci": _wilson_ci(k, len(scored)) if scored else None,
        "p95_latency_ms": p95,
        "cost_per_case_usd": cost_per,
        "tokens_per_case": tokens_per,
        "ungrounded_rate": ungrounded,
        "alert_vs_oracle": alert_metrics,
        # alias so _select_winner can sort on FPR like agreement bakeoff
        "alert_vs_expected": alert_metrics,
        "cases": rows,
    }


def main() -> int:
    if os.getenv("CW_GEMINI_LIVE") != "1":
        print("Set CW_GEMINI_LIVE=1 to run Dist G GenAI bake-off.")
        return 2
    _load_dotenv()
    if not (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")):
        os.environ.setdefault("GEMINI_BACKEND", "vertex")
        os.environ.setdefault("VERTEX_LOCATION", os.getenv("VERTEX_LOCATION") or "global")
    os.environ.setdefault(
        "GOOGLE_CLOUD_PROJECT",
        os.getenv("GOOGLE_CLOUD_PROJECT") or "corridor-watch-508420",
    )

    accounts, txns = build(seed=SEED)
    labels = extract(txns, POSITIVE_G)
    freeze = _write_freeze(accounts, txns)
    print(
        f"Froze Dist G seed={SEED} n={len(txns)} "
        f"fraud={freeze['fraud_count']} benign={freeze['benign_count']} → {FREEZE_JSON}",
        flush=True,
    )
    if freeze["benign_count"] < 1:
        print("Refuse: Dist G must include benign for non-vacuous FPR.")
        return 1
    if freeze["case_count"] < 80:
        print(f"Warn: n={freeze['case_count']} < 80 (Dist-style target). Continuing.")

    models = [
        m.strip()
        for m in (os.getenv("CW_GEMINI_MODELS") or ",".join(DEFAULT_MODELS)).split(",")
        if m.strip()
    ]
    prior: dict[str, dict] = {}
    if os.getenv("CW_GEMINI_MERGE") == "1" and OUT_JSON.exists():
        prev = json.loads(OUT_JSON.read_text())
        for r in prev.get("models") or []:
            if r.get("status") == "ok" and r.get("model"):
                prior[r["model"]] = r
                print(f"merge: keep {r['model']}")

    results = []
    with tempfile.TemporaryDirectory(prefix="cw-distg-") as td:
        # One shared ledger; models only swap Gemini override
        _setup_dist_db(Path(td), accounts, txns)
        for model in models:
            if model in prior:
                results.append(prior[model])
                continue
            print(f"\n=== Dist G / {model} (n={len(txns)}) ===", flush=True)
            try:
                row = _run_model(model, txns, labels)
            except Exception as e:
                row = {"model": model, "status": "error", "error": str(e)[:400]}
            results.append(row)
            partial = {
                "partial": True,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "dataset": "dist_g",
                "n_per_model": len(txns),
                "models": [
                    {k: v for k, v in r.items() if k != "cases"}
                    | {"cases_n": len(r.get("cases") or [])}
                    for r in results
                ],
            }
            OUT_JSON.write_text(json.dumps(partial, indent=2))
            a = row.get("alert_vs_oracle") or {}
            print(
                f"  P={a.get('precision')} R={a.get('recall')} F1={a.get('f1')} "
                f"FPR={a.get('fpr')} $/case={row.get('cost_per_case_usd')} "
                f"agr={row.get('agreement')} p95={row.get('p95_latency_ms')}",
                flush=True,
            )

    selected_model, rationale = _select_winner(results)
    payload = {
        "run_id": uuid.uuid4().hex[:12],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "protocol": "dist_g_genai_unknown",
        "dataset": "dist_g",
        "dataset_version": f"generator_g.seed{SEED}",
        "freeze": str(FREEZE_JSON.relative_to(ROOT)),
        "n_per_model": len(txns),
        "fraud_count": freeze["fraud_count"],
        "benign_count": freeze["benign_count"],
        "positive_scenarios": sorted(POSITIVE_G),
        "pricing_note": "USD from usage_metadata tokens × Vertex rates in agent.estimate_cost_usd",
        "models": results,
        "selected_model": selected_model,
        "selection_rationale": rationale,
        "note": (
            "True unknown GenAI holdout (seed 53). Novel fraud names disjoint from Dist A–F. "
            "Oracle = fraud_scenario ∈ POSITIVE_G; alert = hold/escalate/freeze or risk_level=high. "
            "Not detector Dist A–F; not golden[:n] replay."
        ),
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2) + "\n")

    lines = [
        "# Dist G — GenAI unknown bake-off",
        "",
        f"- run_id: `{payload['run_id']}`",
        f"- dataset: `generator_g.seed{SEED}` (n={len(txns)}, fraud={freeze['fraud_count']}, benign={freeze['benign_count']})",
        f"- freeze: `{FREEZE_JSON.relative_to(ROOT)}`",
        f"- selected_model: **{selected_model}**",
        f"- rationale: {rationale}",
        f"- unknown ensured: POSITIVE_G ∩ KNOWN_A_TO_F = ∅; not golden first-100",
        "",
        "| Model | Status | P | R | F1 | FPR | $/case | Tokens/case | p95 ms | Agreement | Ungrounded |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in results:
        a = r.get("alert_vs_oracle") or {}
        lines.append(
            f"| `{r.get('model')}` | {r.get('status')} | {a.get('precision')} | "
            f"{a.get('recall')} | {a.get('f1')} | {a.get('fpr')} | "
            f"{r.get('cost_per_case_usd')} | {r.get('tokens_per_case')} | "
            f"{r.get('p95_latency_ms')} | {r.get('agreement')} | {r.get('ungrounded_rate')} |"
        )
    OUT_MD.write_text("\n".join(lines) + "\n")

    dist_card = {
        "run_id": payload["run_id"],
        "timestamp_utc": payload["created_at"],
        "git_commit": freeze["git_commit"],
        "environment": "local",
        "dataset": "dist_g",
        "dataset_version": f"generator_g.seed{SEED}",
        "benchmark": "dist_g_genai_unknown",
        "ground_truth": "validation.oracle (eval-only; runtime ignores fraud_scenario)",
        "positive_scenarios": sorted(POSITIVE_G),
        "sample_count": len(txns),
        "fraud_count": freeze["fraud_count"],
        "benign_count": freeze["benign_count"],
        "random_seed": SEED,
        "one_shot": True,
        "do_not_tune": True,
        "status": "ok",
        "genai_artifact": "reports/genai_dist_g_bakeoff.json",
        "freeze_artifact": "reports/dist_g_freeze.json",
        "selected_model": selected_model,
        "selection_rationale": rationale,
        "per_model_alert": {
            r["model"]: r.get("alert_vs_oracle")
            for r in results
            if r.get("model")
        },
        "note": (
            "Dist G is a GenAI unknown evaluation set, not a detector Dist A–F claim. "
            "Do not pitch Dist G F1 alongside detector Dist A–F."
        ),
    }
    DIST_JSON.write_text(json.dumps(dist_card, indent=2) + "\n")
    print(f"\nWrote {OUT_JSON}, {OUT_MD}, {DIST_JSON} — selected={selected_model}")
    return 0 if selected_model else 1


if __name__ == "__main__":
    raise SystemExit(main())
