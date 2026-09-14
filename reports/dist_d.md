# Dist D (frozen one-shot)

seed `37` threshold `40` n=80

precision=0.587 recall=1.0 f1=0.7397 FPR=0.3585

TP=27 FP=19 FN=0 TN=34

Unseen fraud: invoice_loop, nested_shell (partial hop dropped), drain_wake, burst_sink.
Normals: tripartite farm-mill-shop, dividends, CHF trade, noise, ambiguous clinic/tithe inbound. Runtime ignores fraud_scenario.
Clinic/tithe inbound: 0 flagged. Gate missed (precision 0.587, FPR 0.3585): mill pass-through FPs.
Do not retune the detector on this seed. Artifact is pinned.
