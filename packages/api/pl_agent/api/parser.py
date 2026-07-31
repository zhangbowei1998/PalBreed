"""Input parser — routes user input to query types."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from pl_agent.core.schema import Pal, WorkType

# ── work type keyword mappings ────────────────────────────────────

CN_TO_EN_WORK_TYPE: dict[str, str] = {
    "手工": "handiwork",
    "手工作业": "handiwork",
    "制作": "handiwork",
    "生火": "kindling",
    "烧火": "kindling",
    "点火": "kindling",
    "火焰": "kindling",
    "浇水": "watering",
    "灌溉": "watering",
    "播种": "planting",
    "种植": "planting",
    "种地": "planting",
    "发电": "generating_electricity",
    "电力": "generating_electricity",
    "充电": "generating_electricity",
    "采集": "gathering",
    "收获": "gathering",
    "伐木": "lumbering",
    "砍树": "lumbering",
    "采矿": "mining",
    "挖矿": "mining",
    "冷却": "cooling",
    "降温": "cooling",
    "制冷": "cooling",
    "制药": "medicine",
    "医药": "medicine",
    "搬运": "transporting",
    "运输": "transporting",
    "牧场": "farming",
    "放牧": "farming",
}

VALID_EN_WORK_TYPES = frozenset(wt.value for wt in WorkType)
ALL_CN_KEYWORDS = frozenset(CN_TO_EN_WORK_TYPE.keys())


# ── query types ───────────────────────────────────────────────────


class QueryKind(Enum):
    NAME = "name_query"
    SUITABILITY = "suitability_query"
    FUZZY = "fuzzy"


@dataclass
class ParsedQuery:
    kind: QueryKind
    raw_input: str
    pal: Pal | None = None
    work_conditions: list[tuple[str, int]] = field(default_factory=list)
    fuzzy_candidates: list[Pal] = field(default_factory=list)


# ── parser ────────────────────────────────────────────────────────


class QueryParser:
    """解析用户输入, 判断查询类型.

    优先级:
      1. 含 ":" → suitability_query
      2. 纯工种关键词 → suitability_query (level=1)
      3. 名称精确匹配 → name_query
      4. 模糊匹配 → fuzzy / not_found
    """

    def __init__(self, pals: list[Pal]):
        # 建立多维度索引
        self._by_id: dict[str, Pal] = {p.id.casefold(): p for p in pals}
        self._by_cn: dict[str, Pal] = {p.cn_name.casefold(): p for p in pals}
        self._by_en: dict[str, Pal] = {p.en_name.casefold(): p for p in pals}
        self._by_number: dict[str, Pal] = {str(p.number): p for p in pals}
        # aliases
        self._by_alias: dict[str, Pal] = {}
        for p in pals:
            for a in p.aliases:
                self._by_alias[a.casefold()] = p
        # all for fuzzy
        self._all_pals = pals

    def parse(self, text: str) -> ParsedQuery:
        """主解析入口."""
        text = text.strip()
        if not text:
            return ParsedQuery(kind=QueryKind.FUZZY, raw_input=text)

        # 1. 含 ":" → suitability
        if ":" in text:
            conds = self._parse_work_conditions(text)
            if conds:
                return ParsedQuery(
                    kind=QueryKind.SUITABILITY, raw_input=text, work_conditions=conds
                )
            # 冒号但解析失败 → 继续尝试名称匹配

        # 2. 纯工种关键词 (无冒号)
        if text in ALL_CN_KEYWORDS or text in VALID_EN_WORK_TYPES:
            wt = self._resolve_work_type(text)
            return ParsedQuery(
                kind=QueryKind.SUITABILITY, raw_input=text, work_conditions=[(wt, 1)]
            )

        # 3. 精确名称匹配
        pal = self._match_exact(text)
        if pal:
            return ParsedQuery(kind=QueryKind.NAME, raw_input=text, pal=pal)

        # 4. 模糊匹配
        fuzzy = self._match_fuzzy(text)
        if fuzzy:
            return ParsedQuery(
                kind=QueryKind.FUZZY, raw_input=text, fuzzy_candidates=fuzzy
            )

        return ParsedQuery(kind=QueryKind.FUZZY, raw_input=text)

    # ── work conditions ────────────────────────────────────────

    def _parse_work_conditions(self, text: str) -> list[tuple[str, int]]:
        """解析 '手工:6,mining:3' → [(handiwork, 6), (mining, 3)]."""
        parts = [p.strip() for p in text.split(",") if p.strip()]
        result: list[tuple[str, int]] = []
        for part in parts:
            parsed = self._parse_one_condition(part)
            if parsed:
                result.append(parsed)
        return result

    def _parse_one_condition(self, part: str) -> tuple[str, int] | None:
        """解析单个 '工种:等级'."""
        if ":" in part:
            key, _, val = part.partition(":")
            key, val = key.strip(), val.strip()
        else:
            key, val = part.strip(), "1"

        wt = self._resolve_work_type(key)
        if wt is None:
            return None
        try:
            level = int(val)
        except ValueError:
            level = 1
        return (wt, level)

    def _resolve_work_type(self, key: str) -> str | None:
        """中文/英文工种 → 内部字段名."""
        k = key.casefold()
        if k in VALID_EN_WORK_TYPES:
            return k
        return CN_TO_EN_WORK_TYPE.get(key) or CN_TO_EN_WORK_TYPE.get(k)

    # ── name matching ──────────────────────────────────────────

    def _match_exact(self, text: str) -> Pal | None:
        t = text.casefold()
        # 按优先级
        for lookup in [
            self._by_cn,
            self._by_en,
            self._by_id,
            self._by_alias,
            self._by_number,
        ]:
            p = lookup.get(t)
            if p:
                return p
        return None

    def _match_fuzzy(self, text: str) -> list[Pal]:
        """子串前缀匹配 (编辑距离 ≤ 2)."""
        t = text.casefold()
        results: list[Pal] = []

        # 前缀匹配优先
        for p in self._all_pals:
            if p.cn_name.casefold().startswith(t):
                results.append(p)
            elif p.en_name.casefold().startswith(t):
                if p not in results:
                    results.append(p)

        # 包含匹配
        if not results:
            for p in self._all_pals:
                if t in p.cn_name.casefold() or t in p.en_name.casefold():
                    if p not in results:
                        results.append(p)

        return results[:5]

    # ── public helpers ─────────────────────────────────────────

    @property
    def valid_work_types_cn(self) -> list[str]:
        return sorted(set(CN_TO_EN_WORK_TYPE.values()))
