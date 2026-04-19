"""Tool implementations.

- ``find_trailer(imdb_id, language='ru')`` — resolve the IMDb id via TMDB
  ``/find`` (one round-trip across movies+tv), fetch videos from the right
  endpoint, optionally fall back to YouTube search, rank, and return up to
  3 candidates.
- ``search_trailer_by_title(title, year=None, language='ru')`` — same, but
  start from free text; picks the top TMDB match and then proceeds as above.

Ranking priority (stable):
1. Language match (requested language first, then 'en', then others).
2. ``type == Trailer`` > Teaser > Clip > Featurette > other.
3. ``official`` flag from TMDB (or channel heuristic for YouTube).
4. Newer publication date.
"""

from __future__ import annotations

import asyncio
from typing import Any

import structlog

from .clients.youtube import watch_url
from .context import AppContext
from .models import FindTrailerResponse, TitleKind, ToolError, Trailer

log = structlog.get_logger()

_TMDB = "tmdb"
_YOUTUBE = "youtube"

_MAX_RESULTS = 3
_LANGUAGE_MAP = {
    "ru": "ru-RU",
    "en": "en-US",
}
_TYPE_PRIORITY = {"Trailer": 0, "Teaser": 1, "Clip": 2, "Featurette": 3}

# Heuristic list of known official-distributor channel-name substrings.
# Additive, lowercase match; keeps the ranker from learning a hard list.
_OFFICIAL_CHANNEL_HINTS = (
    "warner bros",
    "universal pictures",
    "sony pictures",
    "paramount pictures",
    "20th century",
    "marvel",
    "netflix",
    "hbo",
    "disney",
    "a24",
    "lionsgate",
    "focus features",
    "apple tv",
    "кинопоиск",
    "централ партнершип",
)


# ---------------------------------------------------------------------------
# find_trailer
# ---------------------------------------------------------------------------


async def find_trailer_impl(
    ctx: AppContext, imdb_id: str, language: str = "ru"
) -> FindTrailerResponse:
    if not imdb_id or not imdb_id.startswith("tt"):
        return FindTrailerResponse(
            error=ToolError(
                code="invalid_argument",
                message="`imdb_id` must start with 'tt' (e.g. tt1375666).",
            )
        )

    cache_key = ctx.cache.make_key(
        "find_trailer", {"imdb_id": imdb_id, "language": language}
    )
    cached = await ctx.cache.get(cache_key)
    if cached is not None:
        return FindTrailerResponse.model_validate(cached)

    if ctx.tmdb is None:
        return FindTrailerResponse(
            sources_failed=[_TMDB],
            error=ToolError(
                code="no_primary_source",
                message="TMDB is the primary source; TMDB_API_TOKEN is not configured.",
            ),
        )

    try:
        resolved = await ctx.tmdb.find_any_by_imdb(imdb_id)
    except Exception as exc:
        log.warning("tmdb.find_failed", imdb_id=imdb_id, error=str(exc))
        return FindTrailerResponse(
            sources_failed=[_TMDB],
            error=ToolError(code="upstream_error", message=f"TMDB /find failed: {exc}"),
        )

    if resolved is None:
        return FindTrailerResponse(
            error=ToolError(
                code="not_found",
                message=f"TMDB has no movie or series matching IMDb id {imdb_id}.",
            )
        )
    kind_raw, tmdb_id = resolved
    kind: TitleKind = "series" if kind_raw == "series" else "movie"
    response = await _collect_trailers(ctx, kind=kind, tmdb_id=tmdb_id, language=language)
    await ctx.cache.set(
        cache_key, response.model_dump(mode="json"), ctx.settings.cache_ttl_seconds
    )
    return response


# ---------------------------------------------------------------------------
# search_trailer_by_title
# ---------------------------------------------------------------------------


async def search_trailer_by_title_impl(
    ctx: AppContext,
    title: str,
    year: int | None = None,
    language: str = "ru",
) -> FindTrailerResponse:
    if not title or not title.strip():
        return FindTrailerResponse(
            error=ToolError(code="invalid_argument", message="`title` must not be empty.")
        )

    cache_key = ctx.cache.make_key(
        "search_trailer_by_title",
        {"title": title, "year": year, "language": language},
    )
    cached = await ctx.cache.get(cache_key)
    if cached is not None:
        return FindTrailerResponse.model_validate(cached)

    if ctx.tmdb is None:
        return FindTrailerResponse(
            sources_failed=[_TMDB],
            error=ToolError(
                code="no_primary_source",
                message="TMDB is the primary source; TMDB_API_TOKEN is not configured.",
            ),
        )

    # Pick the best TMDB match across movies + tv in parallel.
    try:
        movie, tv = await asyncio.gather(
            ctx.tmdb.search_movie(title, year),
            ctx.tmdb.search_tv(title, year),
        )
    except Exception as exc:
        log.warning("tmdb.search_failed", error=str(exc))
        return FindTrailerResponse(
            sources_failed=[_TMDB],
            error=ToolError(code="upstream_error", message=f"TMDB search failed: {exc}"),
        )

    best_kind, best_row = _pick_best_match(movie, tv)
    if best_row is None:
        return FindTrailerResponse(
            error=ToolError(
                code="not_found", message=f"TMDB has no match for '{title}'."
            )
        )

    tmdb_id = best_row.get("id")
    if not isinstance(tmdb_id, int):
        return FindTrailerResponse(
            error=ToolError(code="invalid_upstream", message="TMDB match lacks an id.")
        )

    response = await _collect_trailers(
        ctx, kind=best_kind, tmdb_id=tmdb_id, language=language, fallback_query=title
    )
    await ctx.cache.set(
        cache_key, response.model_dump(mode="json"), ctx.settings.cache_ttl_seconds
    )
    return response


def _pick_best_match(
    movie: dict[str, Any] | None, tv: dict[str, Any] | None
) -> tuple[TitleKind, dict[str, Any] | None]:
    """Pick between a movie and TV candidate using TMDB's popularity.

    When both sources return something, the one with the higher
    ``popularity`` wins. Movies win ties — that's the historically safer
    default for search UIs.
    """
    if movie is None and tv is None:
        return "movie", None
    if movie is None:
        return "series", tv
    if tv is None:
        return "movie", movie
    m_pop = movie.get("popularity") or 0
    t_pop = tv.get("popularity") or 0
    if t_pop > m_pop:
        return "series", tv
    return "movie", movie


# ---------------------------------------------------------------------------
# Collect + rank
# ---------------------------------------------------------------------------


async def _collect_trailers(
    ctx: AppContext,
    *,
    kind: TitleKind,
    tmdb_id: int,
    language: str,
    fallback_query: str | None = None,
) -> FindTrailerResponse:
    assert ctx.tmdb is not None  # enforced by callers
    failed: list[str] = []
    trailers: list[Trailer] = []

    # TMDB: ask twice — once for the requested language, once without — then
    # dedupe. TMDB's language filter is strict, so videos that sit in the
    # pool without a language tag only appear in the unfiltered call.
    lang_tag = _LANGUAGE_MAP.get(language, language)
    try:
        lang_videos, any_videos = await asyncio.gather(
            ctx.tmdb.get_videos(kind, tmdb_id, language=lang_tag),
            ctx.tmdb.get_videos(kind, tmdb_id, language=None),
        )
    except Exception as exc:
        log.warning("tmdb.videos_failed", tmdb_id=tmdb_id, kind=kind, error=str(exc))
        failed.append(_TMDB)
        lang_videos, any_videos = [], []

    seen: set[str] = set()
    for video in list(lang_videos) + list(any_videos):
        t = _video_to_trailer(video)
        if t is None:
            continue
        if t.url in seen:
            continue
        seen.add(t.url)
        trailers.append(t)

    # YouTube fallback — only when the primary source came up short and a
    # fallback query is available.
    if not trailers and ctx.youtube is not None and fallback_query:
        try:
            items = await ctx.youtube.search_trailers(
                f"{fallback_query} trailer", language=language, limit=5
            )
            for item in items:
                t = _youtube_to_trailer(item, language=language)
                if t is not None and t.url not in seen:
                    seen.add(t.url)
                    trailers.append(t)
        except Exception as exc:
            log.warning("youtube.search_failed", query=fallback_query, error=str(exc))
            failed.append(_YOUTUBE)

    trailers.sort(key=lambda t: _rank_key(t, preferred_lang=language))
    return FindTrailerResponse(results=trailers[:_MAX_RESULTS], sources_failed=failed)


def _video_to_trailer(video: dict[str, Any]) -> Trailer | None:
    """Map a TMDB ``/videos`` row to a :class:`Trailer`. Drops non-playable rows."""
    site = (video.get("site") or "").lower()
    key = video.get("key")
    if site != "youtube" or not isinstance(key, str) or not key:
        # Vimeo is playable but Telegram's preview resolver is patchy; skip
        # for now. Can be reintroduced once we add explicit per-site handling.
        return None
    tmdb_type = str(video.get("type") or "Trailer")
    kind_map = {
        "Trailer": "trailer",
        "Teaser": "teaser",
        "Clip": "clip",
        "Featurette": "featurette",
    }
    return Trailer(
        url=watch_url(key),
        title=str(video.get("name") or "Trailer"),
        language=video.get("iso_639_1") or None,
        kind=kind_map.get(tmdb_type, "other"),
        source="tmdb",
        channel=None,
        preview_url=f"https://img.youtube.com/vi/{key}/hqdefault.jpg",
        published_at=video.get("published_at"),
    )


def _youtube_to_trailer(item: dict[str, Any], *, language: str) -> Trailer | None:
    id_block = item.get("id") or {}
    snippet = item.get("snippet") or {}
    video_id = id_block.get("videoId")
    if not isinstance(video_id, str) or not video_id:
        return None
    thumbnails = (snippet.get("thumbnails") or {}).get("high") or {}
    return Trailer(
        url=watch_url(video_id),
        title=str(snippet.get("title") or "Trailer"),
        language=language,
        kind="trailer",
        source="youtube",
        channel=snippet.get("channelTitle") or None,
        preview_url=thumbnails.get("url"),
        published_at=snippet.get("publishedAt"),
    )


def _rank_key(t: Trailer, *, preferred_lang: str) -> tuple[int, int, int, str]:
    """Smaller tuple → earlier in the list."""
    lang_rank = 0 if t.language == preferred_lang else (1 if t.language == "en" else 2)
    type_rank = _TYPE_PRIORITY.get(t.kind.capitalize(), 9)
    channel = (t.channel or "").lower()
    official_rank = 0 if any(h in channel for h in _OFFICIAL_CHANNEL_HINTS) else 1
    # Reverse chronological for stable tie-breaking: negate via string compare
    # on ISO-8601 (lexicographic newer > older), so we invert with a '~' trick.
    neg_date = t.published_at or ""
    return lang_rank, type_rank, official_rank, _invert_iso(neg_date)


def _invert_iso(iso: str) -> str:
    """Return a string that sorts newer dates first (ascending)."""
    if not iso:
        return "~"
    # Invert by subtracting each digit from 9. ISO-8601 ordering is preserved
    # by this reflection; makes 'newer' lexicographically smaller.
    digits = {str(d): str(9 - d) for d in range(10)}
    return "".join(digits.get(c, c) for c in iso)
