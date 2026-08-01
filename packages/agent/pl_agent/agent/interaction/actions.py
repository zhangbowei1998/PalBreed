"""Action builders."""

from __future__ import annotations

from ..common.constants import (
    ACTION_CONFIRM_TARGET,
    ACTION_CONTINUE_FROM_PARENT,
    ACTION_EXPAND_PARENT,
    ACTION_SELECT_PARENT_PAIR,
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


def build_select_pair_action(
    child_pal_id: str,
    pair_index: int,
    parent_a_name: str,
    parent_b_name: str,
) -> dict:
    return {
        "action": ACTION_SELECT_PARENT_PAIR,
        "label": f"选择组合 {parent_a_name} + {parent_b_name}",
        "payload": {
            "child_pal_id": child_pal_id,
            "pair_index": pair_index,
        },
    }


def build_continue_action(pal_id: str, pal_name: str) -> dict:
    return {
        "action": ACTION_CONTINUE_FROM_PARENT,
        "label": f"继续追溯 {pal_name}",
        "payload": {"pal_id": pal_id},
    }
