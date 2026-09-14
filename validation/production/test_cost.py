import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_cost_fields_are_separated_from_hallucination():
    gem = json.loads((ROOT / "reports" / "gemini_agreement.json").read_text())
    hall = json.loads((ROOT / "reports" / "hallucination.json").read_text()) if (ROOT / "reports" / "hallucination.json").exists() else {}
    assert gem.get("cost_per_case_usd") is not None
    assert "hallucination" not in str(gem.get("cost_per_case_usd"))
    tokens = None
    cases = gem.get("cases") or []
    if cases:
        toks = [(c.get("prompt_tokens") or 0) + (c.get("completion_tokens") or 0) for c in cases]
        tokens = round(sum(toks) / len(toks), 1)
        gem["tokens_per_case"] = tokens
        (ROOT / "reports" / "gemini_agreement.json").write_text(json.dumps(gem, indent=2))
    (ROOT / "reports" / "cost.json").write_text(json.dumps({
        "usd_per_investigation": gem.get("cost_per_case_usd"),
        "tokens_per_case": tokens,
        "usd_per_1k_txn": None,
        "usd_per_alert": None,
        "note": "Per-investigation cost from live Gemini usage. Per-txn/alert NOT_MEASURED.",
        "hallucination_rate": hall.get("hallucination_rate"),
    }, indent=2))
    assert gem.get("cost_per_case_usd") != hall.get("hallucination_rate")
