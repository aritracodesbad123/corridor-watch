"""
Phase 2 — Adversarial red-team scenario generation.

Generates novel fraud patterns, injects them into the live Phase 1 pipeline,
and reports which evade detection and why. Continuous self-testing loop helper.
"""
from __future__ import annotations

import json
import random
import uuid
from datetime import datetime, timedelta, timezone

from db import connect, init_schema
import audit
from graph_features import score_all, write_scores
import agent as agent_mod

NOW = datetime(2026, 9, 1)
random.seed()


BUILTIN_NOVEL = [
    {
        "pattern_name": "smurfing_time_jitter",
        "description": "Many near-threshold credits spaced irregularly over 5 days into a mid-age account, then slow drip outflows.",
        "inject": "time_jitter_smurf",
    },
    {
        "pattern_name": "beneficiary_rotation_mule",
        "description": "Single mule with rotating beneficiaries each hop to dilute shared_beneficiary_count.",
        "inject": "beneficiary_rotation",
    },
    {
        "pattern_name": "dormant_reactivation_burst",
        "description": "Old low-risk account suddenly bursts high-value corridor activity after 400+ quiet days.",
        "inject": "dormant_burst",
    },
    {
        "pattern_name": "device_hopping_ring",
        "description": "Ring members rotate across fresh devices each txn to evade shared-device clustering.",
        "inject": "device_hopping",
    },
]


def _uid(prefix: str) -> str:
    return f"{prefix}{uuid.uuid4().hex[:8]}"


def _llm_novel_patterns(n: int = 2) -> list[dict]:
    if not agent_mod.gemini_available():
        return []
    try:
        from google.genai import types
        c = agent_mod.client()
        prompt = (
            "Propose novel cross-border remittance fraud patterns for red-team testing. "
            f"Return JSON list of {n} objects with keys pattern_name, description, inject_hint. "
            "Avoid classic pure fan-in mule and obvious shared-device rings. Synthetic/demo only."
        )
        resp = c.models.generate_content(
            model=agent_mod.active_model(),
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.8),
        )
        text = (resp.text or "").strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        data = json.loads(text)
        out = []
        for item in data:
            out.append({
                "pattern_name": item.get("pattern_name", "llm_novel"),
                "description": item.get("description", ""),
                "inject": item.get("inject_hint", "dormant_burst"),
            })
        return out
    except Exception:
        return []


def _insert_account(con, country, days_old, label):
    acc = {
        "account_id": _uid("RA"),
        "name": f"Redteam {label}",
        "country": country,
        "opened_date": (NOW - timedelta(days=days_old)).isoformat(),
        "occupation": "Contractor",
        "stated_income_usd": 22000,
        "kyc_tier": "standard",
        "fraud_label": f"redteam_{label}",
    }
    con.execute(
        "INSERT INTO accounts VALUES (:account_id,:name,:country,:opened_date,"
        ":occupation,:stated_income_usd,:kyc_tier,:fraud_label)",
        acc,
    )
    return acc


def _insert_device(con, days=1):
    d = {
        "device_id": _uid("RD"),
        "fingerprint": uuid.uuid4().hex[:16],
        "first_seen": (NOW - timedelta(days=days)).isoformat(),
        "os": "Android 14",
    }
    con.execute("INSERT INTO devices VALUES (:device_id,:fingerprint,:first_seen,:os)", d)
    return d


def _link_device(con, account_id, device_id):
    con.execute(
        "INSERT OR IGNORE INTO account_devices VALUES (?,?,?)",
        (account_id, device_id, NOW.isoformat()),
    )


def _insert_txn(con, sender, receiver, amount, corridor, ts, scenario, device_id=None):
    t = {
        "txn_id": _uid("RT"),
        "sender_id": sender,
        "receiver_id": receiver,
        "amount": round(amount, 2),
        "currency": "USD",
        "corridor": corridor,
        "ts": ts.isoformat(),
        "device_id": device_id,
        "session_id": None,
        "beneficiary_id": None,
        "purpose": "redteam",
        "source_of_funds": "redteam",
        "fraud_scenario": scenario,
    }
    con.execute(
        "INSERT INTO transactions VALUES (:txn_id,:sender_id,:receiver_id,:amount,:currency,"
        ":corridor,:ts,:device_id,:session_id,:beneficiary_id,:purpose,:source_of_funds,:fraud_scenario)",
        t,
    )
    return t


def inject_scenario(spec: dict) -> dict:
    init_schema()
    con = connect(row_factory=False)
    con.row_factory = None
    kind = spec.get("inject", "dormant_burst")
    created_txn_ids = []

    if kind == "time_jitter_smurf":
        sink = _insert_account(con, "SG", 120, kind)
        for i in range(14):
            feeder = _insert_account(con, "IN", 200, kind)
            ts = NOW - timedelta(days=random.randint(0, 5), hours=random.randint(0, 20))
            t = _insert_txn(con, feeder["account_id"], sink["account_id"], random.uniform(900, 990),
                            "IN->SG", ts, f"redteam:{spec['pattern_name']}")
            created_txn_ids.append(t["txn_id"])

    elif kind == "beneficiary_rotation":
        mule = _insert_account(con, "AE", 4, kind)
        for i in range(7):
            feeder = _insert_account(con, "PH", 3, kind)
            benef_ext = f"EXT-ROT-{i}-{uuid.uuid4().hex[:4]}"
            ts = NOW - timedelta(hours=i)
            t = _insert_txn(con, feeder["account_id"], mule["account_id"], random.uniform(400, 800),
                            "PH->AE", ts, f"redteam:{spec['pattern_name']}")
            created_txn_ids.append(t["txn_id"])
            t2 = _insert_txn(con, mule["account_id"], benef_ext, random.uniform(350, 750),
                             "AE->US", ts + timedelta(hours=1), f"redteam:{spec['pattern_name']}")
            created_txn_ids.append(t2["txn_id"])

    elif kind == "device_hopping":
        for i in range(5):
            acc = _insert_account(con, "ID", 5, kind)
            dev = _insert_device(con, days=1)
            _link_device(con, acc["account_id"], dev["device_id"])
            t = _insert_txn(con, acc["account_id"], f"EXT-HOP-{i}", random.uniform(800, 1800),
                            "ID->SG", NOW - timedelta(hours=i), f"redteam:{spec['pattern_name']}",
                            device_id=dev["device_id"])
            created_txn_ids.append(t["txn_id"])

    else:  # dormant_burst
        acc = _insert_account(con, "VN", 500, kind)
        for i in range(6):
            t = _insert_txn(con, acc["account_id"], f"EXT-BURST-{i}", random.uniform(3000, 7000),
                            "VN->US", NOW - timedelta(hours=i), f"redteam:{spec['pattern_name']}")
            created_txn_ids.append(t["txn_id"])

    con.commit()
    con.close()
    return {"txn_ids": created_txn_ids, "pattern_name": spec["pattern_name"]}


def evaluate_detection(txn_ids: list[str]) -> dict:
    con = connect()
    scores, txns, _ = score_all(con)
    write_scores(con, scores, txns)
    flagged = {
        r["txn_id"] for r in con.execute("SELECT txn_id FROM flagged_transactions").fetchall()
    }
    con.close()
    detected_ids = [t for t in txn_ids if t in flagged]
    return {
        "detected": len(detected_ids) > 0,
        "detected_count": len(detected_ids),
        "total_injected": len(txn_ids),
        "detected_ids": detected_ids,
    }


def run_redteam(include_llm: bool = True, max_scenarios: int = 3) -> dict:
    specs = list(BUILTIN_NOVEL)
    if include_llm:
        specs = _llm_novel_patterns(2) + specs
    specs = specs[:max_scenarios]
    results = []
    for spec in specs:
        injected = inject_scenario(spec)
        det = evaluate_detection(injected["txn_ids"])
        evasion = None
        if not det["detected"]:
            evasion = (
                f"None of {det['total_injected']} injected txns exceeded flag threshold; "
                f"pattern '{spec['pattern_name']}' likely under-weighted by current features."
            )
        scenario_id = _uid("RS")
        payload = {"spec": spec, "injected": injected, "detection": det}
        con = connect(row_factory=False)
        con.execute(
            """INSERT INTO redteam_scenarios
               (scenario_id, created_at, pattern_name, description, injected, detected, evasion_reason, payload)
               VALUES (?,?,?,?,?,?,?,?)""",
            (
                scenario_id,
                datetime.now(timezone.utc).isoformat(),
                spec["pattern_name"],
                spec.get("description", ""),
                1,
                1 if det["detected"] else 0,
                evasion,
                json.dumps(payload),
            ),
        )
        con.commit()
        con.close()
        row = {
            "scenario_id": scenario_id,
            "pattern_name": spec["pattern_name"],
            "description": spec.get("description"),
            "detected": det["detected"],
            "detection": det,
            "evasion_reason": evasion,
        }
        results.append(row)
        audit.log("redteam", "scenario_result", row, actor="phase2")

    summary = {
        "ran": len(results),
        "detected": sum(1 for r in results if r["detected"]),
        "evaded": sum(1 for r in results if not r["detected"]),
        "results": results,
        "requires_human_review": True,
        "note": "Red-team injections mutate the local synthetic DB; re-run data_gen.py to reset.",
    }
    return summary


def list_scenarios(limit: int = 50) -> list[dict]:
    init_schema()
    con = connect()
    rows = con.execute(
        "SELECT scenario_id, created_at, pattern_name, description, injected, detected, evasion_reason "
        "FROM redteam_scenarios ORDER BY created_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]


def reset_redteam() -> dict:
    """Wipe injected red-team transactions/accounts and restore dataset to baseline."""
    init_schema()
    con = connect(row_factory=False)
    con.execute("DELETE FROM transactions WHERE purpose='redteam' OR fraud_scenario LIKE 'redteam%'")
    con.execute("DELETE FROM accounts WHERE fraud_label LIKE 'redteam%' OR account_id LIKE 'RA%'")
    con.execute("DELETE FROM devices WHERE device_id LIKE 'RD%'")
    con.execute("DELETE FROM account_devices WHERE account_id LIKE 'RA%' OR device_id LIKE 'RD%'")
    con.execute("DELETE FROM redteam_scenarios")
    con.commit()
    con.close()

    con = connect()
    scores, txns, _ = score_all(con)
    write_scores(con, scores, txns)
    con.close()

    audit.log("redteam", "redteam_reset", {"ok": True}, actor="phase2")
    return {
        "ok": True,
        "message": "Red-team scenario injections wiped and baseline synthetic database restored.",
    }

