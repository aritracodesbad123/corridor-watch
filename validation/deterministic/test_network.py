import json
from pathlib import Path

import networkx as nx
import pytest

from graph.network_metrics import partition_components, score_network
from graph_features import multi_hop_depth, pass_through_ratio

ROOT = Path(__file__).resolve().parents[2]


def test_network_recall_helper_and_artifact(eval_result):
    net = eval_result.get("network_metrics") or {}
    (ROOT / "reports" / "network_metrics.json").write_text(json.dumps(net, indent=2, default=str))
    (ROOT / "reports" / "network_recall.md").write_text(
        f"# Network recall\n\naccount={net.get('account_recall')} key_node={net.get('key_node_recall')} "
        f"reconstruction={net.get('relationship_reconstruction')} path={net.get('path_recovery')}\n"
    )
    pred = {"nodes": [{"id": "A"}, {"id": "B"}], "edges": [{"source": "A", "target": "B"}]}
    truth = {"nodes": {"A", "B", "C"}, "edges": [("A", "B"), ("B", "C")], "key_nodes": {"A"}}
    scored = score_network(pred, truth)
    assert scored["account_recall"]["recall"] == pytest.approx(2 / 3, abs=0.01)
    assert net.get("account_recall") is not None
    parts = partition_components([
        {"sender_id": "A", "receiver_id": "B"},
        {"sender_id": "B", "receiver_id": "C"},
        {"sender_id": "X", "receiver_id": "Y"},
    ])
    assert len(parts) == 2


def test_feature_fixtures():
    g = nx.DiGraph()
    g.add_edge("A", "M", amount=100, ts="2026-01-01T00:00:00")
    g.add_edge("B", "M", amount=100, ts="2026-01-01T00:01:00")
    g.add_edge("M", "C", amount=180, ts="2026-01-01T00:10:00")
    g.add_edge("C", "D", amount=170, ts="2026-01-01T00:20:00")
    assert g.in_degree("M") == 2
    assert g.out_degree("M") == 1
    assert pass_through_ratio(g, "M") == pytest.approx(0.9, abs=0.05)
    assert multi_hop_depth(g, "M") >= 1
