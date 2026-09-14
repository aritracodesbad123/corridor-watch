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
| pattern_accuracy | 0.8547 (Measured; detection F1 is the scored metric) |

Canonical wrap: `reports/validation_report.json`. Do not present 100% detection F1 as production AML performance.

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

Agreement **1.0** on **100** schema-valid reports (100 invoked). Wilson 95% CI **0.963–1.0**. p95 **4025.4 ms (4.025 s)** — passed the 8 s gate. Cost/case **$0.00143**. Tokens/case **1397.3**.
Gemini cannot downgrade a deterministic disposition (`apply_grounding_gate`).

## What is not measured

| Item | Status |
|---|---|
| Gemini vs deterministic verdict agreement | **measured 1.0 on n=100** |
| Hallucination rate on live cases | live ungrounded **0.0** on 100 invoked (`reports/hallucination.json`); live model hallucination rate NOT_MEASURED as a rate |
| Token usage / cost per case | **measured** $0.00143 / 1397.3 tokens |
| DeepEval official FaithfulnessMetric (LLM judge) | **RAN n=10** score 1.0; 205-case mix is custom BaseMetric, not 205 Gemini-judged cases |
| Shadow v1 vs v2 promotion gate | metric exists; no live promotion run |
| Monthly 99.9% availability | session 5xx only (`/api/metrics` slos) |

Promote a new Gemini model after agreement, grounding, latency, and escalation rates are measured — not because the model name changed.

## Replay a decision later

From the case audit pack / `model_provenance` event:

- `model_provider`, `model_version`, `prompt_version`
- `evidence_hash`, `input_hash`, `output_hash`

That answers “why did the system say this?” for the deterministic path today, and for Gemini when it was invoked.
