"""Pydantic models for the MCP tool surface.

Independent of any upstream provider's wire format; the client modules in
``movie_trailer_mcp.clients`` are responsible for mapping provider payloads
into these types.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

TitleKind = Literal["movie", "series"]
TrailerKind = Literal["trailer", "teaser", "clip", "featurette", "other"]
TrailerSource = Literal["tmdb", "youtube", "vk", "rutube"]


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=False)


class ToolError(_Base):
    """Structured error envelope. Tools never raise through the MCP boundary."""

    code: str = Field(..., description="Stable machine-readable error code.")
    message: str = Field(..., description="Human-readable explanation (English).")


class Trailer(_Base):
    """A single trailer candidate."""

    url: str = Field(..., description="Canonical playable URL (YouTube watch URL, etc.).")
    title: str = Field(..., description="Human-readable video title as reported by the source.")
    language: str | None = Field(
        None, description="ISO 639-1 code (e.g. 'ru', 'en'); None when unknown."
    )
    kind: TrailerKind = Field("trailer", description="Video classification.")
    source: TrailerSource = Field(..., description="Which provider surfaced this trailer.")
    channel: str | None = Field(
        None,
        description="Uploader / channel name. Used by the ranker to prefer official channels.",
    )
    preview_url: str | None = Field(
        None, description="Absolute URL of a thumbnail / poster frame, if the source provides one."
    )
    published_at: str | None = Field(
        None, description="ISO-8601 publication timestamp, if the source reports it."
    )


class FindTrailerResponse(_Base):
    """Response envelope for both ``find_trailer`` and ``search_trailer_by_title``."""

    results: list[Trailer] = Field(default_factory=list)
    sources_failed: list[str] = Field(default_factory=list)
    error: ToolError | None = None
