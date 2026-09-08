# Corridor Watch

Cross-border payment fraud **investigation console & compliance AI reasoning engine** for JAPAC remittance corridors.
Graph detection is table stakes — this product is the reasoning, explainability, multimodal verification, regulatory filing, and institutional-memory layer that sits on top.

---

## 🚀 Capabilities Overview

| Phase | Capability | Description |
|---|---|---|
| **Phase 1** | Graph & Biometric Core | Synthetic data generator (5 fraud scenarios), NetworkX feature extraction (fan-in/out, pass-through ratio, hold times), named pattern scoring, simulated session biometrics, 12-step deterministic investigation DAG, Gemini tool-calling agent, append-only audit trail, and analyst console. |
| **Phase 2** | Judgment & Memory Layer | Source-of-funds (SoF) plausibility check, institutional case memory (TF-IDF Vector RAG precedent search), Model Risk Management (MRM) draft generator, and non-destructive adversarial red-team loop. |
| **Phase 3** | Advanced AI Features | **3-Agent Adversarial Debate** (*Prosecutor vs Defense vs Judge*), **Multimodal Document Verifier** (Gemini Vision OCR + DB cross-check), **What-If Counterfactual Simulator**, **Multi-Jurisdiction SAR Filing Generator** (*FinCEN, MAS, AUSTRAC*), and **Self-Evolving Rule Miner**. |
| **Extensions** | Security & Governance | Analyst Authentication & RBAC headers (`analyst`, `fiu_lead`, `mrm_auditor`), Case Audit Package Export (HTML/PDF ready), and Red-Team Dataset Reset. |

---

## 🤖 Advanced AI Feature Suite (Phase 3)

### 1. Adversarial AI Debate System (`agent_debate.py`)
- **Pipeline**: Runs Prosecutor, Defense, and Chief Compliance Judge agents in sequence.
- **Purpose**: Eliminates single-prompt LLM hallucination and confirmation bias by forcing an explicit debate between incriminating evidence and legitimate business explanations.
- **Endpoint**: `POST /api/alerts/{id}/debate`

### 2. Multimodal Source-of-Funds Document Verifier (`multimodal_sof.py`)
- **Pipeline**: Inspects customer-submitted invoices, paystubs, and bank statements using Gemini Vision OCR.
- **Purpose**: Extracts document type, issuer name, invoice date, total amounts, and authenticity signals, comparing extracted values against wire transfer records in SQLite to spot discrepancies.
- **Endpoint**: `POST /api/alerts/{id}/verify-document`

### 3. Counterfactual "What-If" Sensitivity Simulator (`counterfactual.py`)
- **Pipeline**: Real-time feature perturbation engine.
- **Purpose**: Allows analysts and model auditors to perturb parameters (`account_age_days`, `pass_through_ratio`, `avg_hold_time_minutes`, `shared_device_count`) and view exact risk score deltas ($\pm \Delta$) and sensitivity rankings.
- **Endpoint**: `POST /api/alerts/{id}/counterfactual`

### 4. Multi-Jurisdiction Regulatory Filing Generator (`sar_generator.py`)
- **Pipeline**: Drafts official structured compliance filing narratives.
- **Jurisdictions Supported**:
  - **FinCEN** (US Bank Secrecy Act / Form 111 SAR)
  - **MAS** (Singapore Monetary Authority / CAD STR Form A)
  - **AUSTRAC** (Australia SMR Form B)
- **Endpoint**: `GET /api/alerts/{id}/sar?jurisdiction=fincen|mas|austrac`

### 5. Self-Evolving Rule Miner (`rule_miner.py`)
- **Pipeline**: Machine learning & rule extraction engine.
- **Purpose**: Analyzes historical human analyst dispositions in `analyst_decisions` against graph risk features to discover candidate decision rules with precision/recall statistics.
- **Endpoint**: `GET /api/phase2/rules/mine`

---

## 🛠️ Quick Start & Local Run

```bash
# 1. Setup virtual environment & dependencies
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Seed synthetic database and compute graph risk features
python data_gen.py
python graph_features.py

# 3. (Optional) Enable Gemini LLM reasoning & vision features
export GEMINI_API_KEY="your_api_key_here"
export GEMINI_MODEL="gemini-3.8-flash"  # or gemini-2.5-flash

# 4. Start local API server & console
uvicorn main:app --reload --port 8080
# Open http://localhost:8080 (or http://localhost:8081 if port 8081 is specified)
```

---

## 📡 Complete API Surface

| Method | Path | Purpose |
|---|---|---|
| **GET** | `/api/alerts` | Flagged triage alert queue |
| **GET** | `/api/alerts/{id}` | Case details + network graph + biometrics |
| **POST** | `/api/alerts/{id}/investigate` | Execute investigation (`auto`, `gemini`, `deterministic`) |
| **POST** | `/api/alerts/{id}/decision` | Record analyst disposition & update case memory |
| **GET** | `/api/alerts/{id}/audit` | Case-level append-only audit trail |
| **GET** | `/api/alerts/{id}/export` | Official printable Case Audit Package (HTML/PDF format) |
| **POST** | `/api/alerts/{id}/debate` | Launch 3-agent Adversarial AI Debate |
| **POST** | `/api/alerts/{id}/verify-document` | Multimodal document verification & DB cross-check |
| **POST** | `/api/alerts/{id}/counterfactual` | Run What-If feature perturbation simulator |
| **GET** | `/api/alerts/{id}/sar` | Generate regulatory narrative (`jurisdiction=fincen\|mas\|austrac`) |
| **POST** | `/api/phase2/sof/{id}` | Source-of-funds plausibility draft |
| **GET** | `/api/phase2/memory/{id}` | Similar precedent cases (TF-IDF Vector Cosine RAG) |
| **GET** | `/api/phase2/mrm` | Model Risk Management validation draft |
| **POST** | `/api/phase2/redteam` | Inject adversarial scenarios & evaluate detection evasion |
| **POST** | `/api/phase2/redteam/reset` | Roll back red-team injections and restore baseline synthetic DB |
| **GET** | `/api/phase2/rules/mine` | Mine candidate detection rules from historical dispositions |

---

## 🔒 Security, Authentication & Roles

The system supports request-header driven authentication:
- `X-Analyst-ID`: Identifies the individual actor (e.g. `analyst_sarah`, `lead_michael`). Defaults to `analyst_demo`.
- `X-Analyst-Role`: Enforces security persona permissions:
  - `analyst` (default): Front-line alert triage, SoF checks, decision recording.
  - `fiu_lead`: High-risk case overrides, payment hold directives, FIU escalations.
  - `mrm_auditor`: MRM draft reviews, red-team executions/resets, rule mining sign-offs.

---

## 📋 Operational Workarounds for Out-of-Scope Gaps

Per [docs/GAP_AUDIT.md](file:///Users/aritrachakraborty/Desktop/corridor-watch/docs/GAP_AUDIT.md), certain core banking middleware integrations are intentionally out-of-scope for this POC. The platform provides clear operational workarounds:

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

### Azure Enterprise Port Map
See [docs/AZURE_PORT.md](file:///Users/aritrachakraborty/Desktop/corridor-watch/docs/AZURE_PORT.md) and [CHANGE_REQUEST_LOG.md](file:///Users/aritrachakraborty/Desktop/corridor-watch/CHANGE_REQUEST_LOG.md) for swapping GCP Gemini $\rightarrow$ Azure OpenAI / AI Foundry Agent Service.
