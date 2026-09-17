# GenAI model bake-off (live Cloud Run)

- run_id: `752b339f5f24`
- base_url: `https://corridor-watch-6kmkxbsbwq-as.a.run.app`
- selected_model: **gemini-2.5-pro**
- rationale: Selected gemini-2.5-pro: llm_raw recall=1.0 FPR=0.0 F1=1.0; ops p95=1702.2156659513712ms.

| Model | Status | Raw P | Raw R | Raw F1 | Raw FPR | Gated FPR | p95 ms | Faith mean |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `gemini-2.5-flash` | ok | 1.0 | 1.0 | 1.0 | 0.0 | 0.0 | 9770.235582953319 | 1.0 |
| `gemini-2.5-pro` | ok | 1.0 | 1.0 | 1.0 | 0.0 | 0.0 | 1702.2156659513712 | 1.0 |
| `gemini-3.6-flash` | ok | 1.0 | 1.0 | 1.0 | 0.0 | 0.0 | 8288.21849997621 | 1.0 |
| `gemini-3.8-flash` | ok | 1.0 | 1.0 | 1.0 | 0.0 | 0.0 | 14447.574666002765 | 1.0 |
| `gemini-3.1-pro-preview` | ok | 1.0 | 1.0 | 1.0 | 0.0 | 0.0 | 30199.52645909507 | 1.0 |
