# Hard-negative network benchmark

n=71 archetypes=['CHARITY', 'FAMILY', 'MARKET', 'MERCHANT', 'MULEHUB', 'PAYROLL', 'REMIT', 'SHARED', 'SMURFSINK', 'SUBS', 'TREASURY', 'circular_pass', 'household', 'mule_pass_through']

FPR=0.0 precision=1.0 recall=1.0
legit mean score=14.4 fraud mean=77.79

Feature note: legitimate archetypes are source-only or old-account disbursement (payroll/treasury/marketplace/etc.). Fraud twins reuse the same skeleton with inbound fan-in or pass-through. Runtime ignores `fraud_scenario`.
