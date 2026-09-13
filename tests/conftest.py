from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(autouse=True)
def local_runtime(request, monkeypatch):
    """Keep unit tests on local SQLite even if the shell is ENVIRONMENT=gcp."""
    if getattr(request, "node", None) and request.node.name == "test_gcp_refuses_sqlite":
        yield
        return
    monkeypatch.setenv("ENVIRONMENT", "local")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    from config import reset_settings_cache
    reset_settings_cache()
    yield
    reset_settings_cache()
