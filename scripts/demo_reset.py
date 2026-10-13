#!/usr/bin/env python3
"""Wipe fraud_demo.db and re-seed the exact hackathon demo starting state."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    db = Path(os.environ.get("CW_DB_PATH") or ROOT / "fraud_demo.db")
    for p in (db, Path(str(db) + "-wal"), Path(str(db) + "-shm")):
        if p.exists():
            p.unlink()
            print(f"removed {p}")

    os.environ["CW_DB_PATH"] = str(db)
    from db import init_schema
    from patterns.repository import seed_library
    from phase2_memory import seed_if_empty
    from synthetic.middle_bank import seed_middle_bank
    from synthetic.showcase import seed_showcase
    from synthetic.world import seed_banks

    init_schema()
    seed_if_empty()
    seed_banks()
    seed_library()
    seed_showcase()
    seed_middle_bank()
    print(f"demo-reset ok → {db}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
