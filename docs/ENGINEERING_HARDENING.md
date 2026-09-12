# Engineering hardening completed

## Gaps addressed

1. **Deterministic evaluation harness**
   - `evaluation.py` benchmarks every synthetic transaction using `fraud_scenario` ground truth.
   - Reports precision, recall, F1, false-positive rate, per-typology flag rate, pattern accuracy, confusion pairs, and a quality gate.
   - Benchmark runs disable DAG audit writes to avoid contaminating operational audit history.

2. **Automated tests**
   - `tests/` covers score bounds, schema bootstrap, evaluation smoke testing, decision validation, RBAC, and server-derived analyst identity.

3. **API RBAC**
   - `auth.py` defines explicit analyst/FIU-lead/MRM-auditor permissions.
   - Privileged endpoints now reject unauthorized roles.
   - High-risk dispositions require FIU-lead authorization.
   - Demo mode remains self-contained via `X-Analyst-*`; production-style API-key mapping is supported with `CORRIDOR_WATCH_API_KEYS`.

4. **GenAI output validation**
   - Gemini verdicts are validated through a typed Pydantic schema before caching.
   - Risk score, risk level, pattern and evidence references are constrained.
   - Invalid model output falls back to a deterministic, human-review verdict.

5. **Input validation**
   - Investigation modes, disposition values, red-team scenario counts, and counterfactual feature ranges are validated at the API boundary.

6. **SQLite reliability**
   - Connection timeout, WAL mode and foreign-key enforcement are enabled.

7. **Demo reproducibility**
   - `python data_gen.py` now regenerates source data **and** materializes risk scores/flagged alerts, so a fresh database is immediately runnable.

8. **CORS/lifecycle polish**
   - Allowed origins are configurable with `CORRIDOR_WATCH_ALLOWED_ORIGINS`.
   - FastAPI startup uses the lifespan API.

## Current benchmark result

On the included deterministic synthetic dataset (586 transactions; 117 injected positive examples):

- Recall: **100%**
- Precision: **100%**
- F1: **100%**
- False-positive rate: **0%**
- Named-pattern accuracy: **99.15%**

This is a **development benchmark**, not a claim of production fraud-model performance. The synthetic generator is intentionally structured, so the next evaluation maturity step is an independently authored holdout/adversarial dataset and calibration analysis.
