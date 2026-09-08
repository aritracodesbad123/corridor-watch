# Azure enterprise port map

Corridor Watch's IP is the investigation workflow, prompts, tool schemas, scoring
rules, and analyst UX — not the cloud provider. Estimated rework: **~1 day** for
a functional Azure Container Apps deployment on synthetic data; longer for
tenant-hardened networking / Entra / Purview.

| Hackathon / MVP | Azure production equivalent |
|---|---|
| Gemini via `google-genai` | Azure OpenAI (GPT-4o) or Azure AI Foundry Agent Service |
| SQLite `fraud_demo.db` | Azure SQL Database or Cosmos DB |
| NetworkX (local batch) | Databricks GraphFrames / Microsoft Fabric graph analytics |
| Cloud Run | Azure Container Apps |
| Local `audit_log` table | Azure Monitor + Application Insights (structured traces) |
| Env var API keys | Azure Key Vault references |
| `static/` via FastAPI | Azure Static Web Apps (optional split) or keep single container |
| — | Microsoft Purview for lineage / governance |
| — | Microsoft Entra ID for analyst auth |

## Code touch points

1. **`agent.py`** — replace `google.genai` client with Azure OpenAI tool-calling
   client; keep `SYSTEM_PROMPT`, tool names, and verdict JSON schema identical.
2. **`db.py` / SQL** — swap sqlite3 for SQLAlchemy + Azure SQL connection string
   from Key Vault; schema is already normalized.
3. **`graph_features.py`** — keep NetworkX for POC; for scale, emit the same
   feature columns from GraphFrames jobs into `risk_scores`.
4. **Deploy** — Container Apps from the same Dockerfile; mount secrets as env.

## Data governance talking points (client objection)

- Enterprise Azure OpenAI: contractual **zero retention / no training** on customer data
- Deploy inside client tenant, VNet + private endpoints
- Customer-managed keys via Key Vault
- Synthetic-only until client InfoSec signs off
- Full AI I/O audit trail already in Phase 1 (`audit_log`)
- DPA with explicit no-retention language — non-negotiable

**Positioning:** the AI layer is a thin, auditable, swappable component on top of
the bank's existing controls — not a new black box.
