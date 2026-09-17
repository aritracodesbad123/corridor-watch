# GenAI agreement + USD cost bake-off

- run_id: `18c9176f68de`
- protocol: gemini_agreement replica (n=100 per model)
- selected_model: **gemini-2.5-flash**
- rationale: Selected gemini-2.5-flash: agreement=1.0 cost/case=$0.002032 p95=6653.5ms alert_FPR=0.0

| Model | Status | Agreement | Cost $/case | Tokens/case | p95 ms | Ungrounded | P | R | F1 | FPR |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `gemini-2.5-flash` | ok | 1.0 | 0.002032 | 1915.4 | 6653.5 | 0.0 | 1.0 | 1.0 | 1.0 | 0.0 |
| `gemini-2.5-pro` | ok | 0.99 | 0.010631 | 2165.5 | 10377.1 | 0.0 | 0.9821 | 1.0 | 0.991 | 0.0222 |
| `gemini-3.6-flash` | ok | 1.0 | 0.004045 | 2086.5 | 10028.6 | 0.0 | 1.0 | 1.0 | 1.0 | 0.0 |
| `gemini-3.8-flash` | ok | 1.0 | 0.003405 | 1915.6 | 15376.6 | 0.0 | 1.0 | 1.0 | 1.0 | 0.0 |
| `gemini-3.1-pro-preview` | ok | 1.0 | 0.018758 | 2606.1 | 16218.2 | 0.0 | 1.0 | 1.0 | 1.0 | 0.0 |
