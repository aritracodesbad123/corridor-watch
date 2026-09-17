# Corridor Watch — competition brief

**The transaction is not the crime. The network is.**

This file is the judge-facing brief. Measured numbers live in [`reports/SCORECARD.md`](../reports/SCORECARD.md). Frozen provenance: [`reports/BENCHMARK_PROVENANCE.md`](../reports/BENCHMARK_PROVENANCE.md). Claims policy: [`COMPETITION_CLAIMS.md`](COMPETITION_CLAIMS.md).

All competition benchmark artifacts are frozen one-shot evaluations. Subsequent code changes are not used to alter or replace benchmark results.

## Problem

Cross-border mule, smurf, and layering rings are not single wires. Transaction-threshold rules flag the wrong objects, miss the network, and leave the institution with no memory of how the last confirmed case looked.

## Solution

Corridor Watch treats the **network** as the investigation unit:

1. Detect suspicious networks
2. Build deterministic evidence
3. Investigate the network
4. Ground Gemini on that evidence
5. Require human authorization
6. Convert confirmed cases into Crime Pattern DNA

Crime Pattern DNA is the hero: the system does not only detect today's fraud. Confirmed investigations become institutional knowledge for the next one.

## Architecture

```text
Transactions
     ↓
Network Construction
     ↓
Deterministic Detection
     ↓
Investigation DAG
     ↓
Evidence Pack
     ↓
Gemini Copilot
     ↓
Grounding Gate
     ↓
Human Decision
     ↓
Crime Pattern DNA
     ↓
Institutional Memory
     ↺
Future Investigations
```

Gemini is never a chatbot on the raw ledger. The path is **Evidence → Gemini → grounding gate → human**. Ingest never calls Gemini. High-risk freeze/hold/escalate still requires an FIU lead.

## AI

- Deterministic DAG produces the evidence pack and a verdict without an LLM.
- Gemini explains only that pack (grounding gate). Debate / SAR / SoF notes use the same text-grounding helpers.
- **Absolute GenAI model comparison** is Dist G + agreement/USD (see [`docs/GENAI_MODEL_BENCHMARK.md`](GENAI_MODEL_BENCHMARK.md)): USD winner **`gemini-2.5-flash`** ($0.00201/case Dist G; $0.00203 agreement pack). All five models tied on Dist G P/R/F1/FPR (1.0 / 0.4688 / 0.6383 / 0.0). Artifacts: `reports/genai_dist_g_bakeoff.md`, `reports/genai_agreement_cost_bakeoff.md`.
- An earlier live Cloud Run bake-off (n=8, no benign) selected `gemini-2.5-pro` but is **superseded** for model ranking (vacuous FPR).
- Dist G / agreement GenAI metrics are **separate** from Dist A–F detector SCORECARD.
- Historical single-model agreement pack: **1.0, n=100**, p95 **4.025s**, **$0.00143**/case (`gemini-2.5-flash` only).
- Force Gemini runs a short tool loop when Interactions is available; UI shows provenance (`gemini_tools` | `gemini_prefetch` | `grounded` | `fallback` | `gate_fail`).

## Demo (3–5 minutes)

One case. Spine only:

1. Evidence pack (DAG) — no Gemini yet.
2. Force Gemini brief (plain English + provenance / tools).
3. AI Debate → meeting-ready judge outcome (feeds export).
4. FIU lead confirm hold/escalate.
5. Pattern DNA.

Do not tour every Phase 3 appendix tab.

## Evaluation

Independent generators A–F. Runtime ignores `fraud_scenario`. Dist C–F were frozen before scoring (`graph_features` hash + threshold 40). Do not retune on 23/37/41/47.

| Dist | Detection | Honest miss / note |
|---|---|---|
| A | F1 1.0 FPR 0 (n=586) | Hidden oracle |
| B | F1 1.0 FPR 0 (seed 7) | Was F1 0.4118 / FPR 1.0 |
| C | F1 0.5 FPR 0.7568 (seed 23) | Frozen FP miss |
| D | F1 0.7397 FPR 0.3585 (seed 37) | Frozen mill pass-through FPs |
| E | F1 1.0 FPR 0 (seed 41) | 100% recall on that frozen unseen set, not all fraud |
| F | F1 1.0 FPR 0 (seed 47) | Exact DNA name-match 0; eval-only taxonomy 0.25 |

Dist F methodology: `pattern_accuracy` is exact Pattern DNA label agreement. `taxonomy_accuracy` uses a pre-declared eval-only FAMILY map. Unmapped `trade_overbill` stays novel (detected, not renamed). Dist F names were **not** added as runtime DNA labels.

DeepEval: **205 cases** (custom metrics) plus official Gemini Faithfulness **n=10**. Not 205 Gemini-judged cases. Live GenAI bake-off / hardening: [`docs/GENAI_MODEL_BENCHMARK.md`](GENAI_MODEL_BENCHMARK.md).

Sustained ingest under the defined SLO: **814 TPS**. 5,000 TPS is a target, not achieved.

## Security

RBAC, high-risk step-up, Gemini off ingest, PII tokens at the model boundary, injection decision-change 0.0 (n=50). See SCORECARD security rows.

## Known limitations

- Synthetic data only.
- 814 TPS measured; 5k is a target.
- Dist C/D have known false-positive weaknesses (frozen).
- Investigation-path recall = 0.667.
- Exact novel taxonomy classification remains imperfect.
- PITR-to-past not measured.
- Official Gemini Faithfulness n=10.

## 5-minute local demo

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp credentials.example.json credentials.json   # demo logins only
python data_gen.py && python graph_features.py
export GEMINI_API_KEY=your_key                 # optional; DAG works without it
uvicorn main:app --reload --port 8080
```

Open http://localhost:8080 — sign in as `fiu_lead` / `change-me-fiu`. Path: Home → Investigations → Pattern DNA.

## Judge questions (expect these)

1. **Did you tune on Dist F?** No. Freeze hash `34a3e1a3dff0` was recorded before scoring seed 47. If F had missed, we would not retune on F.
2. **Is taxonomy_accuracy cheating?** No. Exact `pattern_accuracy` stays 0. FAMILY was declared in the generator before the run. Unmapped names stay novel. We did not add Dist F strings as DNA labels.
3. **Why is Dist D FPR 0.36?** Old mill pass-through looks like a mule on graph features. Dist E/F commercial guards fixed later generators; Dist D is frozen history.
4. **Is this 5,000 TPS?** No. Measured sustained ingest under SLO is 814 TPS.
5. **Did Gemini judge 205 cases?** No. 205 DeepEval BaseMetric cases plus 10 official Faithfulness judgments.
6. **Can the model freeze an account?** No. Gemini recommends. FIU lead authorizes.
7. **Does runtime see fraud labels?** No. `fraud_scenario` is eval-only.
8. **What is Pattern DNA?** Confirmed investigations compacted into named graph fingerprints, reused on later networks.
9. **Why investigation-path 0.67?** Two clusters recovered accounts/edges but not the designated path. That miss is on the SCORECARD.
10. **Would this work on a real bank?** Not claimed. Synthetic world; core-banking hold is out of scope.

## Evaluation methodology (one slide)

Independent generators. Hidden oracle. Freeze detector (sha + threshold) **before** C/D/E/F. Report detection F1/FPR separately from name-match. Dist F adds an eval-only family map and leaves novel names novel. Do not retune on a frozen seed. Known misses stay in the pack.
