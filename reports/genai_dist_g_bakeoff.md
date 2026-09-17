# Dist G — GenAI unknown bake-off

- run_id: `982d59f1f0e4`
- dataset: `generator_g.seed53` (n=80, fraud=32, benign=48)
- freeze: `reports/dist_g_freeze.json`
- selected_model: **gemini-2.5-flash**
- rationale: Selected gemini-2.5-flash: agreement=1.0 cost/case=$0.002012 p95=6720.0ms alert_FPR=0.0
- unknown ensured: POSITIVE_G ∩ KNOWN_A_TO_F = ∅; not golden first-100

| Model | Status | P | R | F1 | FPR | $/case | Tokens/case | p95 ms | Agreement | Ungrounded |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `gemini-2.5-flash` | ok | 1.0 | 0.4688 | 0.6383 | 0.0 | 0.002012 | 1932.1 | 6720.0 | 1.0 | 0.0 |
| `gemini-2.5-pro` | ok | 1.0 | 0.4688 | 0.6383 | 0.0 | 0.010252 | 2146.1 | 10153.3 | 1.0 | 0.0 |
| `gemini-3.6-flash` | ok | 1.0 | 0.4688 | 0.6383 | 0.0 | 0.004128 | 2125.7 | 7910.9 | 1.0 | 0.0 |
| `gemini-3.8-flash` | ok | 1.0 | 0.4688 | 0.6383 | 0.0 | 0.003233 | 1887.1 | 73813.5 | 1.0 | 0.0 |
| `gemini-3.1-pro-preview` | ok | 1.0 | 0.4688 | 0.6383 | 0.0 | 0.018887 | 2641.4 | 16499.2 | 1.0 | 0.0 |
