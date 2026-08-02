"""通用只读 SQL 查询端点 — Text-to-SQL 兜底的“安全执行器”。

设计遵循 Text-to-SQL.md 的四道防火墙：
  ① 只读校验：sqlglot AST 解析拦截非 SELECT + 拒绝多语句
  ② 白名单表：仅允许查询白名单视图（v_pal_full / v_item_drop / v_skill_learn）
  ③ 强制 LIMIT：无则追加 100，有则钳制到 200；限制 OFFSET 深翻页
  ④ 超时熔断：3 秒
"""

from __future__ import annotations

import asyncio

import sqlglot
from fastapi import APIRouter, Request
from sqlglot import exp

from .. import SqlQueryRequest
from ..db.queries import OrmQueryService
from ..formatter import format_error, format_success

router = APIRouter(prefix="/api")

# 白名单视图（Agent 只能查这些；底层 22 表不暴露）
ALLOWED_VIEWS = frozenset({"v_pal_full", "v_item_drop", "v_skill_learn"})

DEFAULT_LIMIT = 100
MAX_LIMIT = 200
MAX_OFFSET_PLUS_LIMIT = 500
TIMEOUT_S = 3.0

_ERROR_CODES = {
    "blocked": "SQL_BLOCKED",
    "syntax": "SQL_SYNTAX",
    "timeout": "SQL_TIMEOUT",
    "exec": "SQL_ERROR",
}


class SqlGuard:
    """Text-to-SQL 安全校验（纯逻辑，可独立单元测试）。"""

    @staticmethod
    def _extract_number(node) -> int | None:
        """从 sqlglot 表达式节点提取整数值（Literal/Column 等）。"""
        if node is None:
            return None
        try:
            return int(node.name)
        except (AttributeError, ValueError):
            try:
                return int(node.this)
            except (AttributeError, ValueError, TypeError):
                return None

    @staticmethod
    def validate(sql: str) -> tuple[bool, str | None, str | None]:
        """校验并规范化一条 SQL。

        Returns: (ok, error_code, final_sql)
        - ok=True: 校验通过，final_sql 为强制 LIMIT 后的可执行 SQL
        - ok=False: error_code 为 SQL_BLOCKED/SQL_SYNTAX，final_sql 为 None
        """
        sql = (sql or "").strip()
        if not sql:
            return False, _ERROR_CODES["blocked"], None

        # ① 只读校验：解析为 AST 列表，拒绝多语句
        try:
            parsed = sqlglot.parse(sql, read="postgres")
        except Exception:  # noqa: BLE001 — sqlglot 解析失败 → 语法错误
            return False, _ERROR_CODES["syntax"], None
        if not parsed or len(parsed) != 1:
            return False, _ERROR_CODES["blocked"], None

        statement = parsed[0]
        # sqlglot 中 WITH 子句与主查询合并为单个 Select（with_ 子节点），
        # 因此顶层只需验证是 Select。
        if not isinstance(statement, exp.Select):
            return False, _ERROR_CODES["blocked"], None

        # CTE 别名集合：WITH 里定义的别名不参与白名单校验
        # 注意：sqlglot 中 CTE 挂在 select.args["with_"]（With 节点）
        cte_aliases: set[str] = set()
        with_clause = statement.args.get("with_")
        if with_clause is not None:
            for cte in with_clause.expressions:
                alias = getattr(cte, "alias", None)
                if alias:
                    cte_aliases.add(alias.lower())

        # ② 白名单表：提取所有 FROM 引用的表名（排除 CTE 别名）
        for table in statement.find_all(exp.Table):
            name = table.name.lower()
            if name in cte_aliases:
                continue
            if name not in ALLOWED_VIEWS:
                return False, _ERROR_CODES["blocked"], None

        # ③ 强制 LIMIT + 限制 OFFSET
        limit_expr = statement.args.get("limit")
        offset_expr = statement.args.get("offset")
        offset_val = SqlGuard._extract_number(
            offset_expr.args.get("expression") if offset_expr else None
        ) or 0
        if limit_expr is not None:
            user_limit = SqlGuard._extract_number(limit_expr.expression) or DEFAULT_LIMIT
            final_limit = min(user_limit, MAX_LIMIT)
        else:
            final_limit = DEFAULT_LIMIT

        if offset_val + final_limit > MAX_OFFSET_PLUS_LIMIT:
            return False, _ERROR_CODES["blocked"], None

        # 用 AST 改写 LIMIT，再 transpile 回 postgres 方言
        statement.set(
            "limit", exp.Limit(expression=exp.Literal.number(final_limit))
        )
        try:
            final_sql = statement.sql(dialect="postgres")
        except Exception:  # noqa: BLE001
            return False, _ERROR_CODES["syntax"], None
        return True, None, final_sql


@router.post("/sql/query")
async def sql_query(request: Request):
    """执行一条只读 SELECT（Text-to-SQL 兜底）。"""
    body = SqlQueryRequest.model_validate(await request.json())

    ok, error_code, final_sql = SqlGuard.validate(body.sql)
    if not ok:
        return format_error(error_code, f"SQL 校验未通过: {body.sql}")

    orm_service: OrmQueryService = request.app.state.orm_service
    try:
        result = await asyncio.wait_for(
            orm_service.execute_raw_sql(final_sql), timeout=TIMEOUT_S
        )
    except asyncio.TimeoutError:
        return format_error(_ERROR_CODES["timeout"], "SQL 查询超时")
    except Exception as exc:  # noqa: BLE001
        return format_error(_ERROR_CODES["exec"], f"SQL 执行失败: {exc}")

    return format_success(result)
