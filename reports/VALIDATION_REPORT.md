# Validation report

run_id `0b70b801de90` commit `36e7365f32c227dedfbc43a9a651f6a7830d88d6`. Seed `42`. Pytest exit `0`.

## Deterministic
status=ok f1=1.0 fpr=0.0 samples=586
validation.oracle (eval-only; runtime ignores fraud_scenario). Gate F1 ≥ 0.85.

## Network
account_recall=1.0 key_node_recall=1.0 reconstruction=1.0

## Scale (Pub/Sub → Cloud Run → Cloud SQL)

| Target | Publish TPS | Consume TPS | Gate | Result |
|---|---:|---:|---:|---|
| 100 | 99.97 | 97.59 | 95 | passed |
| 500 | 499.75 | 407.96 | 400 | passed |
| 1,000 | 999.5 | 814.13 | 800 | passed |
| 2,000 | 1999.64 | 1148.32 | 1500 | missed |

Max sustained ingest TPS under a passing gate: **814.13**. Not 5,000 TPS.
Investigation enqueue TPS: 119.77.
Investigation completion TPS (Policy A): 74.76.

## Gemini
agreement=1.0 n=100 ci=[0.963, 1.0] p95_ms=4025.4
cost/case=0.00143 tokens/case=1397.3
hallucination=0.0 unsupported=0.0

## DR
RTO=4.5 current-state clone RPO=0.0 (current_state_clone).
PITR-to-past RPO=NOT_MEASURED. replay_duplicates=None.
