"""Pydantic models for API."""

from pydantic import BaseModel


class QueryRequest(BaseModel):
    input: str
    max_depth: int = 5
