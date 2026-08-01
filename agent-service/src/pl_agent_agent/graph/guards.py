"""Guard rules for expansion and summarization."""

from __future__ import annotations

from ..state.models import SessionState


class GuardViolation(Exception):
    pass


def ensure_expand_allowed(
    state: SessionState,
    *,
    duplicate_count: int,
    duplicate_limit: int,
    current_depth: int,
) -> None:
    if current_depth >= state.limits.max_depth:
        raise GuardViolation(f"已达到最大展开深度 {state.limits.max_depth}")
    if len(state.explored_nodes) >= state.limits.max_nodes:
        raise GuardViolation(f"节点数量已达上限 {state.limits.max_nodes}")
    if duplicate_count >= duplicate_limit:
        raise GuardViolation("重复展开次数过多，请更换节点")


def ensure_summary_allowed(state: SessionState) -> None:
    if not state.target_pal:
        raise GuardViolation("尚未确认目标帕鲁")
