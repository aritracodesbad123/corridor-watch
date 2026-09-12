# Gap audit — brief vs this build

Date: 2026-09-08 · Target: Phase 1 MVP + Phase 2 judgment layer

## Phase 1 — brief requirements

| Requirement | Status | Notes |
|---|---|---|
| Synthetic accounts / txns / devices / beneficiaries / sessions | **Done** | `data_gen.py` |
| Injected fraud: mule, split, shared-device, synthetic ID, multi-hop | **Done** | 5 scenarios |
| Graph features (fan-in/out, pass-through, hold time, shared device/benef, multi-hop, age, corridor velocity) | **Done** | `graph_features.py` |
| Behavioral biometrics (typing, nav, bot, copy-paste) | **Done** | Simulated sessions |
| Named pattern scoring | **Done** | 5 named patterns + composite score |
| 12-step investigation DAG | **Done** | `investigation_dag.py` |
| Deterministic + Gemini agent verdicts | **Done** | `agent.py` auto/fallback |
| FastAPI + SQLite | **Done** | |
| Analyst console: queue, detail, network, verdict, behavioral, decision | **Done** | `static/index.html` |
| Audit trail (evidence, tools, verdicts, decisions) | **Done** | `audit.py` |
| Cloud Run path | **Done** | `Dockerfile` + README |
| Azure port path documented | **Done** | `docs/AZURE_PORT.md` |

### Remaining Phase 1 polish (non-blocking)

- Production auth / Entra (explicit non-goal for POC)
- Richer interactive graph (force-directed) — current SVG neighborhood is demo-grade
- Separated React SPA — vanilla console is intentional for single Cloud Run service

## Phase 2 — brief requirements

| Requirement | Status | Notes |
|---|---|---|
| Source-of-funds plausibility (specific inconsistencies) | **Done** | `phase2_sof.py` |
| Institutional case memory RAG | **Done** | Token-overlap retrieval; seed precedents; stores analyst decisions |
| MRM documentation draft | **Done** | `phase2_mrm.py` folds red-team gaps into limitations |
| Adversarial red-team loop | **Done** | Builtin + optional LLM novel patterns; inject → re-score → report evasion |

### Phase 2 limitations (honest)

- RAG is lexical, not embedding-based — upgrade to Azure AI Search when client data exists
- Red-team mutates local SQLite; reset via `data_gen.py`
- All Phase 2 outputs marked `requires_human_review: true`

## Explicitly out of scope (per brief)

- Competing with Actimize/Feedzai/Quantexa on core graph detection
- SAR narrative as primary differentiator
- Federated cross-institution mule detection
- Real-time voice scam coaching
- Multi-jurisdiction filing translation

## Success criteria check (Phase 1)

| Criterion | Met? |
|---|---|
| Generates synthetic fraud + normal data | Yes |
| Detects ≥3 fraud patterns | Yes (≥5) |
| Explainable evidence-grounded verdicts | Yes (DAG + optional Gemini) |
| Full audit trail | Yes |
| Demoable end-to-end | Yes (local / Cloud Run) |
