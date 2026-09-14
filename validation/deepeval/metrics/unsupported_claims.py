def unsupported_claims(claim_ids: list[str], allowed_ids: set[str]) -> float:
    if not claim_ids:
        return 0.0
    bad = sum(1 for c in claim_ids if c not in allowed_ids)
    return bad / len(claim_ids)
