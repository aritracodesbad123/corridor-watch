# Corridor Watch --- Exact 5 Things to Fix Next

> **Historical sprint notes. Not canonical.** Measured numbers: [`reports/SCORECARD.md`](../reports/SCORECARD.md). Do not quote older Gemini agreement / p95 figures from this file. Live measured: agreement **1.0, n=100**, p95 **4.025s**, cost/case **$0.00143**.


**Date:** 2026-09-14\
**Purpose:** Focus the next engineering sprint exclusively on the five
changes most likely to improve Corridor Watch's competition score and
technical defensibility.

## The exact five fixes

1.  **Fix Distribution B false positives**
2.  **Build a serious hard-negative / legitimate-network benchmark**
3.  **Make network evaluation investigation-useful**
4.  **Finish and prove the real DeepEval evaluation**
5.  **Measure end-to-end investigation throughput**

Do **not** spend the next sprint adding new product features unless they
are required to solve one of these five problems.

------------------------------------------------------------------------

# 1. FIX DISTRIBUTION B FALSE POSITIVES

## Current problem

The independent Distribution B benchmark currently shows approximately:

``` text
Precision   = 25.93%
Recall      = 100.00%
F1          = 41.18%
FPR         = 100.00%

TP = 28
FP = 80
FN = 0
TN = 0
```

The key failure is:

> Corridor Watch detects all suspicious cases, but also flags every
> legitimate case in the current independent distribution.

This is the most urgent issue.

## Goal

Determine exactly why the independent legitimate cases are being
classified as suspicious, then improve the detector so that it retains
strong recall while substantially reducing false positives.

Do **not** simply tune the threshold until the score looks better.

First understand the cause.

## Required work

### A. Trace every false positive

For each legitimate Distribution B case, record:

-   case ID
-   predicted risk
-   predicted pattern
-   composite score
-   triggered features
-   triggered rules
-   network size
-   fan-in/fan-out
-   pass-through ratio
-   average hold time
-   shared devices
-   shared beneficiaries
-   corridor velocity
-   account age
-   transaction count
-   amount statistics

Create:

``` text
reports/dist_b_false_positive_analysis.json
reports/dist_b_false_positive_analysis.md
```

### B. Identify dominant false-positive features

Produce a ranked feature table and identify feature combinations that
trigger false positives.

### C. Compare distributions

Compare:

``` text
Original fraud
Original normal
Distribution B fraud
Distribution B normal
```

Look for distribution shift.

### D. Perform threshold calibration

Run a threshold sweep and record:

-   precision
-   recall
-   F1
-   FPR

Tune only against a validation split, never the frozen final test set.

### E. Improve generalizable behavior

If legitimate archetypes trigger fraud-like features, prefer general
behavioral evidence over hard-coded exceptions.

Avoid case-specific rules such as:

``` text
if payroll then legitimate
```

unless reliable business-context evidence actually exists.

## Acceptance criteria

-   [ ] Root cause documented.
-   [ ] Every major false-positive class explained.
-   [ ] Threshold tuning isolated to validation data.
-   [ ] Frozen test set remains untouched.
-   [ ] FPR materially improves.
-   [ ] Recall remains above the agreed target.
-   [ ] No leakage introduced.
-   [ ] Original benchmark rechecked.
-   [ ] Baseline and improved results both preserved.

------------------------------------------------------------------------

# 2. BUILD A SERIOUS HARD-NEGATIVE / LEGITIMATE-NETWORK BENCHMARK

## Current problem

Distribution B demonstrates that network structures can look suspicious
even when legitimate.

The next benchmark must deliberately contain legitimate networks that
resemble financial crime.

## Goal

Prove that Corridor Watch can distinguish:

> suspicious network structure

from:

> legitimate network structure that happens to look suspicious.

## Required legitimate archetypes

Create at least:

1.  Payroll
2.  Corporate treasury
3.  Marketplace settlement
4.  Family remittance
5.  Shared household device
6.  Charity/disbursement
7.  Merchant settlement
8.  Legitimate cross-border remittance
9.  Subscription/payment aggregation
10. Corporate shared-service account

Each needs multiple variations.

## Make hard negatives genuinely difficult

Examples:

### Payroll

``` text
Company
   │
   ├── Employee
   ├── Employee
   ├── Employee
   └── ...
```

High fan-out should not automatically imply laundering.

### Marketplace

``` text
hundreds of buyers
        ↓
marketplace
        ↓
settlement account
```

High velocity should not automatically imply fraud.

### Family

``` text
multiple people
      ↓
shared device
      ↓
shared beneficiaries
```

Shared-device relationships should not automatically imply fraud.

## Create fraudulent counterparts

For each legitimate archetype, create a structurally similar fraudulent
network.

Example:

``` text
LEGITIMATE:
Payroll hub → employees

FRAUD:
Mule hub → cash-out accounts
```

Then test whether Corridor Watch distinguishes them.

## Metrics

Measure:

-   hard-negative FPR
-   hard-negative precision
-   hard-negative recall
-   normal-network false-positive rate
-   risk-score separation
-   legitimate-network rejection rate

## Acceptance criteria

Create:

``` text
validation/external/hard_negatives/
reports/hard_negative_results.json
reports/hard_negative_report.md
```

The benchmark must have:

-   [ ] 10+ legitimate archetypes.
-   [ ] Multiple variants per archetype.
-   [ ] Fraud counterparts.
-   [ ] Hidden ground truth.
-   [ ] No label leakage.
-   [ ] Frozen final test split.
-   [ ] Feature-distribution documentation.
-   [ ] FPR measured independently.

------------------------------------------------------------------------

# 3. MAKE NETWORK EVALUATION INVESTIGATION-USEFUL

## Current problem

Current network metrics are approximately:

``` text
Account recall              ~20%
Key-node recall             ~20%
Relationship reconstruction ~20%
Path recovery               ~20%
```

These are useful, but may be stricter than the actual investigation
objective.

The system does not necessarily need to reconstruct every peripheral
node.

## Goal

Measure whether Corridor Watch identifies the network components that
materially matter to an investigation.

## Add five metrics

### 3.1 Anchor-node recall

Can the system identify the central suspicious account?

Examples:

-   mule account
-   originator
-   aggregator
-   cash-out account
-   hub

### 3.2 Critical-node recall

Measure recovery of nodes materially important to the investigation:

-   mule
-   controller
-   originator
-   sink
-   cash-out
-   key intermediary

### 3.3 Critical-edge recall

Measure whether relationships establishing suspicious flow are
recovered.

### 3.4 Investigation-path recovery

For each investigation, define the minimal path required to explain the
suspicious behavior.

Example:

``` text
A → B → C → D
```

If Corridor Watch recovers that path, path recovery is 100%.

### 3.5 Network ranking recall@K

Measure whether critical nodes appear in the analyst's:

-   top 10
-   top 20
-   top 50

## Do not remove existing metrics

Keep:

-   account recall
-   relationship recall
-   path recovery

Add the investigation-useful metrics alongside them.

## Acceptance criteria

Create:

``` text
reports/network_evaluation_v2.json
reports/network_evaluation_v2.md
```

Include:

-   [ ] Anchor-node recall
-   [ ] Critical-node recall
-   [ ] Critical-edge recall
-   [ ] Investigation-path recovery
-   [ ] Recall@K
-   [ ] Existing network metrics
-   [ ] Per-typology breakdown
-   [ ] Per-visibility-level breakdown

------------------------------------------------------------------------

# 4. FINISH AND PROVE THE REAL DEEPEVAL EVALUATION

## Current problem

DeepEval-related implementation exists, but the evidence is not yet
strong enough to claim:

> "DeepEval validated Corridor Watch."

The actual DeepEval execution needs to be demonstrated clearly.

Current AI evidence also shows:

``` text
Gemini agreement        ~94.9%
p95 latency              ~18.9 sec
unsupported claims       ~50%
entity-trap handling     current failure
```

## Goal

Create a genuine, reproducible AI evaluation with at least 100 cases.

Preferred:

``` text
250–500 cases
```

## Required test categories

Include:

-   normal
-   obvious fraud
-   subtle fraud
-   hard negatives
-   hybrid fraud
-   novel fraud
-   partial visibility
-   contradictory evidence
-   missing evidence
-   document cases
-   prompt injection
-   tool failures

## Required AI metrics

### Grounding / faithfulness

Are claims supported by supplied evidence?

### Investigation relevancy

Does the response address the actual investigation?

### Investigation correctness

Compare AI output against independent expected outcome for:

-   risk
-   disposition
-   typology
-   critical evidence
-   uncertainty

### Unsupported claims

Count material claims with no valid evidence reference.

### Tool-use correctness

Measure:

-   correct tool
-   correct arguments
-   required tools called
-   unnecessary tools
-   missing tools

## Hallucination suite

Include:

-   numerical traps
-   entity traps
-   fake account IDs
-   fake evidence IDs
-   contradictory documents
-   missing evidence
-   ambiguous evidence

Record separately:

``` text
hallucination rate
unsupported claim rate
entity hallucination rate
numerical hallucination rate
grounding rate
```

Do not collapse these into one metric.

## Prompt-injection suite

Target at least 50 attacks; 100+ preferred.

Include:

-   direct instructions
-   transaction-description injection
-   PDF injection
-   OCR injection
-   Unicode injection
-   metadata injection
-   fake evidence IDs
-   malicious tool arguments
-   contradictory document instructions

Most important metric:

``` text
decision-changing injection rate
```

Target:

``` text
0
```

for the tested attack suite.

## Required run metadata

Every AI run must record:

-   run ID
-   timestamp
-   git commit
-   dataset version
-   model
-   model version
-   prompt version
-   case count
-   seed
-   latency statistics
-   token usage
-   cost

## Fix current reporting inconsistency

Ensure these agree:

``` text
SCORECARD.md
reports/deepeval.json
reports/hallucination.json
reports/gemini_agreement.json
validation/run_suite.py
```

Do not report DeepEval as **Verified** unless an actual DeepEval run
produced the evidence.

## Acceptance criteria

-   [ ] Actual DeepEval execution demonstrated.
-   [ ] 100+ AI cases.
-   [ ] Grounding measured.
-   [ ] Unsupported claims measured.
-   [ ] Hallucination measured.
-   [ ] Investigation correctness measured.
-   [ ] Tool-use correctness measured.
-   [ ] Prompt injection measured.
-   [ ] Decision-change rate measured.
-   [ ] Cost measured.
-   [ ] Latency measured.
-   [ ] Reports use consistent terminology.
-   [ ] No unsupported 100% accuracy claim.

------------------------------------------------------------------------

# 5. MEASURE END-TO-END INVESTIGATION THROUGHPUT

## Current problem

The repository has strong ingestion measurements, but ingestion TPS is
not investigation throughput.

A realistic question is:

``` text
1,000 transactions/sec
       ↓
5% alerts
       ↓
50 investigations/sec
       ↓
Can Corridor Watch process 50/sec?
```

This is not sufficiently measured yet.

## Goal

Measure the complete investigation pipeline under realistic alert rates.

## Required metrics

Measure:

-   ingestion TPS
-   alert generation TPS
-   investigation enqueue TPS
-   investigation start TPS
-   investigation completion TPS
-   Gemini invocation TPS
-   final verdict TPS
-   queue depth
-   queue age
-   time-to-investigation
-   time-to-deterministic-verdict
-   time-to-Gemini-verdict
-   end-to-end time-to-verdict

## Required workload profiles

Run:

``` text
100 TPS
500 TPS
1,000 TPS
2,000 TPS
```

and test the 5,000 TPS target only if infrastructure permits.

At each ingestion rate test alert rates such as:

``` text
1%
5%
10%
20%
```

Example:

``` text
1,000 TPS × 5% alerts = 50 investigations/sec
```

## Test AI policies

Compare:

``` text
Policy A
deterministic only

Policy B
deterministic + Gemini for alerts

Policy C
deterministic + Gemini + advanced investigation

Policy D
critical cases → full AI/debate/human workflow
```

Measure:

-   throughput
-   latency
-   cost
-   queue growth

## Determine sustainable throughput

Report separately:

``` text
maximum ingestion TPS
maximum sustainable ingestion TPS under SLO
maximum investigation TPS
maximum sustainable investigation TPS under SLO
```

## Acceptance criteria

Create:

``` text
reports/investigation_throughput_v2.json
reports/investigation_throughput_v2.md
```

The report must contain:

-   [ ] End-to-end investigation throughput.
-   [ ] Alert rate.
-   [ ] Queue depth.
-   [ ] Completion TPS.
-   [ ] p50 latency.
-   [ ] p95 latency.
-   [ ] p99 latency.
-   [ ] Error rate.
-   [ ] Gemini latency.
-   [ ] AI cost.
-   [ ] Sustained throughput boundary.

------------------------------------------------------------------------

# 6. WHAT NOT TO DO

Do not:

-   [ ] Claim 5,000 TPS without measurement.
-   [ ] Claim 100% F1 from the original synthetic benchmark as proof of
    generalization.
-   [ ] Claim zero hallucinations from grounding tests alone.
-   [ ] Claim DeepEval validation unless DeepEval actually ran.
-   [ ] Tune directly against the frozen independent test set.
-   [ ] Add hard-coded exceptions for individual benchmark cases.
-   [ ] Hide the Distribution B failure.
-   [ ] Remove the original benchmark.
-   [ ] Replace full-network metrics with favorable metrics only.
-   [ ] Treat analyst disposition as confirmed fraud truth.
-   [ ] Optimize for the competition score at the expense of benchmark
    integrity.

------------------------------------------------------------------------

# 7. RECOMMENDED IMPLEMENTATION ORDER

## Step 1

Distribution B forensic analysis.

Deliver:

``` text
dist_b_false_positive_analysis.md
dist_b_false_positive_analysis.json
```

Do not modify the detector until the root cause is understood.

## Step 2

Build legitimate network archetypes and hard negatives.

Deliver:

``` text
hard_negative_dataset
hard_negative_report
```

## Step 3

Implement investigation-useful network metrics.

Deliver:

``` text
network_evaluation_v2
```

## Step 4

Complete actual DeepEval execution.

Deliver:

``` text
100+ case evaluation
grounding
hallucination
unsupported claims
tool use
prompt injection
```

## Step 5

Measure investigation throughput.

Deliver:

``` text
investigation_throughput_v2
```

------------------------------------------------------------------------

# 8. FINAL TARGET STATE

The following are **engineering targets, not current claims**.

``` text
INDEPENDENT GENERALIZATION
────────────────────────────────────
Independent F1             ≥ 0.85
Hard-negative FPR          ≤ 0.10
Hybrid detection           measured
Novel typology              measured


NETWORK INTELLIGENCE
────────────────────────────────────
Anchor recall              ≥ 0.80
Critical-node recall       ≥ 0.80
Critical-edge recall       ≥ 0.70
Investigation path         ≥ 0.70
Recall@K                   measured


GENAI
────────────────────────────────────
Gemini agreement           ≥ 0.90
Grounding                  ≥ 0.95
Unsupported claims         ≤ 0.05
Material hallucination     ≤ 0.01
Decision-changing injection = 0
Tool-use correctness       ≥ 0.90


RELIABILITY
────────────────────────────────────
Duplicate loss             = 0
Race failures               = 0
Unauthorized actions        = 0


SCALE
────────────────────────────────────
Sustainable ingestion       measured
Investigation throughput    measured
p95 investigation latency   measured
p99 investigation latency   measured
Cost/investigation          measured
```

------------------------------------------------------------------------

# 9. DEFINITION OF DONE

The sprint is complete only when all five statements are true.

### 1. False positives

> We know why Distribution B produced 100% FPR, and we have materially
> improved it without contaminating the frozen test set.

### 2. Hard negatives

> We can demonstrate that legitimate high-complexity networks do not
> automatically become fraud alerts.

### 3. Network intelligence

> We can quantify whether Corridor Watch identifies the critical nodes
> and paths that matter to an investigator.

### 4. GenAI

> We have a real, reproducible 100+ case AI evaluation with actual
> DeepEval execution and separate measurements for grounding,
> hallucination, unsupported claims, tool use, and injection resistance.

### 5. Throughput

> We know how many investigations per second the complete system can
> actually process under realistic alert rates.

------------------------------------------------------------------------

# 10. PRIORITY IN ONE LINE

``` text
FIX FPR
   ↓
PROVE HARD NEGATIVES
   ↓
PROVE INVESTIGATION-USEFUL NETWORK RECALL
   ↓
PROVE REAL GENAI QUALITY
   ↓
PROVE INVESTIGATION THROUGHPUT
```

**Do these five before adding another major feature.**
