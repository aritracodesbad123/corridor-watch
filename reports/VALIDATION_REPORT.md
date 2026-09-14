# Validation report

Seed `42`. Pytest exit `0`.

## Deterministic
status=ok f1=1.0 fpr=0.0 samples=586
Clean `data_gen` cut. Gate F1 ≥ 0.85.

## Scale (Pub/Sub → Cloud Run → Cloud SQL)

| Target | Publish TPS | Consume TPS | Gate | Result |
|---|---:|---:|---:|---|
| 100 | 99.97 | 97.59 | 95 | passed |
| 500 | 499.75 | 407.96 | 400 | passed |
| 1,000 | 999.5 | 814.13 | 800 | passed |
| 2,000 | 1999.64 | 1148.32 | 1500 | missed |

Max sustained TPS under a passing gate: **814.13**. Not 5,000 TPS.

## Gemini
agreement=1.0 p95_ms=7754.5 cost/case=0.002229

## DR
RPO=0.0 / RTO=4.5 (Measured)
