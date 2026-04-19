# movie-trailer-mcp

MCP server that finds up to three trailer candidates for a movie or TV series.

## Tools

### `find_trailer(imdb_id, language="ru")`

Resolves the IMDb id to a TMDB movie or TV series via a single `/find` call
and returns ranked trailers from TMDB's attached videos. Russian trailers are
preferred, with English as the automatic fallback.

### `search_trailer_by_title(title, year=None, language="ru")`

Same flow starting from free-text — picks the top TMDB match (movie vs TV by
popularity) and then runs the trailer lookup. When neither TMDB nor the match
provides videos, the optional YouTube fallback (if a key is configured) does a
broader search.

Response envelope (same shape for both tools):

```json
{
  "results": [
    {
      "url": "https://www.youtube.com/watch?v=...",
      "title": "Дюна — Официальный русский трейлер",
      "language": "ru",
      "kind": "trailer",
      "source": "tmdb",
      "channel": null,
      "preview_url": "https://img.youtube.com/vi/.../hqdefault.jpg",
      "published_at": "2021-07-22T15:00:00.000Z"
    }
  ],
  "sources_failed": [],
  "error": null
}
```

## Sources

| Source | Required? | What it does |
|---|---|---|
| **TMDB** (`TMDB_API_TOKEN`) | **yes** | Primary — TMDB's language-tagged `/videos` endpoint. |
| **YouTube Data API v3** (`YOUTUBE_API_KEY`) | optional | Fallback text search when TMDB has nothing. Omit the key to disable silently. |
| VK Video / Rutube | planned | The `Trailer` model has room for `source="vk"` / `"rutube"`; client modules aren't implemented yet. |

## Ranking

Candidates are sorted by:

1. Language match (requested, then `en`, then other).
2. Type (`Trailer` > `Teaser` > `Clip` > `Featurette`).
3. "Official" heuristic: YouTube channel name matches a known distributor hint.
4. Newest publication date first (tie-breaker).

## Local setup

```bash
cp .env.example .env
$EDITOR .env
uv sync --frozen
MCP_TRANSPORT=streamable-http uv run movie-trailer-mcp   # serves 127.0.0.1:8766
```

## Env variables

| Name | Required | Default | Notes |
|---|:-:|---|---|
| `TMDB_API_TOKEN` | ✅ | — | Same token as `movie-metadata-mcp`. |
| `YOUTUBE_API_KEY` |  | — | Leave blank to disable the YouTube fallback. |
| `MCP_AUTH_TOKEN` | for HTTP | — | Bearer token shared with the Telegram bot. |
| `MCP_TRANSPORT` |  | `stdio` | One of `stdio`, `sse`, `streamable-http`. |
| `MCP_HTTP_HOST` |  | `127.0.0.1` | Bind host for HTTP transports. |
| `MCP_HTTP_PORT` |  | `8766` | Bind port for HTTP transports. |
| `CACHE_PATH` |  | `.cache/movie_trailer.sqlite` | TTL cache location. |
| `CACHE_TTL_SECONDS` |  | `21600` | Cache lifetime (6 h). |

## Tests

```bash
uv run pytest                 # unit
uv run pytest -m integration  # live TMDB (+ YouTube if key)
```

Integration tests auto-skip when the relevant credentials are missing.

## Deployment

Runs as a systemd unit alongside `movie-metadata-mcp` and the Telegram bot.
The unit file lives in the `movie-handler-clients` repo under
`deploy/movie-trailer-mcp.service`.
