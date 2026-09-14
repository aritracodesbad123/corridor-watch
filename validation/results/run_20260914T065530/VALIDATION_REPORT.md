# Validation report

run_id `e925c055d4ea` commit `8beb0b0deed4938e87516e931ea79ee35a91b524`. Seed `42`. Pytest exit `0`.

## Deterministic
status=ok f1=1.0 fpr=0.0 samples=586
validation.oracle (eval-only; runtime ignores fraud_scenario). Gate F1 ≥ 0.85.

## Network
account_recall=0.2019 key_node_recall=0.2019 reconstruction=0.1951

## Scale (Pub/Sub → Cloud Run → Cloud SQL)

| Target | Publish TPS | Consume TPS | Gate | Result |
|---|---:|---:|---:|---|
| 100 | 99.97 | 97.59 | 95 | passed |
| 500 | 499.75 | 407.96 | 400 | passed |
| 1,000 | 999.5 | 814.13 | 800 | passed |
| 2,000 | 1999.64 | 1148.32 | 1500 | missed |

Max sustained ingest TPS under a passing gate: **814.13**. Not 5,000 TPS.
Investigation enqueue TPS: 119.77. Completions NOT_MEASURED.

## Gemini
agreement=0.949 n=98 ci=[0.8861, 0.978] p95_ms=18928.3
cost/case=0.002387 tokens/case=1973.3
hallucination=0.0 unsupported=0.5

## DR
RTO=4.5 current-state clone RPO=0.0 (current_state_clone).
PITR-to-past RPO=NOT_MEASURED. replay_duplicates=None.
