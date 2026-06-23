# Agent Instructions

Primary entrypoint for any agent (Claude, Codex, DeepSeek, etc.) working in the
**`movie-trailer-mcp`** repo. Read this first. This file is authoritative for
everything *inside this repo*.

## Workspace

This repo is one of seven siblings in the **`movie_handler`** workspace. Cross-repo
architecture, end-to-end flows, hosts, and shared agreements live in the workspace
root harness: `../AGENTS.md` and `../AGENTS/SPEC.md`. THIS file (and `AGENTS/`
beside it) is the authoritative, repo-scoped layer. Rule of thumb: editing code in
this repo → read this file; reasoning about how the bot + MCP servers fit together
→ read the root harness.

## Project

**`movie-trailer-mcp`** — MCP server that finds up to three ranked trailer
candidates for a movie or TV series. TMDB `/videos` is the primary source; an
optional YouTube Data API v3 text search is the fallback. Consumed by the Telegram
bot (`movie-handler-clients`) over HTTP+SSE; runs on the bot host, port **8766**.

## Document Map

| File | Role |
|------|------|
| `AGENTS.md` | This entrypoint. Repo map, workflow, rules. |
| `CLAUDE.md` | Compatibility pointer to `AGENTS.md`. |
| `AGENTS/SPEC.md` | Repo functional + technical spec: tools, upstreams, ranking, structure. |
| `AGENTS/STATE.md` | Current snapshot: goal, now, next, open, deferred. Overwritten each iteration. |
| `AGENTS/HISTORY.md` | Append-only iteration log, newest first. |
| `AGENTS/MEMORY.md` | Durable repo-local facts + agreements. |
| `AGENTS/ENV.md` | Repo-local env vars + run/deploy notes; shared host facts in `../AGENTS/ENV.md`. |
| `docs/adr/` | Architecture Decision Records (see `docs/adr/TEMPLATE.md`). |
| `README.md` | User-facing tool/env/run reference. Kept current. |

## Startup Checklist

1. Read `AGENTS.md` (this file).
2. Read `AGENTS/SPEC.md` for the repo's tools, upstreams, and ranking.
3. Read `AGENTS/STATE.md` for the live snapshot.
4. Read top entries in `AGENTS/HISTORY.md` and `AGENTS/MEMORY.md`.
5. Check `git status --short` before editing. Open `AGENTS/ENV.md` for env/deploy
   details, `../AGENTS/SPEC.md` for cross-repo context.

## Change Workflow

For every iteration that changes code or behavior:

1. If the tool contract changes — update `AGENTS/SPEC.md` (and root `../AGENTS/SPEC.md`
   if the cross-repo picture shifts) first.
2. Make the changes.
3. Overwrite `AGENTS/STATE.md`.
4. Prepend a new entry to `AGENTS/HISTORY.md` (format below).
5. Commit and push after verification (see Project Rules).

### `AGENTS/HISTORY.md` entry format (≤5 lines, newest first)

```
## YYYY-MM-DD · <short iteration title>
- What: <one line — what changed>
- Why: <one line — reason / task>
- Files: <key paths, comma-separated>
- Next: <one line — what was planned right after>
```

## Memory

`AGENTS/MEMORY.md` is the **single** store of durable agent memory in this repo.
One bullet = one fact; keep it short; add a brief **why** for agreements; convert
relative dates to absolute. Do NOT record what is already in code, git history, or
SPEC/STATE/HISTORY. Consolidate occasionally.

## Language Rules

- Source code, technical docs, code comments: **English**.
- Conversation with the user: **Russian**.
- End-user UI text (trailer titles flow to the bot): **Russian**-first, language-aware.

## Project Rules

- **Structured error returns, not exceptions** across the MCP boundary
  (`ToolError` envelope); degrade gracefully when an upstream is down
  (record it in `sources_failed`).
- **Pydantic models** for all tool I/O (`models.py`). **Secrets only via env vars**
  (`pydantic-settings`), never tool arguments; ship `.env.example`.
- **Transport:** `stdio` for local dev; HTTP+SSE / streamable-http with Bearer
  `MCP_AUTH_TOKEN` for networked use.
- **Every commit passes `ruff` + `mypy --strict` + `pytest` locally before push.**
  Commit + push to `main` directly after verification — no feature branch, no asking.
- Commit identity: `wildcar <wildcar@mail.ru>`. Remote: `github.com/wildcar/movie-trailer-mcp`.

## Stack & Commands

Python ≥ 3.11, `asyncio`, `httpx`, official `mcp` SDK, `pydantic` +
`pydantic-settings`, `structlog`, SQLite (`aiosqlite`) TTL cache, `uv` for deps.

```bash
uv sync                                          # install / sync deps
uv run movie-trailer-mcp                         # run over stdio (entrypoint)
MCP_TRANSPORT=streamable-http uv run movie-trailer-mcp   # serves 127.0.0.1:8766
uv run pytest && uv run ruff check && uv run mypy src
uv run pytest -m integration                     # live TMDB (+ YouTube if key)
npx @modelcontextprotocol/inspector uv run movie-trailer-mcp  # manual verify
```

## Code Style

- Match surrounding code: comment density, naming, idiom.
- Python: `ruff` format + lint (line-length 100), `mypy --strict`.
