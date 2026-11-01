from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration, read from environment variables or a `.env` file."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    serpapi_key: SecretStr | None = None
    gemini_api_key: SecretStr | None = None
    # Gemini retires model IDs often; the alias tracks the current Flash model.
    gemini_model: str = "gemini-flash-latest"

    database_path: Path = Path("data/hr_news.db")
    # Host header allow-list; blocks DNS-rebinding requests against a local server.
    allowed_hosts: list[str] = ["127.0.0.1", "localhost", "testserver"]
    frontend_dist: Path = Path(__file__).resolve().parents[2] / "frontend" / "dist"

    analysis_batch_size: int = Field(default=8, ge=1, le=20)
    analysis_concurrency: int = Field(default=2, ge=1, le=8)
    http_timeout_seconds: float = Field(default=20.0, gt=0)


@lru_cache
def get_settings() -> Settings:
    return Settings()
