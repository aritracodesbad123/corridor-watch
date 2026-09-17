# Dist G (GenAI unknown, frozen one-shot)

seed `53` n=80 (fraud=32, benign=48)  
freeze `reports/dist_g_freeze.json` — dataset `generator_g.seed53`  
bake-off `reports/genai_dist_g_bakeoff.json` (run `982d59f1f0e4`)

**Not a detector Dist.** Do not pitch Dist G F1 next to Dist A–F detector metrics.

Unseen fraud names (disjoint from Dist A–F): `tarmac_drip`, `gate_skip`, `cargo_wake`, `airbill_loop`.  
Normals / ambiguous: JP→KR airport–freight–retail, dividends, trade, noise, shrine gifts, guild dues. Runtime ignores `fraud_scenario`.

## GenAI alert vs oracle (all 5 models)

Alert = hold_payment | escalate_fiu | freeze_account (or risk_level=high).  
Oracle = fraud_scenario ∈ POSITIVE_G. Benign included → FPR non-vacuous.

| Model | P | R | F1 | FPR | $/case | p95 ms | Agr | Ungrounded |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| gemini-2.5-flash | 1.0 | 0.4688 | 0.6383 | 0.0 | 0.002012 | 6720 | 1.0 | 0.0 |
| gemini-2.5-pro | 1.0 | 0.4688 | 0.6383 | 0.0 | 0.010252 | 10153 | 1.0 | 0.0 |
| gemini-3.6-flash | 1.0 | 0.4688 | 0.6383 | 0.0 | 0.004128 | 7911 | 1.0 | 0.0 |
| gemini-3.8-flash | 1.0 | 0.4688 | 0.6383 | 0.0 | 0.003233 | 73814 | 1.0 | 0.0 |
| gemini-3.1-pro-preview | 1.0 | 0.4688 | 0.6383 | 0.0 | 0.018887 | 16499 | 1.0 | 0.0 |

Selected **gemini-2.5-flash** (same alert metrics as peers; lowest USD; p95 under 8s).

Honest ceiling: all models matched the deterministic disposition (agr=1.0). Misses concentrate on `tarmac_drip` (0/14 alerted). GenAI did not independently recover detector misses on this holdout.
