def verdict_stability(verdicts: list[str]) -> float:
    if len(verdicts) < 2:
        return 0.0
    mode = max(set(verdicts), key=verdicts.count)
    return 1.0 - (verdicts.count(mode) / len(verdicts))
