# GenAI model benchmark methodology (CR-031)

## Purpose

Choose the production Gemini model with **measured** differentiation on **live Corridor Watch Cloud Run** (GCP), not a laptop SQLite run.

DAG still owns freeze/hold authority. GenAI is scored for alert quality on unknown/novel-looking live cases and for grounding / latency / tool-loop behavior.

## Live target

| Plane | Value |
|---|---|
| App | `CW_GENAI_BASE_URL` (Cloud Run URL) |
| Project | `corridor-watch-508420` |
| Backend | Vertex (`GEMINI_BACKEND=vertex`) |
| Refuse | localhost / SQLite health |

Bake-off writes are refused unless `/api/health` shows `environment=gcp` and a non-sqlite database.

## Model matrix

1. `gemini-2.5-flash`
2. `gemini-2.5-pro`
3. `gemini-3.6-flash`
4. `gemini-3.8-flash`
5. `gemini-3.1-pro-preview`

Per-model override on live: `X-CW-Eval-Model` + `X-CW-Eval-Secret` (must match `CW_EVAL_MODEL_SECRET` on Cloud Run).

## Unknown-pattern metrics

Holdout: `reports/genai_unknown_pattern_holdout.json` (`source: cloud_run_live`).

For each model:

- `llm_raw_*` — disposition **before** non-downgrade clamp
- `system_gated_*` — after grounding gate

Alert = `hold_payment` | `escalate_fiu` | `freeze_account` (or `risk_level=high`).

Reported: **Precision, Recall, F1, FPR**.

## Winner rule

1. status ok  
2. `llm_raw_recall ≥ 0.85`, DAG agreement ≥ 0.85, faithfulness proxy ≥ 0.7, investigate p95 ≤ 8s  
3. lowest `llm_raw_FPR`  
4. then invent rate, cost proxy, F1, p95  

Artifacts: `reports/genai_model_bakeoff.json`, `reports/genai_model_bakeoff.md`.

## Honest split

- Dist A–F F1/FPR on SCORECARD = **detector** evidence  
- Bake-off P/R/F1/FPR = **GenAI alert** evidence — do not conflate in the pitch  

## How to run

```bash
export CW_LIVE_GENAI=1
export CW_GENAI_BASE_URL=https://corridor-watch-6kmkxbsbwq-as.a.run.app
export CW_GENAI_USER=...
export CW_GENAI_PASS=...
export CW_EVAL_MODEL_SECRET=...   # same value set on Cloud Run
python -m validation.genai.benchmark_models
```
