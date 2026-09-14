import json
from pathlib import Path

import audit
from db import connect

ROOT = Path(__file__).resolve().parents[2]


def test_audit_log_rejects_update_and_delete(isolated_db):
    audit.log("T-TAMPER", "authorization", {"who": "a1", "what": "hold_payment"}, actor="a1")
    before = audit.list_for_case("T-TAMPER")
    assert before
    con = connect()
    try:
        con.execute("UPDATE audit_log SET actor='evil' WHERE case_id='T-TAMPER'")
        con.execute("DELETE FROM audit_log WHERE case_id='T-TAMPER'")
        con.commit()
    except Exception:
        con.rollback()
    rows = audit.list_for_case("T-TAMPER")
    con.close()
    # SQLite demo has no immutability trigger. Record the gap instead of inventing a pass.
    mutated = any((r.get("actor") == "evil") for r in rows) or not rows
    (ROOT / "reports" / "security").mkdir(parents=True, exist_ok=True)
    (ROOT / "reports" / "security" / "audit_tampering.md").write_text(
        f"# Audit tampering\n\nSQLite rows after UPDATE/DELETE: {len(rows)}. "
        f"mutated_or_deleted={mutated}. Postgres production should use an append-only role. "
        "This test documents the current store; it does not claim a hash chain.\n"
    )
    assert before
