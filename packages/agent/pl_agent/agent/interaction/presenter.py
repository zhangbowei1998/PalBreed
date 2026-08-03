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


# 工具名 → 卡片 type（结构化数据直接透传）
_DATA_CARD_TOOL_TYPES = {
    "query_pals_by_passive": "passive",
    "query_item_drops": "drop",
    "query_item_recipe": "recipe",
    "query_pal_skills": "skills",
}


def _pal_detail_card(detail: dict) -> dict:
    """query_pal_detail 结果摘要为小卡片（详情较大，前端按需再取全量）。"""
    return {
        "type": "pal_detail",
        "pal_id": detail.get("id"),
        "cn_name": detail.get("cn_name"),
        "stats": detail.get("stats") or {},
        "skill_count": len(detail.get("skills") or []),
        "drop_count": len(detail.get("drops") or []),
    }


def build_data_cards(tool_calls) -> list[dict]:
    """从本轮 AgentLoop 工具调用结果提取可结构化展示的卡片列表。

    仅保留成功的工具结果；配种/解析/统计类工具不产生卡片。
    """
    cards: list[dict] = []
    for tc in tool_calls or []:
        if not tc.success:
            continue
        name = getattr(tc, "name", "")
        result = tc.result or {}
        if name in _DATA_CARD_TOOL_TYPES:
            cards.append({"type": _DATA_CARD_TOOL_TYPES[name], **result})
        elif name == "query_pal_detail":
            cards.append(_pal_detail_card(result))
    return cards
