# Architecture notes

**The transaction is not the crime. The network is.** Judge-facing brief: [COMPETITION.md](COMPETITION.md).

```text
Transactions
     ↓
Network Construction
     ↓
Deterministic Detection
     ↓
Investigation DAG
     ↓
Evidence Pack
     ↓
Gemini Copilot
     ↓
Grounding Gate
     ↓
Human Decision
     ↓
Crime Pattern DNA
     ↓
Institutional Memory
     ↺
Future Investigations
```

Corridor Watch is two cooperating layers:

1. **Investigation console** — DAG, Gemini copilot, Pattern DNA, analyst RBAC.
2. **Network intelligence platform** — ingest → cheap screen → investigation queue → bounded graph → Crime Pattern DNA → evidence-grounded Gemini → human decision → reusable pattern.

Ingest never calls Gemini. High-risk freeze/hold/escalate requires `fiu_lead`. Graphs distinguish observed / external / inferred / unknown. Visibility is a coverage score, not guilt.

SQLite is local-only. GCP uses Cloud SQL PostgreSQL. Report only measured `achieved_tps`. 5,000 TPS is a **TARGET**.

The durable investigation queue is **PostgreSQL**, not a second Pub/Sub consumer.
`outbox_events` is written in the same ingest transaction. `INVESTIGATION_TOPIC` is a best-effort notification after commit; unpublished outbox rows retry.

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
When `OIDC_ISSUER` is set they also require an MFA-backed SSO session.
Gemini may only recommend a disposition. The model sees tokenized account IDs, not customer names.

## Benchmarks

`python pubsub_load_generator.py --rate 500 --duration 5 --in-process`  # local process only
`python pubsub_load_generator.py --pubsub --rate 1000 --duration 20 --command-url URL --token TOKEN`
`python evaluate.py --mode both --rate 200 --duration 3`

Report only measured `achieved_tps`. Do not present a target rate as a result.
in_process ≠ HTTP ≠ Pub/Sub → Cloud Run.

`/api/metrics` includes measured SLO status and in-process alerts. Requests carry `X-Trace-Id`. Cloud SQL PITR is enabled with `scripts/enable_sql_pitr.sh`; `scripts/dr_status.sh` reads backup state. RPO/RTO are TARGET until a restore game day.

See [COMPETITION_CLAIMS.md](COMPETITION_CLAIMS.md). 5,000 TPS is a **TARGET**, not a verified result.
