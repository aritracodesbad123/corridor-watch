# Demo claims audit — Corridor Watch (hackathon video)

Every claim the video may make must have **code + test**. Claims without both are cut or marked CUT.

| # | Claim | Implementation | Test | Status |
|---|---|---|---|---|
| 1 | Gemini never sees raw ledger account IDs / customer names | `privacy.minimize_txn` → `agent.grounded_gemini_report` payload | `tests/test_security.py::test_minimize_txn_strips_raw_account_ids`; `tests/test_demo_day1.py::test_grounded_payload_has_no_raw_account_ids` | PASS |
| 2 | Output gate rejects ungrounded / invented evidence | `agent.apply_grounding_gate` | `tests/test_security.py::test_grounding_gate_rejects_invented_evidence`; `validation/deepeval/test_grounding.py` | PASS |
| 3 | Gate strips invented free-text entities | `agent.ground_plain_text` / `ground_string_list` | `validation/deepeval/test_grounding.py::test_ground_plain_text_strips_invented_entities` | PASS |
| 4 | Gemini cannot soften disposition below deterministic | `apply_grounding_gate` disposition rank | `validation/deepeval/test_grounding.py::test_grounding_gate_does_not_let_gemini_downgrade` | PASS |
| 5 | Timeout / missing key → deterministic fallback, marked | `agent.investigate` → `deterministic_fallback` | `tests/test_platform.py::test_investigate_survives_sparse_case` (no key path) | PASS |
| 6 | Analysts refused consequential actions (hold/escalate/freeze) | `auth.HIGH_RISK_DECISIONS` + `main.analyst_decision` 403 | `tests/test_platform.py::test_high_risk_decision_still_requires_fiu_lead` | PASS |
| 7 | Score is deterministic from DAG / risk_scores, not model-authored | `investigation_dag.deterministic_verdict`; gate cannot invent score | `tests/test_demo_day1.py::test_cw_mid_02_risk_is_single_source` | PASS |
| 8 | Every decision is audited | `audit.log` / `audit.log_authz` | `tests/test_security.py::test_authorization_event_is_appended`; `validation/security/test_audit_trail.py` | PASS |
| 9 | Confirming decision writes / reinforces Pattern DNA | `patterns.extractor.extract_from_confirmation` → `increment_confirmed` | `tests/test_platform.py::test_confirmed_decision_extracts_or_reinforces_pattern` | PASS |
| 10 | Later alert with same fingerprint can match non-zero | `patterns.matcher.match_patterns` + seeded `CW-MID-03` | `tests/test_demo_day1.py::test_confirm_then_next_alert_matches` | PASS |
| 11 | Structured brief schema (summary, unknown, next checks, evidence chips) | `investigations.schemas.InvestigationReport` | `tests/test_platform.py::test_grounded_report_schema` | PASS |
| 12 | Model cannot execute hold/escalate/freeze from output alone | Decisions only via `/decision` + RBAC; model returns text/schema only | `test_high_risk_decision_still_requires_fiu_lead` | PASS |
| 13 | Provenance states (prefetch / grounded / fallback / gate fail) | UI `CasePanels` + verdict `mode` / `grounded` | UI wired; **demo replay flag** pending Day-1 #2 | PARTIAL |
| 14 | Model name shown in UI | `active_model()` → brief `model_version` | Label UI pending Day-1 #2 | PARTIAL |
| 15 | What-if / SAR exist as real features | `counterfactual.py`, `sar_generator.py`, API routes | Platform tests exist; **video may include only if shown live** | REAL — optional in script |

## Cut from script (not claimed until PARTIAL → PASS)

- Live-only Gemini latency (use demo replay mode once shipped).
- Any “AI froze the account” language.

## Assumptions

1. Canonical alert risk for queue/header is `flagged_transactions.risk_score` (91 for CW-MID-02).
2. `transactions.risk_score` must match that value after Day-1 risk fix (was 90).
3. Corridor velocity **84** is a separate feature score, not the alert risk — label it if shown.
4. No literal **85** in backend seed for CW-MID-02; prior film inconsistency was 90 vs 91.
