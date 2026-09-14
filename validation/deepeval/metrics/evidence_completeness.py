REQUIRED = {"E-TXN"}


def evidence_completeness(present_ids: set[str]) -> float:
    if not REQUIRED:
        return 1.0
    return len(REQUIRED & present_ids) / len(REQUIRED)
