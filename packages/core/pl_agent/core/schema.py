"""
Canonical data models — the single source of truth for all data flowing through the system.

External data sources MUST be transformed into these models by adapters
before entering the core engine. No module outside of `adapters/` should
depend on any external data format.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# =============================================================================
# Enums
# =============================================================================

class Element(Enum):
    """帕鲁属性"""
    FIRE = "Fire"
    WATER = "Water"
    GRASS = "Grass"
    EARTH = "Earth"
    ELECTRIC = "Electric"
    ICE = "Ice"
    DRAGON = "Dragon"
    DARK = "Dark"
    NEUTRAL = "Neutral"


class WorkType(Enum):
    """工作适应性类型 — 12 种"""
    HANDIWORK = "handiwork"
    KINDLING = "kindling"
    WATERING = "watering"
    PLANTING = "planting"
    GENERATING_ELECTRICITY = "generating_electricity"
    GATHERING = "gathering"
    LUMBERING = "lumbering"
    MINING = "mining"
    COOLING = "cooling"
    MEDICINE = "medicine"
    TRANSPORTING = "transporting"
    FARMING = "farming"


# =============================================================================
# Canonical Data Models
# =============================================================================

@dataclass
class WorkSuitability:
    """工作适应性 — 每个工种等级 0-10, 0 表示无此适应性.

    JSON 序列化时只输出非零值, 反序列化时缺失字段视为 0.
    """
    handiwork: int = 0
    kindling: int = 0
    watering: int = 0
    planting: int = 0
    generating_electricity: int = 0
    gathering: int = 0
    lumbering: int = 0
    mining: int = 0
    cooling: int = 0
    medicine: int = 0
    transporting: int = 0
    farming: int = 0

    def max_level(self) -> int:
        """返回最高工作等级"""
        return max(v for v in self.__dict__.values() if isinstance(v, int))

    def has_type(self, work_type: str) -> bool:
        """是否拥有指定工种"""
        return getattr(self, work_type, 0) > 0

    def non_zero(self) -> dict[str, int]:
        """返回非零工种字典 (用于 JSON 序列化)"""
        return {k: v for k, v in self.__dict__.items()
                if isinstance(v, int) and v > 0}

    def to_dict(self) -> dict[str, int]:
        """序列化 — 只输出有值的工种"""
        return self.non_zero()

    @classmethod
    def from_dict(cls, d: dict[str, int]) -> "WorkSuitability":
        """反序列化 — 缺失字段视为 0"""
        valid_fields = set(cls.__dataclass_fields__.keys())
        return cls(**{k: d.get(k, 0) for k in valid_fields})


@dataclass
class Pal:
    """帕鲁 canonical 实体 — 全项目唯一数据规范.

    Attributes:
        id:           内部唯一标识 (内部英文名, 如 "Anubis").
        number:       图鉴编号 (1-204+).
        cn_name:      中文名 (官方译名).
        en_name:      英文名 (图鉴英文名, 可能与 id 不同).
        combi_rank:   CombiRank 繁殖力值 (配种计算核心参数).
        elements:     属性列表 (1-2 个 Element).
        rarity:       稀有度 1-10.
        work_suitability: 工作适应性.
        is_wild:      是否野外可直接捕获.
        aliases:      别称/昵称列表.
        image_url:    图片 URL.
        wiki_url:     Wiki 页面 URL.
        spawn_locations: 主要出没区域.
    """
    id: str
    number: int
    cn_name: str
    en_name: str
    combi_rank: int
    elements: list[Element]
    rarity: int
    work_suitability: WorkSuitability
    is_wild: bool

    # ---- optional metadata ----
    aliases: list[str] = field(default_factory=list)
    image_url: Optional[str] = None
    wiki_url: Optional[str] = None
    spawn_locations: list[str] = field(default_factory=list)

    # ---- quality flags (not serialized to public output) ----
    _incomplete: bool = field(default=False, repr=False)
    _suspicious: bool = field(default=False, repr=False)
    _suspicious_fields: list[str] = field(default_factory=list, repr=False)
    _source: str = field(default="", repr=False)

    def to_dict(self) -> dict:
        """序列化为 JSON 兼容字典 (不含内部标记)."""
        return {
            "id": self.id,
            "number": self.number,
            "cn_name": self.cn_name,
            "en_name": self.en_name,
            "combi_rank": self.combi_rank,
            "elements": [e.value for e in self.elements],
            "rarity": self.rarity,
            "work_suitability": self.work_suitability.to_dict(),
            "is_wild": self.is_wild,
            "aliases": self.aliases,
            "image_url": self.image_url,
            "wiki_url": self.wiki_url,
            "spawn_locations": self.spawn_locations,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Pal":
        """从字典反序列化."""
        elements = [
            e if isinstance(e, Element) else Element(e)
            for e in d.get("elements", [])
        ]
        ws_raw = d.get("work_suitability", {})
        ws = (
            WorkSuitability.from_dict(ws_raw)
            if isinstance(ws_raw, dict) else ws_raw
        )
        return cls(
            id=d["id"],
            number=d["number"],
            cn_name=d["cn_name"],
            en_name=d["en_name"],
            combi_rank=d["combi_rank"],
            elements=elements,
            rarity=d.get("rarity", 1),
            work_suitability=ws,
            is_wild=d.get("is_wild", False),
            aliases=d.get("aliases", []),
            image_url=d.get("image_url"),
            wiki_url=d.get("wiki_url"),
            spawn_locations=d.get("spawn_locations", []),
        )


# =============================================================================
# Breeding Rules
# =============================================================================

@dataclass
class SpecialCombination:
    """特殊配种组合 — 固定父母 → 固定子代."""
    parent_a: str
    parent_b: str
    child: str
    note: str = ""


@dataclass
class SelfOnly:
    """仅同类繁殖的帕鲁."""
    pal_id: str
    note: str = ""


@dataclass
class Unbreedable:
    """不可配种的帕鲁."""
    pal_id: str
    note: str = ""


@dataclass
class MutationRule:
    """突变规则 (1.0 新机制)."""
    parent_a: str
    parent_b: str
    child: str
    note: str = ""


@dataclass
class BreedingRules:
    """配种规则集合."""
    game_version: str
    last_updated: str
    special_combinations: list[SpecialCombination] = field(default_factory=list)
    self_only: list[SelfOnly] = field(default_factory=list)
    unbreedable: list[Unbreedable] = field(default_factory=list)
    breeding_excluded: list[str] = field(default_factory=list)
    mutations: list[MutationRule] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "game_version": self.game_version,
            "last_updated": self.last_updated,
            "special_combinations": [
                {"parent_a": s.parent_a, "parent_b": s.parent_b,
                 "child": s.child, "note": s.note}
                for s in self.special_combinations
            ],
            "self_only": [
                {"pal_id": s.pal_id, "note": s.note}
                for s in self.self_only
            ],
            "unbreedable": [
                {"pal_id": u.pal_id, "note": u.note}
                for u in self.unbreedable
            ],
            "breeding_excluded": self.breeding_excluded,
            "mutations": [
                {"parent_a": m.parent_a, "parent_b": m.parent_b,
                 "child": m.child, "note": m.note}
                for m in self.mutations
            ],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "BreedingRules":
        return cls(
            game_version=d["game_version"],
            last_updated=d["last_updated"],
            special_combinations=[
                SpecialCombination(**s)
                for s in d.get("special_combinations", [])
            ],
            self_only=[SelfOnly(**s) for s in d.get("self_only", [])],
            unbreedable=[Unbreedable(**u) for u in d.get("unbreedable", [])],
            breeding_excluded=d.get("breeding_excluded", []),
            mutations=[
                MutationRule(**m) for m in d.get("mutations", [])
            ],
        )


# =============================================================================
# Dataset Metadata
# =============================================================================

@dataclass
class DatasetMeta:
    """数据集元信息."""
    game_version: str = ""
    generated_at: str = ""
    total_pals: int = 0
    wild_pals: int = 0
    field_completeness: float = 1.0
    source: str = ""
