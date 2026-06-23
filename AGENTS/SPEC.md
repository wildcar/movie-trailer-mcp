# movie-trailer-mcp — repo functional & technical specification

Source of truth for *what this server does* and *how it is built*. Cross-repo
contract lives in `../AGENTS/SPEC.md`; this document is the repo-local detail.

## Purpose

Given an IMDb id (or free-text title) and a preferred language, return up to three
ranked trailer candidates for a movie or TV series. TMDB's language-tagged
`/videos` endpoint is the primary source; an optional YouTube Data API v3 text
search is the fallback when TMDB has nothing. The bot calls this server to render a
`[Трейлер]` button on a movie's details card.

## Stack

- Python ≥ 3.11, `asyncio`, `httpx` async clients.
- MCP: official Anthropic `mcp` SDK; Pydantic-typed tools.
- Models: `pydantic` v2; config/secrets: `pydantic-settings` (`env_file=".env"`).
- Logging: `structlog`. Cache: SQLite via `aiosqlite`, TTL 6 h (`CACHE_TTL_SECONDS`).
- Deps: `uv`. Lint/types/tests: `ruff`, `mypy --strict`, `pytest` (+ `respx`).
- CI: GitHub Actions (`ruff` → `mypy` → `pytest`). `Dockerfile` (`python:3.x-slim`).

## Tools

Both tools share the `FindTrailerResponse` envelope:
`{ results: list[Trailer], sources_failed: list[str], error: ToolError | None }`.
Tools never raise across the MCP boundary — errors come back as `ToolError`
(`code`, `message`).

### `find_trailer(imdb_id: str, language: str = "ru") -> FindTrailerResponse`

Validates `imdb_id` starts with `tt` (else `invalid_argument`). Resolves the id to
a TMDB movie or TV entry via a single `/find` round-trip (covers movies + TV),
fetches videos from the correct endpoint, optionally falls back to YouTube, ranks,
and returns up to 3. Results cached by `(imdb_id, language)`.

### `search_trailer_by_title(title: str, year: int | None = None, language: str = "ru") -> FindTrailerResponse`

Free-text entry point — the **only** fuzzy lookup any non-metadata server does
(see root SPEC cross-server contract). Picks the top TMDB match (movie vs TV by
popularity), then proceeds as `find_trailer`. When neither TMDB nor the matched
title yields videos, the YouTube fallback (if `YOUTUBE_API_KEY` set) does a broader
text search.

### `Trailer` model

`url`, `title`, `language` (ISO 639-1 or None), `kind`
(`trailer|teaser|clip|featurette|other`), `source` (`tmdb|youtube|vk|rutube`),
`channel`, `preview_url`, `published_at` (ISO-8601). `vk`/`rutube` are reserved in
the type union; client modules are not implemented.

## Upstreams

| Source | Required | Role |
|--------|:--------:|------|
| **TMDB** (`TMDB_API_TOKEN`) | yes | Primary — `/find` resolve + language-tagged `/videos`. Same token as `movie-metadata-mcp`. |
| **YouTube Data API v3** (`YOUTUBE_API_KEY`) | optional | Fallback text search when TMDB has nothing. Unset → disabled silently. `search.list` = 100 quota units; 10 000/day free tier. |
| VK Video / Rutube | planned | Reserved in `TrailerSource`; no client yet. |

## Ranking logic (stable sort, `tools.py`)

1. **Language match** — requested language first, then `en`, then others.
2. **Type** — `Trailer` > `Teaser` > `Clip` > `Featurette` > other.
3. **Official** — TMDB `official` flag, or YouTube channel-name match against an
   additive lowercase `_OFFICIAL_CHANNEL_HINTS` list (Warner Bros, Netflix, HBO,
   Disney, Кинопоиск, Централ Партнершип, …).
4. **Newest** publication date (tie-breaker).

Top `_MAX_RESULTS = 3` returned. `_LANGUAGE_MAP` maps `ru→ru-RU`, `en→en-US` for
TMDB queries.

## Project structure

```
src/movie_trailer_mcp/
  server.py        # MCP entrypoint; registers tools; transport selection (project.scripts: movie-trailer-mcp)
  tools.py         # find_trailer_impl / search_trailer_by_title_impl; ranking
  models.py        # Pydantic: Trailer, FindTrailerResponse, ToolError
  config.py        # pydantic-settings: tokens, transport, cache
  context.py       # AppContext: shared clients + cache handle
  cache.py         # SQLite TTL cache (make_key / get / set)
  clients/tmdb.py  # TMDB /find + /videos
  clients/youtube.py # YouTube Data API v3 fallback; watch_url helper
tests/             # test_tools.py (unit, respx); integration/test_live.py (live, marker-gated)
```

## Env variables

`TMDB_API_TOKEN` (req), `YOUTUBE_API_KEY` (opt), `MCP_AUTH_TOKEN` (for HTTP),
`MCP_TRANSPORT` (`stdio`|`sse`|`streamable-http`, default `stdio`),
`MCP_HTTP_HOST` (`127.0.0.1`), `MCP_HTTP_PORT` (`8766`),
`CACHE_PATH` (`.cache/movie_trailer.sqlite`), `CACHE_TTL_SECONDS` (`21600`). See
`AGENTS/ENV.md`.

## Current state

- ✅ Both tools implemented, ranked, cached; unit + integration tests; CI; Docker.
- ✅ Deployed as a systemd unit on the bot host (port 8766); wired into the bot.
- ⏳ VK Video / Rutube source clients reserved in the model but not implemented.
