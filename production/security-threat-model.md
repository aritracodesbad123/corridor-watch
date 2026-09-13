# Security threat model

**Status:** Controls are in code and covered by tests. Hosted SSO redirect and Cloud KMS envelopes are still gaps.

Synthetic data only. No production bank integration (`docs/COMPETITION_CLAIMS.md`).

## Assets

| Asset | Why it matters |
|---|---|
| Ingest ledger + investigation queue | Double-count or lost SAR work |
| Analyst decisions / audit log | Regulatory story |
| Console sessions / API keys / OIDC JWTs | Privilege |
| Gemini prompts and SoF documents | Injection + PII leak |
| Secret Manager values | Database and model keys |

## Actors

- External publisher (Pub/Sub / HTTP ingest)
- Analyst / FIU lead / MRM auditor
- Gemini (untrusted generator)
- Uploaded SoF document (untrusted text)
- Cloud operator (Secret Manager, Cloud SQL)

## Trust boundaries

| Boundary | Rule | Test / control |
|---|---|---|
| Ingest | Schema validate. Idempotent persist. No Gemini. | `test_malformed_transaction_rejected`, `test_cheap_screen_never_needs_gemini`, `test_gemini_unavailable_ingest_still_works` |
| Duplicate delivery | ACK; one ledger row; one queue row | `test_ingest_is_idempotent`, `test_source_event_id_is_duplicate_across_message_ids` |
| Console auth | Password/session, API key, or verified OIDC JWT. Header spoofing off on GCP. | `test_password_login_and_alert_sort`, `test_oidc_bearer_maps_role`, `test_unmapped_oidc_email_is_forbidden` |
| High-risk actions | `fiu_lead` + MFA when `OIDC_ISSUER` is set | `test_high_risk_decision_still_requires_fiu_lead`, `test_high_risk_without_mfa_is_rejected` |
| Authorization | Append-only who/what/when/case/old/new/reason | `test_authorization_event_is_appended` |
| SoF documents | Untrusted. Strip instruction-like text. | `test_wrap_untrusted_redacts_injection`, `test_grounded_prompt_treats_documents_as_untrusted` |
| Gemini output | Schema + evidence IDs. Human decides. | `test_grounding_gate_rejects_invented_evidence`, `test_grounded_report_schema` |
| AI payload | HMAC account tokens, not names | `test_minimize_txn_strips_raw_account_ids` |
| Intelligence share | No raw customer fields | `test_shared_signal_does_not_expose_raw_customer_data`, `test_unauthorized_intelligence_access` |
| GCP data store | PostgreSQL required | `test_gcp_refuses_sqlite` |
| Secrets | Secret Manager: `GEMINI_API_KEY`, `DATABASE_URL`, `CORRIDOR_WATCH_USERS`, optional `CW_PII_HMAC_KEY` | `scripts/deploy_cloud_run.sh` |

## Threats and residual risk

| Threat | Mitigation | Residual |
|---|---|---|
| Replay / double SAR | Source-event unique index + ingest seen-check | Concurrent Postgres race still relies on the unique index |
| Role spoofing | Disabled when `ENVIRONMENT=gcp` | Local header auth is for tests |
| Prompt injection via PDF/SoF | Wrap + redact + grounding gate | Model can still waffle; disposition is a recommendation |
| Secret in git | Deploy script refuses to commit keys | Operators must not paste secrets into issues |
| Lost notify | Transactional outbox | Local notify is a no-op; GCP skip-flag exists |
| Stolen console password | Optional OIDC + MFA step-up | Password console remains for the competition |

## Open production gaps

- Hosted SSO login button / OAuth redirect
- Cloud KMS envelope around the PII HMAC key
- Separate PII database
- WAF / mTLS at a banking edge
- SIEM export of `authorization` events
