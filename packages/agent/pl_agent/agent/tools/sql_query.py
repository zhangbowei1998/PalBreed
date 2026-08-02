"""Text-to-SQL 兜底工具 — 长尾问题查宽表。

仅当既有 9 个常规工具无法覆盖时使用。SQL 字符串经后端 api 安全层执行：
只读 SELECT、白名单视图、强制 LIMIT、超时熔断。
"""

from __future__ import annotations

from ..clients.breeding_api_client import BreedingApiClient
from .base import Tool, ToolError


class RunSqlQueryTool(Tool):
    """长尾问题兜底：把自然语言问题转成 SQL 查宽表。"""

    name = "run_sql_query"
    description = (
        "当用户提问超出配种/工种/技能/被动/物品等常规工具范围时，"
        "把问题翻译成 SQL 查询宽表 v_pal_full（帕鲁全量宽表）"
        "或 v_item_drop（掉落来源）/ v_skill_learn（可学技能）。"
        "只写 SELECT，不写其他语句，记得加 LIMIT。"
        "例：'哪些帕鲁体型是 L 且跑得快' → "
        "SELECT cn_name, size, run_speed FROM v_pal_full "
        "WHERE size='L' AND run_speed > 7000 LIMIT 20"
    )
    parameters = {
        "type": "object",
        "properties": {
            "sql": {
                "type": "string",
                "description": "只读 SELECT 语句，查询白名单视图（v_pal_full / v_item_drop / v_skill_learn）",
            }
        },
        "required": ["sql"],
    }

    def __init__(self, client: BreedingApiClient) -> None:
        self._client = client

    async def run(self, **kwargs):
        sql = str(kwargs.get("sql", "")).strip()
        if not sql:
            raise ToolError("sql 不能为空")
        result = await self._client.run_sql_query(sql)
        # 转成对 LLM 友好的结构
        columns = result.get("columns") or []
        rows = result.get("rows") or []
        return {
            "columns": columns,
            "rows": rows,
            "row_count": len(rows),
        }
