"""Runtime configuration for agent-service."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    breeding_api_base_url: str = "http://localhost:8000"
    max_depth: int = 10
    max_nodes: int = 200
    route_timeout_ms: int = 8000
    top_candidates: int = 3
    duplicate_expand_limit: int = 3


_WORK_TYPE_CN = {
    "handiwork": "手工",
}


def work_type_to_cn(work_type: str) -> str:
    return _WORK_TYPE_CN.get(work_type, work_type)


def load_settings() -> Settings:
    return Settings(
        breeding_api_base_url=os.getenv(
            "BREEDING_API_BASE_URL", "http://localhost:8000"
        ),
        max_depth=int(os.getenv("AGENT_MAX_DEPTH", "10")),
        max_nodes=int(os.getenv("AGENT_MAX_NODES", "200")),
        route_timeout_ms=int(os.getenv("AGENT_ROUTE_TIMEOUT_MS", "8000")),
        top_candidates=int(os.getenv("AGENT_TOP_CANDIDATES", "3")),
        duplicate_expand_limit=int(os.getenv("AGENT_DUPLICATE_EXPAND_LIMIT", "3")),
    )
