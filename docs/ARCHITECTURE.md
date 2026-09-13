# Architecture notes (master spec evolution)

Corridor Watch is now two cooperating layers:

1. **Existing investigation console** — DAG, Gemini tool agent, Phase 2/3 judgment tools, analyst RBAC.
2. **Network intelligence platform** — ingest → cheap screen → investigation queue → bounded graph → Crime Pattern DNA → evidence-grounded Gemini → human decision → reusable pattern.

```
synthetic generator
        ↓
Google Pub/Sub (corridor-transactions)
        ↓
push subscription → Cloud Run /api/pubsub/push
        ↓
validate + idempotent persist     (no Gemini)
        ↓
cheap_screen → LOW / MEDIUM / HIGH / CRITICAL
        ↓
MEDIUM+ rows land in PostgreSQL investigation_queue
        ↓  (optional fan-out message on corridor-investigations)
bounded graph + DNA match
        ↓
Gemini copilot (HIGH/CRITICAL or analyst-requested only)
        ↓
human decision + audit
        ↓
Crime Pattern DNA library
```

Graphs distinguish **observed / external / inferred / unknown**. Visibility is a coverage score, not guilt. Gemini must not invent missing institutions. Synthetic intelligence is an optional overlay; ingest stays cheap.

The durable investigation queue is **PostgreSQL**, not a second Pub/Sub consumer.
`INVESTIGATION_TOPIC` is a best-effort notification after the row is committed.

In-process and HTTP batch ingest are local/dev measurement paths. They are not the Cloud Run scale path.

## Persistence

SQLite exists only for local development and offline evaluation. GCP deployment uses Cloud SQL PostgreSQL through `DATABASE_URL`. If `ENVIRONMENT=gcp` and `DATABASE_URL` is not PostgreSQL, the process refuses to start.

- Local: SQLite `fraud_demo.db`
- GCP: `DATABASE_URL=postgresql://...` (Cloud SQL). No SQLite fallback.
- Application code uses `db.connect()` / `db.upsert()` / `db.insert_or_ignore()` and does not import sqlite3 for new tables.

Queue states: `QUEUED → CLAIMED → RUNNING → COMPLETED`, with `RETRY` and `DEAD_LETTER` on failure. PostgreSQL is the durable queue; `INVESTIGATION_TOPIC` is notify-only.

## Gemini isolation

Ingest (`pubsub/ingestion.py`, `/api/ingest`, `/api/pubsub/push`) never calls Gemini.
If Gemini is down, screening and case creation continue.

## Analyst console

`static/index.html` is a four-view workspace: Home, Corridor Explorer, Investigations, Pattern DNA.
The Investigations layout is viewport-locked. The left queue scrolls on its own. The case pane scrolls horizontally so tabs, feature cards, and the money-flow DAG stay in frame. Corridor geography and the Explorer graph support zoom and pan.

## Human control

`hold_payment`, `escalate_fiu`, and `freeze_account` still require `fiu_lead`.
Gemini may only recommend a disposition.

## Benchmarks

`python pubsub_load_generator.py --rate 500 --duration 5 --in-process`  # local process only
`python pubsub_load_generator.py --pubsub --rate 1000 --duration 20 --command-url URL --token TOKEN`
`python evaluate.py --mode both --rate 200 --duration 3`

Report only measured `achieved_tps`. Do not present a target rate as a result.
in_process ≠ HTTP ≠ Pub/Sub → Cloud Run.

See [COMPETITION_CLAIMS.md](COMPETITION_CLAIMS.md). 5,000 TPS is a **TARGET**, not a verified result.
