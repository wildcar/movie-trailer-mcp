# History

Newest first. Each entry ≤5 lines using the format defined in `AGENTS.md`. This is
the repo-local log; cross-repo detail lives in the root `../AGENTS/HISTORY.md`.

---

## 2026-06-23 · Migrate repo to agent-template harness
- What: Added `AGENTS.md`, `CLAUDE.md` pointer, `AGENTS/{SPEC,STATE,HISTORY,MEMORY,ENV}.md`, `docs/adr/TEMPLATE.md`.
- Why: Adopt the standard `wildcar/agent-template` harness so this repo carries its own authoritative agent docs.
- Files: `AGENTS.md`, `CLAUDE.md`, `AGENTS/*`, `docs/adr/TEMPLATE.md`.
- Next: Repo is feature-complete; no work queued. Deferred: VK/Rutube trailer sources.

## 2026-04-19 · Initial scaffold: movie-trailer-mcp
- What: Scaffolded the trailer MCP server — `find_trailer`, `search_trailer_by_title`, TMDB primary + optional YouTube fallback, ranking, SQLite TTL cache, tests/CI/Docker.
- Why: Priority-3 server in the search→trailer→torrent pipeline.
- Files: `src/movie_trailer_mcp/*`, `tests/*`, `pyproject.toml`, `Dockerfile`, `README.md`, `.env.example`.
- Next: Verify via MCP Inspector, then scaffold rutracker-torrent-mcp (priority 4).
