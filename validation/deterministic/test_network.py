import networkx as nx
import pytest

from graph_features import multi_hop_depth, pass_through_ratio


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
