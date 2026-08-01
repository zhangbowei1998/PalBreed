"""DTOs for upstream API responses."""

from __future__ import annotations

from pydantic import BaseModel, Field


class UpstreamPal(BaseModel):
    id: str
    cn_name: str
    number: str | int | None = None


class SuitabilityCandidate(BaseModel):
    pal: UpstreamPal
    matched_level: int = 0


class ParentPair(BaseModel):
    parent_a: str
    parent_b: str
    method: str = "breed"


class UpstreamEnvelope(BaseModel):
    success: bool
    data: dict = Field(default_factory=dict)
    error: dict | None = None
