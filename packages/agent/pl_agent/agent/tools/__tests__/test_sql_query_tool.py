"""run_sql_query 工具单元测试 — mock client。"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from pl_agent.agent.tools.base import ToolError
from pl_agent.agent.tools.breeding import build_breeding_tools
from pl_agent.agent.tools.sql_query import RunSqlQueryTool


def _client(**overrides):
    defaults = {
        "run_sql_query": AsyncMock(
            return_value={
                "columns": ["cn_name", "size", "run_speed"],
                "rows": [["空涡龙", "XL", 1700], ["圣光骑士", "L", 800]],
                "row_count": 2,
            }
        ),
    }
    defaults.update(overrides)
    return type("MC", (), defaults)()


def test_tool_registered():
    tools = build_breeding_tools(_client())
    names = [t.name for t in tools]
    assert "run_sql_query" in names


@pytest.mark.asyncio
async def test_tool_calls_client():
    client = _client()
    tool = RunSqlQueryTool(client)
    result = await tool.run(
        sql="SELECT cn_name, size FROM v_pal_full LIMIT 10"
    )
    assert result["row_count"] == 2
    assert result["columns"] == ["cn_name", "size", "run_speed"]
    client.run_sql_query.assert_called_once_with(
        "SELECT cn_name, size FROM v_pal_full LIMIT 10"
    )


@pytest.mark.asyncio
async def test_empty_sql_raises():
    tool = RunSqlQueryTool(_client())
    with pytest.raises(ToolError):
        await tool.run(sql="  ")


def test_description_mentions_readonly():
    tool = RunSqlQueryTool(_client())
    assert "SELECT" in tool.description
    assert "LIMIT" in tool.description
    assert "v_pal_full" in tool.description
