"""Deterministic breeding tools — expose the fixed breeding API to the LLM.

配种方案是固定公式，绝不能由 LLM 自行推算；这些工具保证 LLM 通过
function calling 拿到精确结果。
"""

from __future__ import annotations

from ..clients.breeding_api_client import BreedingApiClient
from ..config import resolve_work_type_keyword, work_type_to_cn
from .base import Tool, ToolError


class QueryParentPairsTool(Tool):
    """查询某只帕鲁的父母配种组合（精确数据，不可自行推算）。"""

    name = "query_parent_pairs"
    description = (
        "查询指定帕鲁的父母配种组合。配种结果是固定公式计算出的精确数据，"
        "必须调用本工具获取，绝对不要自己推算。入参是帕鲁名（中文或英文或ID）。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "pal_name": {
                "type": "string",
                "description": "帕鲁名称，例如 墨罗娜、阿努比斯 或英文ID",
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
        pairs = await self._client.get_parent_pairs(pal_id)
        return {
            "pal": {"id": pal_id, "cn_name": pal.get("cn_name", pal_id)},
            "parent_pairs": pairs,
            "total": len(pairs),
        }


class ResolvePalTool(Tool):
    """按名称精确解析一只帕鲁的基础信息。"""

    name = "resolve_pal"
    description = "按名称（中文/英文/ID）解析一只帕鲁的基础信息（编号、中文名、英文名、CombiRank、稀有度等）。"
    parameters = {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "帕鲁名称，例如 墨罗娜、Anubis",
            }
        },
        "required": ["name"],
    }

    def __init__(self, client: BreedingApiClient) -> None:
        self._client = client

    async def run(self, **kwargs):
        name = str(kwargs.get("name", "")).strip()
        if not name:
            raise ToolError("name 不能为空")
        pal = await self._client.resolve_pal_name(name)
        if pal is None:
            raise ToolError(f"未找到帕鲁: {name}")
        return pal


class QueryTopSuitabilityTool(Tool):
    """查询某工种适应性最高的帕鲁。"""

    name = "query_top_suitability"
    description = (
        "查询某个工作工种（如手工、烧火、采矿、浇水、伐木、搬运等）适应性"
        "等级最高的帕鲁。用于回答‘xx最高/最强的是哪只帕鲁’。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "work_type": {
                "type": "string",
                "description": "工种中文关键词，例如 手工、烧火、采矿、浇水、伐木、搬运、生火",
            },
            "top_n": {
                "type": "integer",
                "description": "返回前 N 个（默认 3）",
                "minimum": 1,
                "maximum": 10,
            },
        },
        "required": ["work_type"],
    }

    def __init__(self, client: BreedingApiClient, top_n_default: int = 3) -> None:
        self._client = client
        self._top_n_default = top_n_default

    async def run(self, **kwargs):
        work_type = resolve_work_type_keyword(str(kwargs.get("work_type", "")))
        if work_type is None:
            raise ToolError(f"无法识别的工种: {kwargs.get('work_type')}")
        top_n = int(kwargs.get("top_n") or self._top_n_default)
        candidates = await self._client.query_top_suitability(work_type, 1, top_n)
        return {
            "work_type": work_type_to_cn(work_type),
            "candidates": [
                {
                    "pal_id": c.pal.id,
                    "cn_name": c.pal.cn_name,
                    "matched_level": c.matched_level,
                }
                for c in candidates
            ],
        }


class QueryStatsTool(Tool):
    """查询帕鲁数据库统计信息（总数等）。"""

    name = "query_pal_stats"
    description = "查询帕鲁数据库统计信息，例如一共有多少只帕鲁。"
    parameters = {"type": "object", "properties": {}, "required": []}

    def __init__(self, client: BreedingApiClient) -> None:
        self._client = client

    async def run(self, **kwargs):
        return await self._client.query_stats()


def build_breeding_tools(
    client: BreedingApiClient, top_n_default: int = 3
) -> list[Tool]:
    """Build the full deterministic breeding tool set."""
    from .pal_info import (
        QueryItemDropsTool,
        QueryItemRecipeTool,
        QueryPalDetailTool,
        QueryPalsByPassiveTool,
        QueryPalSkillsTool,
    )

    return [
        QueryParentPairsTool(client),
        ResolvePalTool(client),
        QueryTopSuitabilityTool(client, top_n_default=top_n_default),
        QueryStatsTool(client),
        # tc-imba 新数据能力 (S6-S10)
        QueryPalDetailTool(client),
        QueryPalSkillsTool(client),
        QueryPalsByPassiveTool(client),
        QueryItemDropsTool(client),
        QueryItemRecipeTool(client),
    ]
