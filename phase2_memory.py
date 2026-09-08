"""
Phase 2 — Institutional case memory (lightweight RAG).

Stores prior investigated cases + outcomes; retrieves similar precedents by
token overlap on pattern/corridor/summary (no external vector DB required for MVP).
"""
from __future__ import annotations

import json
import re
import uuid
from collections import Counter
from datetime import datetime, timezone

from db import connect, init_schema
import audit


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


import math


def _tokenize(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9_]+", (text or "").lower()) if len(t) > 2]


SEED_CASES = [
    {
        "pattern": "mule_pass_through",
        "summary": "Fresh SG account received 8 sub-threshold IN remittances then forwarded 95% to AE collector within 24h.",
        "outcome": "payment_held_kyc_escalated",
        "corridor": "IN->SG",
        "risk_level": "high",
    },
    {
        "pattern": "shared_device_ring",
        "summary": "Five unrelated PH senders shared one Android fingerprint and burst-sent to US beneficiaries same day.",
        "outcome": "accounts_frozen_device_blocklisted",
        "corridor": "PH->US",
        "risk_level": "high",
    },
    {
        "pattern": "synthetic_identity",
        "summary": "Student/unemployed profile in AE received multiple $5k+ inflows inconsistent with stated income.",
        "outcome": "enhanced_due_diligence_requested",
        "corridor": "??->AE",
        "risk_level": "high",
    },
    {
        "pattern": "split_transaction_laundering",
        "summary": "Twelve feeders sent $480-$990 into one sink sharing a common beneficiary within 24 hours.",
        "outcome": "sar_drafted_human_approved",
        "corridor": "ID->SG",
        "risk_level": "high",
    },
    {
        "pattern": "multi_hop_chain",
        "summary": "Funds layered across four owned accounts over 18 hours with short hold times before exit.",
        "outcome": "network_case_opened",
        "corridor": "VN->US",
        "risk_level": "medium",
    },
    {
        "pattern": "elevated_activity",
        "summary": "Legitimate SME payroll corridor spike during festival season; SoF docs matched invoices.",
        "outcome": "cleared_false_positive",
        "corridor": "IN->SG",
        "risk_level": "low",
    },
]


def seed_if_empty() -> int:
    init_schema()
    con = connect()
    n = con.execute("SELECT COUNT(*) AS c FROM case_memory").fetchone()["c"]
    if n:
        con.close()
        return 0
    for c in SEED_CASES:
        remember(
            pattern=c["pattern"],
            summary=c["summary"],
            outcome=c["outcome"],
            corridor=c["corridor"],
            risk_level=c["risk_level"],
            case_id=str(uuid.uuid4())[:10],
        )
    return len(SEED_CASES)


def remember(pattern: str, summary: str, outcome: str, corridor: str = "",
             risk_level: str = "medium", case_id: str | None = None) -> str:
    init_schema()
    case_id = case_id or str(uuid.uuid4())[:10]
    embedding_text = f"{pattern} {corridor} {risk_level} {summary} {outcome}"
    con = connect(row_factory=False)
    con.execute(
        """INSERT OR REPLACE INTO case_memory
           (case_id, pattern, summary, outcome, corridor, risk_level, created_at, embedding_text)
           VALUES (?,?,?,?,?,?,?,?)""",
        (case_id, pattern, summary, outcome, corridor, risk_level, _now(), embedding_text),
    )
    con.commit()
    con.close()
    return case_id


def _vector_cosine_tfidf(query_tokens: list[str], docs: list[dict]) -> list[float]:
    """Calculate TF-IDF weighted vector cosine similarity between query and all docs."""
    doc_token_lists = [_tokenize(d.get("embedding_text", "")) for d in docs]
    n_docs = len(docs) + 1
    df = Counter()
    for tokens in doc_token_lists + [query_tokens]:
        for token in set(tokens):
            df[token] += 1

    idf = {term: math.log((n_docs + 1) / (count + 1)) + 1 for term, count in df.items()}

    q_counts = Counter(query_tokens)
    q_len = len(query_tokens) or 1
    q_vec = {t: (cnt / q_len) * idf.get(t, 1.0) for t, cnt in q_counts.items()}
    q_norm = math.sqrt(sum(val ** 2 for val in q_vec.values())) or 1.0

    scores = []
    for doc_tokens in doc_token_lists:
        if not doc_tokens or not query_tokens:
            scores.append(0.0)
            continue
        d_counts = Counter(doc_tokens)
        d_len = len(doc_tokens)
        d_vec = {t: (cnt / d_len) * idf.get(t, 1.0) for t, cnt in d_counts.items()}
        d_norm = math.sqrt(sum(val ** 2 for val in d_vec.values())) or 1.0

        dot_product = sum(q_vec[t] * d_vec[t] for t in q_vec if t in d_vec)
        scores.append(dot_product / (q_norm * d_norm))

    return scores


def retrieve(query: str, limit: int = 5) -> list[dict]:
    seed_if_empty()
    con = connect()
    rows = [dict(r) for r in con.execute("SELECT * FROM case_memory").fetchall()]
    con.close()
    q_tokens = _tokenize(query)
    scores = _vector_cosine_tfidf(q_tokens, rows)
    ranked = []
    for r, s in zip(rows, scores):
        if r.get("pattern") and r["pattern"] in query:
            s += 0.30
        ranked.append({**r, "similarity": round(s, 4)})
    ranked.sort(key=lambda x: x["similarity"], reverse=True)
    return ranked[:limit]


def precedent_brief(txn_id: str) -> dict:
    con = connect()
    txn = con.execute("SELECT * FROM flagged_transactions WHERE txn_id=?", (txn_id,)).fetchone()
    verdict_row = con.execute("SELECT verdict FROM verdicts WHERE txn_id=?", (txn_id,)).fetchone()
    con.close()
    if not txn:
        raise ValueError("transaction not found")
    txn = dict(txn)
    pattern = txn.get("primary_pattern") or ""
    corridor = txn.get("corridor") or ""
    extra = ""
    if verdict_row:
        try:
            v = json.loads(verdict_row["verdict"])
            extra = v.get("rationale", "")
            pattern = pattern or v.get("primary_pattern", "")
        except json.JSONDecodeError:
            pass
    query = f"{pattern} {corridor} {extra} remittance mule device"
    hits = retrieve(query, limit=5)
    outcomes = Counter(h["outcome"] for h in hits)
    brief = {
        "txn_id": txn_id,
        "query": query,
        "precedents": hits,
        "outcome_distribution": dict(outcomes),
        "summary": (
            f"Retrieved {len(hits)} similar prior cases for pattern '{pattern}' on corridor '{corridor}'. "
            f"Most common prior outcome: {outcomes.most_common(1)[0][0] if outcomes else 'n/a'}."
        ),
        "requires_human_review": True,
    }
    audit.log(txn_id, "case_memory_retrieve", {"hits": len(hits)}, actor="phase2")
    return brief


def remember_from_decision(txn_id: str, decision: str, notes: str = "") -> str:
    con = connect()
    txn = con.execute("SELECT * FROM flagged_transactions WHERE txn_id=?", (txn_id,)).fetchone()
    verd = con.execute("SELECT verdict FROM verdicts WHERE txn_id=?", (txn_id,)).fetchone()
    con.close()
    if not txn:
        raise ValueError("transaction not found")
    txn = dict(txn)
    rationale = ""
    pattern = txn.get("primary_pattern") or "elevated_activity"
    risk_level = "medium"
    if verd:
        try:
            v = json.loads(verd["verdict"])
            rationale = v.get("rationale", "")
            pattern = v.get("primary_pattern", pattern)
            risk_level = v.get("risk_level", risk_level)
        except json.JSONDecodeError:
            pass
    summary = f"Txn {txn_id} ${txn['amount']} {txn['corridor']}. {rationale} Analyst: {decision}. {notes}".strip()
    cid = remember(pattern, summary, decision, txn.get("corridor", ""), risk_level, case_id=txn_id)
    audit.log(txn_id, "case_memory_store", {"case_id": cid, "decision": decision}, actor="phase2")
    return cid
