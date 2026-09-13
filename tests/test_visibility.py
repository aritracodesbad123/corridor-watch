"""Cross-institution visibility, intelligence, and middle-bank tests."""
from __future__ import annotations

from fastapi.testclient import TestClient

from graph.visibility import OBSERVED, EXTERNAL, INFERRED, UNKNOWN, annotate_network, classify_account, visibility_score
from intelligence.provider import ingest_signal, simulate_resolution
from intelligence.schemas import IntelligenceSignal
from patterns.matcher import match_patterns
from synthetic.middle_bank import HERO_TXN_ID, seed_middle_bank


def test_observed_nodes():
    meta = classify_account("ACC-HOME", {"ACC-HOME": {"bank_id": "BANK_SG"}})
    assert meta["visibility"] == OBSERVED
    assert meta["entity_type"] == "INTERNAL_ACCOUNT"


def test_external_nodes():
    meta = classify_account("EXT-MID-HK-D", {}, {"EXT-MID-HK-D"})
    assert meta["visibility"] == EXTERNAL
    assert meta["source"] == "external_intelligence"


def test_inferred_nodes():
    network = {
        "nodes": [{"id": "A", "kind": "account"}, {"id": "B", "kind": "account"}],
        "edges": [{"source": "A", "target": "B", "relationship_type": "POSSIBLE_LINK"}],
    }
    annotate_network(network, accounts={"A": {"bank_id": "BANK_SG"}})
    inferred = [e for e in network["edges"] if e.get("visibility") == INFERRED]
    assert inferred
    assert inferred[0]["relationship_type"] == "POSSIBLE_LINK"


def test_unknown_boundaries():
    meta = classify_account("UNK-DOWNSTREAM")
    assert meta["visibility"] == UNKNOWN


def test_visibility_score():
    score = visibility_score(
        [{"visibility": OBSERVED}, {"visibility": OBSERVED}, {"visibility": UNKNOWN}],
        [{"visibility": OBSERVED}, {"visibility": INFERRED}],
        [{"boundary_id": "BOUNDARY-01"}],
    )
    assert 0 <= score["network_visibility_score"] <= 1
    assert score["label"] == "visibility_indicator"
    assert score["unknown"]["boundaries"] == 1


def test_external_boundary_edge(isolated_db):
    seed_middle_bank()
    from graph.investigator import bounded_network
    from investigations.service import load_txn
    network = bounded_network(load_txn(HERO_TXN_ID))
    assert any(e.get("relationship_type") == "TRANSFER" for e in network["edges"])
    assert network["visibility"]["network_visibility_score"] is not None
    assert network["partial_network"] is True
    assert any(n.get("visibility") == UNKNOWN for n in network["nodes"]) or network["boundaries"]


def test_partial_network(isolated_db):
    seed_middle_bank()
    from graph.investigator import bounded_network
    from investigations.service import load_txn
    network = bounded_network(load_txn(HERO_TXN_ID))
    banks = {n.get("institution_id") for n in network["nodes"] if n.get("institution_id")}
    assert "BANK_SG" in banks
    assert "BANK_HK" not in banks or any(n.get("visibility") == UNKNOWN for n in network["nodes"])


def test_inferred_edge_is_labeled():
    network = {"nodes": [{"id": "X"}], "edges": [{"source": "X", "target": "Y", "relationship_type": "POSSIBLE_LINK"}]}
    annotate_network(network)
    edge = network["edges"][0]
    assert edge["visibility"] == INFERRED
    assert edge["visibility"] != OBSERVED


def test_cross_institution_graph(isolated_db):
    seed_middle_bank()
    from graph.investigator import bounded_network
    from investigations.service import load_txn
    network = bounded_network(load_txn(HERO_TXN_ID))
    assert len(network.get("institutions") or []) >= 2


def test_external_signal_ingestion(isolated_db):
    saved = ingest_signal({
        "intelligence_id": "INT-TEST-1",
        "source_institution": "BANK_C",
        "entity_type": "ACCOUNT",
        "entity_reference": "EXT-88321",
        "signal_type": "confirmed_mule",
        "confidence": 0.91,
        "pattern_id": "CW-007",
    }, actor="test")
    assert saved["intelligence_id"] == "INT-TEST-1"
    assert "name" not in saved
    assert "account_number" not in saved


def test_external_signal_updates_investigation(isolated_db):
    seed_middle_bank()
    from graph.investigator import bounded_network
    from investigations.service import load_txn
    before = bounded_network(load_txn(HERO_TXN_ID))
    simulate_resolution(actor="test")
    after = bounded_network(load_txn(HERO_TXN_ID))
    refs = {n.get("id") for n in after["nodes"]}
    assert "EXT-MID-HK-D" in refs
    assert after["visibility"]["external"]["nodes"] >= before["visibility"]["external"]["nodes"]


def test_external_signal_updates_pattern(isolated_db):
    seed_middle_bank()
    txn = {"txn_id": HERO_TXN_ID, "sender_id": "ACC-MID-SG-MULE", "receiver_id": "ACC-MID-PH-EXIT", "corridor": "SG->PH", "fraud_scenario": "mule_pass_through"}
    network = {
        "features": {
            "fan_in": 6, "fan_out": 2, "shared_device_groups": 1,
            "shared_beneficiary_groups": 0, "cross_border": 2, "institution_count": 3, "txn_count": 4,
        },
        "visibility": {"network_visibility_score": 0.54},
    }
    matches = match_patterns(txn, network, {"account_age_days": 16, "pass_through_ratio": 0.98, "avg_hold_time_minutes": 18}, persist=False)
    assert matches
    assert any(m.get("institutional_scope") == "CROSS_INSTITUTION" for m in matches)
    assert "evidence_coverage" in matches[0]
    assert "missing_expected_signals" in matches[0]


def test_prompt_contains_visibility():
    from agent import GROUNDED_SYSTEM_PROMPT
    assert "UNKNOWN" in GROUNDED_SYSTEM_PROMPT
    assert "visibility" in GROUNDED_SYSTEM_PROMPT.lower()
    assert "invent" in GROUNDED_SYSTEM_PROMPT.lower()


def test_unknown_not_presented_as_fact():
    from agent import GROUNDED_SYSTEM_PROMPT
    assert "Never present an inference or unknown hop as an observed fact" in GROUNDED_SYSTEM_PROMPT


def test_evidence_ids_required():
    from agent import GROUNDED_SYSTEM_PROMPT
    assert "evidence_id" in GROUNDED_SYSTEM_PROMPT


def test_unauthorized_intelligence_access():
    from main import app
    client = TestClient(app)
    denied = client.get("/api/intelligence", headers={"X-Analyst-Role": "nobody"})
    assert denied.status_code in {401, 403}
    analyst = client.post(
        "/api/intelligence/simulate",
        headers={"X-Analyst-Role": "analyst", "X-Analyst-ID": "a1"},
    )
    assert analyst.status_code == 403


def test_shared_signal_does_not_expose_raw_customer_data():
    signal = IntelligenceSignal(
        intelligence_id="INT-PRIV",
        source_institution="BANK_C",
        entity_reference="EXT-88321",
        signal_type="confirmed_mule",
        confidence=0.9,
    )
    public = signal.public_dict()
    blob = str(public).lower()
    assert "passport" not in blob
    assert "ssn" not in blob
    assert set(public) <= {
        "intelligence_id", "source_institution", "entity_type", "entity_reference",
        "signal_type", "confidence", "pattern_id", "sharing_tier", "visibility",
        "timestamp", "notes",
    }


def test_visibility_api(isolated_db):
    seed_middle_bank()
    from main import app
    client = TestClient(app)
    res = client.get(f"/api/investigations/{HERO_TXN_ID}/visibility", headers={"X-Analyst-Role": "analyst"})
    assert res.status_code == 200
    body = res.json()
    assert "network_visibility_score" in body
    assert body["note"].startswith("Visibility")
    fiu = client.post("/api/intelligence/simulate", headers={"X-Analyst-Role": "fiu_lead", "X-Analyst-ID": "lead"})
    assert fiu.status_code == 200
