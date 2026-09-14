def test_tool_names_are_declared():
    from agent import _tool_declarations
    names = {t.get("name") for t in _tool_declarations()}
    assert {"get_account_context", "get_shared_devices", "get_session_biometrics", "get_network_neighborhood"} <= names
