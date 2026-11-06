"""Runtime configuration. Every value can be set through the environment or backend/.env."""
import secrets
from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="NEXUS_", extra="ignore")

    env: Literal["dev", "test", "production"] = "dev"
    database_url: str = "sqlite:///./nexus.db"
    jwt_secret: str = ""
    jwt_ttl_minutes: int = 480
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    max_upload_bytes: int = 5 * 1024 * 1024
    max_lines_per_file: int = 50_000
    # Purchase orders above this value need an admin rather than an approver.
    po_admin_threshold: float = 5000.0

    # Optional. Without a key NEXUS uses its rule-based extractors and templated narrative,
    # and labels the output accordingly.
    openai_api_key: str = Field(default="", validation_alias="OPENAI_API_KEY")
    openai_model: str = "gpt-4o-mini"
    openai_timeout_seconds: float = 30.0

    @model_validator(mode="after")
    def _secret(self) -> "Settings":
        if not self.jwt_secret:
            if self.env == "production":
                raise ValueError("NEXUS_JWT_SECRET must be set in production")
            # Dev only: sessions end when the server restarts.
            self.jwt_secret = secrets.token_urlsafe(48)
        return self

    @property
    def demo_enabled(self) -> bool:
        return self.env != "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
