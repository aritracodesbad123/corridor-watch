from graph.visibility import INFERRED, OBSERVED, UNKNOWN, annotate_network, visibility_score


def _net(frac_hidden: float) -> dict:
    nodes = [{"id": f"N{i}", "institution_id": "BANK_SG"} for i in range(10)]
    edges = [{"source": f"N{i}", "target": f"N{i+1}", "txn_id": f"T{i}"} for i in range(9)]
    hide = int(len(nodes) * frac_hidden)
    for node in nodes[:hide]:
        node["id"] = f"UNK-{node['id']}"
    return {"nodes": nodes, "edges": edges}


def test_visibility_sweep_and_overclaim():
    scores = {}
    for pct in (1.0, 0.75, 0.5, 0.25, 0.1):
        net = annotate_network(_net(1.0 - pct))
        scores[pct] = net["visibility"]["network_visibility_score"]
        for node in net["nodes"]:
            if node.get("visibility") == UNKNOWN:
                assert node.get("visibility") != "NO"
        for edge in net["edges"]:
            if edge.get("visibility") == INFERRED:
                assert edge.get("visibility") != OBSERVED
    assert scores[1.0] >= scores[0.1]
    vis = visibility_score(
        [{"visibility": UNKNOWN}, {"visibility": OBSERVED}],
        [{"visibility": INFERRED}],
    )
    assert vis["unknown"]["nodes"] >= 1
