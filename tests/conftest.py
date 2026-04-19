"""Shared test fixtures."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest_asyncio

from movie_trailer_mcp.cache import SQLiteCache
from movie_trailer_mcp.clients.tmdb import TMDBClient
from movie_trailer_mcp.clients.youtube import YouTubeClient
from movie_trailer_mcp.config import Settings
from movie_trailer_mcp.context import AppContext


@pytest_asyncio.fixture
async def settings(tmp_path: Path) -> Settings:
    return Settings(
        tmdb_api_token="test-tmdb-token",
        youtube_api_key="test-yt-key",
        mcp_auth_token=None,
        cache_path=tmp_path / "cache.sqlite",
        cache_ttl_seconds=60,
    )


@pytest_asyncio.fixture
async def app_ctx(settings: Settings) -> AsyncIterator[AppContext]:
    cache = SQLiteCache(settings.cache_path)
    await cache.open()
    tmdb = TMDBClient(settings.tmdb_api_token or "t")
    youtube = YouTubeClient(settings.youtube_api_key or "k")
    try:
        yield AppContext(settings=settings, cache=cache, tmdb=tmdb, youtube=youtube)
    finally:
        await tmdb.aclose()
        await youtube.aclose()
        await cache.close()
