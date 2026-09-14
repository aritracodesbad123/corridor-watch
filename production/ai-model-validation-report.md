# AI model validation report

**Status:** Deterministic engine is evaluated on synthetic data. Gemini is gated, not independently scored in production.

This is not a Vertex model card. Prompt label `investigator-v8` is an application version.

## Architecture (fail-safe)

```
Transaction → cheap_screen (no Gemini)
           → investigation_queue
           → deterministic evidence + DNA
           → optional Gemini copilot
           → grounding gate
           → HUMAN_REVIEW
```

Gemini never runs on ingest. High-risk `hold_payment` / `escalate_fiu` / `freeze_account` stay with `fiu_lead`.

## Deterministic detection (synthetic_v1)

Source: `benchmarks/latest.json`. Ground truth = `transactions.fraud_scenario`. **Labeled synthetic data, not a bank book.**

| Metric | Value |
|---|---|
| sample_count | 586 |
| precision / recall / f1 | 1.0 / 1.0 / 1.0 |
| false_positive_rate | 0.0 |
| pattern_accuracy | 0.9915 |
| quality_gate | passed (recall ≥ 0.9, precision ≥ 0.5, pattern_accuracy ≥ 0.9) |
| investigation_compression | 117 flagged → 30 networks (3.9×) |

One pattern confusion: `multi_hop_chain → shared_device_ring` (1 case).

Do not present 100% precision as production AML performance.

## Gemini controls that are enforced

| Control | Where | Test |
|---|---|---|
| Schema-constrained `InvestigationReport` | `investigations/schemas.py` | `test_grounded_report_schema` |
| Cite supplied `evidence_id` or keep deterministic report | `apply_grounding_gate` | `test_grounding_gate_rejects_invented_evidence` |
| Documents are untrusted | `privacy.wrap_untrusted`, grounded prompt rule 11 | `test_wrap_untrusted_redacts_injection` |
| No raw account IDs in the model payload | `privacy.minimize_txn` | `test_minimize_txn_strips_raw_account_ids` |
| Provenance: provider, prompt, evidence/input/output hashes | report + `model_provenance` audit | `test_deterministic_report_records_prompt_version` |
| Visibility ≠ guilt; do not invent institutions | `GROUNDED_SYSTEM_PROMPT` | `test_unknown_not_presented_as_fact` |

## Live Gemini agreement (2026-09-14)

Source: `reports/gemini_agreement.json`. Isolated ingest, **100** cases, `gemini-2.5-flash`. Gate agreement ≥ 0.85 on schema-valid reports; p95 ≤ 8 s.

Agreement **0.949** on **98** schema-valid reports (100 attempted; **2 HTTP 429**). Wilson 95% CI **0.89–0.98**. p95 **18928 ms** — **missed** the 8 s gate. Cost/case **$0.002387**. Tokens/case **1973.3**.
Do not present this as 100% of 100 calls. Schema fallback is no longer the main loss mode. Gemini cannot downgrade a deterministic disposition (`apply_grounding_gate`).

## What is not measured

| Item | Status |
|---|---|
| Gemini vs deterministic verdict agreement | **measured 0.949 on 98/100 schema-valid**; 2 HTTP 429 |
| Hallucination rate on live cases | live ungrounded **0.0** on 100 invoked (`reports/hallucination.json`) |
| Token usage / cost per case | **measured** $0.00241 / 1977.8 tokens on schema-valid cost mean |
| DeepEval official FaithfulnessMetric (LLM judge) | NOT_MEASURED unless Gemini judge binds |
| Shadow v1 vs v2 promotion gate | metric exists; no live promotion run |
| Monthly 99.9% availability | session 5xx only (`/api/metrics` slos) |

Promote a new Gemini model after agreement, grounding, latency, and escalation rates are measured — not because the model name changed.

## Replay a decision later

From the case audit pack / `model_provenance` event:

- `model_provider`, `model_version`, `prompt_version`
- `evidence_hash`, `input_hash`, `output_hash`

That answers “why did the system say this?” for the deterministic path today, and for Gemini when it was invoked.
