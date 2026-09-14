# Dist F (frozen one-shot)

seed `47` threshold `40` n=81  
freeze `reports/dist_f_freeze.json` — dataset `generator_f.seed47`, commit `129bb69febcd`, `graph_features` sha `34a3e1a3dff0`

precision=1.0 recall=1.0 f1=1.0 FPR=0.0  
TP=32 FP=0 FN=0 TN=49

Do not retune the detector on this seed. Artifact is pinned. Runtime ignores `fraud_scenario`. Dist F names are not Pattern DNA labels.

## Two different accuracy numbers

`pattern_accuracy` measures exact canonical Pattern DNA label agreement. On Dist F it is **0.0** because generator names are novel (`dock_smurf`, `berth_skip`, `quay_wake`, `trade_overbill`) and the detector still emits only the five DNA families + `elevated_activity`.

`taxonomy_accuracy` uses an explicitly documented evaluation-only semantic family mapping declared in `validation/external/generator_f.py` (`FAMILY`) before the run:

| Generator name | DNA family | Status |
|---|---|---|
| `dock_smurf` | `split_transaction_laundering` | mapped |
| `berth_skip` | `multi_hop_chain` | mapped |
| `quay_wake` | `mule_pass_through` | mapped |
| `trade_overbill` | — | **unmapped novel** |

taxonomy_accuracy=0.25 mapping_coverage=0.75 novel_detection_recall=1.0

Novel/unmapped families remain novel rather than being forcibly assigned to an existing Pattern DNA label. `trade_overbill` was flagged (detection recall 1.0) without claiming a DNA name.
