"""Live integration smoke tests — skipped unless credentials are present."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio

from movie_trailer_mcp.cache import SQLiteCache
from movie_trailer_mcp.clients.tmdb import TMDBClient
from movie_trailer_mcp.clients.youtube import YouTubeClient
from movie_trailer_mcp.config import Settings
from movie_trailer_mcp.context import AppContext
from movie_trailer_mcp.tools import find_trailer_impl

pytestmark = pytest.mark.integration


@pytest_asyncio.fixture
async def live_ctx(tmp_path) -> AsyncIterator[AppContext]:  # type: ignore[no-untyped-def]
    settings = Settings(
        tmdb_api_token=os.getenv("TMDB_API_TOKEN"),
        youtube_api_key=os.getenv("YOUTUBE_API_KEY"),
        cache_path=tmp_path / "c.sqlite",
    )
    cache = SQLiteCache(settings.cache_path)
    await cache.open()
    tmdb = TMDBClient(settings.tmdb_api_token) if settings.tmdb_api_token else None
    youtube = YouTubeClient(settings.youtube_api_key) if settings.youtube_api_key else None
    try:
        yield AppContext(settings=settings, cache=cache, tmdb=tmdb, youtube=youtube)
    finally:
        if tmdb:
            await tmdb.aclose()
        if youtube:
            await youtube.aclose()
        await cache.close()


@pytest.mark.skipif(not os.getenv("TMDB_API_TOKEN"), reason="TMDB_API_TOKEN not set")
async def test_find_trailer_live_dune(live_ctx: AppContext) -> None:
    resp = await find_trailer_impl(live_ctx, "tt1160419", language="ru")
    assert resp.error is None
    assert resp.results
    assert all(t.url.startswith("https://www.youtube.com/watch?v=") for t in resp.results)
