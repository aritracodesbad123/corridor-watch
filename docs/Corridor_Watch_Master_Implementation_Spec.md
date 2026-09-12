# Corridor Watch — Master Implementation Specification

**Status:** Active build plan  
**Purpose:** Coding-agent source of truth for evolving Corridor Watch into a high-potential Google Cloud / JAPAC financial-crime hackathon submission.  
**Repository:** `https://github.com/aritracodesbad123/corridor-watch`

---

## 1. Executive Objective

Corridor Watch should evolve from its current FastAPI AML/fraud POC into:

> **A cloud-native financial-crime intelligence platform that detects suspicious transaction networks across accounts, institutions and cross-border corridors, converts confirmed investigations into reusable Crime Pattern DNA, and uses Gemini as an evidence-grounded investigation copilot while keeping consequential decisions human-authorized and auditable.**

### North-star thesis

> **The transaction is not the crime. The network is.**

Do not build a generic “AI AML detector.” The product must demonstrate a shift from isolated transaction alerts to network-level financial-crime intelligence.

---

# 2. What Makes the Product Differentiated

Google and other financial-crime vendors already provide AML risk scoring and AI-assisted AML capabilities. Corridor Watch must therefore **not** compete on “we also have an AML model.”

The differentiation should be the combination of:

1. **High-throughput streaming**
2. **Cross-border corridor intelligence**
3. **Cross-institution synthetic network analysis**
4. **Network-first investigations**
5. **Crime Pattern DNA**
6. **Evidence-grounded Gemini investigation**
7. **Human-authorized decisioning**
8. **Governance and auditability**
9. **Measurable investigator workload reduction**

### Product distinction

Traditional model:

```text
Transaction
    ↓
Risk score
    ↓
Alert
    ↓
Analyst
```

Corridor Watch:

```text
Transactions
    ↓
Relationships
    ↓
Financial network
    ↓
Cross-border corridor
    ↓
Crime Pattern DNA
    ↓
AI investigation
    ↓
Human decision
    ↓
Reusable intelligence
```

---

# 3. Hackathon Rubric Strategy

The target judging rubric is:

| Criterion | Weight | Build Priority |
|---|---:|---|
| Technical Merit & GenAI | 40% | Highest |
| Problem Alignment & Impact | 25% | Highest |
| Innovation & Creativity | 25% | Highest |
| UX & Solution Design | 10% | High |

## Technical Merit & GenAI — 40%

Demonstrate:

- Google Pub/Sub
- Cloud Run
- Cloud SQL PostgreSQL
- scalable ingestion
- graph analysis
- Gemini
- evidence-grounded reasoning
- structured model outputs
- observability
- failure handling
- selective AI invocation

## Problem Alignment & Impact — 25%

Demonstrate:

- cross-border financial crime
- fragmented visibility
- network-level detection
- investigator workload
- measurable investigation compression
- human-controlled financial decisions

## Innovation & Creativity — 25%

Demonstrate:

- Corridor Intelligence
- Network-as-investigation-unit
- Crime Pattern DNA
- cross-institution simulation
- reusable intelligence feedback loop
- privacy-aware intelligence exchange concept

## UX — 10%

Demonstrate:

- command center
- corridor explorer
- investigation workspace
- clear evidence
- graph/timeline
- clear authorized actions

---

# 4. Existing Repository Baseline

Before changing code, inspect the repository and preserve existing functionality.

Important current files:

- `main.py`
- `auth.py`
- `db.py`
- `audit.py`
- `data_gen.py`
- `graph_features.py`
- `agent.py`
- `Dockerfile`
- `requirements.txt`
- `static/`

Current roles:

```text
analyst
fiu_lead
mrm_auditor
```

Current high-risk authorization must remain enforced:

```text
hold_payment
escalate_fiu
freeze_account
```

Ordinary analysts must not receive those permissions.

Current local startup:

```bash
python -m uvicorn main:app --reload
```

---

# 5. Non-Negotiable Architecture Principles

## 5.1 Never send the 5,000 TPS stream directly to Gemini

Use:

```text
5,000 TPS
   ↓
fast screening
   ↓
risk tier
   ↓
only suspicious/high-value events
   ↓
graph investigation
   ↓
Gemini
```

Gemini is an investigation layer, not the ingestion bottleneck.

## 5.2 Human remains responsible for consequential decisions

Gemini may recommend.

Gemini must not autonomously execute:

- account freeze
- payment hold
- FIU escalation
- other high-risk dispositions

## 5.3 All financial data is synthetic

Never use real customer data.

## 5.4 Every AI claim should be evidence-grounded

The model must not invent:

- transactions
- accounts
- customers
- countries
- evidence
- regulatory requirements
- investigation results

## 5.5 Benchmark numbers must be measured

Never fabricate throughput, latency, precision, recall, cost, or investigator-time savings.

---

# 6. Target Architecture

```text
                 SYNTHETIC BANKING WORLD
       accounts / devices / banks / corridors
                         |
                         v
                Google Pub/Sub
             corridor-transactions
                         |
                         v
               Cloud Run ingestion
                         |
                 validation/idempotency
                         |
                   fast screening
                         |
             +-----------+-----------+
             |                       |
           normal                suspicious
             |                       |
             v                       v
          metrics           Pub/Sub investigations
                                     |
                                     v
                          Cloud Run investigation
                                     |
                 +-------------------+-------------------+
                 |                   |                   |
                 v                   v                   v
              Graph              Risk fusion       Pattern match
            enrichment
                 |                   |                   |
                 +-------------------+-------------------+
                                     |
                                     v
                              Gemini Investigator
                                     |
                                     v
                            Analyst Investigation UI
                                     |
                                     v
                            Human Decision / Review
                                     |
                                     v
                                Audit Trail
                                     |
                                     v
                           Crime Pattern DNA
                                     |
                                     v
                            Future Detection
```

---

# 7. Phase 0 — Baseline and Repository Audit

## Objective

Understand the existing code before refactoring.

## Tasks

- [ ] Inspect every current Python module.
- [ ] Identify all database access.
- [ ] Identify all API endpoints.
- [ ] Identify all frontend flows.
- [ ] Identify all Gemini calls.
- [ ] Identify current graph implementation.
- [ ] Identify existing synthetic scenarios.
- [ ] Identify current tests.
- [ ] Run application locally.
- [ ] Capture baseline behavior.

## Acceptance criteria

- Existing app starts.
- Existing UI works.
- Existing decision endpoint works.
- RBAC behavior remains correct.
- Existing synthetic data generation works.
- Existing Gemini path works if configured.

Do not refactor blindly.

---

# 8. Phase 1 — Testing Foundation

Create tests before major architectural changes.

Suggested:

```text
tests/
  test_auth.py
  test_transactions.py
  test_decisions.py
  test_audit.py
  test_risk.py
  test_graph.py
  test_patterns.py
  test_pubsub.py
  test_idempotency.py
  test_agent.py
```

Test:

- normal decisions
- high-risk authorization
- malformed transactions
- duplicate transaction IDs
- graph calculations
- risk tiers
- pattern matching
- structured Gemini outputs
- audit events

---

# 9. Phase 2 — Database Abstraction

## Problem

SQLite is useful locally but unsuitable as the primary persistence layer for horizontally scaled Cloud Run.

## Target

```text
Local → SQLite
GCP → Cloud SQL PostgreSQL
```

Introduce a repository/data-access abstraction.

Possible structure:

```text
db/
  __init__.py
  base.py
  sqlite.py
  postgres.py
  repositories/
    accounts.py
    transactions.py
    investigations.py
    patterns.py
    audit.py
```

The exact structure may vary, but application logic must not depend directly on SQLite.

## Requirements

- explicit database configuration;
- PostgreSQL support;
- migration mechanism;
- connection pooling;
- transaction uniqueness;
- idempotent writes;
- indexed investigation queries;
- local SQLite compatibility.

---

# 10. Phase 3 — Data Model Expansion

## Transaction

Support:

```text
txn_id
timestamp
sender_account_id
receiver_account_id
amount
currency
origin_country
destination_country
origin_bank_id
destination_bank_id
channel
beneficiary_id
device_id
session_id
risk_score
risk_tier
status
```

## Account

```text
account_id
customer_id
bank_id
country
created_at
account_type
risk_profile
```

## Device

```text
device_id
first_seen
last_seen
country
```

## Beneficiary

```text
beneficiary_id
bank_id
country
created_at
```

## Investigation

Support:

```text
case_id
created_at
updated_at
status
risk_level
primary_txn_id
network_id
pattern_ids
ai_summary
ai_hypothesis
confidence
analyst_decision
assigned_role
```

## Pattern

Support:

```text
pattern_id
version
name
description
signals
graph_signature
temporal_signature
corridor_signature
created_at
created_by
active
```

---

# 11. Phase 4 — Synthetic Multi-Institution Banking World

Create:

```text
synthetic/
  world.py
  banks.py
  accounts.py
  devices.py
  beneficiaries.py
  corridors.py
  transaction_generator.py
  fraud_patterns.py
  publisher.py
```

Generate synthetic institutions such as:

```text
BANK_JP
BANK_SG
BANK_IN
BANK_PH
BANK_ID
PAYMENT_PROVIDER_X
```

All institution names are synthetic.

## Synthetic corridors

Support configurable scenarios such as:

```text
JP → SG
JP → PH
JP → ID
IN → SG
IN → AE
PH → SG
VN → SG
```

These are synthetic test scenarios, not claims about actual criminal prevalence.

---

# 12. Phase 5 — Correlated Fraud Scenarios

Fraud must be generated as coherent network behavior.

## Required patterns

### 12.1 Mule pass-through

```text
Victim → Mule A → Mule B → Mule C → Beneficiary
```

Signals:

- new account
- rapid movement
- short holding period
- unusual velocity

### 12.2 Fan-in / fan-out

```text
A ─┐
B ─┼→ MULE → X
C ─┘
```

### 12.3 Shared device ring

```text
Account A ─┐
Account B ─┼→ Device D
Account C ─┘
```

### 12.4 Shared beneficiary ring

Multiple unrelated accounts route funds to the same beneficiary.

### 12.5 Structuring

One large inflow rapidly split into smaller movements.

### 12.6 Multi-hop movement

```text
A → B → C → D → overseas
```

### 12.7 Cross-institution movement

```text
Bank A → Bank B → Payment Provider → overseas
```

### 12.8 Synthetic identity pattern

Combine:

- young account;
- new device;
- unusual activity;
- relationship reuse;
- abnormal transaction velocity.

Every scenario needs:

```text
scenario_id
ground_truth
entities
transactions
expected_signals
```

---

# 13. Phase 6 — High-Throughput Transaction Publisher

Create:

```text
pubsub_load_generator.py
```

Example:

```bash
python pubsub_load_generator.py --rate 5000 --duration 300
```

Support:

```text
--rate
--duration
--project
--topic
--batch-size
--scenario-mix
--seed
```

Use asynchronous/batched publishing.

Do not implement one blocking network call per transaction.

## Required benchmark profiles

```text
100 TPS
500 TPS
2,000 TPS
5,000 TPS
10,000 TPS stress test
```

The actual achieved throughput must be measured.

---

# 14. Phase 7 — Pub/Sub Ingestion

Use a transaction topic:

```text
corridor-transactions
```

Create a lightweight ingestion path.

Responsibilities:

1. authenticate/validate incoming Pub/Sub request;
2. decode message;
3. validate schema;
4. deduplicate;
5. persist;
6. compute cheap features;
7. assign risk tier;
8. publish suspicious events;
9. emit metrics;
10. return quickly.

Do not call Gemini here.

Do not perform large graph traversals here.

---

# 15. Phase 8 — Investigation Queue

Create:

```text
corridor-investigations
```

Flow:

```text
corridor-transactions
       ↓
fast screening
       ↓
suspicious
       ↓
corridor-investigations
```

This separates high-volume ingestion from slower investigation work.

---

# 16. Phase 9 — Risk Tiers

Implement configurable tiers.

```text
LOW
  deterministic processing only

MEDIUM
  graph enrichment

HIGH
  graph + Gemini

CRITICAL
  graph + Gemini + human escalation
```

Thresholds must be configurable.

Do not hard-code a claim such as “3% of transactions are suspicious.”

---

# 17. Phase 10 — Graph Intelligence

The graph is a core product feature.

## Nodes

```text
Transaction
Account
Customer
Device
Beneficiary
Bank
Country
```

## Relationships

```text
SENDS
RECEIVES
USES_DEVICE
USES_BENEFICIARY
BELONGS_TO_BANK
LOCATED_IN
CROSSES
```

## Features

Implement/test:

- degree;
- fan-in;
- fan-out;
- transaction velocity;
- burstiness;
- shared-device count;
- shared-beneficiary count;
- hop count;
- path length;
- cross-border transitions;
- account age;
- time-to-forward;
- network size;
- suspicious-neighbor count.

## Investigation bounds

Never rebuild the entire universe for every event.

Use configurable:

```text
max hops
lookback window
lookahead window
max nodes
max edges
```

Example starting point:

```text
3 hops
24-hour lookback
2-hour lookahead
bounded network size
```

Benchmark and tune these values.

---

# 18. Phase 11 — Corridor Intelligence

A corridor is a first-class investigation concept.

Example:

```text
JP → SG
```

The system should calculate corridor-level context such as:

- transaction volume;
- suspicious transaction volume;
- suspicious network count;
- unique accounts;
- velocity;
- cross-border transitions;
- pattern matches;
- risk trend.

The UI should allow investigators to move from:

```text
country pair
    ↓
corridor
    ↓
network
    ↓
case
    ↓
transaction
```

---

# 19. Phase 12 — Crime Pattern DNA

This is a signature feature and must be implemented as a reusable intelligence system.

## Concept

A confirmed investigation produces a structured pattern fingerprint.

Example:

```json
{
  "pattern_id": "CW-017",
  "name": "rapid_mule_fanout",
  "entry_signals": ["new_account", "incoming_spike"],
  "movement_signals": ["rapid_fanout"],
  "relationship_signals": ["shared_device"],
  "geography_signals": ["cross_border"],
  "timing_signals": ["short_hold_period"],
  "exit_signals": ["shared_beneficiary"]
}
```

The exact schema can evolve.

## Lifecycle

```text
Investigation
     ↓
Analyst confirmation
     ↓
Pattern extraction
     ↓
Crime Pattern DNA
     ↓
Pattern library
     ↓
Future matching
     ↓
New investigation
```

## Matching

Match future networks using:

- graph structure;
- temporal behavior;
- relationship signals;
- corridor signals;
- transaction velocity;
- account/device/beneficiary patterns.

Every match must show evidence.

---

# 20. Phase 13 — Gemini Investigation Copilot

This is the most important GenAI component.

## Gemini's role

Gemini is:

> **an evidence-grounded financial-crime investigation copilot.**

It is NOT:

> an autonomous transaction decision engine.

## Input evidence

Provide structured evidence:

```text
transaction summary
account history
network nodes
network edges
graph features
risk signals
corridor context
Crime Pattern DNA matches
prior confirmed patterns
relevant internal policy/rules
```

## Required output

Use a strict Pydantic response model containing:

```text
investigation_summary
risk_hypothesis
supporting_evidence[]
contradicting_evidence[]
matched_patterns[]
alternative_explanations[]
recommended_next_checks[]
recommended_disposition
confidence
```

Include evidence IDs where practical.

---

# 21. Gemini Reasoning Workflow

Implement logically separated stages:

## Stage A — Evidence synthesis

Summarize supplied evidence.

## Stage B — Network reasoning

Explain relationships and flows.

## Stage C — Pattern matching

Compare against Crime Pattern DNA.

## Stage D — Hypothesis

Produce a primary hypothesis.

## Stage E — Counter-hypothesis

Provide plausible legitimate/alternative explanations.

## Stage F — Evidence challenge

Explain what additional evidence would strengthen or disprove the hypothesis.

## Stage G — Investigation plan

Recommend concrete next checks.

## Stage H — Analyst narrative

Produce concise investigator-facing output.

---

# 22. Gemini Grounding Rules

System prompt must require:

1. Use only supplied evidence.
2. Never invent IDs.
3. Never invent transactions.
4. Never invent accounts.
5. Never invent countries.
6. Distinguish evidence from inference.
7. State uncertainty.
8. Provide alternative explanations where appropriate.
9. Never claim an action has occurred unless evidence says so.
10. Never make final high-risk decisions.
11. Never invent regulatory requirements.
12. Return valid structured output.

If evidence is insufficient, Gemini should explicitly say so.

---

# 23. Evidence Model

Create a common evidence representation.

Example:

```json
{
  "evidence_id": "E-102",
  "type": "shared_device",
  "description": "Accounts A12 and B84 used device D8831",
  "source": "graph_feature",
  "source_ref": "device:D8831",
  "confidence": 1.0
}
```

The AI output should reference evidence IDs where possible.

This creates explainability and makes hallucination easier to detect.

---

# 24. Human-in-the-Loop RBAC

Preserve and strengthen:

```text
analyst
fiu_lead
mrm_auditor
```

## Analyst

Can:

- review cases;
- clear cases;
- add notes;
- request additional investigation;
- perform permitted ordinary decisions.

## FIU Lead

Can:

- approve high-risk dispositions;
- escalate cases;
- authorize sensitive actions.

## MRM Auditor

Can:

- inspect model outputs;
- inspect decision history;
- inspect pattern versions;
- inspect evidence;
- inspect audit history.

Gemini must never bypass these permissions.

---

# 25. Audit Trail

For every material action record:

```text
timestamp
actor
role
case_id
transaction_id
action
decision
evidence references
model version
pattern version
notes
```

Critical decision events belong in the database.

High-volume operational logs belong in structured application/cloud logging.

---

# 26. Governance Architecture

Target Google Cloud governance/security layer:

```text
Knowledge Catalog
Sensitive Data Protection
IAM
Cloud Audit Logs
Secret Manager
Cloud KMS
VPC Service Controls
Security Command Center
Cloud Monitoring
```

Govern:

```text
data classification
PII status
business domain
owner
retention
purpose
lineage
access policy
```

The governance catalog should describe datasets, schemas, fields and pipelines.

Do not create a governance catalog entry for every individual transaction.

---

# 27. Observability

Expose application metrics:

```text
transactions_received_total
transactions_processed_total
transactions_failed_total
transactions_duplicate_total

ingestion_latency_p50
ingestion_latency_p95
ingestion_latency_p99

suspicious_transactions_total
investigations_started_total
investigations_completed_total

gemini_requests_total
gemini_failures_total
gemini_latency_p50
gemini_latency_p95

pattern_matches_total
analyst_decisions_total
false_positive_total
confirmed_positive_total
```

Also monitor:

```text
Pub/Sub backlog
Cloud Run instances
DB latency
DB connection utilization
```

---

# 28. Evaluation Framework

Create a reproducible evaluator:

```bash
python evaluate.py   --rate 5000   --duration 300   --scenario-mix default
```

Produce:

```text
throughput
latency
error rate
duplicate rate
precision
recall
false-positive rate
investigation latency
pattern-match performance
AI groundedness results
```

All results must be derived from actual runs.

---

# 29. Baseline Comparison

Build two evaluation modes.

## Baseline

```text
transaction-level deterministic rules
```

## Corridor Watch

```text
rules
+
graph
+
Crime Pattern DNA
+
Gemini investigator
```

Compare:

- alerts;
- false positives;
- network detections;
- investigation cases;
- investigation time;
- evidence completeness;
- analyst workload.

Do not invent improvements.

---

# 30. Investigation Compression

Measure the change in unit of analyst work.

Ideal demonstration:

```text
40 related transaction events
        ↓
1 suspicious network
        ↓
1 coherent investigation
```

The exact number is test-dependent.

The product objective is:

> reduce fragmented alert review while retaining suspicious network coverage.

---

# 31. Multi-Institution Intelligence Simulation

Simulate:

```text
Bank A
Bank B
Bank C
Payment Provider
```

The synthetic environment should demonstrate that suspicious relationships may span institutions.

Do not imply that raw customer data should automatically be centralized.

---

# 32. Privacy-Aware Intelligence Concept

Explore an architecture where institutions exchange intelligence signals rather than raw histories.

Potential shared artifacts:

```text
risk indicators
entity fingerprints
pattern IDs
device relationship signals
beneficiary risk signals
corridor risk signals
case references
```

Prototype with synthetic institution namespaces.

Future research can investigate:

- pseudonymization;
- controlled entity resolution;
- federated analytics;
- privacy-preserving matching;
- governed intelligence exchange.

Do not claim that hashing alone provides privacy.

---

# 33. Frontend

Build four primary screens.

## 33.1 Command Center

Show:

```text
live TPS
active investigations
high-risk cases
suspicious networks
active corridors
Pub/Sub backlog
Cloud Run scaling
```

## 33.2 Corridor Explorer

Show:

```text
origin
destination
volume
risk
network count
patterns
time window
graph
```

## 33.3 Investigation Workspace

Show:

```text
case summary
risk
network graph
timeline
evidence
pattern matches
Gemini investigation
alternative explanations
next checks
decision controls
audit history
```

## 33.4 Crime Pattern Library

Show:

```text
pattern ID
name
version
signals
matches
confirmed cases
status
```

---

# 34. UX Principle

An investigator must be able to answer:

1. What happened?
2. Why is it suspicious?
3. What network is involved?
4. What evidence supports the AI hypothesis?
5. What should I do next?
6. What am I authorized to do?

Avoid decorative charts that do not support investigation.

---

# 35. Cloud Architecture

Target:

```text
Artifact Registry
       |
       v
Cloud Run
       |
       +--- Pub/Sub
       |
       +--- Cloud SQL PostgreSQL
       |
       +--- Secret Manager
       |
       +--- Gemini / Vertex AI
       |
       +--- Cloud Logging
       |
       +--- Cloud Monitoring
```

Use same-region deployment for latency/cost considerations.

Tune Cloud Run based on actual benchmark results.

Start with reasonable benchmark candidates for:

```text
CPU
memory
concurrency
min instances
max instances
```

Do not assume a configuration is optimal without measurement.

---

# 36. Database Performance

Evaluate indexes including:

```text
transactions(txn_id)
transactions(ts)
transactions(sender_account_id, ts)
transactions(receiver_account_id, ts)
transactions(device_id, ts)
transactions(beneficiary_id, ts)

accounts(account_id)
accounts(bank_id)

investigations(case_id)
investigations(status)

audit_log(transaction_id)
audit_log(actor)
audit_log(timestamp)
```

Use actual query plans to refine indexes.

---

# 37. Production Docker

Do not generate the production database during image build.

Remove production dependence on:

```text
python data_gen.py
python graph_features.py
```

from the Docker build process.

Production image should primarily:

1. install dependencies;
2. copy application;
3. start service.

Database migrations and synthetic workload generation are separate operations.

---

# 38. Configuration

Use environment variables for:

```text
ENVIRONMENT
DATABASE_URL
GOOGLE_CLOUD_PROJECT
REGION

TRANSACTION_TOPIC
INVESTIGATION_TOPIC

GEMINI_MODEL

RISK_THRESHOLD_LOW
RISK_THRESHOLD_MEDIUM
RISK_THRESHOLD_HIGH

GRAPH_MAX_HOPS
GRAPH_LOOKBACK_MINUTES
GRAPH_LOOKAHEAD_MINUTES
MAX_INVESTIGATION_SIZE
```

Never commit credentials.

Use Secret Manager in GCP.

---

# 39. Failure Handling

Test:

- duplicate Pub/Sub delivery;
- malformed message;
- DB outage;
- Gemini outage;
- Pub/Sub failure;
- investigation timeout;
- oversized graph;
- worker restart;
- retry;
- analyst retry.

If Gemini fails:

```text
ingestion continues
risk screening continues
case can remain pending AI investigation
```

Do not make the transaction pipeline synchronously dependent on Gemini.

---

# 40. Security

Implement:

- authenticated Pub/Sub push;
- least-privilege service accounts;
- Secret Manager;
- no credentials in Git;
- RBAC;
- input validation;
- request limits;
- safe errors;
- dependency pinning;
- synthetic-only financial data.

---

# 41. Suggested Target Repository Structure

```text
corridor-watch/
│
├── main.py
├── config.py
├── auth.py
├── audit.py
├── agent.py
│
├── db/
│   ├── __init__.py
│   ├── base.py
│   ├── sqlite.py
│   ├── postgres.py
│   └── repositories/
│
├── risk/
│   ├── rules.py
│   ├── features.py
│   └── tiers.py
│
├── graph/
│   ├── builder.py
│   ├── features.py
│   └── investigator.py
│
├── patterns/
│   ├── schema.py
│   ├── matcher.py
│   ├── extractor.py
│   └── repository.py
│
├── investigations/
│   ├── service.py
│   ├── schemas.py
│   └── worker.py
│
├── pubsub/
│   ├── publisher.py
│   ├── ingestion.py
│   └── schemas.py
│
├── synthetic/
│   ├── world.py
│   ├── banks.py
│   ├── fraud_patterns.py
│   ├── transaction_generator.py
│   └── publisher.py
│
├── evaluation/
│   ├── evaluate.py
│   ├── metrics.py
│   └── reports.py
│
├── tests/
│
├── static/
│
├── migrations/
│
├── Dockerfile
├── requirements.txt
└── README.md
```

Refactor incrementally. Do not move everything in one destructive rewrite.

---

# 42. Implementation Sequence

## Sprint 1 — Stabilize

- [ ] baseline repository;
- [ ] tests;
- [ ] preserve UI;
- [ ] preserve RBAC;
- [ ] document APIs.

## Sprint 2 — Data

- [ ] DB abstraction;
- [ ] PostgreSQL;
- [ ] migrations;
- [ ] idempotency;
- [ ] indexes.

## Sprint 3 — Streaming

- [ ] Pub/Sub schemas;
- [ ] transaction topic;
- [ ] ingestion;
- [ ] deduplication;
- [ ] investigation topic.

## Sprint 4 — Synthetic Scale

- [ ] multi-bank world;
- [ ] correlated fraud;
- [ ] load generator;
- [ ] benchmark profiles.

## Sprint 5 — Graph

- [ ] bounded traversal;
- [ ] network features;
- [ ] corridor intelligence;
- [ ] network risk.

## Sprint 6 — Crime Pattern DNA

- [ ] schema;
- [ ] extraction;
- [ ] library;
- [ ] matching;
- [ ] feedback.

## Sprint 7 — Gemini

- [ ] evidence package;
- [ ] structured output;
- [ ] grounding;
- [ ] hypotheses;
- [ ] alternatives;
- [ ] next checks;
- [ ] model/pattern version tracking.

## Sprint 8 — UX

- [ ] command center;
- [ ] corridor explorer;
- [ ] investigation workspace;
- [ ] pattern library;
- [ ] RBAC controls.

## Sprint 9 — Governance/Security

- [ ] IAM;
- [ ] Secret Manager;
- [ ] audit;
- [ ] logging;
- [ ] governance metadata;
- [ ] security hardening.

## Sprint 10 — Evaluation/Demo

- [ ] load benchmark;
- [ ] baseline comparison;
- [ ] detection metrics;
- [ ] AI groundedness tests;
- [ ] polished demo;
- [ ] README;
- [ ] architecture diagram;
- [ ] judging narrative.

---

# 43. Immediate Next Action List

A coding agent should start with these tasks in order.

### Task 1 — Repository audit

Inspect current repository and write a short internal implementation map.

### Task 2 — Tests

Create baseline tests for existing behavior.

### Task 3 — DB abstraction

Decouple application logic from SQLite.

### Task 4 — PostgreSQL

Add Cloud SQL-compatible persistence and migrations.

### Task 5 — Pub/Sub

Add schemas, publishing and idempotent ingestion.

### Task 6 — Synthetic banking world

Build multi-institution correlated transaction generation.

### Task 7 — 5,000 TPS publisher

Build batched/asynchronous benchmark tooling.

### Task 8 — Investigation pipeline

Separate ingestion from investigation.

### Task 9 — Graph intelligence

Implement bounded network investigation.

### Task 10 — Crime Pattern DNA

Implement extraction, storage, matching and feedback.

### Task 11 — Gemini investigator

Replace generic AI behavior with evidence-grounded structured investigation.

### Task 12 — Investigator UI

Build command center, corridor, graph, evidence and case workflow.

### Task 13 — Governance/security

Add production-oriented controls.

### Task 14 — Benchmark

Measure 100 / 500 / 2,000 / 5,000 / 10,000 TPS.

### Task 15 — Final demo

Only after stability and measurements are complete.

---

# 44. Definition of Done

The project is considered hackathon-ready when a judge can watch this flow end-to-end:

```text
5,000 TPS synthetic stream
        ↓
suspicious activity emerges
        ↓
network automatically reconstructed
        ↓
cross-institution relationships revealed
        ↓
Crime Pattern DNA matched
        ↓
Gemini investigates supplied evidence
        ↓
AI states hypothesis + uncertainty
        ↓
AI proposes next investigative checks
        ↓
analyst reviews evidence
        ↓
RBAC controls available actions
        ↓
human decision
        ↓
audit record
        ↓
confirmed case becomes reusable intelligence
```

---

# 45. Final Demonstration Scenario

The final demo should use one carefully engineered campaign.

## Scene 1 — Normal traffic

Start the synthetic stream.

Show live:

```text
~5,000 TPS
```

Only use the measured achieved rate in the final presentation.

## Scene 2 — Crime campaign begins

Inject:

```text
new mule account
+
shared device
+
fan-out
+
rapid movement
+
cross-border transfer
+
shared beneficiary
```

## Scene 3 — Fast detection

Show that the system detects suspicious behavior without sending all transactions to Gemini.

## Scene 4 — Network discovery

Open the network and show:

```text
accounts
devices
beneficiaries
banks
countries
transactions
```

## Scene 5 — Crime Pattern DNA

Show a matching known pattern.

## Scene 6 — Gemini investigation

Show:

- evidence;
- hypothesis;
- alternative explanation;
- confidence;
- next investigative checks.

## Scene 7 — Human decision

Demonstrate role-aware actions.

## Scene 8 — Audit

Show:

```text
who
what
when
role
evidence
model version
pattern version
```

## Scene 9 — Intelligence feedback

Show:

```text
confirmed case
     ↓
Crime Pattern DNA
     ↓
future network
     ↓
pattern match
```

Final message:

> **The investigation did not just resolve one alert. It created intelligence that can help detect the next network.**

---

# 46. Metrics That Matter

The north-star metric is not raw TPS.

Measure:

```text
throughput
+
detection recall
+
false-positive rate
+
investigation compression
+
investigator time
+
AI groundedness
```

The desired product story is:

> **More transaction coverage, fewer fragmented alerts, better evidence, faster investigations.**

---

# 47. Final Positioning

Use this as the canonical product description:

> **Corridor Watch is a cloud-native financial-crime intelligence platform that detects suspicious transaction networks across accounts, institutions and cross-border corridors, converts confirmed investigations into reusable Crime Pattern DNA, and uses Gemini as an evidence-grounded investigation copilot while keeping consequential decisions human-authorized and auditable.**

Short pitch:

> **The transaction is not the crime. The network is.**

---

# 48. Coding Agent Rules

Any coding agent receiving this document must:

1. Inspect the repository before modifying it.
2. Preserve existing functionality unless explicitly superseded.
3. Make incremental changes.
4. Add/update tests for every major feature.
5. Never fabricate benchmark results.
6. Never use real financial/customer data.
7. Keep Gemini out of the synchronous high-throughput ingestion path.
8. Keep high-risk decisions human-authorized.
9. Keep AI outputs evidence-grounded.
10. Keep local development possible.
11. Prefer clear interfaces between ingestion, risk, graph, patterns, investigation and persistence.
12. Document architectural changes.
13. Update README/setup instructions after infrastructure changes.
14. Use environment variables for deployment configuration.
15. Never commit secrets.
16. Do not replace working components merely for stylistic reasons.
17. Prioritize the judging rubric when choosing between implementation alternatives.
18. If a requested feature conflicts with safety, authorization, auditability or evidence-grounding, preserve those controls.

---

# 49. Priority Matrix

## P0 — Must Have

- PostgreSQL support
- Pub/Sub ingestion
- idempotency
- 5,000 TPS benchmark
- multi-bank synthetic world
- graph investigation
- Crime Pattern DNA
- evidence-grounded Gemini investigator
- human/RBAC decisions
- audit trail
- polished investigation UI

## P1 — Strongly Recommended

- corridor analytics
- investigation compression metrics
- baseline comparison
- Cloud Monitoring metrics
- governance metadata
- failure handling
- 10,000 TPS stress test
- reusable pattern feedback

## P2 — If Time Allows

- privacy-aware signal exchange prototype
- advanced entity resolution
- federated analytics simulation
- richer pattern similarity
- model evaluation dashboard
- cost-per-investigation analytics

## P3 — Do Not Prioritize Before Core Completion

- cosmetic dashboard features
- additional generic chat features
- unnecessary ML models
- complex infrastructure unrelated to the demo
- decorative visualizations

---

# 50. Strategic End State

The highest-potential version of Corridor Watch should not claim to replace enterprise AML platforms.

It should demonstrate a new operational layer:

```text
Existing AML / rules / models
             ↓
      Corridor Watch
             ↓
  network intelligence
             ↓
    Crime Pattern DNA
             ↓
     Gemini investigator
             ↓
       human analyst
             ↓
       audit / feedback
```

The strategic differentiation is:

> **Existing systems can score an event. Corridor Watch explains the network around the event, identifies reusable crime patterns, and turns fragmented signals into an evidence-backed investigation.**

That is the target architecture, product story and implementation direction.
