# Corridor Watch — Comprehensive Technical Documentation

**Corridor Watch** is an end-to-end cross-border payment fraud investigation console, explainability layer, and compliance AI reasoning engine built for JAPAC remittance corridors.

Graph anomaly detection is table stakes — Corridor Watch provides the reasoning, explainability, multimodal document intelligence, institutional case memory, regulatory filing, and model governance layer that sits on top of core banking transaction streams.

---

## 🌟 Complete Capability Architecture (Phases 1 – 3)

```
                       +---------------------------------------+
                       |      Analyst Console & Web UI         |
                       | (Flow DAG, D3 Geo Map, Multi-Tab UI)  |
                       +-------------------+-------------------+
                                           |
    +--------------------------------------+--------------------------------------+
    |                                      |                                      |
+---v------------------+       +-----------v----------+       +-------------------v---+
|  Phase 1: Detection  |       |  Phase 2: Judgment   |       | Phase 3: Advanced AI  |
|  & DAG Investigation |       |  & Memory (RAG)      |       | Feature Suite         |
+----------------------+       +----------------------+       +-----------------------+
| • Synthetic Data Gen |       | • SoF Check          |       | • AI Debate System    |
| • NetworkX Features  |       | • TF-IDF Vector RAG  |       | • Multimodal Vision   |
| • 5 Pattern Scorers  |       | • MRM Validation     |       | • What-If Simulator   |
| • Session Biometrics |       | • Red-Team Loop      |       | • SAR Narrative Gen   |
| • 12-Step DAG        |       | • Dataset Rollback   |       | • Self-Evolving Rules |
| • Gemini Tool Agent  |       |                      |       |                       |
+----------------------+       +----------------------+       +-----------------------+
```

---

## 🧩 Detailed Feature Breakdown

### Phase 1: Core Fraud Detection & Investigation Engine

1. **Synthetic Remittance Data Generator (`data_gen.py`)**:
   - Generates realistic accounts, multi-currency transactions, device fingerprints, beneficiaries, and user login sessions across JAPAC remittance corridors (e.g. `IN->SG`, `PH->US`, `ID->SG`, `VN->US`, `AE->US`).
   - Injects 5 realistic fraud typologies:
     - **Mule Pass-Through**: Fresh account receives rapid inflows and immediately drains $\ge 90\%$ outbound within 24 hours.
     - **Split Transaction Laundering**: Micro-feeder accounts transfer sub-threshold amounts into a common sink.
     - **Shared Device Ring**: Multiple unrelated accounts operating from identical hardware device fingerprints.
     - **Synthetic Identity**: Low-income or unemployed profile receiving unexpected high-value transfers.
     - **Multi-Hop Chain**: Funds layered through a chain of 3+ owned intermediate accounts before exit.

2. **NetworkX Graph Feature Engine (`graph_features.py`)**:
   - Constructs directed money-movement graphs ($G = (V, E)$) and extracts topological risk indicators:
     - `fan_in_count` & `fan_out_count`: Inbound/outbound transaction degree.
     - `pass_through_ratio`: $\frac{\text{Outflow Volume}}{\text{Inflow Volume}}$ ratio.
     - `avg_hold_time_minutes`: Average minutes funds sit in an account before outbound transfer.
     - `shared_device_count`: Number of peer accounts sharing hardware fingerprints.
     - `shared_beneficiary_count`: Number of peer accounts sharing payout beneficiaries.
     - `multi_hop_chain_depth`: Length of outbound money-layering path.
     - `corridor_velocity_score`: Hourly transaction frequency spike.
     - `account_age_days`: Account longevity.

3. **Named Pattern & Composite Risk Scorers (`graph_features.py`)**:
   - Classifies 5 named fraud patterns with independent sub-scores ($0-100$) and computes an overall composite risk score.

4. **Behavioral Biometrics Telemetry Simulator (`graph_features.py`, `investigation_dag.py`)**:
   - Simulates user session telemetry: typing cadence deviation, navigation velocity, bot likelihood score, copy-paste risk, and geo-IP mismatch.

5. **12-Step Deterministic Investigation DAG (`investigation_dag.py`)**:
   - Auditable rule-based workflow executing 12 sequential evidence steps:
     1. Load flagged transaction record
     2. Load sender KYC profile
     3. Load receiver KYC profile
     4. Load graph risk features
     5. Pull session behavioral biometrics
     6. Enumerate shared devices
     7. Enumerate shared beneficiaries
     8. Build 1-hop transaction neighborhood
     9. Assess corridor velocity
     10. Score named fraud patterns
     11. Assemble structured evidence pack
     12. Draft deterministic verdict
   - Operates independently without requiring an LLM.

6. **Gemini Tool-Calling Reasoning Agent (`agent.py`)**:
   - Tool-calling agent using Google Gemini (`gemini-3.8-flash` / `gemini-2.5-flash`).
   - Equipped with 4 investigation tools: `get_account_context`, `get_shared_devices`, `get_session_biometrics`, `get_network_neighborhood`.
   - Uses stateless tool-history tracking to preserve thought signatures across function calls.

7. **Append-Only Audit Trail (`audit.py`)**:
   - Logs every step, tool invocation, model prompt/response, analyst decision, and system event to `audit_log`.

8. **Analyst Investigation Console (`static/index.html`)**:
   - Real-time investigation interface featuring:
     - Triage queue sorted by risk score.
     - Interactive Money Flow DAG view (layered left-to-right by hop depth).
     - D3.js + TopoJSON real-world JAPAC geographic corridor map.
     - Case details, session biometrics, verdict cards, and decision recording.

---

### Phase 2: Judgment, Memory & Governance Layer

1. **Source-of-Funds (SoF) Plausibility Verification (`phase2_sof.py`)**:
   - Evaluates free-text customer SoF explanations against profile evidence.
   - Detects specific inconsistencies (e.g. transfer amount vs stated annual income, salary claim for unemployed profile, savings narrative for a 3-day-old account, verbatim text re-use across transfers).

2. **Institutional Case Memory (TF-IDF Vector RAG) (`phase2_memory.py`)**:
   - Stores historical investigated cases and outcome dispositions.
   - Performs TF-IDF term-weighted vector cosine similarity search to retrieve top 5 similar precedent cases for any new alert.

3. **Model Risk Management (MRM) Draft Generator (`phase2_mrm.py`)**:
   - Auto-generates a model validation document for compliance auditors.
   - Summarizes dataset populations, feature inputs, DAG workflows, and documents model limitations.

4. **Non-Destructive Adversarial Red-Team Sandbox (`phase2_redteam.py`)**:
   - Generates novel evasive fraud scenarios (e.g., time-jittered smurfing, beneficiary rotation, device hopping) and injects them into the live database to test model evasion rates.
   - Includes `reset_redteam()` to wipe test injections and instantly roll back SQLite data to the clean baseline.

---

### Phase 3: Advanced AI Feature Suite

1. **3-Agent Adversarial AI Debate (`agent_debate.py`)**:
   - Runs a 3-stage agentic debate loop to eliminate single-prompt LLM hallucination and confirmation bias:
     - **Prosecutor Agent**: Builds the incriminating case for fraud using pass-through ratio, hold times, and shared devices.
     - **Defense Agent**: Identifies legitimate business explanations using KYC, stated income, and corridor norms.
     - **Judge Agent**: Weighs both arguments, calculates a confidence score ($0-100\%$), and issues a final synthesis verdict.
   - **Endpoint**: `POST /api/alerts/{id}/debate`

2. **Multimodal Source-of-Funds Document Verifier (`multimodal_sof.py`)**:
   - Inspects customer-submitted invoices, paystubs, and bank statements using Gemini Multimodal Vision.
   - Extracts document figures, issuer names, invoice dates, and authenticity indicators, and cross-checks extracted amounts against wire transfer figures in SQLite.
   - **Endpoint**: `POST /api/alerts/{id}/verify-document`

3. **Counterfactual "What-If" Sensitivity Simulator (`counterfactual.py`)**:
   - Real-time feature perturbation engine.
   - Allows analysts to perturb parameters (`account_age_days`, `pass_through_ratio`, `avg_hold_time_minutes`, `shared_device_count`) and view side-by-side risk score deltas ($\pm \Delta$) and sensitivity rankings.
   - **Endpoint**: `POST /api/alerts/{id}/counterfactual`

4. **Multi-Jurisdiction Regulatory Filing Generator (`sar_generator.py`)**:
   - Drafts official compliance narratives formatted for specific regional regulators:
     - **FinCEN** (US Form 111 SAR)
     - **MAS** (Singapore CAD STR Form A)
     - **AUSTRAC** (Australia SMR Form B)
   - **Endpoint**: `GET /api/alerts/{id}/sar?jurisdiction=fincen|mas|austrac`

5. **Self-Evolving Rule Miner (`rule_miner.py`)**:
   - Analyzes historical human analyst dispositions in `analyst_decisions` against graph risk features.
   - Mines high-precision candidate decision rules with precision/recall metrics for compliance MRM review.
   - **Endpoint**: `GET /api/phase2/rules/mine`

---

## 🔒 Security, Authentication & Role Simulation

The system enforces request-header driven authentication:
- `X-Analyst-ID`: Identifies the individual actor (e.g. `analyst_sarah`, `lead_michael`). Defaults to `analyst_demo`.
- `X-Analyst-Role`: Enforces role-based permissions:
  - `analyst` (Compliance Analyst): Alert triage, SoF checks, decision recording.
  - `fiu_lead` (FIU Team Lead): High-risk case overrides, payment hold directives, FIU escalations.
  - `mrm_auditor` (MRM Auditor): MRM draft reviews, red-team executions/resets, rule mining sign-offs.

---

## 📡 Complete API Reference (16 Endpoints)

| Method | Path | Purpose |
|---|---|---|
| **GET** | `/api/health` | Service health & Gemini availability status |
| **GET** | `/api/alerts` | Triage queue of flagged transactions |
| **GET** | `/api/alerts/{id}` | Case detail, sender/receiver profile, network DAG |
| **POST** | `/api/alerts/{id}/investigate` | Run investigation (`auto`, `gemini`, `deterministic`) |
| **POST** | `/api/alerts/{id}/decision` | Record analyst disposition & update case memory |
| **GET** | `/api/alerts/{id}/audit` | Case-level audit trail events |
| **GET** | `/api/alerts/{id}/export` | Official printable Case Audit Package (HTML/PDF format) |
| **POST** | `/api/alerts/{id}/debate` | Execute 3-agent Adversarial AI Debate |
| **POST** | `/api/alerts/{id}/verify-document` | Multimodal document verification & DB cross-check |
| **POST** | `/api/alerts/{id}/counterfactual` | Run What-If feature perturbation simulator |
| **GET** | `/api/alerts/{id}/sar` | Generate regulatory narrative (`jurisdiction=fincen\|mas\|austrac`) |
| **POST** | `/api/phase2/sof/{id}` | Source-of-funds plausibility review draft |
| **GET** | `/api/phase2/memory/{id}` | Retrieve precedent cases (TF-IDF Vector Cosine RAG) |
| **GET** | `/api/phase2/mrm` | Generate Model Risk Management validation draft |
| **POST** | `/api/phase2/redteam` | Run adversarial red-team scenario injections |
| **POST** | `/api/phase2/redteam/reset` | Roll back red-team test injections to baseline DB |
| **GET** | `/api/phase2/rules/mine` | Mine candidate detection rules from analyst decisions |

---

## 🛠️ Quick Start & Local Run

```bash
# 1. Setup virtual environment & dependencies
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Seed synthetic database and compute graph risk features
python data_gen.py
python graph_features.py

# 3. (Optional) Set Gemini API Key
export GEMINI_API_KEY="your_api_key_here"
export GEMINI_MODEL="gemini-3.8-flash"  # or gemini-2.5-flash

# 4. Launch FastAPI web server
uvicorn main:app --reload --port 8080
# Open http://localhost:8080 (or http://localhost:8081 if port 8081 is specified)
```

---

## 📋 Operational Workarounds for Out-of-Scope Gaps

Per [docs/GAP_AUDIT.md](file:///Users/aritrachakraborty/Desktop/corridor-watch/docs/GAP_AUDIT.md), core banking middleware integrations are intentionally out-of-scope for this POC. The platform provides documented workarounds:

1. **Automated Payment Hold/Release Execution**:
   - *Workaround*: Verdicts return explicit `recommended_action` directives (e.g., `"Hold payment, escalate to FIU case queue"`). Compliance officers review the verdict and execute the hold signal in core banking message middleware (SWIFT / ISO 20022).
2. **Regulatory SAR / STR Filings**:
   - *Workaround*: Use `GET /api/alerts/{id}/sar` to draft narrative sections or `GET /api/alerts/{id}/export` to generate an official Case Audit Package for attachment to regulatory filing portals.
3. **Database Migration**:
   - *Workaround*: SQLite schema definitions in `db.py` use standard ANSI SQL and migrate cleanly to Azure SQL / PostgreSQL via SQLAlchemy.
4. **Red-Team Dataset Reset**:
   - *Workaround*: Red-team scenario injections can be wiped and restored to baseline synthetic data anytime via `POST /api/phase2/redteam/reset` or `python data_gen.py`.

---

## ☁️ Deployment Guides

### Cloud Run (GCP)
```bash
gcloud run deploy corridor-watch \
  --source . \
  --region asia-southeast1 \
  --allow-unauthenticated \
  --set-env-vars GEMINI_API_KEY=your_key
```

### Azure Enterprise Deployment
See [docs/AZURE_PORT.md](file:///Users/aritrachakraborty/Desktop/corridor-watch/docs/AZURE_PORT.md) and [CHANGE_REQUEST_LOG.md](file:///Users/aritrachakraborty/Desktop/corridor-watch/CHANGE_REQUEST_LOG.md) for swapping GCP Gemini $\rightarrow$ Azure OpenAI / AI Foundry Agent Service.
