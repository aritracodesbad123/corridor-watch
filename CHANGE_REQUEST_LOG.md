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
