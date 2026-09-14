# Dist B false-positive analysis

Frozen test seed `7`. Validation seed `11` (threshold sweep only).

Generator B 'normal' is a source-only star. split_transaction_laundering used corridor_velocity with no inbound requirement, so the hub scored ≥40 and every outbound payroll wire inherited that score.

Hard-negative FPR is 0% on payroll/treasury/marketplace networks because those graphs are source-only *or* old-account disbursement without inbound fan-in. Generator B 'normal' is the same topology (payroll star) plus high corridor velocity. Before the inbound guard, velocity was scored as split regardless of fan-in, so Dist B FPR was 100% while hard-negatives already stayed below flag.

Ruled out: temporal shift, account-age, shared devices, feature leakage, beneficiary concentration. Cause: graph topology + benchmark construction (source-only velocity counted as smurfing).

One change: `split_vel = vel * 8` only when `fan_in >= 3` or `pass_through >= 0.3`.

- legitimate n=80
- would flag before fix=80
- flagged now=0
- dominant class=`source_only_corridor_velocity`
- before metrics={'tp': 28, 'fp': 80, 'fn': 0, 'tn': 0, 'precision': 0.2593, 'recall': 1.0, 'f1': 0.4118, 'false_positive_rate': 1.0}
