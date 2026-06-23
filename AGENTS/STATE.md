# State

Repo snapshot. Overwrite each iteration. Cross-repo view in `../AGENTS/STATE.md`.

## Goal

Return up to three ranked trailer candidates for a movie/series from an IMDb id or
free-text title — TMDB primary, YouTube fallback — over MCP for the Telegram bot.

## Now

- `find_trailer` and `search_trailer_by_title` implemented, ranked, and SQLite-cached.
- Deployed as a systemd unit on the bot host (port 8766); wired into the bot.
- Repo migrated to the `agent-template` harness layout.

## Next

- (when needed) Nothing planned. Server is feature-complete for current bot needs.

## Open questions

- —

## Deferred

- **VK Video / Rutube trailer sources.** `TrailerSource` already allows
  `source="vk"`/`"rutube"`, but no client modules exist. Add `clients/vk.py` /
  `clients/rutube.py` and fold them into the ranker when a Russian-source trailer
  gap is observed.
