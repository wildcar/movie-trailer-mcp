# Memory

Durable repo-local facts and agreements NOT derivable from code, git history, or
SPEC/STATE/HISTORY. The ONLY agent memory store in this repo. Cross-repo facts live
in `../AGENTS/MEMORY.md` — do not duplicate them here.

MEMORY.md = durable facts/agreements; current state → STATE.md; iteration log → HISTORY.md.

## Project facts

- TMDB token env var is `TMDB_API_TOKEN` (the v4 Read Access Token, a JWT-like
  `eyJ…` string) — it is the **same** key `movie-metadata-mcp` uses. Reuse it.
- YouTube fallback is optional: leave `YOUTUBE_API_KEY` empty to disable it
  silently; TMDB then stays the only source. `search.list` costs 100 of the free
  10 000 daily quota units.
- `search_trailer_by_title` is the deliberate cross-server exception — it is the
  only fuzzy text lookup outside `movie-metadata-mcp` (see root SPEC contract).
- Official-channel ranking is a heuristic substring list (`_OFFICIAL_CHANNEL_HINTS`
  in `tools.py`); keep it additive/lowercase rather than a hard whitelist.
- The systemd unit file lives in the **`movie-handler-clients`** repo at
  `deploy/movie-trailer-mcp.service`, not here.
