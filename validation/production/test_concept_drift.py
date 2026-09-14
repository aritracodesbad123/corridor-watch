from phase2_redteam import BUILTIN_NOVEL


def test_year_style_evasions_exist_as_drift_proxy():
    names = {p["inject"] for p in BUILTIN_NOVEL}
    assert {"time_jitter_smurf", "beneficiary_rotation", "device_hopping"} <= names
