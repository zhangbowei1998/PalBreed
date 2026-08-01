"""Intent recognizer — LLM-first with deterministic rule fallback."""

from __future__ import annotations

import json
import re

from ..clients.breeding_api_client import BreedingApiClient
from ..config import resolve_work_type_keyword
from ..llm import ChatMessage, LLMClient, Role
from ..prompts import INTENT_RECOGNIZER_SYSTEM_PROMPT
from .schemas import Intent, IntentResult

def _extract_json_object(text: str) -> dict | None:
    """从模型输出里抽取第一个 JSON 对象."""
    text = text.strip()
    if text.startswith("{"):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    return None


class IntentRecognizer:
    def __init__(
        self,
        *,
        llm: LLMClient | None = None,
        breeding_api: BreedingApiClient | None = None,
    ) -> None:
        self._llm = llm
        self._api = breeding_api

    @property
    def has_llm(self) -> bool:
        return self._llm is not None

    async def recognize(self, message: str) -> IntentResult:
        if self._llm is not None:
            try:
                result = await self._recognize_with_llm(message)
                if result is not None:
                    return result
            except Exception:
                # LLM 失败时回落到规则识别
                pass
        return await self._recognize_with_rules(message)

    async def _recognize_with_llm(self, message: str) -> IntentResult | None:
        response = await self._llm.chat(
            [
                ChatMessage(role=Role.SYSTEM, content=INTENT_RECOGNIZER_SYSTEM_PROMPT),
                ChatMessage(role=Role.USER, content=message),
            ]
        )
        payload = _extract_json_object(response.content)
        if not payload:
            return None

        intent_str = str(payload.get("intent", ""))
        if intent_str not in {i.value for i in Intent}:
            return None

        return IntentResult(
            intent=Intent(intent_str),
            work_type=self._normalize_work_type(payload.get("work_type")),
            pal_name=payload.get("pal_name") or None,
            reason=str(payload.get("reason", "")),
        )

    def _normalize_work_type(self, value: object) -> str | None:
        if not value:
            return None
        text = str(value)
        # 已经是内部字段名（英文）
        if text in {
            "handiwork",
            "kindling",
            "watering",
            "planting",
            "generating_electricity",
            "gathering",
            "lumbering",
            "mining",
            "cooling",
            "medicine",
            "transporting",
            "farming",
        }:
            return text
        return resolve_work_type_keyword(text)

    async def _recognize_with_rules(self, message: str) -> IntentResult:
        text = message.strip()

        work_type = resolve_work_type_keyword(text)
        if work_type and ("最高" in text or "最强" in text or "最厉害" in text):
            return IntentResult(
                intent=Intent.TOP_SUITABILITY,
                work_type=work_type,
                reason="规则：工种+最高/最强",
            )

        # 尝试解析为帕鲁名（复用 breeding API 精确匹配）
        if self._api is not None and 0 < len(text) <= 12:
            pal = await self._api.resolve_pal_name(text)
            if pal:
                return IntentResult(
                    intent=Intent.EXPAND_PAL,
                    pal_name=pal.get("id") or text,
                    reason="规则：API 命中帕鲁名",
                )

        if any(
            k in text for k in ("一共", "多少只", "多少个", "总数", "最稀有", "有几个")
        ):
            return IntentResult(
                intent=Intent.PAL_STATS,
                reason="规则：统计关键词",
            )

        return IntentResult(
            intent=Intent.GENERAL_CHAT,
            reason="规则：未匹配到业务意图",
        )
