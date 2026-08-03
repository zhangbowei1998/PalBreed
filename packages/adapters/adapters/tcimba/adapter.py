"""tc-imba 适配器 — 聚合解析结果，构造 TciDataBundle 供 PostgresWriter 写入 22 表。

数据流: data/tc-imba/ json → parser 解析 → TciDataBundle → PostgresWriter.upsert_ext
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from . import parser


@dataclass
class TciDataBundle:
    """tc-imba 全量数据的聚合视图（语义 id，尚未映射 DB int id）。

    供 PostgresWriter.upsert_ext 使用；写入时先插主表再映射关联表。
    """

    # 帕鲁
    pal_raw: list[dict] = field(default_factory=list)       # parse_pal_raw 结果
    # 技能
    skills: list[dict] = field(default_factory=list)
    pal_skills: list[dict] = field(default_factory=list)     # {game_id, waza_id, learn_level}
    # 被动
    passives: list[dict] = field(default_factory=list)
    passive_effects: list[dict] = field(default_factory=list)
    passive_invokes: list[dict] = field(default_factory=list)
    pal_passives: list[dict] = field(default_factory=list)  # {game_id, passive_id}
    # 物品
    items: list[dict] = field(default_factory=list)
    item_recipes: list[dict] = field(default_factory=list)
    item_recipe_stations: list[dict] = field(default_factory=list)
    item_recipe_materials: list[dict] = field(default_factory=list)
    item_sources: list[dict] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        return {
            "pal": len(self.pal_raw),
            "skill": len(self.skills),
            "pal_skill": len(self.pal_skills),
            "passive": len(self.passives),
            "passive_effect": len(self.passive_effects),
            "passive_invoke": len(self.passive_invokes),
            "pal_passive": len(self.pal_passives),
            "item": len(self.items),
            "item_recipe": len(self.item_recipes),
            "item_recipe_station": len(self.item_recipe_stations),
            "item_recipe_material": len(self.item_recipe_materials),
            "item_source": len(self.item_sources),
        }


def build_bundle(data_dir: Path, *, include_old_pal: dict | None = None) -> TciDataBundle:
    """从 data/tc-imba/ 目录构建完整 TciDataBundle。

    include_old_pal: 旧 pal_data.json（可选），用于继承 is_wild 等 tc-imba 缺失字段。
    """
    pals_json = parser.load_json(data_dir / "pals.json")
    breeding_json = parser.load_json(data_dir / "breeding.json")
    zh = parser.load_json(data_dir / "pals_zh.json")
    en = parser.load_json(data_dir / "pals_en.json")
    zh_skills = parser.load_json(data_dir / "zh_skills.json")
    zh_passives = parser.load_json(data_dir / "zh_passives.json")
    zh_items = parser.load_json(data_dir / "zh_items.json")

    passives_json = parser.load_json(data_dir / "passives.json")
    items_json = parser.load_json(data_dir / "items.json")

    pal_raw = parser.parse_pal_raw(pals_json, breeding_json, zh, en)

    # 旧数据继承（is_wild / spawn_locations / aliases）
    old = include_old_pal or {}
    for p in pal_raw:
        op = old.get(p["id"], {})
        p.setdefault("is_wild", op.get("is_wild", True))
        p.setdefault("aliases", op.get("aliases", []))
        p.setdefault("spawn_locations", op.get("spawn_locations", []))
        # 资源 URL（图标域名已实测有效）
        icon = p.get("icon", "")
        p["image_url"] = (
            f"https://resource-palworld.tc-imba.com/icons/{icon}.webp" if icon else None
        )
        p["wiki_url"] = f"https://palworld.tc-imba.com/pals/{p['id']}"

    skills, pal_skills = parser.parse_skills(pal_raw, zh_skills)
    passives, passive_effects, passive_invokes = parser.parse_passives(passives_json, zh_passives)
    items, item_recipes, stations, materials, sources = parser.parse_items(items_json, zh_items)

    # 帕鲁固有被动 {game_id, passive_id}
    pal_passives = [
        {"game_id": p["id"], "passive_id": pid}
        for p in pal_raw for pid in p.get("passives", [])
    ]

    return TciDataBundle(
        pal_raw=pal_raw,
        skills=skills,
        pal_skills=pal_skills,
        passives=passives,
        passive_effects=passive_effects,
        passive_invokes=passive_invokes,
        pal_passives=pal_passives,
        items=items,
        item_recipes=item_recipes,
        item_recipe_stations=stations,
        item_recipe_materials=materials,
        item_sources=sources,
    )


def load_old_pal_data(path: Path) -> dict:
    """加载旧 pal_data.json（用于继承 tc-imba 缺失字段）。"""
    if not path.exists():
        return {}
    return parser.load_json(path)
