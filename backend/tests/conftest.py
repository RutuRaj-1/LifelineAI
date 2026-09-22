import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("DATABASE_URL", f"sqlite:///{ROOT / 'backend' / 'test.db'}")
os.environ.setdefault("SIMULATE_TRAVEL", "false")  # keep tests deterministic/fast
os.environ.setdefault("PIPELINE_STEP_DELAY", "0")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db import Base, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _schema():
    engine.dispose()
    db_file = ROOT / "backend" / "test.db"
    if db_file.exists():
        try:
            db_file.unlink()
        except Exception:
            pass
    Base.metadata.create_all(bind=engine)
    yield
    engine.dispose()
    if db_file.exists():
        try:
            db_file.unlink()
        except Exception:
            pass


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c
