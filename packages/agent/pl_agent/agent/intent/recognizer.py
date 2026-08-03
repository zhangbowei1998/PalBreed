"""Intent recognizer — LLM-first with deterministic rule fallback."""

from __future__ import annotations

import json
import re

from ..clients.breeding_api_client import BreedingApiClient
from ..config import resolve_work_type_keyword
from ..llm import ChatMessage, LLMClient, Role
from ..prompts import INTENT_RECOGNIZER_SYSTEM_PROMPT
from .schemas import Intent, IntentResult


# 详情/物品类疑问句中的"谓语/疑问词"片段，剥离后剩下的主体即为名称候选。
_DETAIL_STRIP_PATTERNS = (
    r"(?:有什么|有哪些|是哪些|的属性|的技能|的掉落|的伙伴技能|的召唤|的详情|的"
    r"面板|的)"
    r"(?:技能|属性|掉落|伙伴技能|召唤|详情|面板)?"
)


def _extract_pal_candidate(text: str) -> str | None:
    """从「XX 有什么技能/属性/掉落」类句子中提取帕鲁名候选。

    依次剥离详情关键词及其前后疑问片段，得到最可能是名称的主体。
    例："阿努比斯有什么技能" → "阿努比斯"；"阿努比斯的属性" → "阿努比斯"。
    剥离失败时原样返回（调用方会再试一次整体匹配）。
    """
    stripped = re.sub(r"[，。！？?、\s]+", "", text)
    # 去掉结尾的详情关键词（如 "有什么技能" / "的属性" / "技能" / "详情"）
    cleaned = re.sub(_DETAIL_STRIP_PATTERNS, "", stripped)
    cleaned = cleaned.strip(" ，,。！!？?：:、的")
    return cleaned or None


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
            item_name=payload.get("item_name") or None,
            passive_name=payload.get("passive_name") or None,
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

        # 被动技能：哪只帕鲁拥有 XX（被动）
        passive_kw = ("被动" in text) or any(
            p in text for p in ("工匠精神", "稀有", "传奇", "认真", "凶猛", "脑筋", "速霸", "体魄")
        )
        if passive_kw:
            # 提取被动名：形如 "哪只有工匠精神" / "工匠精神是哪只"
            m = re.search(r"(工匠精神|认真|稀有|传奇|凶猛|脑筋|速霸|体魄|传说|笨拙|胆小|鲁莽|暴躁|安静|软弱|强壮|美丽|优雅|幸运|精悍|巨人|灵活|耐性|神速)", text)
            passive = m.group(1) if m else None
            if passive:
                return IntentResult(
                    intent=Intent.PASSIVE_QUERY,
                    passive_name=passive,
                    reason="规则：被动关键词",
                )

        # 物品掉落 / 制作配方
        item_kw = any(
            k in text
            for k in ("怎么获取", "哪里获得", "哪里掉", "怎么获得", "怎么做", "制作", "配方", "掉", "从哪")
        )
        if item_kw:
            # 若提到帕鲁名则优先 expand/pal_detail（由后续 API 精确命中接管）；
            # 这里先粗提取物品名（非帕鲁名的名词短语）
            if self._api is not None and 0 < len(text) <= 12:
                pal = await self._api.resolve_pal_name(text)
                if pal:
                    return IntentResult(
                        intent=Intent.EXPAND_PAL,
                        pal_name=pal.get("id") or text,
                        reason="规则：物品关键词但 API 命中帕鲁名",
                    )
            return IntentResult(
                intent=Intent.ITEM_QUERY,
                reason="规则：物品获取/制作关键词",
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

        # 帕鲁详情：属性/技能/掉落/伙伴技能/召唤
        if any(
            k in text for k in ("属性", "技能", "掉落", "伙伴技能", "召唤", "详情", "面板")
        ):
            if self._api is not None:
                # 先尝试剥离详情关键词提取帕鲁名候选（如 "阿努比斯有什么技能" → "阿努比斯"）
                candidate = _extract_pal_candidate(text)
                for probe in (candidate, text):
                    if probe and 0 < len(probe) <= 12:
                        pal = await self._api.resolve_pal_name(probe)
                        if pal:
                            return IntentResult(
                                intent=Intent.PAL_DETAIL,
                                pal_name=pal.get("id") or probe,
                                reason="规则：详情关键词 + API 命中帕鲁名",
                            )
            return IntentResult(
                intent=Intent.PAL_DETAIL,
                reason="规则：详情关键词",
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
