"""Intent recognition structured schemas."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class Intent(str, Enum):
    TOP_SUITABILITY = "top_suitability"  # 某工种最高/最强
    EXPAND_PAL = "expand_pal"  # 查看某帕鲁的父母（配种）
    PAL_STATS = "pal_stats"  # 数据库统计问答
    GENERAL_CHAT = "general_chat"  # 其他闲聊


class IntentResult(BaseModel):
    intent: Intent = Intent.GENERAL_CHAT
    work_type: str | None = Field(default=None)  # 内部工种字段名，如 "kindling"
    pal_name: str | None = Field(default=None)  # 用户提到的帕鲁中文名/ID
    reason: str = Field(default="")

    def is_top_suitability(self) -> bool:
        return self.intent == Intent.TOP_SUITABILITY

    def is_expand_pal(self) -> bool:
        return self.intent == Intent.EXPAND_PAL
