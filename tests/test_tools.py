"""Tool-level tests with respx-mocked HTTP."""

from __future__ import annotations

import httpx
import respx

from movie_trailer_mcp.clients.tmdb import TMDB_BASE_URL
from movie_trailer_mcp.clients.youtube import YOUTUBE_BASE_URL
from movie_trailer_mcp.context import AppContext
from movie_trailer_mcp.tools import find_trailer_impl, search_trailer_by_title_impl


def _stub_find_movie(respx_mock: respx.MockRouter, imdb: str, tmdb_id: int) -> None:
    respx_mock.get(f"{TMDB_BASE_URL}/find/{imdb}").mock(
        return_value=httpx.Response(
            200,
            json={"movie_results": [{"id": tmdb_id}], "tv_results": []},
        )
    )


def _stub_videos_movie(
    respx_mock: respx.MockRouter, tmdb_id: int, videos: list[dict]
) -> None:
    respx_mock.get(f"{TMDB_BASE_URL}/movie/{tmdb_id}/videos").mock(
        return_value=httpx.Response(200, json={"results": videos})
    )


async def test_find_trailer_happy_path(app_ctx: AppContext, respx_mock: respx.MockRouter) -> None:
    _stub_find_movie(respx_mock, "tt1160419", 438631)
    videos = [
        {
            "key": "n9xhJrPXop4",
            "name": "Дюна — трейлер",
            "iso_639_1": "ru",
            "type": "Trailer",
            "site": "YouTube",
            "published_at": "2021-07-22T15:00:00.000Z",
        },
        {
            "key": "8g18jFHCLXk",
            "name": "Dune — Official Trailer",
            "iso_639_1": "en",
            "type": "Trailer",
            "site": "YouTube",
            "published_at": "2020-09-09T15:00:00.000Z",
        },
        {
            "key": "teaserKEY",
            "name": "Dune — Teaser",
            "iso_639_1": "en",
            "type": "Teaser",
            "site": "YouTube",
            "published_at": "2020-06-01T15:00:00.000Z",
        },
    ]
    _stub_videos_movie(respx_mock, 438631, videos)

    resp = await find_trailer_impl(app_ctx, "tt1160419", language="ru")

    assert resp.error is None
    assert len(resp.results) == 3
    # Russian trailer wins the top slot.
    assert resp.results[0].language == "ru"
    assert resp.results[0].source == "tmdb"
    # English trailer ranks above English teaser.
    assert resp.results[1].language == "en"
    assert resp.results[1].kind == "trailer"
    assert resp.results[2].kind == "teaser"
    # Preview URL falls back to the YouTube hqdefault thumb.
    assert "img.youtube.com" in (resp.results[0].preview_url or "")


async def test_find_trailer_rejects_bad_imdb(app_ctx: AppContext) -> None:
    resp = await find_trailer_impl(app_ctx, "not-an-id")
    assert resp.error is not None
    assert resp.error.code == "invalid_argument"


async def test_find_trailer_not_found(
    app_ctx: AppContext, respx_mock: respx.MockRouter
) -> None:
    respx_mock.get(f"{TMDB_BASE_URL}/find/tt9999999").mock(
        return_value=httpx.Response(200, json={"movie_results": [], "tv_results": []})
    )

    resp = await find_trailer_impl(app_ctx, "tt9999999")
    assert resp.error is not None
    assert resp.error.code == "not_found"


async def test_find_trailer_uses_tv_endpoint_for_series(
    app_ctx: AppContext, respx_mock: respx.MockRouter
) -> None:
    respx_mock.get(f"{TMDB_BASE_URL}/find/tt8134470").mock(
        return_value=httpx.Response(
            200, json={"movie_results": [], "tv_results": [{"id": 100474}]}
        )
    )
    respx_mock.get(f"{TMDB_BASE_URL}/tv/100474/videos").mock(
        return_value=httpx.Response(
            200,
            json={
                "results": [
                    {
                        "key": "undoingkey",
                        "name": "The Undoing — Teaser",
                        "iso_639_1": "en",
                        "type": "Teaser",
                        "site": "YouTube",
                    }
                ]
            },
        )
    )

    resp = await find_trailer_impl(app_ctx, "tt8134470", language="ru")
    assert resp.error is None
    assert resp.results and resp.results[0].source == "tmdb"


async def test_search_trailer_by_title_prefers_higher_popularity_tv(
    app_ctx: AppContext, respx_mock: respx.MockRouter
) -> None:
    respx_mock.get(f"{TMDB_BASE_URL}/search/movie").mock(
        return_value=httpx.Response(
            200, json={"results": [{"id": 1, "popularity": 3.0}]}
        )
    )
    respx_mock.get(f"{TMDB_BASE_URL}/search/tv").mock(
        return_value=httpx.Response(
            200, json={"results": [{"id": 42, "popularity": 50.0}]}
        )
    )
    respx_mock.get(f"{TMDB_BASE_URL}/tv/42/videos").mock(
        return_value=httpx.Response(
            200,
            json={
                "results": [
                    {
                        "key": "xxx",
                        "name": "Trailer",
                        "iso_639_1": "en",
                        "type": "Trailer",
                        "site": "YouTube",
                    }
                ]
            },
        )
    )

    resp = await search_trailer_by_title_impl(app_ctx, "Anything")
    assert resp.error is None
    assert resp.results and "xxx" in resp.results[0].url


async def test_find_trailer_youtube_fallback_when_tmdb_empty_via_search(
    app_ctx: AppContext, respx_mock: respx.MockRouter
) -> None:
    # TMDB search picks a movie but it has no videos; YouTube fallback fires.
    respx_mock.get(f"{TMDB_BASE_URL}/search/movie").mock(
        return_value=httpx.Response(200, json={"results": [{"id": 1, "popularity": 1}]})
    )
    respx_mock.get(f"{TMDB_BASE_URL}/search/tv").mock(
        return_value=httpx.Response(200, json={"results": []})
    )
    respx_mock.get(f"{TMDB_BASE_URL}/movie/1/videos").mock(
        return_value=httpx.Response(200, json={"results": []})
    )
    respx_mock.get(f"{YOUTUBE_BASE_URL}/search").mock(
        return_value=httpx.Response(
            200,
            json={
                "items": [
                    {
                        "id": {"videoId": "yt1"},
                        "snippet": {
                            "title": "Obscure Flick — Official Trailer",
                            "channelTitle": "Warner Bros. Pictures",
                            "thumbnails": {"high": {"url": "https://img/yt1.jpg"}},
                            "publishedAt": "2024-01-01T00:00:00Z",
                        },
                    }
                ]
            },
        )
    )

    resp = await search_trailer_by_title_impl(app_ctx, "Obscure Flick")
    assert resp.error is None
    assert resp.results and resp.results[0].source == "youtube"
    assert resp.results[0].channel == "Warner Bros. Pictures"


async def test_cache_short_circuits_second_call(
    app_ctx: AppContext, respx_mock: respx.MockRouter
) -> None:
    _stub_find_movie(respx_mock, "tt1160419", 1)
    _stub_videos_movie(
        respx_mock,
        1,
        [{"key": "a", "name": "T", "iso_639_1": "ru", "type": "Trailer", "site": "YouTube"}],
    )

    await find_trailer_impl(app_ctx, "tt1160419")
    n_after_first = len(respx_mock.calls)
    await find_trailer_impl(app_ctx, "tt1160419")
    assert len(respx_mock.calls) == n_after_first
