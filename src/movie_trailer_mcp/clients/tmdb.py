"""TMDB client — surface is narrow and trailer-focused.

Two endpoint groups are needed:
- ``/find/{imdb_id}`` — resolve IMDb id to either a movie or a TV series id.
- ``/{movie|tv}/{id}/videos`` — fetch the attached videos (trailers, teasers,
  clips). TMDB's ``language`` query parameter controls which videos are
  returned; asking for ``ru-RU`` yields Russian-language uploads (when
  present), ``null`` returns everything.
"""

from __future__ import annotations

from typing import Any

import httpx

TMDB_BASE_URL = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE_URL = "https://image.tmdb.org/t/p/w500"


class TMDBError(Exception):
    """Raised when TMDB returns a non-success response."""


class TMDBClient:
    def __init__(
        self,
        token: str,
        *,
        http: httpx.AsyncClient | None = None,
        timeout: float = 10.0,
    ) -> None:
        self._token = token
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        self._http = http or httpx.AsyncClient(
            base_url=TMDB_BASE_URL, headers=headers, timeout=timeout
        )
        self._owns_http = http is None

    async def aclose(self) -> None:
        if self._owns_http:
            await self._http.aclose()

    # ------------------------------------------------------------------
    # Resolve
    # ------------------------------------------------------------------
    async def find_any_by_imdb(self, imdb_id: str) -> tuple[str, int] | None:
        """Return ``("movie" | "series", tmdb_id)`` for the IMDb id, or None.

        One round-trip — ``/find`` returns all categories at once.
        """
        data = await self._get_json(
            f"/find/{imdb_id}", params={"external_source": "imdb_id"}
        )
        movies = data.get("movie_results") or []
        if isinstance(movies, list) and movies and isinstance(movies[0].get("id"), int):
            return "movie", int(movies[0]["id"])
        tv = data.get("tv_results") or []
        if isinstance(tv, list) and tv and isinstance(tv[0].get("id"), int):
            return "series", int(tv[0]["id"])
        return None

    # ------------------------------------------------------------------
    # Videos
    # ------------------------------------------------------------------
    async def get_videos(
        self, kind: str, tmdb_id: int, *, language: str | None = None
    ) -> list[dict[str, Any]]:
        """Fetch attached videos for a movie (``kind='movie'``) or TV series.

        ``language`` accepts a BCP-47 tag (``ru-RU``, ``en-US``). When None,
        TMDB returns videos in any language it has.
        """
        path = f"/movie/{tmdb_id}/videos" if kind == "movie" else f"/tv/{tmdb_id}/videos"
        params: dict[str, Any] = {}
        if language:
            params["language"] = language
        data = await self._get_json(path, params=params)
        results = data.get("results", [])
        return results if isinstance(results, list) else []

    # ------------------------------------------------------------------
    # Text search (for search_trailer_by_title)
    # ------------------------------------------------------------------
    async def search_movie(self, title: str, year: int | None = None) -> dict[str, Any] | None:
        return await self._top_search("/search/movie", title, year, year_param="year")

    async def search_tv(self, title: str, year: int | None = None) -> dict[str, Any] | None:
        return await self._top_search(
            "/search/tv", title, year, year_param="first_air_date_year"
        )

    async def _top_search(
        self, path: str, query: str, year: int | None, *, year_param: str
    ) -> dict[str, Any] | None:
        params: dict[str, Any] = {"query": query, "language": "ru-RU", "page": 1}
        if year is not None:
            params[year_param] = year
        data = await self._get_json(path, params=params)
        results = data.get("results")
        if isinstance(results, list) and results:
            first: dict[str, Any] = results[0]
            return first
        return None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    async def _get_json(self, path: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
        resp = await self._http.get(path, params=params)
        if resp.status_code >= 400:
            raise TMDBError(f"TMDB {path} → {resp.status_code}: {resp.text}")
        payload: dict[str, Any] = resp.json()
        return payload
