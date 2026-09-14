# Validation report

run_id `389972d7dc82` commit `8beb0b0deed4938e87516e931ea79ee35a91b524`. Seed `42`. Pytest exit `0`.

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
Investigation throughput: {'enqueue_tps': 119.77, 'completion_tps': None, 'time_to_verdict': None, 'note': 'Enqueue TPS from ingest artifacts. Completions/AI TPS NOT_MEASURED on these probes.', 'runs': [{'target': 100, 'queued_for_investigation': 233, 'elapsed_seconds': 20.599, 'enqueue_tps': 11.31, 'completions_per_sec': None, 'ai_investigations_per_sec': None, 'gemini_requests_total': None}, {'target': 500, 'queued_for_investigation': 546, 'elapsed_seconds': 12.277, 'enqueue_tps': 44.47, 'completions_per_sec': None, 'ai_investigations_per_sec': None, 'gemini_requests_total': None}, {'target': 1000, 'queued_for_investigation': 1056, 'elapsed_seconds': 12.328, 'enqueue_tps': 85.66, 'completions_per_sec': None, 'ai_investigations_per_sec': None, 'gemini_requests_total': None}, {'target': 2000, 'queued_for_investigation': 2086, 'elapsed_seconds': 17.417, 'enqueue_tps': 119.77, 'completions_per_sec': None, 'ai_investigations_per_sec': None, 'gemini_requests_total': None}]}

## Gemini
agreement=1.0 n=3 ci=[0.4385, 1.0] p95_ms=7754.5
cost/case=0.002229 tokens/case=1845.7
hallucination=0.0 unsupported=0.5

## DR
RTO=4.5 current-state clone RPO=0.0 (current_state_clone).
PITR-to-past RPO=NOT_MEASURED. replay_duplicates=None.
