import pytest
from app.db import SessionLocal, check_db_health, get_db


def test_check_db_health():
    assert check_db_health() is True


def test_get_db_session_lifecycle():
    generator = get_db()
    session = next(generator)
    assert session is not None
    assert session.is_active

    # Closing generator cleans up session
    try:
        next(generator)
    except StopIteration:
        pass


def test_get_db_rollback_on_exception():
    generator = get_db()
    session = next(generator)

    # Simulate an unhandled exception inside the request context
    with pytest.raises(RuntimeError, match="Simulated database error"):
        try:
            raise RuntimeError("Simulated database error")
        except Exception as exc:
            generator.throw(exc)


def test_health_endpoint_reports_database(client):
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["database"] == "connected"
    assert "version" in data
