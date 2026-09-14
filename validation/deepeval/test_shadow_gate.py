def shadow_promote(v1: dict, v2: dict) -> bool:
    return (
        v2["agreement"] - v1["agreement"] >= 0.03
        and v2["hallucination"] - v1["hallucination"] <= 0
        and v2["cost"] <= v1["cost"] * 1.10
    )


def test_shadow_gate_rejects_costly_worse_model():
    v1 = {"agreement": 0.90, "hallucination": 0.02, "cost": 0.04}
    v2 = {"agreement": 0.91, "hallucination": 0.03, "cost": 0.08}
    assert shadow_promote(v1, v2) is False


def test_shadow_gate_promotes_better_cheaper():
    v1 = {"agreement": 0.85, "hallucination": 0.05, "cost": 0.05}
    v2 = {"agreement": 0.89, "hallucination": 0.04, "cost": 0.05}
    assert shadow_promote(v1, v2) is True
