"""
Live Cloud Run GenAI model bake-off (CR-031).

Requires:
  CW_LIVE_GENAI=1
  CW_GENAI_BASE_URL=https://…run.app   (not localhost)
  CW_GENAI_USER / CW_GENAI_PASS          (console login)
  CW_EVAL_MODEL_SECRET                  (must match Cloud Run env)

Usage:
  CW_LIVE_GENAI=1 CW_GENAI_BASE_URL=https://… \\
  CW_GENAI_USER=… CW_GENAI_PASS=… CW_EVAL_MODEL_SECRET=… \\
  python -m validation.genai.benchmark_models
"""
from __future__ import annotations

import json
import os
import statistics
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / "reports"
DEFAULT_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.5-pro",
    "gemini-3.6-flash",
    "gemini-3.8-flash",
    "gemini-3.1-pro-preview",
]
ALERT_DISPOSITIONS = {"hold_payment", "escalate_fiu", "freeze_account"}


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


def _refuse_local(base: str) -> None:
    low = base.lower()
    if not base or "localhost" in low or "127.0.0.1" in low or low.startswith("http://0."):
        raise SystemExit("CW_GENAI_BASE_URL must be the live Cloud Run URL (not localhost)")


def _http(method: str, url: str, body: dict | None = None, headers: dict | None = None, timeout: int = 180) -> dict:
    data = None if body is None else json.dumps(body).encode()
    req = Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    for k, v in (headers or {}).items():
        if v is not None:
            req.add_header(k, v)
    try:
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode()
            return json.loads(raw) if raw else {}
    except HTTPError as e:
        detail = e.read().decode()[:400]
        raise RuntimeError(f"{method} {url} -> {e.code}: {detail}") from e
    except URLError as e:
        raise RuntimeError(f"{method} {url} failed: {e}") from e


def _login(base: str) -> str:
    user = _env("CW_GENAI_USER") or _env("CW_DEMO_USER")
    password = _env("CW_GENAI_PASS") or _env("CW_DEMO_PASS")
    if not user or not password:
        raise SystemExit("Set CW_GENAI_USER and CW_GENAI_PASS for live auth")
    out = _http("POST", f"{base}/api/auth/login", {"username": user, "password": password})
    token = out.get("token")
    if not token:
        raise SystemExit("login did not return token")
    return token


def _auth_headers(token: str, model: str | None = None) -> dict:
    h = {"Authorization": f"Bearer {token}"}
    secret = _env("CW_EVAL_MODEL_SECRET")
    if model and secret:
        h["X-CW-Eval-Model"] = model
        h["X-CW-Eval-Secret"] = secret
    return h


def _is_alert(disp: str | None, risk_level: str | None = None) -> bool:
    if (disp or "").lower() in ALERT_DISPOSITIONS:
        return True
    return (risk_level or "").lower() == "high"


def _metrics(y_true: list[bool], y_pred: list[bool]) -> dict:
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
    f1 = (2 * prec * rec / (prec + rec)) if (prec + rec) else 0.0
    fpr = fp / (fp + tn) if (fp + tn) else 0.0
    return {
        "tp": tp, "fp": fp, "tn": tn, "fn": fn,
        "precision": round(prec, 4), "recall": round(rec, 4),
        "f1": round(f1, 4), "fpr": round(fpr, 4),
    }


def _build_holdout(base: str, token: str, n: int = 80) -> dict:
    path = REPORTS / "genai_unknown_pattern_holdout.json"
    if path.exists() and _env("CW_GENAI_REFRESH_HOLDOUT") != "1":
        return json.loads(path.read_text())
    alerts = _http("GET", f"{base}/api/alerts?sort=risk", headers=_auth_headers(token))
    rows = alerts if isinstance(alerts, list) else alerts.get("alerts") or alerts.get("items") or []
    fraud, benign = [], []
    for row in rows:
        txn_id = row.get("txn_id")
        if not txn_id:
            continue
        score = float(row.get("risk_score") or 0)
        pattern = str(row.get("primary_pattern") or "")
        # Live proxy labels: high-risk / named mule patterns = fraud; low-risk = benign.
        # Dist F IDs are preferred when present in the live ledger.
        novel = any(x in pattern for x in ("overbill", "smurf", "berth", "quay", "dock", "mule", "split", "multi_hop", "shared_device"))
        label_fraud = score >= 50 or novel
        item = {"txn_id": txn_id, "oracle_fraud": label_fraud, "risk_score": score, "primary_pattern": pattern}
        if label_fraud:
            fraud.append(item)
        else:
            benign.append(item)
    half = max(1, n // 2)
    cases = fraud[:half] + benign[:half]
    if len(cases) < 10:
        raise SystemExit(f"live holdout too small ({len(cases)}); need flagged cases on Cloud Run")
    holdout = {
        "source": "cloud_run_live",
        "base_url": base,
        "seed": "live-risk-tier-proxy",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "note": "Oracle labels derived on live ledger (risk/pattern). Runtime prompts never see oracle_fraud.",
        "cases": cases,
    }
    REPORTS.mkdir(exist_ok=True)
    path.write_text(json.dumps(holdout, indent=2))
    return holdout


def _investigate(base: str, token: str, txn_id: str, model: str) -> dict:
    t0 = time.perf_counter()
    try:
        out = _http(
            "POST",
            f"{base}/api/alerts/{txn_id}/investigate",
            {"mode": "gemini", "force": True},
            headers=_auth_headers(token, model),
            timeout=300,
        )
        ms = (time.perf_counter() - t0) * 1000
        out["_latency_ms"] = ms
        out["_ok"] = True
        return out
    except Exception as e:
        return {"_ok": False, "_error": str(e), "_latency_ms": (time.perf_counter() - t0) * 1000}


def _debate(base: str, token: str, txn_id: str, model: str) -> dict:
    t0 = time.perf_counter()
    try:
        out = _http(
            "POST",
            f"{base}/api/alerts/{txn_id}/debate?use_llm=true",
            headers=_auth_headers(token, model),
            timeout=300,
        )
        out["_latency_ms"] = (time.perf_counter() - t0) * 1000
        out["_ok"] = True
        return out
    except Exception as e:
        return {"_ok": False, "_error": str(e), "_latency_ms": (time.perf_counter() - t0) * 1000}


def _select_winner(rows: list[dict]) -> tuple[str | None, str]:
    ok = [r for r in rows if r.get("status") == "ok"]
    gated = [
        r for r in ok
        if (r.get("unknown_pattern") or {}).get("llm_raw", {}).get("recall", 0) >= 0.85
        and (r.get("ops") or {}).get("dag_agreement", 0) >= 0.85
        and (r.get("faithfulness") or {}).get("mean", 0) >= 0.7
        and (r.get("ops") or {}).get("p95_ms", 9e9) <= 8000
    ]
    if not gated:
        gated = [r for r in ok if (r.get("unknown_pattern") or {}).get("llm_raw", {}).get("recall", 0) >= 0.7]
    if not gated:
        return None, "No model met recall/agreement/faithfulness/p95 gates."
    gated.sort(key=lambda r: (
        (r.get("unknown_pattern") or {}).get("llm_raw", {}).get("fpr", 1),
        (r.get("ops") or {}).get("pre_gate_invent_rate", 1),
        (r.get("ops") or {}).get("cost_proxy", 1),
        -(r.get("unknown_pattern") or {}).get("llm_raw", {}).get("f1", 0),
        (r.get("ops") or {}).get("p95_ms", 9e9),
    ))
    w = gated[0]
    raw = (w.get("unknown_pattern") or {}).get("llm_raw") or {}
    rationale = (
        f"Selected {w['model']}: llm_raw recall={raw.get('recall')} FPR={raw.get('fpr')} "
        f"F1={raw.get('f1')}; ops p95={((w.get('ops') or {}).get('p95_ms'))}ms."
    )
    return w["model"], rationale


def main() -> int:
    if _env("CW_LIVE_GENAI") != "1":
        print("Set CW_LIVE_GENAI=1 to run the live bake-off.")
        return 2
    base = _env("CW_GENAI_BASE_URL").rstrip("/")
    _refuse_local(base)
    models = [m.strip() for m in (_env("CW_GENAI_MODELS") or ",".join(DEFAULT_MODELS)).split(",") if m.strip()]

    health = _http("GET", f"{base}/api/health")
    if health.get("environment") != "gcp" or health.get("database") == "sqlite":
        raise SystemExit(f"live health refused: {health}")

    token = _login(base)
    holdout = _build_holdout(base, token, n=int(_env("CW_GENAI_HOLDOUT_N") or "80"))
    cases = holdout["cases"]
    # Slice sizes (capped by holdout length)
    n_unknown = min(len(cases), int(_env("CW_GENAI_N_UNKNOWN") or "80"))
    n_ops = min(len(cases), int(_env("CW_GENAI_N_OPS") or "40"))
    n_faith = min(len(cases), int(_env("CW_GENAI_N_FAITH") or "20"))
    n_debate = min(len(cases), int(_env("CW_GENAI_N_DEBATE") or "15"))
    n_tools = min(len(cases), int(_env("CW_GENAI_N_TOOLS") or "10"))

    print(f"Bake-off base={base} models={models} holdout={len(cases)}")
    print(f"health={json.dumps({k: health.get(k) for k in ('environment','database','gemini_backend','gemini_model','ok')})}")

    run_id = uuid.uuid4().hex[:12]
    rows: list[dict] = []
    for model in models:
        print(f"\n=== {model} ===")
        row: dict[str, Any] = {"model": model, "status": "ok"}
        try:
            # Unknown-pattern alert quality
            y_true, y_raw, y_gated, latencies = [], [], [], []
            invent_hits = 0
            agree = 0
            agree_n = 0
            for case in cases[:n_unknown]:
                res = _investigate(base, token, case["txn_id"], model)
                if not res.get("_ok"):
                    if "NOT_FOUND" in str(res.get("_error")) or "404" in str(res.get("_error")) or "PERMISSION" in str(res.get("_error")).upper():
                        row["status"] = "skipped"
                        row["skip_error"] = res.get("_error")
                        break
                    continue
                latencies.append(res.get("_latency_ms") or 0)
                v = res.get("verdict") or res
                report = v.get("investigation_report") or res.get("investigation_report") or {}
                raw_disp = v.get("llm_raw_disposition") or report.get("recommended_disposition")
                gated_disp = report.get("recommended_disposition")
                y_true.append(bool(case["oracle_fraud"]))
                y_raw.append(_is_alert(raw_disp, v.get("risk_level")))
                y_gated.append(_is_alert(gated_disp, v.get("risk_level")))
                rewrites = int(v.get("grounding_rewrites") or getattr(report, "grounding_rewrites", 0) or 0)
                if rewrites > 0:
                    invent_hits += 1
                # ops agreement vs DAG disposition when present
                det = (v.get("dag_risk_score") is not None)
                if det and gated_disp:
                    agree_n += 1
                    # soft: same alert band as DAG risk
                    dag_alert = float(v.get("dag_risk_score") or v.get("risk_score") or 0) >= 50
                    if _is_alert(gated_disp) == dag_alert:
                        agree += 1
            if row.get("status") == "skipped":
                rows.append(row)
                print(f"skipped: {row.get('skip_error')}")
                continue

            raw_m = _metrics(y_true, y_raw) if y_true else {}
            gated_m = _metrics(y_true, y_gated) if y_true else {}
            row["unknown_pattern"] = {"n": len(y_true), "llm_raw": raw_m, "system_gated": gated_m}
            p95 = sorted(latencies)[int(0.95 * (len(latencies) - 1))] if latencies else None
            row["ops"] = {
                "n": min(n_ops, len(latencies)),
                "p50_ms": statistics.median(latencies) if latencies else None,
                "p95_ms": p95,
                "pre_gate_invent_rate": round(invent_hits / max(1, len(y_true)), 4),
                "dag_agreement": round(agree / agree_n, 4) if agree_n else 0.0,
                "cost_proxy": round((sum(latencies) / max(1, len(latencies))) / 1000.0, 4) if latencies else 1.0,
            }

            # Faithfulness proxy: grounded flag rate on n_faith (official DeepEval optional later)
            faith_ok = 0
            faith_n = 0
            for case in cases[:n_faith]:
                res = _investigate(base, token, case["txn_id"], model)
                if not res.get("_ok"):
                    continue
                v = res.get("verdict") or res
                report = v.get("investigation_report") or {}
                faith_n += 1
                if report.get("grounded") or v.get("provenance") in {"grounded", "gemini_tools", "gemini_prefetch"}:
                    faith_ok += 1
            row["faithfulness"] = {
                "n": faith_n,
                "mean": round(faith_ok / faith_n, 4) if faith_n else 0.0,
                "note": "live grounded-flag proxy; DeepEval FaithfulnessMetric optional offline",
            }

            # Debate slice
            debate_lat, debate_rw, debate_fail = [], 0, 0
            for case in cases[:n_debate]:
                d = _debate(base, token, case["txn_id"], model)
                if not d.get("_ok"):
                    debate_fail += 1
                    continue
                debate_lat.append(d.get("_latency_ms") or 0)
                debate_rw += int(d.get("grounding_rewrites") or 0)
            row["debate"] = {
                "n": n_debate,
                "p95_ms": sorted(debate_lat)[int(0.95 * (len(debate_lat) - 1))] if debate_lat else None,
                "grounding_rewrites_total": debate_rw,
                "fallback_rate": round(debate_fail / max(1, n_debate), 4),
            }

            # Tool-loop slice
            tool_ok = 0
            for case in cases[:n_tools]:
                res = _investigate(base, token, case["txn_id"], model)
                if not res.get("_ok"):
                    continue
                v = res.get("verdict") or res
                if v.get("provenance") == "gemini_tools" or (v.get("tool_calls") or []):
                    tool_ok += 1
            row["tool_loop"] = {"n": n_tools, "success": tool_ok, "success_rate": round(tool_ok / max(1, n_tools), 4)}
            print(json.dumps({k: row[k] for k in ("model", "unknown_pattern", "ops", "faithfulness")}, default=str))
        except Exception as e:
            row["status"] = "skipped"
            row["skip_error"] = str(e)
            print(f"skipped: {e}")
        rows.append(row)

    selected, rationale = _select_winner(rows)
    payload = {
        "run_id": run_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "base_url": base,
        "health": health,
        "models": rows,
        "selected_model": selected,
        "selection_rationale": rationale,
        "holdout": str(REPORTS / "genai_unknown_pattern_holdout.json"),
    }
    REPORTS.mkdir(exist_ok=True)
    (REPORTS / "genai_model_bakeoff.json").write_text(json.dumps(payload, indent=2, default=str))

    lines = [
        "# GenAI model bake-off (live Cloud Run)",
        "",
        f"- run_id: `{run_id}`",
        f"- base_url: `{base}`",
        f"- selected_model: **{selected}**",
        f"- rationale: {rationale}",
        "",
        "| Model | Status | Raw P | Raw R | Raw F1 | Raw FPR | Gated FPR | p95 ms | Faith mean |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in rows:
        raw = ((r.get("unknown_pattern") or {}).get("llm_raw") or {})
        gated = ((r.get("unknown_pattern") or {}).get("system_gated") or {})
        ops = r.get("ops") or {}
        faith = r.get("faithfulness") or {}
        lines.append(
            f"| `{r.get('model')}` | {r.get('status')} | {raw.get('precision','—')} | {raw.get('recall','—')} | "
            f"{raw.get('f1','—')} | {raw.get('fpr','—')} | {gated.get('fpr','—')} | {ops.get('p95_ms','—')} | {faith.get('mean','—')} |"
        )
    (REPORTS / "genai_model_bakeoff.md").write_text("\n".join(lines) + "\n")
    print(f"\nWrote reports/genai_model_bakeoff.json and .md — selected={selected}")
    return 0 if selected else 1


if __name__ == "__main__":
    sys.exit(main())
