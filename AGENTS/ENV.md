# Environment

Repo-local env vars and run/deploy notes for `movie-trailer-mcp`. Shared host
facts (dev box, bot host, media host, credential layout, tool versions) live in the
workspace root `../AGENTS/ENV.md` — read that for anything not repo-specific.

## Repo-specific env vars

| Name | Required | Default | Notes |
|------|:--------:|---------|-------|
| `TMDB_API_TOKEN` | ✅ | — | TMDB v4 Read Access Token; **same key as `movie-metadata-mcp`**. |
| `YOUTUBE_API_KEY` |  | — | Optional YouTube Data API v3 fallback. Empty → disabled silently. |
| `MCP_AUTH_TOKEN` | for HTTP | — | Bearer token shared with the Telegram bot. |
| `MCP_TRANSPORT` |  | `stdio` | `stdio` \| `sse` \| `streamable-http`. |
| `MCP_HTTP_HOST` |  | `127.0.0.1` | Bind host for HTTP transports. |
| `MCP_HTTP_PORT` |  | `8766` | Bind port for HTTP transports. |
| `CACHE_PATH` |  | `.cache/movie_trailer.sqlite` | SQLite TTL cache, relative to CWD. |
| `CACHE_TTL_SECONDS` |  | `21600` | Cache lifetime (6 h). |

Real values go in `./.env` (gitignored); never commit a real `.env`. `.env.example`
ships placeholders + obtain-instructions for both API keys.

## Run & verify (dev box)

```bash
uv sync
uv run movie-trailer-mcp                                  # stdio
MCP_TRANSPORT=streamable-http uv run movie-trailer-mcp     # serves 127.0.0.1:8766
uv run pytest && uv run ruff check && uv run mypy src
uv run pytest -m integration                              # live TMDB (+ YouTube if key); auto-skips without creds
npx @modelcontextprotocol/inspector uv run movie-trailer-mcp
```

## Deploy

- Runs as a systemd unit on the **bot host** (`homesrv`, user `movie`, `/opt/movie-trailer-mcp`),
  bound to `127.0.0.1:8766`. Unit file is in `movie-handler-clients` at
  `deploy/movie-trailer-mcp.service`. See `../AGENTS/ENV.md` for the prod
  `git pull --ff-only` + `uv sync --no-dev` + `systemctl restart` recipe.
