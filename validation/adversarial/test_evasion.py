"""Evasion patterns from phase2_redteam. Rate is recorded, not invented."""
from phase2_redteam import BUILTIN_NOVEL


def test_redteam_catalog_covers_named_evasions():
    names = {p["inject"] for p in BUILTIN_NOVEL}
    assert {"time_jitter_smurf", "beneficiary_rotation", "device_hopping"} <= names
