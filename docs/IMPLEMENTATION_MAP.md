# Corridor Watch — implementation map

Internal map of the repository after the master-spec evolution. Existing Phase 1–3 modules remain the investigation console; new packages add streaming, multi-institution synthesis, Crime Pattern DNA, and evidence-grounded Gemini output.

## Preserved baseline

| Module | Role |
|---|---|
| `main.py` | FastAPI surface (legacy alert APIs kept) |
| `auth.py` | `analyst` / `fiu_lead` / `mrm_auditor` RBAC; optional OIDC bearer + MFA step-up |
| `privacy.py` | HMAC account tokens + untrusted document wrap for Gemini |
| `db.py` | Connection + schema; SQLite local-only, PostgreSQL required on GCP |
| `audit.py` | Append-only case audit |
| `data_gen.py` | Seeded demo population (5 typologies) |
| `graph_features.py` | NetworkX scoring + neighborhood viz |
| `investigation_dag.py` | 12-step deterministic DAG |
| `agent.py` | Gemini tool-calling + fallback verdict |
| `phase2_*.py`, `agent_debate.py`, `multimodal_sof.py`, `counterfactual.py`, `sar_generator.py`, `rule_miner.py` | Judgment / demo suite |
| `static/index.html` | Analyst console (Home / Explorer / Investigations / Pattern DNA; queue and case panes scroll in-viewport; map zoom) |

High-risk dispositions (`hold_payment`, `escalate_fiu`, `freeze_account`) remain FIU-lead only. Gemini never executes those actions.

## New platform layer

| Package | Role |
|---|---|
| `config.py` | Environment configuration |
| `metrics.py` | In-process counters, SLO snapshot, alert evaluation |
| `tracing.py` | Request `trace_id` / `span_id` from W3C or Cloud Trace headers |
| `risk/` | Cheap screening + configurable risk tiers |
| `pubsub/` | Transaction schema, idempotent ingest, transactional outbox, optional GCP publish |
| `synthetic/` | Multi-bank world + correlated fraud campaigns |
| `graph/` | Bounded traversal, corridor intelligence, visibility / boundaries |
| `intelligence/` | Synthetic external signals (RBAC, no raw customer data) |
| `patterns/` | Crime Pattern DNA schema, extract, match, store |
| `investigations/` | Evidence IDs, grounded report, durable queue claim/retry |
| `pubsub_load_generator.py` | Three-mode load test: in-process, HTTP, Pub/Sub → Cloud Run |
| `evaluate.py` | Detection + ingest evaluation CLI |

## Request path (Gemini stays off the hot path)

```
synthetic / Pub/Sub / HTTP ingest
        ↓
validate + (source_system, source_event_id) dedupe
        ↓
cheap risk screen → LOW | MEDIUM | HIGH | CRITICAL
        ↓
one DB transaction: ledger + investigation_queue + outbox_events
        ↓
outbox drain → optional Pub/Sub notify (not the consumer)
        ↓
MEDIUM+ workers claim queue (QUEUED → CLAIMED → RUNNING → COMPLETED / RETRY / DEAD_LETTER)
        ↓
graph / DNA / optional Gemini
        ↓
analyst UI → human decision → audit → pattern library
```

The durable investigation queue is PostgreSQL. Outbox rows are authoritative for notify retry. `INVESTIGATION_TOPIC` is a notification, not a second ingest pipeline. `CW_ROLE` can run `api`, `investigation`, or `outbox` processes.

## Local vs GCP

- **Local:** SQLite + HTTP ingest (`POST /api/ingest/...`). No GCP credentials required.
- **GCP:** `DATABASE_URL` → Cloud SQL PostgreSQL; SQLite is refused. `GOOGLE_CLOUD_PROJECT` enables Pub/Sub publish/push.

Ingest stages (`ingest_decode`, `ingest_validate`, `ingest_idempotency`, writes, publish, DB pool wait) are timed in `/api/metrics` and Command Center `ingest_stages_ms`.

## Tests

Baseline behavior stays in `tests/test_core.py`. Platform coverage is in `tests/test_platform.py` (auth, ingest idempotency, queue retry, GCP SQLite refusal, transaction baseline, DNA, grounded report, RBAC). Reliability coverage is in `tests/test_reliability.py` (source-event duplicates, outbox, backoff). The evidence suite is `validation/` (not `evaluation/` — that name is taken by `evaluation.py`). Claims policy: [COMPETITION_CLAIMS.md](COMPETITION_CLAIMS.md). Scorecard: [SCORECARD.md](../reports/SCORECARD.md). Production evidence: [load-test](../production/load-test-report.md), [DR](../production/disaster-recovery-report.md), [threat model](../production/security-threat-model.md), [AI validation](../production/ai-model-validation-report.md).
