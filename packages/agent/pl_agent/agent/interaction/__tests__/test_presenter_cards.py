"""build_data_cards 单元测试 — 从工具调用结果提取结构化卡片。"""

from pl_agent.agent.interaction.presenter import build_data_cards
from pl_agent.agent.monitoring.models import ToolCallRecord


def _tc(name: str, result: dict, success: bool = True) -> ToolCallRecord:
    return ToolCallRecord(name=name, arguments={}, result=result, success=success)


def test_passive_card():
    cards = build_data_cards([
        _tc("query_pals_by_passive", {"passive": "重量级", "pals": [{"id": "KingAlpaca"}], "total": 1}),
    ])
    assert len(cards) == 1
    assert cards[0]["type"] == "passive"
    assert cards[0]["passive"] == "重量级"


def test_drop_card():
    cards = build_data_cards([
        _tc("query_item_drops", {"item": "骨头", "pals": [{"pal_cn": "加姆"}], "total": 1}),
    ])
    assert cards[0]["type"] == "drop"
    assert cards[0]["item"] == "骨头"


def test_recipe_card():
    cards = build_data_cards([
        _tc("query_item_recipe", {"item": "金属锭", "recipe": [{"station": "BlastFurnace"}], "total": 1}),
    ])
    assert cards[0]["type"] == "recipe"


def test_skills_card():
    cards = build_data_cards([
        _tc("query_pal_skills", {"pal": {"id": "Anubis"}, "skills": [], "total": 0}),
    ])
    assert cards[0]["type"] == "skills"


def test_pal_detail_card_summary():
    cards = build_data_cards([
        _tc("query_pal_detail", {
            "id": "Anubis", "cn_name": "阿努比斯", "stats": {"hp": 120},
            "skills": [1, 2, 3], "drops": [1, 2],
        }),
    ])
    assert cards[0]["type"] == "pal_detail"
    assert cards[0]["pal_id"] == "Anubis"
    assert cards[0]["skill_count"] == 3
    assert cards[0]["drop_count"] == 2


def test_failed_tool_excluded():
    cards = build_data_cards([
        _tc("query_item_drops", {}, success=False),
    ])
    assert cards == []


def test_breeding_tools_no_card():
    cards = build_data_cards([
        _tc("query_parent_pairs", {"parent_pairs": []}),
        _tc("resolve_pal", {"id": "Anubis"}),
        _tc("query_pal_stats", {}),
    ])
    assert cards == []


def test_none_tool_calls():
    assert build_data_cards(None) == []
