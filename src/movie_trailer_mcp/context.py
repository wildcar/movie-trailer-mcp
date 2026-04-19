"""Application context: long-lived clients + cache for the MCP server."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

from .cache import SQLiteCache
from .clients.tmdb import TMDBClient
from .clients.youtube import YouTubeClient
from .config import Settings


@dataclass
class AppContext:
    """Everything tool implementations need. Clients are ``None`` when their
    credentials aren't configured — tools should check and degrade gracefully.
    """

    settings: Settings
    cache: SQLiteCache
    tmdb: TMDBClient | None
    youtube: YouTubeClient | None


@asynccontextmanager
async def build_app_context(settings: Settings) -> AsyncIterator[AppContext]:
    cache = SQLiteCache(settings.cache_path)
    await cache.open()

    tmdb = TMDBClient(settings.tmdb_api_token) if settings.tmdb_api_token else None
    youtube = YouTubeClient(settings.youtube_api_key) if settings.youtube_api_key else None

    try:
        yield AppContext(settings=settings, cache=cache, tmdb=tmdb, youtube=youtube)
    finally:
        if tmdb is not None:
            await tmdb.aclose()
        if youtube is not None:
            await youtube.aclose()
        await cache.close()
