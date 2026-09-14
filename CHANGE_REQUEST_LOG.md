# Corridor Watch — Change Request Log

| CR ID | Target Component | Description | Status | Target Release |
|---|---|---|---|---|
| **CR-001** | Documentation | Create change request log (`CHANGE_REQUEST_LOG.md`) and update `README.md` with complete workarounds and operational guide. | **Completed** | v1.2.0 |
| **CR-002** | Security & Auth | Introduce Analyst Authentication headers (`X-Analyst-ID`, `X-Analyst-Role`) and Role-Based Access Control (`analyst`, `fiu_lead`, `mrm_auditor`). | **Completed** | v1.2.0 |
| **CR-003** | Red-Teaming | Add non-destructive red-team tagging (`is_redteam`) and dataset reset endpoint (`POST /api/phase2/redteam/reset`) to roll back test cases without corrupting baseline synthetic data. | **Completed** | v1.2.0 |
| **CR-004** | Case Memory (RAG) | Upgrade precedent case retrieval from basic unigram token overlap to TF-IDF cosine vector similarity search. | **Completed** | v1.2.0 |
| **CR-005** | Case Audit & Export | Implement printable HTML/PDF-ready Case Audit Package export endpoint (`GET /api/alerts/{id}/export`) and UI action. | **Completed** | v1.2.0 |
| **CR-006** | Model Provider | Enhance LLM provider abstraction to allow runtime swappability between Gemini and Azure OpenAI / enterprise endpoints. | **Completed** | v1.2.0 |
| **CR-007** | AI Debate Co-Pilot | Implement 3-agent Adversarial AI Debate loop (Prosecutor, Defense, Judge) for unbiased verdict generation. | **Completed** | v1.3.0 |
| **CR-008** | Multimodal SoF Verifier | Add Multimodal Document Inspection (Gemini Vision) for customer-uploaded bank statements and invoices. | **Completed** | v1.3.0 |
| **CR-009** | Counterfactual Simulator | Build interactive What-If feature perturbation simulator and sensitivity explainer. | **Completed** | v1.3.0 |
| **CR-010** | SAR Narrative Generator | Multi-jurisdiction regulatory filing narrative generator for FinCEN (US), MAS (Singapore), and AUSTRAC (Australia). | **Completed** | v1.3.0 |
| **CR-011** | Self-Evolving Rule Miner | Mine high-precision candidate decision rules from historical analyst dispositions with precision/recall metrics. | **Completed** | v1.3.0 |
| **CR-012** | Platform evolution | Config, SQLite/PostgreSQL abstraction, Pub/Sub ingest, multi-bank synthetic world, Crime Pattern DNA, grounded Gemini report, command/corridor/pattern UI. | **Completed** | v1.5.0 |
| **CR-013** | Scale proof | Multi-instance Cloud Run, Cloud SQL `db-custom-2-7680`, Pub/Sub load-test with ledger measurement. Publisher held 200–1000 TPS; consume remained SQL-bound. Not a 5,000 TPS claim. | **Completed (measured)** | v1.6.0 |
| **CR-014** | Analyst console | Viewport-locked Investigations layout: independent queue scroll, horizontal case-pane scroll, corridor-map and Explorer graph zoom/pan. | **Completed** | v1.6.1 |
| **CR-015** | Competition proof | Ingest stage timings + upserts, GCP SQLite refusal, durable queue claim/retry, transaction-only baseline, Command Center impact/scale panel, Pattern DNA explainability, claims policy. | **Completed** | v1.7.0 |
| **CR-016** | Partial visibility | Observed/external/inferred/unknown graph states, network visibility score, synthetic intelligence, middle-bank demo, cross-institution Pattern DNA. | **Completed** | v1.8.0 |
| **CR-017** | Operational reliability | Transactional outbox, source-event idempotency, queue backoff/DLQ, optional worker split, untrusted SoF wrapping, measured SLO snapshot. | **Completed** | v1.9.0 |
| **CR-018** | Production security | Optional OIDC bearer, MFA step-up for high-risk actions, authz audit, PII tokens at the Gemini boundary, grounding gate + model provenance. | **Completed** | v1.10.0 |
| **CR-019** | Operations | Request traces, measured SLO + in-process alerts, Command Center SLO card, Cloud SQL PITR/DR status scripts. | **Completed** | v1.11.0 |
| **CR-020** | Production evidence | Four `production/` reports: measured load paths, DR procedure without invented RPO, threat model mapped to tests, AI validation on synthetic + grounding gates. | **Completed** | v1.11.0 |
| **CR-021** | Validation suite | Executable `validation/` suite + `reports/SCORECARD.md`. Prove existing controls (grounding, 5.65 TPS SLO, adversarial, DR Target, UX/a11y). No DeepEval dependency. Do not claim 5,000 TPS. | **Completed** | v1.12.0 |
| **CR-022** | Validation honesty | Reverse CR-021: add real `deepeval` package + BaseMetric wrappers. Hidden oracle, Dist B generator, network recall, hallucination≠cost, injection decision-change, races, investigation enqueue TPS, miner holdout. Never claim 5,000 TPS. | **Completed** | v1.13.0 |
| **CR-023** | Five score-gap fixes | Dist B source-only velocity no longer counts as split; hard-negative *networks*; investigation-useful network v2; DeepEval n≥100 `ran:true`; investigation *completion* TPS. Frozen Dist B seed 7. Never claim 5,000 TPS. | **Completed** | v1.14.0 |
| **CR-024** | Judge remaining three | DeepEval 200+ mixed kinds `ran:true`; Dist B vs hard-neg topology diagnosis on frozen seed 7 (before F1 0.4118 kept); canonical `FINAL_VALIDATION_REPORT.md` with one run ID per experiment. Never claim 5,000 TPS. | **Completed** | v1.15.0 |
| **CR-025** | Dist C holdout | Independent generator C, freeze detector, run once on seed 23. No detector retune. Never claim 5,000 TPS. | **Completed** | v1.16.0 |
| **CR-026** | Collecting guard + Dist D | Fan-in counts only with ptr/youth/short-hold/burst-vel. Dist C artifact pinned. Dist D seed 37 one-shot gate. Never claim 5,000 TPS. | **Completed** | v1.17.0 |

---

## Detailed Change Request Specifications

### CR-007: Adversarial AI Debate System
- **Module**: `agent_debate.py`
- **Endpoint**: `POST /api/alerts/{id}/debate`
- **Capability**: Runs Prosecutor, Defense, and Chief Compliance Judge agents to evaluate alert objectivity.

### CR-008: Multimodal Source-of-Funds Verification
- **Module**: `multimodal_sof.py`
- **Endpoint**: `POST /api/alerts/{id}/verify-document`
- **Capability**: Extracts text, amounts, bank stamps, and issuer names from uploaded images/PDF invoices using Gemini Multimodal Vision and performs cross-field database verification.

### CR-009: Counterfactual "What-If" Sensitivity Simulator
- **Module**: `counterfactual.py`
- **Endpoint**: `POST /api/alerts/{id}/counterfactual`
- **Capability**: Dynamically perturb feature inputs (`account_age_days`, `pass_through_ratio`, `avg_hold_time_minutes`, `shared_device_count`) to compute score deltas and rank order sensitivities.

### CR-010: Multi-Jurisdiction Regulatory Filing (SAR / STR)
- **Module**: `sar_generator.py`
- **Endpoint**: `GET /api/alerts/{id}/sar?jurisdiction=fincen|mas|austrac`
- **Capability**: Drafts regulatory narratives compliant with FinCEN (US), MAS (Singapore), and AUSTRAC (Australia) filing guidance.

### CR-011: Self-Evolving Rule Mining Engine
- **Module**: `rule_miner.py`
- **Endpoint**: `GET /api/phase2/rules/mine`
- **Capability**: Analyzes historical analyst dispositions against scored feature sets to discover candidate rules with precision/recall metrics.

### CR-013: Scale proof
- **Modules**: `scripts/scale_cloud_sql.sh`, `scripts/deploy_cloud_run.sh`, `pubsub_load_generator.py`, `db.py`
- **Capability**: Raises Cloud SQL off `db-f1-micro`, sizes Cloud Run against a real connection budget, and records ledger-measured Pub/Sub ingest. Report only `achieved_tps`. Do not treat `--in-process` or HTTP batch as Cloud Run scale proof.

### CR-014: Console viewport and map zoom
- **Module**: `static/index.html`
- **Capability**: Investigations queue scrolls independently of page length. The case pane (tabs, feature cards, money-flow DAG) scrolls horizontally when content is wider than the frame. Corridor geography and Corridor Explorer graph support zoom in / zoom out / reset, wheel zoom, and drag-to-pan.

### CR-015: Competition proof without new AI surface
- **Modules**: `metrics.py`, `db.py`, `pubsub/ingestion.py`, `investigations/queue.py`, `evaluation.py`, `static/index.html`, `docs/COMPETITION_CLAIMS.md`
- **Capability**: Make the existing Detect → Investigate → Learn loop measurable. Profile ingest stages, keep Gemini off the hot path, compare a transaction-only baseline, and never present 5,000 TPS as achieved.

### CR-016: Cross-institution partial visibility
- **Modules**: `graph/visibility.py`, `intelligence/`, `synthetic/middle_bank.py`, `investigations/`, `static/index.html`
- **Capability**: Distinguish observed, external, inferred, and unknown network areas. Visibility is not guilt. Synthetic intelligence can resolve a boundary without inventing Bank D.

### CR-017: Operational reliability
- **Modules**: `pubsub/outbox.py`, `pubsub/ingestion.py`, `investigations/queue.py`, `metrics.py`, `scripts/cloud_run_entrypoint.sh`
- **Capability**: Persist ingest + queue + outbox in one commit. Deduplicate on `(source_system, source_event_id)`. Retry with backoff then `DEAD_LETTER`. `CW_ROLE=api|investigation|outbox` splits workers without changing the default Cloud Run API service. Gemini stays off ingest. 5,000 TPS remains a TARGET.

### CR-018: Production security
- **Modules**: `auth.py`, `privacy.py`, `audit.py`, `agent.py`, `workflow.py`
- **Capability**: Accept an IdP JWT when `OIDC_ISSUER` is set. High-risk decisions and workflow escalate require MFA on that session. Authorization events are append-only. Gemini sees tokenized account IDs and untrusted document text. Invented evidence IDs fail the grounding gate.

### CR-019: Operations
- **Modules**: `tracing.py`, `metrics.py`, `static/index.html`, `scripts/dr_status.sh`, `scripts/enable_sql_pitr.sh`
- **Capability**: Correlate requests with `X-Trace-Id` / W3C `traceparent`. `/api/metrics` evaluates SLOs and fires in-process alerts (DLQ, pool, 5xx, Gemini errors). DR scripts inspect or enable Cloud SQL PITR. RPO/RTO stay TARGET until a restore is measured.

### CR-020: Production evidence
- **Modules**: `production/load-test-report.md`, `production/disaster-recovery-report.md`, `production/security-threat-model.md`, `production/ai-model-validation-report.md`
- **Capability**: Present only measured ingest (5.65 TPS Pub/Sub consume; 1,912 TPS is in-process). Keep 5,000 TPS, RPO/RTO, and Gemini agreement rates as TARGET. Map security and AI controls to existing tests.

### CR-021: Validation suite
- **Modules**: `validation/`, `validation/run_suite.py`, `reports/SCORECARD.md`, `static/index.html`
- **Capability**: One seeded suite for detector quality, Gemini grounding/injection (stdlib metrics, not a DeepEval package), reliability, recorded 5.65 TPS SLO boundary, RBAC/PII/provenance, DR Target, and analyst-loop + a11y smoke. Live 100–2k TPS Cloud gates stay skipped unless `CW_SCALE_LIVE=1`.

### CR-022: Validation honesty and DeepEval
- **Modules**: `validation/`, `evaluation.py`, `risk/tiers.py`, `patterns/matcher.py`, `privacy.py`, `rule_miner.py`, `reports/`
- **Capability**: Real `deepeval` package + BaseMetric wrappers. Hidden oracle (runtime ignores `fraud_scenario`). Dist B generator. Network recall. Hallucination ≠ cost. Injection decision-change. Concurrent claim races. Investigation enqueue TPS. Rule-miner 70/30 holdout without invented 94% precision. Do not claim 5,000 TPS or 100% Gemini from n=3.

### CR-023: Five score-gap fixes
- **Modules**: `graph_features.py`, `validation/external/`, `graph/network_metrics.py`, `validation/deepeval/`, `validation/scale/`, `reports/`
- **Capability**: Dist B FPR from source-only velocity (forensics then detector). Hard-negative network archetypes + fraud twins. Investigation-useful network metrics beside full-graph account recall. DeepEval on ≥100 investigation reports (`ran: true` only then). Investigation completion TPS / time-to-verdict (Policy A/B). Frozen Dist B test seed 7; threshold sweep on seed 11 only. Do not claim 5,000 TPS.

### CR-024: Remaining three (DeepEval mix, Dist B diagnosis, canonical report)
- **Modules**: `validation/datasets/golden.py`, `validation/deepeval/`, `validation/run_suite.py`, `FINAL_VALIDATION_REPORT.md`
- **Capability**: 200+ mixed investigation reports (normal/obvious/subtle/hardneg/partial/contradict/missing/document/injection/toolfail/hybrid). Dist B vs hard-neg topology diagnosis on frozen seed 7; keep before F1 0.4118 / FPR 1.0. One run ID / commit / timestamp per experiment in `FINAL_VALIDATION_REPORT.md`. Do not claim 5,000 TPS.

### CR-025: Dist C one-shot holdout
- **Modules**: `validation/external/generator_c.py`, `validation/external/test_dist_c.py`, `evaluation.py`
- **Capability**: Independent Dist C (seed 23) with novel normals, altered topology, new amounts, unseen fraud names, partial visibility, noise, ambiguous inbound. Freeze `graph_features.py` fingerprint before scoring. Run once. Do not retune. Do not claim 5,000 TPS.

### CR-026: Collecting guard + Dist D
- **Modules**: `graph_features.py`, `validation/external/generator_d.py`, `validation/external/test_dist_d.py`
- **Capability**: Fan-in contributes to mule/split/composite only if pass-through, age≤7, hold<180, or corridor velocity≥4. Dist C seed-23 json is pinned. Dist D seed 37 is the post-fix one-shot gate. Do not retune on 23 or 37. Do not claim 5,000 TPS.
