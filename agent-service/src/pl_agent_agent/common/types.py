"""Common typed structures."""

from __future__ import annotations

from typing import Literal, TypedDict


class Candidate(TypedDict):
    pal_id: str
    cn_name: str
    score: int
    reason: str


class AgentAction(TypedDict, total=False):
    action: Literal["expand_parent", "summarize_route", "confirm_target"]
    label: str
    payload: dict


class AgentMessage(TypedDict):
    role: Literal["assistant"]
    content: str
