"""pal_info 工具（S6-S10）单元测试 — mock client。"""

from unittest.mock import AsyncMock

import pytest

from pl_agent.agent.tools.base import ToolError
from pl_agent.agent.tools.pal_info import (
    QueryItemDropsTool,
    QueryItemRecipeTool,
    QueryPalDetailTool,
    QueryPalsByPassiveTool,
    QueryPalSkillsTool,
)


def _client(**overrides):
    defaults = {
        "resolve_pal_name": AsyncMock(return_value={"id": "Anubis", "cn_name": "阿努比斯"}),
        "get_pal_detail_full": AsyncMock(return_value={"id": "Anubis", "stats": {"hp": 120}}),
        "get_pal_skills": AsyncMock(return_value=[{"cn_name": "碎石霰弹", "learn_level": 1}]),
        "query_pals_by_passive": AsyncMock(return_value=[{"id": "KingAlpaca", "cn_name": "君王美露帕"}]),
        "get_item_drops": AsyncMock(return_value=[{"pal_id": "Garm", "pal_cn": "加姆", "rate": 3}]),
        "get_item_recipe": AsyncMock(return_value=[{"station": "BlastFurnace", "material": "金属矿石", "count": 2}]),
    }
    defaults.update(overrides)
    return type("MC", (), defaults)()


@pytest.mark.asyncio
async def test_query_pal_detail():
    c = _client()
    tool = QueryPalDetailTool(c)
    r = await tool.run(pal_name="阿努比斯")
    assert r["cn_name"] == "阿努比斯"
    assert r["stats"]["hp"] == 120
    c.resolve_pal_name.assert_awaited_once_with("阿努比斯")
    c.get_pal_detail_full.assert_awaited_once_with("Anubis")


@pytest.mark.asyncio
async def test_query_pal_detail_not_found():
    c = _client(resolve_pal_name=AsyncMock(return_value=None))
    tool = QueryPalDetailTool(c)
    with pytest.raises(ToolError):
        await tool.run(pal_name="不存在")


@pytest.mark.asyncio
async def test_query_pal_skills():
    c = _client()
    tool = QueryPalSkillsTool(c)
    r = await tool.run(pal_name="Anubis")
    assert r["pal"]["id"] == "Anubis"
    assert r["skills"][0]["cn_name"] == "碎石霰弹"
    assert r["total"] == 1


@pytest.mark.asyncio
async def test_query_pals_by_passive():
    c = _client()
    tool = QueryPalsByPassiveTool(c)
    r = await tool.run(passive_name="重量级")
    assert r["passive"] == "重量级"
    assert r["pals"][0]["cn_name"] == "君王美露帕"
    c.query_pals_by_passive.assert_awaited_once_with("重量级")


@pytest.mark.asyncio
async def test_query_item_drops():
    c = _client()
    tool = QueryItemDropsTool(c)
    r = await tool.run(item_name="骨头")
    assert r["item"] == "骨头"
    assert r["pals"][0]["pal_cn"] == "加姆"
    c.get_item_drops.assert_awaited_once_with("骨头")


@pytest.mark.asyncio
async def test_query_item_recipe():
    c = _client()
    tool = QueryItemRecipeTool(c)
    r = await tool.run(item_name="金属锭")
    assert r["recipe"][0]["station"] == "BlastFurnace"
    assert r["recipe"][0]["material"] == "金属矿石"
    c.get_item_recipe.assert_awaited_once_with("金属锭")


@pytest.mark.asyncio
async def test_empty_args_raise_tool_error():
    c = _client()
    for tool in (QueryPalDetailTool(c), QueryItemDropsTool(c), QueryPalsByPassiveTool(c)):
        with pytest.raises(ToolError):
            await tool.run()
