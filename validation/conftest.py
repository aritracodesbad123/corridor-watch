from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(autouse=True)
def local_runtime(request, monkeypatch):
    if getattr(request, "node", None) and request.node.name == "test_header_spoof_disabled_on_gcp":
        yield
        return
    monkeypatch.setenv("ENVIRONMENT", "local")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    from config import reset_settings_cache
    reset_settings_cache()
    yield
    reset_settings_cache()


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    import db
    from config import reset_settings_cache
    from db import init_schema
    from patterns.repository import seed_library

    monkeypatch.setattr(db, "DB_PATH", tmp_path / "validation.db")
    monkeypatch.setenv("ENVIRONMENT", "local")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    reset_settings_cache()
    init_schema()
    seed_library()
    yield
    reset_settings_cache()
