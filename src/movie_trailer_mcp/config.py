"""Runtime configuration loaded from env + .env."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    tmdb_api_token: str | None = Field(
        None, description="TMDB v4 Read Access Token (same key as movie-metadata-mcp)."
    )
    youtube_api_key: str | None = Field(
        None, description="Optional YouTube Data API v3 key used as fallback."
    )
    mcp_auth_token: str | None = Field(
        None, description="Bearer token required for HTTP transports."
    )
    cache_path: Path = Field(Path(".cache/movie_trailer.sqlite"))
    cache_ttl_seconds: int = Field(
        21_600, ge=60, description="TTL for cached trailer lookups (default 6h)."
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
