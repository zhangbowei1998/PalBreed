"""Action builders."""

from __future__ import annotations

from ..common.constants import (
    ACTION_CONFIRM_TARGET,
    ACTION_EXPAND_PARENT,
    ACTION_SUMMARIZE_ROUTE,
    MODE_EXPLORED_ONLY,
)


def build_confirm_action(pal_id: str, label: str) -> dict:
    return {
        "action": ACTION_CONFIRM_TARGET,
        "label": f"确认 {label}",
        "payload": {"pal_id": pal_id},
    }


def build_expand_action(pal_id: str, source_message_id: str = "") -> dict:
    return {
        "action": ACTION_EXPAND_PARENT,
        "label": f"展开 {pal_id}",
        "payload": {"pal_id": pal_id, "source_message_id": source_message_id},
    }


def build_summarize_action(session_id: str) -> dict:
    return {
        "action": ACTION_SUMMARIZE_ROUTE,
        "label": "生成配种路线",
        "payload": {"session_id": session_id, "mode": MODE_EXPLORED_ONLY},
    }
