# Architecture notes (master spec evolution)

Corridor Watch is now two cooperating layers:

1. **Existing investigation console** — DAG, Gemini tool agent, Phase 2/3 judgment tools, analyst RBAC.
2. **Network intelligence platform** — ingest → cheap screen → investigation queue → bounded graph → Crime Pattern DNA → evidence-grounded Gemini → human decision → reusable pattern.

```
synthetic / Pub/Sub / HTTP ingest
        ↓
validate + idempotent persist     (no Gemini)
        ↓
LOW / MEDIUM / HIGH / CRITICAL
        ↓
MEDIUM+ investigation queue
        ↓
bounded graph + DNA match
        ↓
Gemini copilot (HIGH/CRITICAL or analyst-requested only)
        ↓
human decision + audit
        ↓
Crime Pattern DNA library
```

## Persistence

- Local: SQLite `fraud_demo.db`
- Cloud SQL: set `DATABASE_URL=postgresql://...`
- Application code uses `db.connect()` / `db.upsert()` and does not import sqlite3 for new tables.

## Gemini isolation

Ingest (`pubsub/ingestion.py`, `/api/ingest`, `/api/pubsub/push`) never calls Gemini.
If Gemini is down, screening and case creation continue.

## Human control

`hold_payment`, `escalate_fiu`, and `freeze_account` still require `fiu_lead`.
Gemini may only recommend a disposition.

## Benchmarks

`python pubsub_load_generator.py --rate 500 --duration 5 --in-process`
`python evaluate.py --mode both --rate 200 --duration 3`

Report only measured `achieved_tps`. Do not present a target rate as a result.
