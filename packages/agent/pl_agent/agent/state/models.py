"""Session state models."""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field


class TargetCandidate(BaseModel):
    pal_id: str
    cn_name: str
    score: int = 0
    reason: str = ""


class Edge(BaseModel):
    child_pal_id: str
    parent_a_id: str
    parent_a_name: str
    parent_b_id: str
    parent_b_name: str
    method: str = "breed"
    depth: int = 1


class ClickEvent(BaseModel):
    pal_id: str
    ts: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class Limits(BaseModel):
    max_depth: int = 10
    max_nodes: int = 200


class SessionMeta(BaseModel):
    version: int = 1
    updated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class ChatTurn(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class SessionState(BaseModel):
    session_id: str
    target_pal: str | None = None
    target_candidates: list[TargetCandidate] = Field(default_factory=list)
    confirmed_target_pal: str | None = None
    current_focus_pal: str | None = None
    pending_frontier: list[str] = Field(default_factory=list)
    explored_nodes: list[str] = Field(default_factory=list)
    node_depths: dict[str, int] = Field(default_factory=dict)
    edges: list[Edge] = Field(default_factory=list)
    candidate_pairs: dict[str, list[Edge]] = Field(default_factory=dict)
    selected_pairs: list[Edge] = Field(default_factory=list)
    click_trace: list[ClickEvent] = Field(default_factory=list)
    chat_history: list[ChatTurn] = Field(default_factory=list)
    history_summary: str = ""  # 上下文压缩：早期对话的 LLM 摘要
    limits: Limits = Field(default_factory=Limits)
    meta: SessionMeta = Field(default_factory=SessionMeta)

    def touch(self) -> None:
        self.meta.version += 1
        self.meta.updated_at = datetime.now(timezone.utc).isoformat()
