# GenAI model benchmark methodology

## Purpose

Choose the production Gemini model with **measured** differentiation. Absolute ranking uses **Dist G** (unknown holdout with benign) and **agreement + USD** (golden n=100 × 5 models). Both report real **`$/case`** from token usage × Vertex rates (`agent.estimate_cost_usd`).

DAG still owns freeze/hold authority. GenAI is scored for alert quality, grounding, latency, and cost.

## Model matrix

1. `gemini-2.5-flash`
2. `gemini-2.5-pro`
3. `gemini-3.6-flash`
4. `gemini-3.8-flash`
5. `gemini-3.1-pro-preview`

## Honest split

- Dist A–F F1/FPR on SCORECARD = **detector** evidence  
- **Dist G** + **agreement+USD** = **absolute GenAI model comparison** (canonical for README / Final Validation Report)  
- Live Cloud Run bake-off (n=8, no benign) is **superseded** for ranking (vacuous FPR); do not cite as primary  

## Dist G — GenAI unknown holdout (canonical)

Frozen seed **53** (`validation/external/generator_g.py`). Novel fraud: `tarmac_drip`, `gate_skip`, `cargo_wake`, `airbill_loop` (disjoint from Dist A–F). n=80 with **48 benign** so FPR is non-vacuous. Not `golden[:n]`.

```bash
export CW_GEMINI_LIVE=1
.venv/bin/python -m validation.genai.dist_g_bakeoff
```

Artifacts: `reports/dist_g_freeze.json`, `reports/dist_g.json`, `reports/genai_dist_g_bakeoff.json`, `.md`.

Latest one-shot (`run_id` `982d59f1f0e4`): all five models **P=1.0 R=0.4688 F1=0.6383 FPR=0.0**; selected **gemini-2.5-flash** at **$0.002012/case** (agr=1.0, p95=6720ms).

## Agreement + USD cost (canonical)

Same path as `validation/deepeval/test_investigation.py` / `reports/gemini_agreement.json`:
golden cases → `build_investigation` → agreement vs deterministic, p95, tokens, **`cost_per_case_usd`**.

```bash
export CW_GEMINI_LIVE=1
export CW_GEMINI_N=100
python -m validation.genai.agreement_cost_bakeoff
```

Artifacts: `reports/genai_agreement_cost_bakeoff.json`, `.md`.

Latest full run (`run_id` `18c9176f68de`, n=100): selected **gemini-2.5-flash** at **$0.002032/case** (agr=1.0).

## Superseded: live Cloud Run bake-off

Provisional ops holdout (`reports/genai_model_bakeoff.*`) had no benign rows — FPR not informative. Kept off the public evidence pack; do not use for model selection claims.
