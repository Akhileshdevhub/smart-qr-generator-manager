"""Application configuration.

All settings are read from environment variables (loaded from a local .env
file in development). Nothing secret is hard-coded here so the same code can
run locally on SQLite and in production on PostgreSQL just by changing the
environment. See .env.example for the full list of variables.
"""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Absolute path to the project root (the folder that contains this app/ package).
# Used to locate the frontend/ directory regardless of the current working dir.
PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    # --- Core ---
    environment: str = "development"           # "development" or "production"
    secret_key: str = "dev-only-change-me"     # used to sign JWTs; MUST be overridden in production
    # Public base URL of the app. Dynamic QR codes encode "<base_url>/r/<short_id>",
    # so this value is literally baked into every printed dynamic QR image.
    base_url: str = "http://localhost:8000"

    # --- Auth ---
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24  # 24h; short-lived enough for a demo, simple to reason about

    # --- Database ---
    # SQLite by default so the project runs with zero setup. Point DATABASE_URL at
    # a PostgreSQL instance (postgresql+psycopg://...) for production.
    database_url: str = f"sqlite:///{PROJECT_ROOT / 'qr_app.db'}"

    # --- Uploads / limits ---
    max_logo_bytes: int = 2 * 1024 * 1024      # 2 MB cap on uploaded logos
    max_logo_dimension: int = 2000             # reject absurdly large images (px)

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance.

    Cached so the .env file is parsed once per process and tests can override
    it via dependency injection instead of re-reading the file each request.
    """
    return Settings()


settings = get_settings()
