# Dist B false-positive analysis

Frozen test seed `7`. Validation seed `11` (threshold sweep only).

Generator B 'normal' is a source-only star. split_transaction_laundering used corridor_velocity with no inbound requirement, so the hub scored ≥40 and every outbound payroll wire inherited that score.

- legitimate n=80
- would flag before fix=80
- flagged now=0
- dominant class=`source_only_corridor_velocity`
- before metrics={'tp': 28, 'fp': 80, 'fn': 0, 'tn': 0, 'precision': 0.2593, 'recall': 1.0, 'f1': 0.4118, 'false_positive_rate': 1.0}
