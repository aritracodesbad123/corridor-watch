from pathlib import Path

HTML = Path(__file__).resolve().parents[2] / "static" / "index.html"


def test_queue_tabs_explorer_and_dag_have_aria():
    text = HTML.read_text()
    assert 'id="rows" role="list" aria-label="Triage queue"' in text
    assert 'role="tablist"' in text
    assert 'role="tab"' in text
    assert 'aria-label="Filter by risk level"' in text
    assert 'aria-label="Search entity, account, or corridor"' in text
    assert 'aria-label="Zoom in"' in text
    assert 'role="img" aria-label=' in text
    assert ".tab:focus-visible" in text
    assert ".pill.high{background:var(--red-dim);color:var(--red)}" in text
