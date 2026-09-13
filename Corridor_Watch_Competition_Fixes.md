# Corridor Watch — Competition Fix & Mitigation Plan

## Purpose

Close the gaps identified during the latest competition-rubric review of the public Corridor Watch repository.

**Repository:** https://github.com/aritracodesbad123/corridor-watch

**Target:** Move from a strong ~88/100 submission toward a 92–97/100 class submission by improving **measured scale, impact proof, demo clarity, and production consistency** — without adding unnecessary features.

---

## 1. Priority Summary

| Priority | Problem | Fix |
|---|---|---|
| P0 | Cloud SQL / ingest throughput bottleneck | Profile every ingest stage, optimize DB round trips, pooling, commits and indexes |
| P0 | 5,000 TPS is a target, not demonstrated | Run reproducible Pub/Sub → Cloud Run → Cloud SQL benchmarks and report only measured TPS |
| P0 | SQLite / Cloud SQL ambiguity | Make SQLite local-only; GCP runtime must use Cloud SQL PostgreSQL |
| P1 | Durable investigation queue semantics | Add explicit QUEUED → CLAIMED → RUNNING → COMPLETED/RETRY/DEAD_LETTER states |
| P1 | Business impact not quantified enough | Add investigation-compression and baseline-comparison metrics |
| P1 | Feature breadth can dilute the story | Make Detect → Investigate → Learn → Detect Again the primary demo |
| P1 | Pattern DNA needs stronger visibility | Show match strength, matched/missing signals and subsequent detection |
| P1 | Gemini output needs stronger explainability | Require structured evidence IDs, alternative explanation and next checks |
| P2 | Benchmark evidence is buried | Add a compact, honest scale/evidence panel |
| P2 | Failure behavior needs proof | Test duplicate delivery, worker failure, DB outage and Gemini outage |

---

# 2. P0 — Fix the Cloud SQL / Ingest Throughput Bottleneck

The repository currently documents a measured Pub/Sub → Cloud Run → Cloud SQL result of roughly **5.65 achieved TPS at a 200 TPS target**, with the consume path identified as SQL/connector-bound and 503s appearing when the pool is cold or saturated.

This is the biggest technical weakness.

## Do not solve it by blindly increasing Cloud Run instances

First determine where time is spent.

Instrument this exact path:

```text
Pub/Sub push
    ↓
HTTP request
    ↓
decode / JSON parse
    ↓
Pydantic validation
    ↓
idempotency check
    ↓
transaction upsert
    ↓
risk/screen write
    ↓
investigation queue write
    ↓
notification publish
    ↓
ACK
```

Add timing metrics for:

```text
corridor_ingest_decode_seconds
corridor_ingest_validate_seconds
corridor_ingest_idempotency_seconds
corridor_ingest_transaction_write_seconds
corridor_ingest_queue_write_seconds
corridor_ingest_publish_seconds
corridor_ingest_total_seconds
db_pool_wait_seconds
db_connection_checkout_seconds
db_transaction_seconds
db_query_seconds
```

### Definition of done

You should be able to answer:

> At 200 TPS, what percentage of ingest latency is spent waiting for a DB connection, executing SQL, committing, or doing application work?

---

# 3. P0 — Optimize the Database Write Path

Review the hot path for:

- multiple DB round trips per transaction
- SELECT-before-INSERT patterns
- individual commits for several operations
- repeated connection acquisition
- redundant indexes
- synchronous verbose audit writes
- unnecessary investigation queue writes
- expensive post-write processing

Prefer PostgreSQL uniqueness and upserts:

```sql
INSERT INTO transactions (...)
VALUES (...)
ON CONFLICT (txn_id) DO NOTHING;
```

and:

```sql
INSERT INTO ingestion_events (...)
VALUES (...)
ON CONFLICT (message_id) DO NOTHING;
```

Avoid:

```text
SELECT
  ↓
if exists
  ↓
INSERT
```

when PostgreSQL can enforce uniqueness.

## Keep critical audit events durable

Database audit:

- analyst decision
- FIU authorization
- case state change
- pattern confirmation
- investigation completion

High-volume telemetry:

- latency
- counters
- debug traces
- Pub/Sub delivery timing
- model timing

→ Cloud Logging / metrics.

---

# 4. P0 — Benchmark Connection Pooling Systematically

Current documented defaults include Cloud Run scaling, concurrency, PostgreSQL pool size and ingest slots.

Do not increase everything simultaneously.

Run a matrix:

| Cloud Run | Concurrency | Pool | Ingest slots |
|---:|---:|---:|---:|
| 2 | 8 | 4 | 4 |
| 2 | 16 | 8 | 8 |
| 5 | 8 | 4 | 4 |
| 5 | 16 | 8 | 8 |
| 10 | 16 | 8 | 8 |
| 10 | 32 | 8 | 8 |

Record:

- achieved TPS
- P50/P95/P99
- DB CPU
- DB connections
- 5xx rate
- Pub/Sub backlog
- Cloud Run instance count
- queue depth

Choose the best configuration from measurements.

---

# 5. P0 — Keep Deep Investigation Off the Ingest Path

The desired path remains:

```text
Pub/Sub
   ↓
fast ingest
   ↓
cheap screen
   ↓
durable investigation queue
   ↓
bounded investigation
   ↓
Gemini
```

Ingest should not:

- build a large graph
- call Gemini
- perform deep precedent retrieval
- generate SAR
- run AI debate
- perform multimodal verification
- run expensive rule mining

This separation is one of the strongest architectural decisions in the project. Preserve it.

---

# 6. P1 — Make the Investigation Queue Operationally Robust

Use explicit states:

```text
QUEUED
  ↓
CLAIMED
  ↓
RUNNING
  ↓
COMPLETED
```

Failure:

```text
RUNNING
  ↓
FAILED
  ↓
RETRY
  ↓
RUNNING
```

Permanent failure:

```text
FAILED
  ↓
DEAD_LETTER
```

Store:

```text
attempt_count
claimed_at
completed_at
last_error
next_attempt_at
worker_id
```

A PostgreSQL worker can use:

```sql
SELECT ...
FROM investigation_queue
WHERE status = 'QUEUED'
ORDER BY priority DESC, created_at
FOR UPDATE SKIP LOCKED
LIMIT N;
```

### Failure test

Kill a worker during an investigation.

The job must become retryable and must not disappear.

---

# 7. P1 — Clarify Pub/Sub vs PostgreSQL Queue

The current architecture correctly treats PostgreSQL as the durable investigation queue and the second Pub/Sub topic as a best-effort notification.

Keep that design, but make it visually explicit:

```text
corridor-transactions
        ↓
     Cloud Run
        ↓
 deterministic screen
        ↓
PostgreSQL durable queue
        │
        ├──→ investigation worker
        │          ↓
        │     bounded graph
        │          ↓
        │     Pattern DNA
        │          ↓
        │        Gemini
        │
        └──→ optional notification topic
```

Do not describe the second topic as the authoritative queue if PostgreSQL is the durable queue.

---

# 8. P0 — Resolve SQLite / Cloud SQL Production Ambiguity

The desired distinction is:

```text
LOCAL DEVELOPMENT
SQLite

GCP DEPLOYMENT
Cloud Run
   ↓
Cloud SQL PostgreSQL
```

Update documentation to say clearly:

> SQLite exists only for local development and offline evaluation. GCP deployment uses Cloud SQL PostgreSQL through DATABASE_URL.

If Cloud Run currently creates or falls back to SQLite when `DATABASE_URL` is present, disable that fallback.

### Definition of done

On Cloud Run:

```text
DATABASE_URL present
        ↓
PostgreSQL selected
        ↓
no SQLite fallback
```

---

# 9. P1 — Add Quantitative Business Impact

Current evaluation already covers:

- precision
- recall
- F1
- false-positive rate
- per-typology detection
- named-pattern accuracy

Add investigator-facing metrics.

## Investigation Compression

Measure:

```text
baseline_items_reviewed
vs
network_items_reviewed
```

Example format:

```text
Traditional review: 27 transactions
Network investigation: 1 network / 8 key entities

Investigation compression: 3.4×
```

Only show measured synthetic results.

## Additional metrics

Add:

```text
evidence_coverage
analyst_actionability_rate
false_positive_reduction
network_detection_lift
time_to_case_ready
```

---

# 10. P1 — Build a Transaction-Only Baseline

Create a deliberately simple baseline:

```text
amount threshold
velocity threshold
account-age threshold
```

Compare it against Corridor Watch:

```text
transaction signals
+
network graph
+
behavioral signals
+
Pattern DNA
```

Report:

| Metric | Transaction baseline | Corridor Watch |
|---|---:|---:|
| Precision | measured | measured |
| Recall | measured | measured |
| F1 | measured | measured |
| False-positive rate | measured | measured |
| Network detection | N/A | measured |
| Investigation compression | baseline | measured |

This demonstrates that the innovation is not simply "more AI."

---

# 11. P1 — Make Crime Pattern DNA the Main Innovation

Make the central product loop:

```text
DETECT
  ↓
INVESTIGATE
  ↓
HUMAN CONFIRMATION
  ↓
CRIME PATTERN DNA
  ↓
MATCH FUTURE NETWORK
  ↓
FASTER INVESTIGATION
```

Show real computed values such as:

```text
Confirmed patterns
Pattern matches today
New matches since last case
Average match strength
```

---

# 12. P1 — Add Pattern Match Explainability

When a new case matches a DNA fingerprint, show:

```text
Pattern DNA: MULTI-HOP-LAYER-07

Match strength: 92%

Matched:
✓ 3-hop money movement
✓ 94% pass-through
✓ shared beneficiary
✓ shared device cluster
✓ IN → SG corridor
✓ 18-minute average hold time

Missing:
○ synthetic identity indicator
```

This is stronger than a generic "pattern matched" message.

---

# 13. P1 — Make Gemini Evidence-Addressable

Require structured output:

```json
{
  "primary_hypothesis": "...",
  "confidence": 0.91,
  "supporting_evidence": [
    "EVID-007",
    "EVID-011",
    "EVID-019"
  ],
  "alternative_explanation": "...",
  "next_checks": [
    "...",
    "..."
  ],
  "recommended_action": "escalate_fiu"
}
```

Every evidence ID should resolve to underlying transaction/account/network evidence.

This improves:

- GenAI credibility
- explainability
- governance
- UX
- judging confidence

---

# 14. P1 — Make Prosecutor / Defense / Judge Measurable

Don't only display three AI responses.

Show:

```text
Prosecution evidence: 7
Defense evidence: 3
Judge confidence: 86%

Key disagreement:
Rapid pass-through is suspicious, but recipient profile
indicates a plausible commercial settlement relationship.
```

This proves why the adversarial design exists.

---

# 15. P1 — Make Human-in-the-Loop a Demo Moment

### Analyst

Attempts:

```text
Freeze account
```

System:

```text
403
FIU Lead authorization required
```

### FIU Lead

Approves.

Audit records:

```text
Decision
Actor
Role
Timestamp
Evidence
Case ID
Previous state
New state
```

This is a high-value governance demonstration.

---

# 16. P2 — Simplify the Command Center

Do not expose every capability at once.

Use six primary cards:

```text
LIVE TPS
P95 INGEST
PUB/SUB BACKLOG
CLOUD RUN INSTANCES
SUSPICIOUS NETWORKS
ACTIVE INVESTIGATIONS
```

Then:

```text
TODAY'S IMPACT

Network detection
Investigation compression
Pattern DNA matches
False-positive reduction
```

All values must be computed, not hardcoded.

---

# 17. P2 — Add an Honest Scale Evidence Panel

Show:

```text
TARGET
5,000 TPS

MEASURED
X TPS

P95
X ms

STATUS
Benchmark in progress / achieved
```

If 5,000 is not achieved, never display:

```text
5,000 TPS achieved
```

Instead display:

> 5,000 TPS synthetic target

and:

> Current measured end-to-end throughput: X TPS

This protects credibility.

---

# 18. P2 — Turn the Current Bottleneck Into Engineering Evidence

If 5,000 TPS is not reached yet, show:

```text
ENGINEERING VALIDATION

Target workload       5,000 TPS
Measured              X TPS
Publisher capacity    Y TPS
Ingest capacity       X TPS
Primary bottleneck    Cloud SQL write path
Next optimization     Batched persistence
```

A judge can see that the team understands the bottleneck rather than hiding it.

---

# 19. P2 — Add Failure Tests

Test:

### Pub/Sub duplicate

Expected:

```text
one logical transaction
duplicate safely acknowledged
```

### Cloud Run restart

Expected:

```text
durable transaction
retryable investigation job
```

### PostgreSQL unavailable

Expected:

```text
controlled failure/retry
no silent data loss
```

### Gemini unavailable

Expected:

```text
ingestion continues
deterministic investigation continues
Gemini marked unavailable
```

---

# 20. P2 — Make Benchmarking Reproducible

Create one canonical command:

```bash
python pubsub_load_generator.py   --pubsub   --project YOUR_PROJECT   --rate 5000   --duration 60   --command-url https://YOUR_SERVICE   --token FIU_BEARER   --persist   --pretty
```

Record:

```text
target_tps
published
publish_tps
received
processed
failed
duplicates
achieved_tps
p50
p95
p99
pubsub_backlog_start
pubsub_backlog_end
cloud_run_max_instances
db_cpu
db_connections
```

Save timestamped results under:

```text
benchmarks/results/
```

For example:

```text
benchmarks/results/
  2026-09-13-pubsub-200tps.json
  2026-09-13-pubsub-500tps.json
  2026-09-13-pubsub-1000tps.json
```

Never commit secrets.

---

# 21. P2 — Build a Scale Curve

Measure:

```text
100 TPS
200 TPS
500 TPS
1,000 TPS
2,000 TPS
5,000 TPS
```

Plot:

```text
achieved TPS vs target TPS
P95 latency vs target TPS
```

If 5,000 is not yet achieved, the curve still provides strong engineering evidence.

---

# 22. P2 — Create a Competition Claims Policy

Add:

```text
docs/COMPETITION_CLAIMS.md
```

Use three statuses.

### Verified

Measured and reproducible.

### Implemented

Implemented and tested functionally, but not independently benchmarked at production scale.

### Target

Desired capacity or future capability.

Example:

```text
5,000 TPS
STATUS: TARGET

Pub/Sub ingestion
STATUS: IMPLEMENTED + TESTED

Cloud SQL persistence
STATUS: IMPLEMENTED + BENCHMARKED

Gemini investigation
STATUS: IMPLEMENTED

Production bank integration
STATUS: OUT OF SCOPE
```

This prevents accidental overclaiming during the presentation.

---

# 23. Recommended Final Architecture

Present the system as:

```text
Synthetic Banking World
        │
        │ 5K TPS TARGET
        ▼
Google Cloud Pub/Sub
        │
        ▼
Cloud Run Ingestion
        │
        ├── validate
        ├── idempotent persist
        └── cheap screen
                 │
                 ▼
       PostgreSQL investigation queue
                 │
                 ▼
          bounded graph engine
                 │
          ┌──────┴──────┐
          ▼             ▼
     Pattern DNA      Evidence
          │             │
          └──────┬──────┘
                 ▼
        Gemini Investigator
        evidence-grounded
                 │
                 ▼
        Human authorization
                 │
                 ▼
            Audit trail
                 │
                 ▼
          Pattern confirmation
                 │
                 └────→ future detection
```

---

# 24. Competition Definition of Done

## Technical

- [ ] Cloud Run uses Cloud SQL PostgreSQL
- [ ] SQLite is local-only
- [ ] Pub/Sub push is the real cloud ingest path
- [ ] Idempotency tested
- [ ] DB pooling benchmarked
- [ ] ingest stages instrumented
- [ ] investigation retry semantics tested
- [ ] Gemini is off the hot path
- [ ] deterministic investigation works without Gemini
- [ ] benchmark results are reproducible

## Scale

- [ ] 100 TPS measured
- [ ] 200 TPS measured
- [ ] 500 TPS measured
- [ ] 1,000 TPS measured
- [ ] 2,000 TPS measured
- [ ] 5,000 TPS attempted
- [ ] achieved TPS reported honestly
- [ ] P50/P95/P99 recorded
- [ ] Pub/Sub backlog recorded
- [ ] Cloud Run scaling recorded
- [ ] Cloud SQL utilization recorded

## Financial Crime

- [ ] network-level investigation demonstrated
- [ ] multi-hop case demonstrated
- [ ] corridor intelligence demonstrated
- [ ] Pattern DNA created from confirmed case
- [ ] subsequent Pattern DNA match demonstrated
- [ ] evidence IDs shown
- [ ] alternative explanation shown

## Governance

- [ ] analyst cannot perform FIU-only action
- [ ] FIU Lead can authorize
- [ ] action is audited
- [ ] Gemini cannot directly execute consequential actions
- [ ] case export works
- [ ] MRM output works
- [ ] red-team workflow works

## Impact

- [ ] transaction-only baseline exists
- [ ] network-aware comparison exists
- [ ] false-positive comparison exists
- [ ] investigation compression metric exists
- [ ] analyst-actionability metric exists

## UX

- [ ] Command Center understandable in 5 seconds
- [ ] suspicious network visible immediately
- [ ] evidence traceable
- [ ] Gemini output structured
- [ ] Pattern DNA visually prominent
- [ ] advanced features do not dominate the main journey

---

# 25. Recommended 3–5 Minute Demo

### 0:00–0:30 — Problem

> Traditional monitoring sees suspicious transactions. Criminal networks operate across accounts, devices and corridors.

Show a suspicious corridor and connected network.

### 0:30–1:00 — Scale

Show:

```text
5,000 TPS TARGET
LIVE MEASURED TPS: X
P95: X ms
PUB/SUB BACKLOG: X
```

If 5,000 is not achieved, say so honestly.

### 1:00–2:00 — Investigation

Show:

- graph
- hop depth
- shared devices
- beneficiaries
- velocity
- evidence IDs
- Pattern DNA match

### 2:00–2:45 — Gemini

Show:

- primary hypothesis
- supporting evidence
- alternative explanation
- next checks
- confidence

Then show Prosecutor vs Defense if time permits.

### 2:45–3:15 — Human governance

Analyst attempts:

```text
FREEZE ACCOUNT
```

→ denied.

FIU Lead approves.

→ audit event.

### 3:15–4:00 — Learning loop

Confirmed case:

```text
Case
 ↓
Crime Pattern DNA
 ↓
New matching network
 ↓
Detection
```

End with:

> **The transaction is not the crime. The network is.**

---

# 26. What NOT to Do

Do not:

- add another LLM
- add another agent
- add another dashboard
- claim 5,000 TPS without measurement
- hide the current bottleneck
- represent synthetic evaluation as production validation
- put Gemini into the ingest path
- replace deterministic investigation with an LLM
- allow autonomous freeze/hold decisions
- spend the final sprint on cosmetic features before scale and benchmark work

---

# 27. Expected Rubric Improvement

| Rubric | Current assessment | Target after fixes |
|---|---:|---:|
| Technical Merit & GenAI | ~35/40 | 37–39/40 |
| Problem Alignment & Impact | ~23/25 | 24–25/25 |
| Innovation & Creativity | ~22/25 | 23–24/25 |
| UX & Solution Design | ~8/10 | 9–10/10 |
| **Total** | **~88/100** | **93–98/100** |

These are targets, not guarantees.

---

# 28. Final Implementation Order

If time is limited:

1. **DB/ingest profiling and optimization**
2. **End-to-end Pub/Sub benchmark**
3. **PostgreSQL/SQLite production consistency**
4. **Investigation queue reliability**
5. **Transaction-only baseline**
6. **Investigation compression metric**
7. **Pattern DNA match visualization**
8. **Evidence-addressable Gemini output**
9. **Judge-friendly Command Center**
10. **Final 3–5 minute demo**

## Final strategy

**Do not make Corridor Watch bigger. Make the existing system more provable.**

The project already has substantial feature breadth. The next jump in competition score comes from:

**measured performance + quantified impact + evidence-grounded AI + transparent governance + focused storytelling.**
