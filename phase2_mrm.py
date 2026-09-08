"""
Phase 2 — MRM (model risk management) documentation draft generator.

Produces a first-draft validation document for the Phase 1 scoring + agent stack,
incorporating red-team coverage gaps as documented limitations. Analyst/MRM review required.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from db import connect, init_schema
import audit


def _stats() -> dict:
    init_schema()
    con = connect()
    accounts = con.execute("SELECT COUNT(*) AS c FROM accounts").fetchone()["c"]
    txns = con.execute("SELECT COUNT(*) AS c FROM transactions").fetchone()["c"]
    flagged = con.execute("SELECT COUNT(*) AS c FROM flagged_transactions").fetchone()["c"]
    patterns = con.execute(
        "SELECT primary_pattern, COUNT(*) AS c FROM risk_scores GROUP BY primary_pattern"
    ).fetchall()
    scenarios = con.execute(
        "SELECT fraud_scenario, COUNT(*) AS c FROM transactions GROUP BY fraud_scenario"
    ).fetchall()
    red = con.execute("SELECT * FROM redteam_scenarios ORDER BY created_at DESC LIMIT 20").fetchall()
    con.close()
    return {
        "accounts": accounts,
        "transactions": txns,
        "flagged": flagged,
        "pattern_distribution": {r["primary_pattern"]: r["c"] for r in patterns},
        "scenario_distribution": {r["fraud_scenario"]: r["c"] for r in scenarios},
        "redteam": [dict(r) for r in red],
    }


def generate_mrm_draft() -> dict:
    stats = _stats()
    red = stats["redteam"]
    escaped = [r for r in red if r.get("injected") and not r.get("detected")]
    detected = [r for r in red if r.get("injected") and r.get("detected")]

    limitations = [
        "Synthetic data only — no claim of production calibration or population stability.",
        "NetworkX features are batch/offline; latency and concept drift under real-time streams untested.",
        "Behavioral biometrics are simulated session features, not vendor telemetry.",
        "LLM narrative layer is assistive; deterministic DAG remains the auditable baseline.",
        "No champion/challenger production monitoring, PSI/CSI drift dashboards, or challenger model yet.",
    ]
    for r in escaped:
        limitations.append(
            f"Red-team gap: scenario '{r.get('pattern_name')}' evaded detection — {r.get('evasion_reason')}"
        )

    doc = {
        "title": "Corridor Watch — Model Risk Management Draft (Phase 1 Scoring + Investigation Agent)",
        "version": "0.1-draft",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "requires_human_review": True,
        "intended_use": (
            "Assist compliance analysts investigating flagged cross-border remittance alerts "
            "by gathering graph/behavioral evidence and drafting explainable verdicts. "
            "Not authorized for automated payment hold/release or regulatory filing submission."
        ),
        "model_inventory": [
            {
                "component": "graph_feature_scorer",
                "type": "rules_plus_network_features",
                "inputs": [
                    "fan_in_count", "fan_out_count", "pass_through_ratio", "avg_hold_time_minutes",
                    "shared_device_count", "shared_beneficiary_count", "multi_hop_chain_depth",
                    "account_age_days", "corridor_velocity_score", "behavioral_risk",
                ],
                "outputs": ["account risk_score", "primary_pattern", "pattern_scores"],
            },
            {
                "component": "investigation_dag",
                "type": "deterministic_workflow",
                "steps": 12,
                "outputs": ["evidence_pack", "deterministic_verdict"],
            },
            {
                "component": "llm_investigation_agent",
                "type": "tool_calling_llm",
                "provider_hackathon": "Gemini via google-genai",
                "provider_enterprise": "Azure OpenAI / AI Foundry Agent Service",
                "outputs": ["narrative rationale", "recommended_action"],
            },
        ],
        "data_lineage": {
            "training_or_calibration_data": "Synthetic only (Faker + seeded fraud injectors)",
            "pii": "None — fabricated names/IDs",
            "feature_store": "SQLite tables accounts/transactions/sessions/risk_scores",
        },
        "validation_snapshot": {
            "population": stats,
            "redteam_detected": len(detected),
            "redteam_escaped": len(escaped),
            "flag_threshold": 40,
        },
        "performance_claims": [
            "Detects injected mule_pass_through, shared_device_ring, and split_transaction_laundering patterns in synthetic set.",
            "Every investigation step and tool call is written to audit_log.",
            "Deterministic fallback ensures verdict availability when LLM is unavailable.",
        ],
        "limitations_and_gaps": limitations,
        "governance_controls": [
            "Human-in-the-loop on all Phase 2 drafts (SoF, MRM, red-team reports).",
            "Audit trail of prompts/tool I/O for AI calls.",
            "Provider-swappable reasoning client for Azure enterprise deployment with zero-retention contractual terms.",
        ],
        "recommended_next_validation_tests": [
            "Blind holdout of synthetic scenarios with precision/recall by pattern.",
            "Stability of pattern labels under ±20% amount perturbation.",
            "Adversarial red-team cadence (weekly) with coverage matrix updates.",
            "Analyst override rate monitoring once pilot starts.",
        ],
        "draft_narrative": _narrative(stats, escaped),
    }
    audit.log("mrm", "mrm_draft_generated", {"limitations": len(limitations)}, actor="phase2")
    return doc


def _narrative(stats: dict, escaped: list) -> str:
    return (
        f"This draft covers Corridor Watch Phase 1 as of {datetime.now(timezone.utc).date()}. "
        f"The synthetic population contains {stats['accounts']} accounts and {stats['transactions']} transactions, "
        f"with {stats['flagged']} alerts above threshold. Named pattern distribution on scored accounts: "
        f"{json.dumps(stats['pattern_distribution'])}. "
        f"Red-team runs show {len(escaped)} currently documented evasion gaps that are listed as model limitations. "
        "This document is a first draft for MRM / validation review and is not a completed model approval package."
    )
