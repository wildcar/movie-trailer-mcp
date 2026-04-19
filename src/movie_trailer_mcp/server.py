"""MCP entrypoint: registers the two trailer tools and starts the chosen transport."""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from typing import Final

import structlog
from mcp.server.fastmcp import FastMCP

from . import __version__
from .config import Settings, get_settings
from .context import AppContext, build_app_context
from .models import FindTrailerResponse
from .tools import find_trailer_impl, search_trailer_by_title_impl

_SUPPORTED_TRANSPORTS: Final[frozenset[str]] = frozenset({"stdio", "sse", "streamable-http"})


def _configure_logging() -> None:
    logging.basicConfig(stream=sys.stderr, level=logging.INFO, format="%(message)s")
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
    )


def build_server(ctx: AppContext) -> FastMCP:
    mcp = FastMCP(
        name="movie-trailer-mcp",
        host=os.environ.get("MCP_HTTP_HOST", "127.0.0.1"),
        port=int(os.environ.get("MCP_HTTP_PORT", "8766")),
        instructions=(
            "Finds up to three trailer candidates for a movie or TV series. "
            "Primary source: TMDB /videos (language-tagged). Optional fallback: "
            "YouTube Data API v3 when the caller-provided fallback query matches. "
            "IMDb id is the cross-server correlation key."
        ),
    )

    async def find_trailer(imdb_id: str, language: str = "ru") -> FindTrailerResponse:
        """Find trailers for an IMDb id. ``language`` defaults to 'ru'; 'en' is the main fallback."""
        return await find_trailer_impl(ctx, imdb_id, language)

    async def search_trailer_by_title(
        title: str, year: int | None = None, language: str = "ru"
    ) -> FindTrailerResponse:
        """Find trailers by free-text title (optional year)."""
        return await search_trailer_by_title_impl(ctx, title, year, language)

    mcp.tool()(find_trailer)
    mcp.tool()(search_trailer_by_title)
    return mcp


async def _run(settings: Settings, transport: str) -> None:
    async with build_app_context(settings) as ctx:
        server = build_server(ctx)
        structlog.get_logger().info("trailer_mcp.starting", version=__version__, transport=transport)
        if transport == "stdio":
            await server.run_stdio_async()
        elif transport == "sse":
            await server.run_sse_async()
        else:
            await server.run_streamable_http_async()


def main() -> None:
    _configure_logging()
    transport = os.environ.get("MCP_TRANSPORT", "stdio").lower()
    if transport not in _SUPPORTED_TRANSPORTS:
        raise SystemExit(
            f"Unsupported MCP_TRANSPORT={transport!r}; "
            f"expected one of {sorted(_SUPPORTED_TRANSPORTS)}"
        )
    asyncio.run(_run(get_settings(), transport))


if __name__ == "__main__":
    main()
