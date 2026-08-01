"""Response presenter."""

from __future__ import annotations

from ..state.models import SessionState


def build_response(
    *,
    messages: list[str],
    actions: list[dict],
    state: SessionState,
    meta: dict | None = None,
) -> dict:
    return {
        "messages": [{"role": "assistant", "content": text} for text in messages],
        "actions": actions,
        "state_snapshot": state.model_dump(),
        "meta": meta or {},
    }
