"""Pal 信息 / 物品信息工具 — 暴露 tc-imba 新数据能力 (S6-S10) 给 LLM。

这些工具保证 LLM 通过 function calling 拿到精确数据，绝不自行推算。
"""

from __future__ import annotations

from ..clients.breeding_api_client import BreedingApiClient
from .base import Tool, ToolError


class QueryPalDetailTool(Tool):
    """查询帕鲁全量详情（属性/技能/被动/掉落/伙伴技能/召唤）。"""

    name = "query_pal_detail"
    description = (
        "查询一只帕鲁的全量详情：基础属性(stats)、可学技能、固有被动、击杀掉落、"
        "伙伴技能、召唤材料。用于回答“XX的属性/技能/掉落/伙伴技能是什么”等。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "pal_name": {
                "type": "string",
                "description": "帕鲁名称，例如 阿努比斯、Anubis",
            }
        },
        "required": ["pal_name"],
    }

    def __init__(self, client: BreedingApiClient) -> None:
        self._client = client

    async def run(self, **kwargs):
        pal_name = str(kwargs.get("pal_name", "")).strip()
        if not pal_name:
            raise ToolError("pal_name 不能为空")
        pal = await self._client.resolve_pal_name(pal_name)
        if pal is None:
            raise ToolError(f"未找到帕鲁: {pal_name}")
        pal_id = pal.get("id")
        detail = await self._client.get_pal_detail_full(pal_id)
        detail["cn_name"] = pal.get("cn_name", pal_id)
        return detail


class QueryPalSkillsTool(Tool):
    """查询帕鲁可学技能（含学习等级）。"""

    name = "query_pal_skills"
    description = (
        "查询一只帕鲁可学习的技能列表（含学习等级）。用于回答“XX能学什么技能/技能是哪些”等。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "pal_name": {
                "type": "string",
                "description": "帕鲁名称，例如 阿努比斯、Anubis",
            }
        },
        "required": ["pal_name"],
    }

    def __init__(self, client: BreedingApiClient) -> None:
        self._client = client

    async def run(self, **kwargs):
        pal_name = str(kwargs.get("pal_name", "")).strip()
        if not pal_name:
            raise ToolError("pal_name 不能为空")
        pal = await self._client.resolve_pal_name(pal_name)
        if pal is None:
            raise ToolError(f"未找到帕鲁: {pal_name}")
        pal_id = pal.get("id")
        skills = await self._client.get_pal_skills(pal_id)
        return {
            "pal": {"id": pal_id, "cn_name": pal.get("cn_name", pal_id)},
            "skills": skills,
            "total": len(skills),
        }


class QueryPalsByPassiveTool(Tool):
    """按被动技能查拥有该被动的帕鲁（配种被动传承）。"""

    name = "query_pals_by_passive"
    description = (
        "按被动技能中文名查询拥有该被动的帕鲁列表。用于回答“哪只帕鲁有XX(被动技能)”、“XX(被动)是哪只帕鲁的”等。"
        "被动如 工匠精神、认真、稀有、传奇、重量级。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "passive_name": {
                "type": "string",
                "description": "被动技能中文名，例如 工匠精神、重量级",
            }
        },
        "required": ["passive_name"],
    }

    def __init__(self, client: BreedingApiClient) -> None:
        self._client = client

    async def run(self, **kwargs):
        passive_name = str(kwargs.get("passive_name", "")).strip()
        if not passive_name:
            raise ToolError("passive_name 不能为空")
        pals = await self._client.query_pals_by_passive(passive_name)
        return {"passive": passive_name, "pals": pals, "total": len(pals)}


class QueryItemDropsTool(Tool):
    """查询某物品/材料由哪些帕鲁掉落（材料反查）。"""

    name = "query_item_drops"
    description = (
        "查询某物品/材料由哪些帕鲁掉落（含掉率）。用于回答“XX怎么获取/XX哪里获得/哪些帕鲁掉XX”等"
        "关于掉落来源的问题。例如 骨头、金属矿石、帕鲁油。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "item_name": {
                "type": "string",
                "description": "物品中文名，例如 骨头、金属矿石",
            }
        },
        "required": ["item_name"],
    }

    def __init__(self, client: BreedingApiClient) -> None:
        self._client = client

    async def run(self, **kwargs):
        item_name = str(kwargs.get("item_name", "")).strip()
        if not item_name:
            raise ToolError("item_name 不能为空")
        pals = await self._client.get_item_drops(item_name)
        return {"item": item_name, "pals": pals, "total": len(pals)}


class QueryItemRecipeTool(Tool):
    """查询物品的制作配方（设施 + 材料）。"""

    name = "query_item_recipe"
    description = (
        "查询某物品的制作配方（制作设施 + 所需材料及数量）。用于回答“XX怎么做/XX的配方/怎么制作XX”等"
        "关于制作配方的问题。例如 金属锭、帕鲁球。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "item_name": {
                "type": "string",
                "description": "物品中文名，例如 金属锭、帕鲁球",
            }
        },
        "required": ["item_name"],
    }

    def __init__(self, client: BreedingApiClient) -> None:
        self._client = client

    async def run(self, **kwargs):
        item_name = str(kwargs.get("item_name", "")).strip()
        if not item_name:
            raise ToolError("item_name 不能为空")
        recipe = await self._client.get_item_recipe(item_name)
        return {"item": item_name, "recipe": recipe, "total": len(recipe)}
