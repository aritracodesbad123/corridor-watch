"""Synthetic multi-institution banking world."""
from __future__ import annotations

from synthetic.banks import BANKS

CORRIDORS = [
    ("JP", "SG"),
    ("JP", "PH"),
    ("JP", "ID"),
    ("IN", "SG"),
    ("IN", "AE"),
    ("PH", "SG"),
    ("VN", "SG"),
    ("ID", "SG"),
    ("PH", "US"),
    ("IN", "HK"),
    ("AE", "HK"),
    ("SG", "AE"),
]

BANK_BY_COUNTRY = {b["country"]: b["bank_id"] for b in BANKS if b["institution_type"] == "bank"}
BANK_BY_COUNTRY.setdefault("US", "BANK_SG")


def bank_for(country: str) -> str:
    if country == "SG" and country in BANK_BY_COUNTRY:
        return BANK_BY_COUNTRY[country]
    return BANK_BY_COUNTRY.get(country, "PAYMENT_PROVIDER_X")


def seed_banks() -> int:
    from db import connect, init_schema

    init_schema()
    con = connect()
    for bank in BANKS:
        existing = con.execute("SELECT 1 FROM banks WHERE bank_id=?", (bank["bank_id"],)).fetchone()
        if existing:
            continue
        con.execute(
            "INSERT INTO banks (bank_id, name, country, institution_type) VALUES (?,?,?,?)",
            (bank["bank_id"], bank["name"], bank["country"], bank["institution_type"]),
        )
    con.commit()
    con.close()
    return len(BANKS)
