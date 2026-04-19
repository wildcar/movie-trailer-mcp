"""YouTube Data API v3 client — optional fallback.

Used only when the caller asks for a trailer that TMDB couldn't supply.
The free quota is 10 000 units/day and a single ``search.list`` call costs
100 units, so we keep invocations bounded (limit=5, one call per lookup).
"""

from __future__ import annotations

from typing import Any

import httpx

YOUTUBE_BASE_URL = "https://www.googleapis.com/youtube/v3"


class YouTubeError(Exception):
    """Raised when YouTube returns a non-success response."""


class YouTubeClient:
    def __init__(
        self,
        api_key: str,
        *,
        http: httpx.AsyncClient | None = None,
        timeout: float = 10.0,
    ) -> None:
        self._api_key = api_key
        self._http = http or httpx.AsyncClient(base_url=YOUTUBE_BASE_URL, timeout=timeout)
        self._owns_http = http is None

    async def aclose(self) -> None:
        if self._owns_http:
            await self._http.aclose()

    async def search_trailers(
        self, query: str, *, language: str | None = None, limit: int = 5
    ) -> list[dict[str, Any]]:
        """Search YouTube for trailers matching ``query``.

        Returns raw items with nested ``snippet`` / ``id`` fields — the caller
        normalises them into :class:`Trailer`. We restrict ``type=video`` and
        ``safeSearch=moderate`` so the result list is playable URLs only.
        """
        params: dict[str, Any] = {
            "key": self._api_key,
            "q": query,
            "type": "video",
            "part": "snippet",
            "maxResults": max(1, min(limit, 25)),
            "safeSearch": "moderate",
            "videoEmbeddable": "true",
        }
        if language:
            params["relevanceLanguage"] = language

        resp = await self._http.get("/search", params=params)
        if resp.status_code >= 400:
            raise YouTubeError(f"YouTube search → {resp.status_code}: {resp.text}")
        data: dict[str, Any] = resp.json()
        items = data.get("items", [])
        return items if isinstance(items, list) else []


def watch_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"
