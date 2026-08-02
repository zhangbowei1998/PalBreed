"""tc-imba JSON 解析器 — 将 data-palworld.tc-imba.com 原始数据解析为结构化 dict 列表。

这些是「tc-imba 源数据视图」（带语义 id 如 game_id/item_id/passive_id），
由 adapter.py 聚合为 TciDataBundle，再由 PostgresWriter 写入 22 表（映射为 DB int id）。
"""

from __future__ import annotations

import json
from pathlib import Path

# ---- 字段映射（与 scripts/convert_tcimba.py 一致）----
WORK_MAP = {
    "Handcraft": "handiwork",
    "EmitFlame": "kindling",
    "Watering": "watering",
    "Seeding": "planting",
    "GenerateElectricity": "generating_electricity",
    "Collection": "gathering",
    "Deforest": "lumbering",
    "Mining": "mining",
    "Cool": "cooling",
    "ProductMedicine": "medicine",
    "Transport": "transporting",
    "MonsterFarm": "farming",
}

ELEMENT_MAP = {
    "Normal": "Neutral",
    "Fire": "Fire",
    "Water": "Water",
    "Electricity": "Electric",
    "Leaf": "Grass",
    "Ice": "Ice",
    "Dark": "Dark",
    "Dragon": "Dragon",
    "Earth": "Earth",
    "None": "Neutral",
}

WORK_TYPES = tuple(WORK_MAP.values())


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


# =============================================================================
# 帕鲁
# =============================================================================

def parse_pal_raw(pals_json: dict, breeding_json: dict, zh: dict, en: dict) -> list[dict]:
    """每个帕鲁的原始解析结果（含 stats/friendship/partner_skill 等子对象）。

    返回 dict: {
        id, zukan_index, zukan_index_suffix, cn_name, en_name, combi_rank,
        rarity, elements[映射后], work_suitability{映射后}, breed_child,
        genus, size, egg, nocturnal, reaction, best_work, summonable, predator,
        boss_first_defeat_reward, icon,
        stats{}, friendship{}, enemy_scaling{}, partner_skill{},
        active_skills[{waza_id, level, ...}], passives[], drops[], boss_drops[],
        summon_level, summon_materials[]
    }
    """
    pals_attr = {p["id"]: p for p in pals_json["pals"]}
    br_rank = {p["id"]: p for p in breeding_json["pals"]}
    out = []
    for pid, br in br_rank.items():
        attr = pals_attr.get(pid, {})
        elements = [ELEMENT_MAP.get(e, e) for e in attr.get("elements", []) if e]
        work_raw = attr.get("work", {})
        work = {WORK_MAP[k]: v for k, v in work_raw.items() if k in WORK_MAP and v}
        out.append({
            "id": pid,
            "zukan_index": br.get("zukanIndex", 0),
            "zukan_index_suffix": br.get("zukanIndexSuffix", ""),
            "icon": br.get("icon", ""),
            # 源数据个别名字带首尾空白（如 LilyQueen_Dark "黑月女王 "）会
            # 导致父帕鲁名 strip 后无法精确匹配 → 424；统一去除空白。
            "cn_name": str(zh.get(pid, {}).get("name", pid)).strip(),
            "en_name": str(en.get(pid, {}).get("name", pid)).strip(),
            "combi_rank": br["rank"],
            "rarity": attr.get("rarity", 1),
            "elements": elements,
            "work_suitability": work,
            "best_work": WORK_MAP.get(attr.get("bestWork", ""), ""),
            "breed_child": br.get("breedChild", True),
            "genus": attr.get("genus"),
            "size": attr.get("size"),
            "egg": attr.get("egg"),
            "nocturnal": attr.get("nocturnal"),
            "reaction": attr.get("reaction"),
            "summonable": attr.get("summonable", False),
            "predator": attr.get("predator", False),
            "boss_first_defeat_reward": attr.get("bossFirstDefeatReward"),
            "stats": attr.get("stats", {}),
            "friendship": attr.get("friendship", {}),
            "enemy_scaling": attr.get("enemyScaling", {}),
            "partner_skill": attr.get("partnerSkill"),
            "active_skills": attr.get("activeSkills", []),
            "passives": attr.get("passives", []),
            "drops": attr.get("drops", []),
            "boss_drops": attr.get("bossDrops", []),
            "summon_level": attr.get("summonLevel"),
            "summon_materials": attr.get("summonMaterials", []),
        })
    return out


# =============================================================================
# 技能
# =============================================================================

def parse_skills(pal_raw: list[dict], zh_skills: dict) -> tuple[list[dict], list[dict]]:
    """从所有帕鲁的 active_skills 聚合出 (skills[], pal_skills[]).

    skills[]: {waza_id, element, category, power, cool_time, min_range, max_range,
               strength, effect_type, effect_value, cn_name, description}
    pal_skills[]: {game_id, waza_id, learn_level}
    """
    skill_map: dict[str, dict] = {}
    pal_skills: list[dict] = []
    for p in pal_raw:
        for s in p["active_skills"]:
            wid = s["wazaId"]
            effect = s.get("effect") or {}
            skill_map.setdefault(wid, {
                "waza_id": wid,
                "element": s.get("element"),
                "category": s.get("category"),
                "power": s.get("power"),
                "cool_time": s.get("coolTime"),
                "min_range": s.get("minRange"),
                "max_range": s.get("maxRange"),
                "strength": s.get("strength"),
                "effect_type": effect.get("type"),
                "effect_value": effect.get("value"),
                "cn_name": zh_skills.get(wid, {}).get("name", wid),
                "description": zh_skills.get(wid, {}).get("description", ""),
            })
            pal_skills.append({"game_id": p["id"], "waza_id": wid, "learn_level": s["level"]})
    return list(skill_map.values()), pal_skills


# =============================================================================
# 被动
# =============================================================================

def parse_passives(passives_json: dict, zh_passives: dict) -> tuple[list[dict], list[dict], list[dict]]:
    """解析被动 → (passives[], passive_effects[], passive_invokes[]).

    passives[]: {passive_id, rank, lottery_weight, cn_name}
    passive_effects[]: {passive_id, effect_type, effect_value, effect_target}
    passive_invokes[]: {passive_id, invoke}   # invoke[] 数组拆行
    """
    passives: list[dict] = []
    effects: list[dict] = []
    invokes: list[dict] = []
    for ps in passives_json.get("passives", []):
        pid = ps["id"]
        passives.append({
            "passive_id": pid,
            "rank": ps.get("rank"),
            "lottery_weight": ps.get("lotteryWeight"),
            "cn_name": zh_passives.get(pid, {}).get("name", pid),
        })
        for e in ps.get("effects", []):
            effects.append({
                "passive_id": pid,
                "effect_type": e.get("type"),
                "effect_value": e.get("value"),
                "effect_target": e.get("target"),
            })
        for inv in ps.get("invoke", []):
            invokes.append({"passive_id": pid, "invoke": inv})
    return passives, effects, invokes


# =============================================================================
# 物品
# =============================================================================

def parse_items(items_json: dict, zh_items: dict) -> tuple[list[dict], list[dict], list[dict], list[dict], list[dict]]:
    """解析物品 → (items[], item_recipes[], item_recipe_stations[], item_recipe_materials[], item_sources[]).

    items[]: {item_id, type_a, type_b, sort_id, rarity, rank, weight, price, max_stack,
              handcraft, cn_name, description}
    item_recipes[]: {item_id, work, product_count}
    item_recipe_stations[]: {item_id, station}      # craftedAt[] 数组拆行
    item_recipe_materials[]: {item_id, material_item, count}
    item_sources[]: {item_id, kind, area, grade, chance}
    """
    items: list[dict] = []
    recipes: list[dict] = []
    stations: list[dict] = []
    materials: list[dict] = []
    sources: list[dict] = []
    for it in items_json.get("items", []):
        iid = it["id"]
        items.append({
            "item_id": iid,
            "type_a": it.get("typeA"),
            "type_b": it.get("typeB"),
            "sort_id": it.get("sortId"),
            "rarity": it.get("rarity"),
            "rank": it.get("rank"),
            "weight": it.get("weight"),
            "price": it.get("price"),
            "max_stack": it.get("maxStack"),
            "handcraft": it.get("handcraft", False),
            "cn_name": zh_items.get(iid, {}).get("name", iid),
            "description": zh_items.get(iid, {}).get("description", ""),
        })
        recipe = it.get("recipe")
        if recipe:
            recipes.append({
                "item_id": iid,
                "work": recipe.get("work"),
                "product_count": recipe.get("productCount"),
            })
            for st in recipe.get("craftedAt", []):
                stations.append({"item_id": iid, "station": st})
            for m in recipe.get("materials", []):
                materials.append({
                    "item_id": iid,
                    "material_item": m.get("item"),
                    "count": m.get("count", 1),
                })
        for s in it.get("sources", []):
            sources.append({
                "item_id": iid,
                "kind": s.get("kind"),
                "area": s.get("area"),
                "grade": s.get("grade"),
                "chance": s.get("chance"),
            })
    return items, recipes, stations, materials, sources
