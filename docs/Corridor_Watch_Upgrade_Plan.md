# Corridor Watch — Cross-Institution / Partial-Visibility Upgrade Plan

## Objective

Extend Corridor Watch from a bank-centric AML investigation system into a
cross-institution-aware financial-crime network intelligence platform.

### Core problem

A bank may observe only one layer of a laundering chain.

Corridor Watch must therefore distinguish between:

- **Observed** — directly visible from the bank's own data
- **External** — supplied by an authorized external intelligence source
- **Inferred** — hypothesized from available evidence
- **Unknown** — a network area that may exist but cannot currently be observed or verified

### Critical rule

Never claim that Corridor Watch sees the entire laundering chain.

Preferred product claim:

> "Corridor Watch understands the visible network, identifies institutional
> boundaries, quantifies what remains unknown, and progressively reconstructs
> the broader laundering topology as trusted intelligence becomes available."

---

# 1. Product Positioning

Keep the primary product positioned as a **bank / financial-institution AML
investigation and network-intelligence platform**.

Evolution:

```text
Bank-level network intelligence
        ↓
Cross-institution intelligence
        ↓
Federated financial-crime intelligence layer
````

Do not turn the current product into a regulator-only product.

The core thesis remains:

> **The transaction is not the crime. The network is.**

---

# 2. First-Class Network Visibility

Every investigation and graph must distinguish four visibility states.

## OBSERVED

Directly visible in the bank's own transaction, account, device, KYC,
session, or related system data.

## EXTERNAL

Supplied by an authorized external intelligence source or institution.

## INFERRED

A relationship or entity hypothesized from observed evidence.

## UNKNOWN

A network area that may exist but cannot currently be observed or verified.

### Critical requirement

Never represent inferred or unknown information as fact.

---

# 3. Extend the Graph Entity Model

Support these entity types:

```text
PERSON
ACCOUNT
INSTITUTION
DEVICE
BENEFICIARY
SESSION
COUNTRY
CORRIDOR
PAYMENT_RAIL
UNKNOWN_ENTITY
```

## Institution subtypes

```text
INTERNAL_INSTITUTION
EXTERNAL_INSTITUTION
CORRESPONDENT_INSTITUTION
```

## Account subtypes

```text
INTERNAL_ACCOUNT
EXTERNAL_ACCOUNT
UNKNOWN_ACCOUNT
```

Add fields where appropriate:

```text
entity_id
entity_type
institution_id
country
visibility
confidence
source
created_at
updated_at
```

Allowed visibility values:

```text
observed
external
inferred
unknown
```

Do not break existing entity representations.

Add fields compatibly.

---

# 4. Extend the Graph Edge Model

Edges should support:

```text
edge_id
source_node
target_node
relationship_type
timestamp
amount
currency
visibility
confidence
source
evidence_ids
```

Relationship types should include:

```text
TRANSFER
OWNS
CONTROLS
USES_DEVICE
USES_BENEFICIARY
SHARES_DEVICE
SHARES_BENEFICIARY
SAME_SESSION
BELONGS_TO_INSTITUTION
CROSSES_CORRIDOR
POSSIBLE_LINK
```

Observed and inferred edges must remain visually and semantically distinct.

An inferred relationship must never look identical to an observed transaction.

---

# 5. Network Visibility Score

Introduce:

```text
network_visibility_score
```

Range:

```text
0.0 - 1.0
```

This is **NOT** a probability of guilt.

It should reflect some combination of:

* observed node coverage
* observed edge coverage
* unresolved boundary nodes
* external intelligence coverage
* inferred edge confidence

Example UI:

```text
NETWORK VISIBILITY: 63%

Observed:              14
External:               7
Inferred:               4
Unknown boundary:       3
```

Clearly label this as a **visibility indicator**, not a confidence score or
guilt probability.

Keep these concepts separate:

```text
risk_score
network_visibility_score
```

Do not automatically lower risk because visibility is incomplete.

---

# 6. Institutional Boundary Nodes

Do not simply stop graph expansion when the transaction leaves the bank.

Represent the external institution/account as a boundary node.

Example:

```text
Bank A
   |
   v
External Account
   |
   v
YOUR BANK
   |
   v
External Account
   |
   v
Bank C
```

The graph should explicitly communicate:

```text
OBSERVED
EXTERNAL
INFERRED
UNKNOWN
```

If the chain cannot be verified beyond a boundary, create an UNKNOWN or
UNRESOLVED boundary representation rather than inventing downstream entities.

---

# 7. Institution-Level Graph Intelligence

Add institution-level aggregation.

For each institution, support metrics such as:

* suspicious transaction count
* suspicious transaction amount
* connected accounts
* suspicious networks
* corridor frequency
* average pass-through behavior
* recurring topology
* Pattern DNA matches
* observed vs inferred relationships
* external intelligence signals

Use neutral AML language.

### Good

```text
Recurring intermediary relationship
Elevated network exposure
Repeated suspicious topology
Repeated high-velocity pass-through pattern
```

### Avoid

```text
Bank X is laundering money
Bank X is criminal
Bank X is part of the laundering operation
```

A network signal involving another institution is not proof of institutional
criminality.

---

# 8. Partial-Network Investigation Flow

Change the investigation architecture to:

```text
Flagged Transaction
        |
        v
Internal Evidence
        |
        v
External Boundary Mapping
        |
        v
Graph Expansion
        |
        v
Visibility Assessment
        |
        v
Pattern DNA Matching
        |
        v
Risk Assessment
        |
        v
Gemini Investigation Copilot
        |
        v
Human Decision
```

The system must work even when there is **zero external intelligence**.

---

# 9. Synthetic "We Are the Middle Bank" Demo Scenario

Build a synthetic scenario where Corridor Watch is the middle bank.

Example:

```text
Bank A
   |
   v
Feeder Accounts
   |
   v
Mule Account
   |
   v
YOUR BANK
   |
   v
Bank C
   |
   v
Bank D
   |
   v
Final Off-Ramp
```

Initially expose only:

```text
Bank A -> YOUR BANK -> Bank C
```

The system should detect suspicious behavior such as:

* rapid pass-through
* account depletion
* fan-in / fan-out
* newly opened account
* cross-border transfer
* unusual corridor
* beneficiary behavior
* shared device
* transaction velocity

The UI should explicitly communicate:

```text
PARTIAL NETWORK OBSERVED
```

Example:

```text
Upstream:             PARTIAL
Internal:             FULL
Downstream:           PARTIAL
Unresolved boundaries: 3
```

The system should not pretend to know Bank D or the final off-ramp unless
synthetic intelligence later reveals them.

---

# 10. Synthetic External Intelligence

Create a local synthetic intelligence adapter/provider.

Simulate institutions such as:

```text
BANK_A
BANK_B
BANK_C
BANK_D
BANK_E
```

Use synthetic identifiers only.

Example signal:

```json
{
  "intelligence_id": "INT-00421",
  "source_institution": "BANK-C",
  "entity_type": "ACCOUNT",
  "entity_reference": "EXT-88321",
  "signal_type": "confirmed_mule",
  "confidence": 0.91,
  "pattern_id": "CW-DNA-0042",
  "timestamp": "..."
}
```

Do not use real customer information.

Create a clean provider interface so the synthetic provider can later be
replaced by an authorized real intelligence source.

---

# 11. Privacy-Preserving Intelligence Abstraction

Do not design the POC around unrestricted raw transaction sharing.

Support intelligence-sharing abstractions such as:

```text
LOCAL_ONLY
SHARED_SIGNAL
SHARED_PATTERN
SHARED_ENTITY_RISK
```

Prefer sharing:

* pattern IDs
* risk signals
* synthetic/hashed references
* institution metadata
* corridor signals
* typology
* confidence
* authorized evidence references

The architecture should make it possible to add stronger privacy controls later.

Do not implement production-grade cryptographic or federated-learning
machinery for the hackathon unless explicitly required.

---

# 12. Cross-Institution Crime Pattern DNA

Extend Pattern DNA with:

```text
INSTITUTIONAL_SCOPE
```

Allowed values:

```text
LOCAL
CROSS_INSTITUTION
```

Example cross-institution pattern:

```text
feeder -> mule -> intermediary -> exit
```

Signals:

```text
account age < 30 days
pass-through > 90%
hold time < 60 minutes
multiple feeders
cross-border exit
repeated beneficiary behavior
```

Pattern matching must support **partial topology**.

Return:

```text
pattern_match_score
visibility
evidence_coverage
matched_signals
missing_expected_signals
```

Do not equate pattern-match score with certainty of criminal activity.

---

# 13. Gemini Investigation Changes

Gemini must receive explicit visibility-aware context.

Prompt structure should separate:

```text
OBSERVED FACTS
EXTERNAL INTELLIGENCE
INFERENCES
UNKNOWN / UNRESOLVED AREAS
```

Required Gemini response structure:

```text
1. Primary hypothesis
2. Observed evidence
3. External intelligence
4. Inference
5. Alternative legitimate explanation
6. Unknown / unresolved areas
7. Recommended next checks
8. Confidence
```

Gemini must NEVER:

* convert an inference into an observed fact
* invent missing downstream institutions
* invent missing accounts
* claim complete network visibility
* fabricate external intelligence

Gemini should explicitly state when the available network is incomplete.

Keep Gemini off the high-throughput transaction-ingestion hot path.

---

# 14. Evidence IDs

Every important claim should reference evidence.

Examples:

Observed evidence:

```text
E-102
E-103
E-104
```

External intelligence:

```text
EXT-22
```

Unresolved boundary:

```text
BOUNDARY-03
```

Gemini should be able to cite these IDs in its investigation output.

No unsupported narrative should be presented as evidence.

---

# 15. Risk vs Visibility

Keep these as separate concepts.

Example:

```text
Risk Score:             91 / 100
Network Visibility:    54%
```

Interpretation:

> "The observed activity is highly suspicious, but only 54% of the relevant
> network is currently visible."

Do NOT interpret:

```text
Visibility = 54%
```

as:

```text
Confidence of guilt = 54%
```

Do not suppress suspicious cases simply because the network is incomplete.

---

# 16. API Additions

Preserve all existing APIs.

Add, where consistent with the existing FastAPI architecture:

```text
GET  /api/investigations/{id}/visibility
GET  /api/investigations/{id}/network
GET  /api/investigations/{id}/boundaries

GET  /api/institutions
GET  /api/institutions/{id}/network

GET  /api/intelligence
POST /api/intelligence/signal

GET  /api/patterns/{id}/matches

POST /api/intelligence/simulate
```

Use the existing authentication/RBAC/audit architecture.

External intelligence access must not bypass authorization.

---

# 17. UI Additions

## Investigation page

Add:

* network visibility bar
* observed/external/inferred/unknown counts
* graph legend
* institutional boundary panel
* evidence IDs
* unresolved areas
* external intelligence signals

## Graph

Add:

* clear visual distinction between observed/external/inferred/unknown
* institution boundaries
* bounded graph expansion
* unknown boundary markers

Never imply unknown nodes are known.

## Corridor Explorer

Add:

* institutions
* suspicious networks
* recurring topology
* cross-institution Pattern DNA
* visibility coverage

## Command Center

Add:

* network visibility
* external boundary nodes
* cross-institution pattern matches
* shared intelligence signals
* institution count
* partial-network investigations

Never make another institution appear criminal solely because it occurs in a
suspicious graph.

---

# 18. Synthetic Multi-Bank World

Create a synthetic multi-bank environment:

```text
BANK_A
BANK_B
BANK_C
BANK_D
BANK_E
```

Generate:

* internal transactions
* interbank transactions
* cross-border transactions
* external accounts
* correspondent relationships
* synthetic intelligence signals

Support these scenarios:

### Scenario 1 — Complete visibility

The investigation has enough data to reconstruct the relevant topology.

### Scenario 2 — Middle-bank partial visibility

Corridor Watch sees the middle of the laundering chain but not both ends.

### Scenario 3 — Upstream partial visibility

The originator side is incomplete.

### Scenario 4 — Downstream partial visibility

The destination side is incomplete.

### Scenario 5 — Multiple banks see different pieces

Each institution has a different partial graph.

### Scenario 6 — External intelligence resolves an unknown

A previously unknown boundary becomes an external observed intelligence node.

The same investigation engine should work across all scenarios.

---

# 19. Tests

## Visibility

Add tests:

```text
test_observed_nodes
test_external_nodes
test_inferred_nodes
test_unknown_boundaries
test_visibility_score
```

## Graph

Add tests:

```text
test_external_boundary_edge
test_partial_network
test_inferred_edge_is_labeled
test_cross_institution_graph
```

## Intelligence

Add tests:

```text
test_external_signal_ingestion
test_external_signal_updates_pattern
test_external_signal_updates_investigation
```

## Gemini

Add tests:

```text
test_prompt_contains_visibility
test_unknown_not_presented_as_fact
test_evidence_ids_required
```

## Security

Add tests:

```text
test_unauthorized_intelligence_access
test_institution_data_isolation
test_shared_signal_does_not_expose_raw_customer_data
```

## Regression

All existing tests must continue to pass.

---

# 20. Do Not Build Yet

Do NOT add these as real integrations in the hackathon POC:

* real bank-to-bank transaction exchange
* SWIFT integration
* real FIU integration
* unrestricted customer identity sharing
* blockchain intelligence exchange
* complex federated learning
* production-grade privacy cryptography
* real law-enforcement feeds

Instead, create clean interfaces/adapters and synthetic providers.

The architecture should make these integrations possible later without
requiring them for the hackathon.

---

# 21. Governance and Audit

Audit these events:

```text
external_intelligence_received
external_intelligence_used
network_visibility_changed
pattern_match_created
inferred_relationship_created
shared_signal_created
shared_signal_accessed
```

Maintain strict separation:

```text
FACT
INTELLIGENCE
INFERENCE
DECISION
```

Consequential actions remain human-authorized.

Existing RBAC must remain intact.

---

# 22. Final Hackathon Demo

Build a compelling end-to-end scenario.

## Step 1

Start a high-volume synthetic transaction stream.

## Step 2

A suspicious inbound transaction appears.

## Step 3

Lightweight risk screening flags it.

## Step 4

The graph expands.

## Step 5

UI shows:

```text
NETWORK VISIBILITY: 51%
```

## Step 6

Cross-institution Pattern DNA matches.

## Step 7

Gemini explains the case using evidence IDs.

## Step 8

External intelligence arrives.

## Step 9

The unknown boundary is resolved.

## Step 10

Visibility changes:

```text
51% -> 84%
```

## Step 11

Risk changes based on new evidence:

```text
78 -> 94
```

## Step 12

An analyst attempts a consequential action.

## Step 13

RBAC blocks the unauthorized action.

## Step 14

FIU Lead reviews the case.

## Step 15

FIU Lead authorizes the decision.

## Step 16

The audit trail records every important event.

## Step 17

The investigation contributes reusable Pattern DNA.

This demonstrates:

* scale
* graph intelligence
* partial visibility
* cross-institution reasoning
* GenAI
* governance
* human authorization
* auditability
* learning from investigations

---

# 23. Implementation Order

## PHASE 1 — DATA MODEL

Implement:

* visibility fields
* institution entities
* external/boundary nodes
* edge provenance
* confidence
* evidence IDs

Do not change existing behavior unnecessarily.

---

## PHASE 2 — GRAPH

Implement:

* partial graph expansion
* institutional boundaries
* institution aggregation
* network visibility calculation

---

## PHASE 3 — INVESTIGATION

Implement:

* visibility-aware investigation
* boundary evidence
* structured evidence pack
* observed/external/inferred/unknown output

---

## PHASE 4 — PATTERN DNA

Implement:

* CROSS_INSTITUTION scope
* partial topology matching
* visibility-aware matching

---

## PHASE 5 — INTELLIGENCE

Implement:

* intelligence schema
* synthetic provider
* intelligence APIs
* intelligence-to-investigation integration
* intelligence-to-DNA integration

---

## PHASE 6 — GEMINI

Implement:

* visibility-aware context
* facts/inferences/unknown separation
* evidence IDs
* alternative legitimate explanation
* no hallucinated entities

---

## PHASE 7 — UI

Implement:

* visibility panel
* graph legend
* boundary visualization
* institution-level corridor view
* intelligence panel
* investigation expansion animation

---

## PHASE 8 — TESTS

Add:

* unit tests
* integration tests
* security tests
* regression tests

---

## PHASE 9 — DEMO

Create the middle-bank scenario and make it deterministic/reproducible.

---

# 24. Definition of Done

```text
[ ] Existing bank-centric flow still works.

[ ] SQLite local development still works.

[ ] PostgreSQL / Cloud SQL path still works.

[ ] Existing ingestion APIs still work.

[ ] Existing Pub/Sub ingestion path still works.

[ ] Gemini remains off the transaction hot path.

[ ] Graph supports observed/external/inferred/unknown.

[ ] External boundary nodes are visible.

[ ] Network visibility score is calculated.

[ ] Risk and visibility are separate.

[ ] Institution-level graph aggregation exists.

[ ] Synthetic multi-bank world exists.

[ ] Synthetic external intelligence provider exists.

[ ] Cross-institution Pattern DNA exists.

[ ] Partial topology matching works.

[ ] Gemini explicitly separates facts, intelligence, inference, and unknowns.

[ ] Gemini uses evidence IDs.

[ ] Gemini does not invent missing network nodes.

[ ] External intelligence access is RBAC-protected.

[ ] All intelligence-related actions are audited.

[ ] Existing RBAC remains intact.

[ ] No raw customer data is exposed through shared synthetic signals.

[ ] New API endpoints are tested.

[ ] New UI components show visibility clearly.

[ ] Existing tests remain green.

[ ] Middle-bank demo is deterministic.

[ ] Throughput benchmarking remains separate from deep investigation work.

[ ] 5,000 TPS is reported only if actually measured.
```

---

# 25. Critical Engineering Rule

## DO NOT BREAK THE EXISTING BANK-CENTRIC IMPLEMENTATION.

Current flow:

```text
Transaction
  -> risk
  -> graph
  -> investigation
  -> Gemini
  -> decision
  -> audit
  -> Pattern DNA
```

Target flow:

```text
Transaction
  -> risk
  -> partial graph
  -> visibility
  -> external intelligence
  -> investigation
  -> Gemini
  -> decision
  -> audit
  -> cross-institution Pattern DNA
```

The target flow MUST also work when:

```text
external_intelligence = none
```

The architecture should degrade gracefully to the existing bank-centric
investigation behavior.

---

# 26. Performance / Cloud Architecture Rule

Do not run full graph expansion and Gemini synchronously for every transaction.

Keep the high-throughput path lightweight:

```text
Transaction
    |
    v
Pub/Sub
    |
    v
Cloud Run ingestion
    |
    +--> validation
    |
    +--> deduplication
    |
    +--> persistence
    |
    +--> lightweight deterministic screening
```

Only suspicious/interesting transactions should enter:

```text
Investigation
    |
    v
Bounded graph expansion
    |
    v
External intelligence enrichment
    |
    v
Pattern DNA
    |
    v
Gemini
```

5,000 TPS should be treated as a synthetic stress/peak-scale target unless
actually measured in the deployed environment.

Always distinguish:

```text
target_tps
```

from:

```text
achieved_tps
```

Only report `achieved_tps` when supported by an actual benchmark.

---

# 27. Recommended Data Model Principle

Every piece of network intelligence should answer four questions:

```text
WHAT is this?
WHO/WHAT supplied it?
HOW confident are we?
CAN we directly observe it?
```

For example:

```text
Entity:
    EXT-88321

Type:
    ACCOUNT

Visibility:
    EXTERNAL

Source:
    BANK-C

Confidence:
    0.91

Evidence:
    EXT-00421

Institution:
    BANK-C
```

This provenance should travel through:

```text
ingestion
    -> graph
    -> investigation
    -> Pattern DNA
    -> Gemini
    -> decision
    -> audit
```

Do not discard provenance during transformations.

---

# 28. Recommended Investigation Object

Where practical, an investigation should be able to expose something conceptually
similar to:

```json
{
  "investigation_id": "INV-10042",
  "risk_score": 91,
  "network_visibility_score": 0.54,

  "observed": {
    "nodes": 14,
    "edges": 21
  },

  "external": {
    "nodes": 4,
    "edges": 6
  },

  "inferred": {
    "nodes": 2,
    "edges": 3
  },

  "unknown": {
    "boundaries": 3
  },

  "evidence_ids": [
    "E-102",
    "E-103",
    "E-104"
  ],

  "external_intelligence_ids": [
    "EXT-22"
  ],

  "pattern_matches": [
    "CW-DNA-0042"
  ]
}
```

Do not require this exact JSON if it conflicts with the current architecture.
The important part is preserving the semantic separation.

---

# 29. Recommended Gemini Context Contract

Before calling Gemini, construct a structured investigation context.

Conceptually:

```json
{
  "case": {
    "id": "INV-10042",
    "risk_score": 91,
    "network_visibility_score": 0.54
  },

  "observed_facts": [
    {
      "evidence_id": "E-102",
      "fact": "Account received funds from 7 distinct senders"
    }
  ],

  "external_intelligence": [
    {
      "intelligence_id": "EXT-22",
      "signal": "External account associated with mule pattern",
      "confidence": 0.91
    }
  ],

  "inferences": [
    {
      "evidence_id": "INF-03",
      "inference": "Possible intermediary account"
    }
  ],

  "unknown_areas": [
    {
      "boundary_id": "BOUNDARY-03",
      "description": "Downstream institution not visible"
    }
  ]
}
```

Gemini should reason over this structure instead of receiving an unstructured
blob of mixed facts.

---

# 30. Recommended Analyst Language

The UI and Gemini should use language appropriate for AML investigation.

Prefer:

```text
Suspicious activity observed
Potential intermediary relationship
Network exposure
Possible pass-through behavior
Partial network visibility
External intelligence indicates
Evidence suggests
Unable to verify downstream activity
Requires additional investigation
```

Avoid unsupported definitive language such as:

```text
This is definitely laundering
Bank X is criminal
This account is certainly a mule
The entire network has been identified
```

The system is an investigation intelligence platform, not a criminal verdict
engine.

---

# 31. Future Architecture Boundary

The hackathon implementation should establish interfaces for future expansion.

Conceptually:

```text
                    Corridor Watch
                          |
        +-----------------+------------------+
        |                 |                  |
        v                 v                  v
 Local Bank Data    External Signals    Pattern DNA
        |                 |                  |
        +-----------------+------------------+
                          |
                          v
                 Network Intelligence
                          |
                          v
                  Gemini Copilot
                          |
                          v
                  Human Decision
                          |
                          v
                       Audit
```

Future external providers can eventually implement the same intelligence
interface.

Do not hard-code the product around a single fictional bank-to-bank protocol.

---

# 32. Final Product Thesis

> **The transaction is not the crime. The network is.**
>
> But no single bank sees the whole network.
>
> Corridor Watch makes that uncertainty explicit, investigates the network a
> bank can observe, incorporates trusted external intelligence when available,
> and uses evidence-grounded AI to connect the pieces without pretending
> unknown information is fact.

## Final positioning sentence

> **Corridor Watch is a cloud-native financial-crime intelligence platform
> that detects suspicious transaction networks, makes partial network
> visibility explicit, incorporates trusted cross-institution intelligence,
> converts confirmed investigations into reusable Crime Pattern DNA, and uses
> Gemini as an evidence-grounded investigation copilot while keeping
> consequential decisions human-authorized and auditable.**

# END OF PLAN

```
```
