"""PostgresExtWriter — 将 TciDataBundle 写入 22 表（幂等）。

写入顺序（FK 依赖）:
1. 主表: pal / skill / passive / item（收集 SERIAL id 映射）
2. 帕鲁 1:1 详情: pal_stats / pal_friendship / pal_enemy_scaling / pal_partner_skill
3. 关联表: pal_skill / pal_passive / pal_drop / pal_summon /
           passive_effect / passive_invoke /
           item_recipe / item_recipe_station / item_recipe_material / item_source
4. 既有子表: pal_element / pal_aliase / work_suitability（随 pal 一起）
"""

from __future__ import annotations

import logging
from collections import defaultdict

import asyncpg

from adapters.tcimba.adapter import TciDataBundle
from .config import PostgresConfig

logger = logging.getLogger(__name__)

# ---- pal 主表（含 tc-imba 扩展列）----
UPSERT_PAL_EXT = """
INSERT INTO pal (game_id, zukan_index, zukan_index_suffix, cn_name, en_name,
                 combi_rank, rarity, is_wild, breed_child,
                 genus, size, egg, nocturnal, reaction, best_work,
                 summonable, predator, boss_first_defeat_reward, image_url, wiki_url)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9,
        $10, $11, $12, $13, $14, $15,
        $16, $17, $18, $19, $20)
ON CONFLICT (game_id) DO UPDATE SET
    zukan_index = EXCLUDED.zukan_index,
    zukan_index_suffix = EXCLUDED.zukan_index_suffix,
    cn_name = EXCLUDED.cn_name,
    en_name = EXCLUDED.en_name,
    combi_rank = EXCLUDED.combi_rank,
    rarity = EXCLUDED.rarity,
    is_wild = EXCLUDED.is_wild,
    breed_child = EXCLUDED.breed_child,
    genus = EXCLUDED.genus,
    size = EXCLUDED.size,
    egg = EXCLUDED.egg,
    nocturnal = EXCLUDED.nocturnal,
    reaction = EXCLUDED.reaction,
    best_work = EXCLUDED.best_work,
    summonable = EXCLUDED.summonable,
    predator = EXCLUDED.predator,
    boss_first_defeat_reward = EXCLUDED.boss_first_defeat_reward,
    image_url = EXCLUDED.image_url,
    wiki_url = EXCLUDED.wiki_url
RETURNING id
""".strip()

DELETE_ELEMENTS = "DELETE FROM pal_element WHERE pal_id = $1"
INSERT_ELEMENT = (
    "INSERT INTO pal_element (pal_id, element_type) VALUES ($1, $2) ON CONFLICT DO NOTHING"
)
DELETE_ALIASES = "DELETE FROM pal_aliase WHERE pal_id = $1"
INSERT_ALIAS = (
    "INSERT INTO pal_aliase (pal_id, alias, source) VALUES ($1, $2, 'community') ON CONFLICT DO NOTHING"
)
UPSERT_WORK = """
INSERT INTO work_suitability (pal_id, work_type, level)
VALUES ($1, $2, $3)
ON CONFLICT (pal_id, work_type) DO UPDATE SET level = EXCLUDED.level
""".strip()

# ---- skill ----
UPSERT_SKILL = """
INSERT INTO skill (waza_id, element, category, power, cool_time, min_range,
                   max_range, strength, effect_type, effect_value, cn_name, description)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
ON CONFLICT (waza_id) DO UPDATE SET
    element = EXCLUDED.element, category = EXCLUDED.category,
    power = EXCLUDED.power, cool_time = EXCLUDED.cool_time,
    min_range = EXCLUDED.min_range, max_range = EXCLUDED.max_range,
    strength = EXCLUDED.strength, effect_type = EXCLUDED.effect_type,
    effect_value = EXCLUDED.effect_value, cn_name = EXCLUDED.cn_name,
    description = EXCLUDED.description
RETURNING id
""".strip()

# ---- passive ----
UPSERT_PASSIVE = """
INSERT INTO passive (passive_id, rank, lottery_weight, cn_name)
VALUES ($1, $2, $3, $4)
ON CONFLICT (passive_id) DO UPDATE SET
    rank = EXCLUDED.rank, lottery_weight = EXCLUDED.lottery_weight,
    cn_name = EXCLUDED.cn_name
RETURNING id
""".strip()

# ---- item ----
UPSERT_ITEM = """
INSERT INTO item (item_id, type_a, type_b, sort_id, rarity, rank, weight,
                  price, max_stack, handcraft, cn_name, description)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
ON CONFLICT (item_id) DO UPDATE SET
    type_a = EXCLUDED.type_a, type_b = EXCLUDED.type_b,
    sort_id = EXCLUDED.sort_id, rarity = EXCLUDED.rarity, rank = EXCLUDED.rank,
    weight = EXCLUDED.weight, price = EXCLUDED.price, max_stack = EXCLUDED.max_stack,
    handcraft = EXCLUDED.handcraft, cn_name = EXCLUDED.cn_name,
    description = EXCLUDED.description
RETURNING id
""".strip()

# ---- 关联表 ----
INSERT_PAL_STATS = """
INSERT INTO pal_stats (pal_id, hp, melee_attack, shot_attack, defense, support,
                       craft_speed, stamina, food_amount, max_full_stomach,
                       capture_rate, exp_ratio, price, male_probability,
                       slow_walk_speed, walk_speed, run_speed, ride_sprint_speed,
                       transport_speed, swim_speed)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
        $11, $12, $13, $14, $15, $16, $17, $18, $19, $20)
ON CONFLICT (pal_id) DO UPDATE SET
    hp = EXCLUDED.hp, melee_attack = EXCLUDED.melee_attack,
    shot_attack = EXCLUDED.shot_attack, defense = EXCLUDED.defense,
    support = EXCLUDED.support, craft_speed = EXCLUDED.craft_speed,
    stamina = EXCLUDED.stamina, food_amount = EXCLUDED.food_amount,
    max_full_stomach = EXCLUDED.max_full_stomach, capture_rate = EXCLUDED.capture_rate,
    exp_ratio = EXCLUDED.exp_ratio, price = EXCLUDED.price,
    male_probability = EXCLUDED.male_probability, slow_walk_speed = EXCLUDED.slow_walk_speed,
    walk_speed = EXCLUDED.walk_speed, run_speed = EXCLUDED.run_speed,
    ride_sprint_speed = EXCLUDED.ride_sprint_speed, transport_speed = EXCLUDED.transport_speed,
    swim_speed = EXCLUDED.swim_speed
""".strip()

INSERT_PAL_FRIENDSHIP = """
INSERT INTO pal_friendship (pal_id, hp, shot_attack, defense)
VALUES ($1, $2, $3, $4)
ON CONFLICT (pal_id) DO UPDATE SET hp = EXCLUDED.hp,
    shot_attack = EXCLUDED.shot_attack, defense = EXCLUDED.defense
""".strip()

INSERT_PAL_ENEMY = """
INSERT INTO pal_enemy_scaling (pal_id, receive_damage)
VALUES ($1, $2)
ON CONFLICT (pal_id) DO UPDATE SET receive_damage = EXCLUDED.receive_damage
""".strip()

INSERT_PAL_PARTNER = """
INSERT INTO pal_partner_skill (pal_id, action_name, effect_time, cool_time,
                               exec_cost, idle_cost, toggle, can_throw_pal)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
ON CONFLICT (pal_id) DO UPDATE SET
    action_name = EXCLUDED.action_name, effect_time = EXCLUDED.effect_time,
    cool_time = EXCLUDED.cool_time, exec_cost = EXCLUDED.exec_cost,
    idle_cost = EXCLUDED.idle_cost, toggle = EXCLUDED.toggle,
    can_throw_pal = EXCLUDED.can_throw_pal
""".strip()

DELETE_PAL_SKILL = "DELETE FROM pal_skill WHERE pal_id = $1"
INSERT_PAL_SKILL = (
    "INSERT INTO pal_skill (pal_id, skill_id, learn_level) VALUES ($1, $2, $3) "
    "ON CONFLICT (pal_id, skill_id) DO UPDATE SET learn_level = EXCLUDED.learn_level"
)
DELETE_PAL_PASSIVE = "DELETE FROM pal_passive WHERE pal_id = $1"
INSERT_PAL_PASSIVE = (
    "INSERT INTO pal_passive (pal_id, passive_id) VALUES ($1, $2) "
    "ON CONFLICT DO NOTHING"
)

INSERT_PASSIVE_EFFECT = """
INSERT INTO passive_effect (passive_id, effect_type, effect_value, effect_target)
VALUES ($1, $2, $3, $4)
""".strip()
DELETE_PASSIVE_EFFECT = "DELETE FROM passive_effect WHERE passive_id = $1"
INSERT_PASSIVE_INVOKE = (
    "INSERT INTO passive_invoke (passive_id, invoke) VALUES ($1, $2)"
)
DELETE_PASSIVE_INVOKE = "DELETE FROM passive_invoke WHERE passive_id = $1"

INSERT_PAL_DROP = """
INSERT INTO pal_drop (pal_id, item_id, rate, min, max, min_level, is_boss)
VALUES ($1, $2, $3, $4, $5, $6, $7)
ON CONFLICT (pal_id, item_id, is_boss) DO UPDATE SET
    rate = EXCLUDED.rate, min = EXCLUDED.min, max = EXCLUDED.max,
    min_level = EXCLUDED.min_level
""".strip()

INSERT_PAL_SUMMON = """
INSERT INTO pal_summon (pal_id, material_item_id, level, count)
VALUES ($1, $2, $3, $4)
ON CONFLICT (pal_id, material_item_id) DO UPDATE SET
    level = EXCLUDED.level, count = EXCLUDED.count
""".strip()

DELETE_ITEM_RECIPE = "DELETE FROM item_recipe WHERE item_id = $1"
INSERT_ITEM_RECIPE = """
INSERT INTO item_recipe (item_id, work, product_count)
VALUES ($1, $2, $3) RETURNING id
""".strip()
DELETE_ITEM_STATION = "DELETE FROM item_recipe_station WHERE recipe_id = $1"
INSERT_ITEM_STATION = (
    "INSERT INTO item_recipe_station (recipe_id, station) VALUES ($1, $2)"
)
DELETE_ITEM_MATERIAL = "DELETE FROM item_recipe_material WHERE recipe_id = $1"
INSERT_ITEM_MATERIAL = (
    "INSERT INTO item_recipe_material (recipe_id, material_item_id, count) VALUES ($1, $2, $3)"
)
DELETE_ITEM_SOURCE = "DELETE FROM item_source WHERE item_id = $1"
INSERT_ITEM_SOURCE = (
    "INSERT INTO item_source (item_id, kind, area, grade, chance) VALUES ($1, $2, $3, $4, $5)"
)


class PostgresExtWriter:
    """Write TciDataBundle to the 22-table schema (idempotent)."""

    def __init__(self, config: PostgresConfig | None = None):
        self.config = config or PostgresConfig.from_env()
        self._pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        if self._pool is None:
            self._pool = await asyncpg.create_pool(
                dsn=self.config.dsn, min_size=1, max_size=4
            )
            logger.info("PostgresExtWriter connected: %s:%d/%s",
                        self.config.host, self.config.port, self.config.database)

    async def close(self) -> None:
        if self._pool:
            await self._pool.close()
            self._pool = None

    async def _ensure_pool(self) -> None:
        if self._pool is None:
            await self.connect()

    async def upsert_ext(self, bundle: TciDataBundle) -> dict[str, int]:
        """写全部 22 表。返回各表写入行数。"""
        await self._ensure_pool()
        stats: dict[str, int] = {}
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                # 1. 主表 id 映射
                pal_id_map: dict[str, int] = {}
                for p in bundle.pal_raw:
                    row = await conn.fetchrow(
                        UPSERT_PAL_EXT,
                        p["id"], p["zukan_index"], p.get("zukan_index_suffix", ""),
                        p["cn_name"], p["en_name"], p["combi_rank"], p["rarity"],
                        p.get("is_wild", True), p["breed_child"],
                        p.get("genus"), p.get("size"), p.get("egg"),
                        p.get("nocturnal"), p.get("reaction"), p.get("best_work"),
                        p.get("summonable", False), p.get("predator", False),
                        p.get("boss_first_defeat_reward"),
                        p.get("image_url"), p.get("wiki_url"),
                    )
                    pal_id_map[p["id"]] = row["id"]
                    # pal 子表
                    await conn.execute(DELETE_ELEMENTS, row["id"])
                    for e in p.get("elements", []):
                        await conn.execute(INSERT_ELEMENT, row["id"], e)
                    await conn.execute(DELETE_ALIASES, row["id"])
                    for a in p.get("aliases", []):
                        await conn.execute(INSERT_ALIAS, row["id"], a)
                    for wt, lv in (p.get("work_suitability") or {}).items():
                        await conn.execute(UPSERT_WORK, row["id"], wt, lv)
                stats["pal"] = len(pal_id_map)

                skill_id_map: dict[str, int] = {}
                for s in bundle.skills:
                    row = await conn.fetchrow(
                        UPSERT_SKILL, s["waza_id"], s.get("element"), s.get("category"),
                        s.get("power"), s.get("cool_time"), s.get("min_range"),
                        s.get("max_range"), s.get("strength"), s.get("effect_type"),
                        s.get("effect_value"), s.get("cn_name", ""), s.get("description", ""),
                    )
                    skill_id_map[s["waza_id"]] = row["id"]
                stats["skill"] = len(skill_id_map)

                passive_id_map: dict[str, int] = {}
                for p in bundle.passives:
                    row = await conn.fetchrow(
                        UPSERT_PASSIVE, p["passive_id"], p.get("rank"),
                        p.get("lottery_weight"), p.get("cn_name", ""),
                    )
                    passive_id_map[p["passive_id"]] = row["id"]
                stats["passive"] = len(passive_id_map)

                item_id_map: dict[str, int] = {}
                item_lower_map: dict[str, int] = {}
                for it in bundle.items:
                    row = await conn.fetchrow(
                        UPSERT_ITEM, it["item_id"], it.get("type_a"), it.get("type_b"),
                        it.get("sort_id"), it.get("rarity"), it.get("rank"),
                        it.get("weight"), it.get("price"), it.get("max_stack"),
                        it.get("handcraft", False), it.get("cn_name", ""),
                        it.get("description", ""),
                    )
                    item_id_map[it["item_id"]] = row["id"]
                    item_lower_map[it["item_id"].lower()] = row["id"]
                stats["item"] = len(item_id_map)

                # 2. 帕鲁 1:1 详情
                for p in bundle.pal_raw:
                    pid = pal_id_map[p["id"]]
                    st = p.get("stats") or {}
                    await conn.execute(
                        INSERT_PAL_STATS, pid, st.get("hp"), st.get("meleeAttack"),
                        st.get("shotAttack"), st.get("defense"), st.get("support"),
                        st.get("craftSpeed"), st.get("stamina"), st.get("foodAmount"),
                        st.get("maxFullStomach"), st.get("captureRate"),
                        st.get("expRatio"), st.get("price"), st.get("maleProbability"),
                        st.get("slowWalkSpeed"), st.get("walkSpeed"), st.get("runSpeed"),
                        st.get("rideSprintSpeed"), st.get("transportSpeed"),
                        st.get("swimSpeed"),
                    )
                    fr = p.get("friendship") or {}
                    await conn.execute(
                        INSERT_PAL_FRIENDSHIP, pid, fr.get("hp"),
                        fr.get("shotAttack"), fr.get("defense"),
                    )
                    es = p.get("enemy_scaling") or {}
                    await conn.execute(INSERT_PAL_ENEMY, pid, es.get("receiveDamage"))
                    pk = p.get("partner_skill") or {}
                    action = pk.get("action") or {}
                    await conn.execute(
                        INSERT_PAL_PARTNER, pid, action.get("name"),
                        action.get("effectTime"), action.get("coolTime"),
                        action.get("execCost"), action.get("idleCost"),
                        action.get("toggle", False), action.get("canThrowPal", False),
                    )
                stats["pal_stats"] = len(bundle.pal_raw)

                # 3. 关联表
                # pal_skill
                await conn.executemany(
                    INSERT_PAL_SKILL,
                    [(pal_id_map[ps["game_id"]], skill_id_map[ps["waza_id"]],
                      ps["learn_level"]) for ps in bundle.pal_skills],
                )
                stats["pal_skill"] = len(bundle.pal_skills)

                # pal_passive
                await conn.executemany(
                    INSERT_PAL_PASSIVE,
                    [(pal_id_map[pp["game_id"]], passive_id_map[pp["passive_id"]])
                     for pp in bundle.pal_passives],
                )
                stats["pal_passive"] = len(bundle.pal_passives)

                # passive_effect / passive_invoke（按 passive 分组 delete+insert 幂等）
                effects_by_pas: dict[str, list[dict]] = defaultdict(list)
                for pe in bundle.passive_effects:
                    effects_by_pas[pe["passive_id"]].append(pe)
                for pid_key, effects in effects_by_pas.items():
                    pid = passive_id_map[pid_key]
                    await conn.execute(DELETE_PASSIVE_EFFECT, pid)
                    for pe in effects:
                        await conn.execute(
                            INSERT_PASSIVE_EFFECT, pid, pe.get("effect_type"),
                            pe.get("effect_value"), pe.get("effect_target"),
                        )
                invokes_by_pas: dict[str, list[dict]] = defaultdict(list)
                for pv in bundle.passive_invokes:
                    invokes_by_pas[pv["passive_id"]].append(pv)
                for pid_key, invokes in invokes_by_pas.items():
                    pid = passive_id_map[pid_key]
                    await conn.execute(DELETE_PASSIVE_INVOKE, pid)
                    for pv in invokes:
                        await conn.execute(INSERT_PASSIVE_INVOKE, pid, pv["invoke"])
                stats["passive_effect"] = len(bundle.passive_effects)
                stats["passive_invoke"] = len(bundle.passive_invokes)

                # pal_drop（item 匹配大小写归一）
                drop_cnt = 0
                for p in bundle.pal_raw:
                    pid = pal_id_map[p["id"]]
                    for d in p.get("drops", []):
                        item_id = item_lower_map.get(d["item"].lower())
                        if item_id is None:
                            logger.warning("pal_drop 未匹配 item: %s -> %s", p["id"], d["item"])
                            continue
                        await conn.execute(
                            INSERT_PAL_DROP, pid, item_id, d.get("rate"),
                            d.get("min"), d.get("max"), d.get("minLevel"), False,
                        )
                        drop_cnt += 1
                    for d in p.get("boss_drops", []):
                        item_id = item_lower_map.get(d["item"].lower())
                        if item_id is None:
                            logger.warning("pal_drop(boss) 未匹配 item: %s -> %s", p["id"], d["item"])
                            continue
                        await conn.execute(
                            INSERT_PAL_DROP, pid, item_id, d.get("rate"),
                            d.get("min"), d.get("max"), d.get("minLevel"), True,
                        )
                        drop_cnt += 1
                stats["pal_drop"] = drop_cnt

                # pal_summon
                summon_cnt = 0
                for p in bundle.pal_raw:
                    if not p.get("summon_materials"):
                        continue
                    pid = pal_id_map[p["id"]]
                    lvl = p.get("summon_level")
                    for m in p["summon_materials"]:
                        item_id = item_lower_map.get(m.get("item", "").lower())
                        if item_id is None:
                            logger.warning("pal_summon 未匹配 item: %s -> %s", p["id"], m.get("item"))
                            continue
                        await conn.execute(INSERT_PAL_SUMMON, pid, item_id, lvl, m.get("count", 1))
                        summon_cnt += 1
                stats["pal_summon"] = summon_cnt

                # item_recipe + station + material（按 item 分组，避免 O(n²)）
                stations_by_item: dict[str, list[str]] = defaultdict(list)
                for s in bundle.item_recipe_stations:
                    stations_by_item[s["item_id"]].append(s["station"])
                materials_by_item: dict[str, list[dict]] = defaultdict(list)
                for m in bundle.item_recipe_materials:
                    materials_by_item[m["item_id"]].append(m)

                recipe_cnt = station_cnt = material_cnt = 0
                for r in bundle.item_recipes:
                    item_id = item_id_map[r["item_id"]]
                    # 先删旧 recipe（幂等），再插新
                    await conn.execute(DELETE_ITEM_RECIPE, item_id)
                    row = await conn.fetchrow(
                        INSERT_ITEM_RECIPE, item_id, r.get("work"), r.get("product_count"),
                    )
                    recipe_id = row["id"]
                    await conn.execute(DELETE_ITEM_STATION, recipe_id)
                    for st in stations_by_item.get(r["item_id"], []):
                        await conn.execute(INSERT_ITEM_STATION, recipe_id, st)
                        station_cnt += 1
                    await conn.execute(DELETE_ITEM_MATERIAL, recipe_id)
                    for m in materials_by_item.get(r["item_id"], []):
                        mat_item_id = item_lower_map.get(m.get("material_item", "").lower())
                        if mat_item_id is None:
                            logger.warning("recipe material 未匹配 item: %s -> %s",
                                           r["item_id"], m.get("material_item"))
                            continue
                        await conn.execute(INSERT_ITEM_MATERIAL, recipe_id, mat_item_id, m.get("count", 1))
                        material_cnt += 1
                    recipe_cnt += 1
                stats["item_recipe"] = recipe_cnt
                stats["item_recipe_station"] = station_cnt
                stats["item_recipe_material"] = material_cnt

                # item_source（按 item 分组: 每 item delete 一次 + insert 全部）
                sources_by_item: dict[str, list[dict]] = defaultdict(list)
                for s in bundle.item_sources:
                    sources_by_item[s["item_id"]].append(s)
                source_cnt = 0
                for item_id_key, srcs in sources_by_item.items():
                    item_id = item_id_map[item_id_key]
                    await conn.execute(DELETE_ITEM_SOURCE, item_id)
                    for s in srcs:
                        await conn.execute(
                            INSERT_ITEM_SOURCE, item_id, s.get("kind"), s.get("area"),
                            s.get("grade"), s.get("chance"),
                        )
                        source_cnt += 1
                stats["item_source"] = source_cnt

        logger.info("PostgresExtWriter upsert_ext 完成: %s", stats)
        return stats
