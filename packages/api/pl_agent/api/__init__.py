"""Pydantic models for API."""

from pydantic import BaseModel


class QueryRequest(BaseModel):
    input: str
    max_depth: int = 5


class SqlQueryRequest(BaseModel):
    """Text-to-SQL 兜底查询请求（只读 SELECT，经安全层执行）。"""

    sql: str
