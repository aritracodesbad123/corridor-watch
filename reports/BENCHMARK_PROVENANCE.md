# Frozen benchmark provenance

All competition benchmark artifacts are frozen one-shot evaluations. Subsequent code changes are not used to alter or replace benchmark results.

Chain for each independent distribution: **dataset → seed → freeze artifact → result artifact → git commit at freeze → graph_features hash**.

| Dist | Dataset / generator | Seed | Freeze | Result | Commit (12) | `graph_features` sha12 |
|---|---|---:|---|---|---|---|
| A | `data_gen` / hidden oracle | 42 | (suite wrap, not a holdout freeze) | `reports/validation_report.json` | `129bb69febcd` | — |
| B | `validation/external/generator_b.py` (`generator_b.seed7`) | 7 | (fitted; `dist_b_before.json` is the pre-fix baseline) | `reports/dist_b.json` | `129bb69febcd` | — |
| C | `validation/external/generator_c.py` (`generator_c.seed23`) | 23 | `reports/dist_c_freeze.json` | `reports/dist_c.json` | `a4de7e1817a8` | `26fbe680d558` |
| D | `validation/external/generator_d.py` (`generator_d.seed37`) | 37 | `reports/dist_d_freeze.json` | `reports/dist_d.json` | `8323b0486fc1` | `50938d088d57` |
| E | `validation/external/generator_e.py` (`generator_e.seed41`) | 41 | `reports/dist_e_freeze.json` | `reports/dist_e.json` | `0a0c06ce73ce` | `87fcdbefdd16` |
| F | `validation/external/generator_f.py` (`generator_f.seed47`) | 47 | `reports/dist_f_freeze.json` | `reports/dist_f.json` | `129bb69febcd` | `34a3e1a3dff0` |

`FLAG_THRESHOLD` was 40 on every freeze. Dist F was scored at commit `129bb69febcd` (the Dist E freeze HEAD) **before** the Dist F sources were committed. That is the detector that the freeze hash fingerprints. Do not re-hash current `graph_features.py` against seed 47.

Runtime never reads `fraud_scenario`. Dist F `FAMILY` is eval-only and lives in the generator **and** the freeze file.

Do not overwrite `reports/dist_{c,d,e,f}.json` or their freeze files.
