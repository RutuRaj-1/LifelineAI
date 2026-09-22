from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", str(ROOT / ".env")), extra="ignore")

    app_env: str = "development"
    database_url: str = f"sqlite:///{ROOT / 'backend' / 'lifeline.db'}"
    redis_url: str = ""
    jwt_secret: str = "change-me-in-production"
    jwt_expire_minutes: int = 60 * 12
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-small"

    google_maps_api_key: str = ""
    storage_backend: str = "local"  # local | firebase
    upload_dir: str = str(ROOT / "backend" / "uploads")
    firebase_storage_bucket: str = ""
    firebase_credentials_path: str = ""
    twilio_account_sid: str = ""  # SMS is mocked (logged) unless all three are set AND SMS_LIVE=true
    twilio_auth_token: str = ""
    twilio_from_number: str = ""

    simulate_travel: bool = True  # demo: move the patient towards the hospital automatically
    demo_tick_seconds: float = 4.0  # 1 simulated minute of travel per tick
    pipeline_step_delay: float = 1.2  # small pause between agent steps so live updates are visible in the demo


@lru_cache
def get_settings() -> Settings:
    return Settings()
