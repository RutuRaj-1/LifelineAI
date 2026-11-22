import pytest
from app.config import DEFAULT_DEV_JWT_SECRET, Settings


def test_default_settings():
    s = Settings(_env_file=None)
    assert s.app_env in ("development", "test")
    assert len(s.jwt_secret.encode("utf-8")) >= 32
    assert s.jwt_algorithm == "HS256"


def test_production_rejects_default_dev_secret():
    with pytest.raises(ValueError, match="Production environment requires a custom"):
        Settings(
            _env_file=None,
            app_env="production",
            jwt_secret=DEFAULT_DEV_JWT_SECRET,
        )


def test_production_rejects_legacy_placeholder():
    with pytest.raises(ValueError, match="Production environment requires a custom"):
        Settings(
            _env_file=None,
            app_env="production",
            jwt_secret="change-me-in-production",
        )


def test_production_rejects_short_secret():
    with pytest.raises(ValueError, match="at least 32 bytes"):
        Settings(
            _env_file=None,
            app_env="production",
            jwt_secret="short-key-12345",
        )


def test_production_accepts_strong_secret():
    valid_secret = "a" * 32
    s = Settings(
        _env_file=None,
        app_env="production",
        jwt_secret=valid_secret,
    )
    assert s.jwt_secret == valid_secret


def test_development_mode_allows_dev_secret():
    s = Settings(
        _env_file=None,
        app_env="development",
        jwt_secret=DEFAULT_DEV_JWT_SECRET,
    )
    assert s.jwt_secret == DEFAULT_DEV_JWT_SECRET
