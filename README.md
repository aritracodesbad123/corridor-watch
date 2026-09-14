# Corridor Watch

> **The transaction is not the crime. The network is.**

Corridor Watch detects **suspicious transaction networks**, builds a deterministic evidence pack, investigates the graph, grounds Gemini on that evidence, requires a human for consequential actions, and turns confirmed cases into **Crime Pattern DNA** — institutional memory, not a one-off alert.

```text
Transactions → Network → Deterministic detection → Investigation DAG
    → Evidence pack → Gemini copilot → Grounding gate → Human decision
    → Crime Pattern DNA → Institutional memory ↺ future investigations
```

Gemini is **Evidence → grounding gate → human**, not User → chatbot → answer.

## What it does

1. Detect suspicious networks
2. Build deterministic evidence
3. Investigate the network
4. Ground Gemini on that evidence
5. Require human authorization
6. Convert confirmed cases into Crime Pattern DNA

## Strongest measured results

Canonical scorecard: [`reports/SCORECARD.md`](reports/SCORECARD.md). Judge brief: [`docs/COMPETITION.md`](docs/COMPETITION.md). Claims policy: [`docs/COMPETITION_CLAIMS.md`](docs/COMPETITION_CLAIMS.md).

| Claim | Number | Bound |
|---|---|---|
| Dist E / Dist F detection recall | **1.0** on those frozen unseen families | Not “100% accuracy on all fraud” |
| Dist B F1 | **1.0** (was 0.4118) | Seed 7, FPR 0 |
| Gemini agreement | **1.0, n=100** | vs deterministic disposition |
| Gemini p95 | **4.025 s** | gate 8000 ms |
| Gemini cost/case | **$0.00143** | `gemini-2.5-flash` |
| DeepEval | **205 cases** | custom metrics |
| Official Gemini Faithfulness | **n=10** | not 205 Gemini-judged cases |
| Sustained ingest under SLO | **814 TPS** | 5,000 TPS is a **target, not achieved** |

All competition benchmark artifacts are frozen one-shot evaluations. Subsequent code changes are not used to alter or replace benchmark results.

## 5-minute local demo

```bash
git clone https://github.com/aritracodesbad123/corridor-watch.git
cd corridor-watch
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp credentials.example.json credentials.json
python data_gen.py
python graph_features.py
# optional: export GEMINI_API_KEY=...  (DAG works without it)
uvicorn main:app --reload --port 8080
```

Open http://localhost:8080 — sign in as `fiu_lead` / `change-me-fiu` (from the example file).

Demo path (3–5 min, one case): **Home (network lights up) → Investigations (graph + money flow) → deterministic evidence → Gemini on that evidence → grounding → confirm → export → Pattern DNA library.** Full script: [`docs/COMPETITION.md`](docs/COMPETITION.md).

Cloud Run: [`docs/CLOUD_RUN.md`](docs/CLOUD_RUN.md). Do not put API keys in the image or in git.

## Known limitations

- Synthetic data only.
- 814 TPS measured; 5,000 TPS is a target.
- Dist C/D have frozen false-positive weaknesses.
- Investigation-path recall = 0.667.
- Exact novel taxonomy classification remains imperfect (Dist F name-match 0; eval-only taxonomy 0.25).
- PITR-to-past not measured.
- Official Gemini Faithfulness n=10.

Dist F `pattern_accuracy` is exact Pattern DNA label agreement. `taxonomy_accuracy` is a pre-declared eval-only family map. Unmapped families stay novel. Dist F names were not added as runtime DNA labels.

## Authentication

The console is password-authenticated. Copy `credentials.example.json` to `credentials.json` (gitignored). Roles: `analyst`, `fiu_lead`, `mrm_auditor`. High-risk freeze/hold/escalate requires `fiu_lead`.

## Deploy

```bash
export GEMINI_API_KEY="your_key"   # Secret Manager only; not in the image
./scripts/deploy_cloud_run.sh YOUR_PROJECT_ID asia-southeast1
```

SQLite is local-only. Cloud Run requires Cloud SQL PostgreSQL. Report only measured `achieved_tps`.

More: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md), [`docs/CLOUD_RUN.md`](docs/CLOUD_RUN.md), [`FINAL_VALIDATION_REPORT.md`](FINAL_VALIDATION_REPORT.md).
