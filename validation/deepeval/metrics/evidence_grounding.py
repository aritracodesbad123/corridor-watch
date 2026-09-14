def evidence_grounding(claim_ids: list[str], allowed_ids: set[str]) -> float:
    if not claim_ids:
        return 1.0
    ok = sum(1 for c in claim_ids if c in allowed_ids)
    return ok / len(claim_ids)
