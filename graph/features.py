"""Network feature helpers for a bounded transaction set."""
from __future__ import annotations

from collections import defaultdict


def network_features(txns: list[dict], focus_accounts: set[str]) -> dict:
    fan_in: dict[str, int] = defaultdict(int)
    fan_out: dict[str, int] = defaultdict(int)
    devices: dict[str, set[str]] = defaultdict(set)
    benefs: dict[str, set[str]] = defaultdict(set)
    banks: set[str] = set()
    countries: set[str] = set()
    for t in txns:
        fan_out[t["sender_id"]] += 1
        fan_in[t["receiver_id"]] += 1
        if t.get("device_id"):
            devices[t["device_id"]].add(t["sender_id"])
        if t.get("beneficiary_id"):
            benefs[t["beneficiary_id"]].add(t["sender_id"])
        for key in ("origin_bank_id", "destination_bank_id"):
            if t.get(key):
                banks.add(t[key])
        corridor = t.get("corridor") or ""
        if "->" in corridor:
            a, b = corridor.split("->", 1)
            countries.add(a)
            countries.add(b)
    shared_device = sum(1 for peers in devices.values() if len(peers) > 1)
    shared_benef = sum(1 for peers in benefs.values() if len(peers) > 1)
    focus_fan_in = sum(fan_in[a] for a in focus_accounts)
    focus_fan_out = sum(fan_out[a] for a in focus_accounts)
    return {
        "txn_count": len(txns),
        "account_count": len({t["sender_id"] for t in txns} | {t["receiver_id"] for t in txns}),
        "fan_in": focus_fan_in,
        "fan_out": focus_fan_out,
        "shared_device_groups": shared_device,
        "shared_beneficiary_groups": shared_benef,
        "institution_count": len(banks),
        "country_count": len(countries),
        "cross_border": sum(1 for t in txns if "->" in (t.get("corridor") or "") and t["corridor"].split("->")[0] != t["corridor"].split("->")[-1]),
    }
