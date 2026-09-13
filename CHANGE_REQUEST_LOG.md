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
