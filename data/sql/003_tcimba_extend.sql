-- 003_tcimba_extend.sql
-- tc-imba 全量数据扩展 — 5 表 → 22 表
-- 使用: psql -d pl_agent -f data/sql/003_tcimba_extend.sql
-- ⚠️ 幂等设计: 已有库可重复执行（IF NOT EXISTS / ADD COLUMN IF NOT EXISTS）
--    新库执行顺序: 001 → 002 → 003

BEGIN;

-- ============================================================================
-- 1. pal 主表扩展列（tc-imba 字段）
-- ============================================================================
ALTER TABLE pal
    ADD COLUMN IF NOT EXISTS zukan_index_suffix   VARCHAR(16) NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS genus                VARCHAR(32),
    ADD COLUMN IF NOT EXISTS size                 VARCHAR(8),
    ADD COLUMN IF NOT EXISTS egg                  VARCHAR(64),
    ADD COLUMN IF NOT EXISTS nocturnal            BOOLEAN,
    ADD COLUMN IF NOT EXISTS reaction             VARCHAR(32),
    ADD COLUMN IF NOT EXISTS best_work            VARCHAR(32),
    ADD COLUMN IF NOT EXISTS summonable           BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS predator             BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS boss_first_defeat_reward VARCHAR(64);

-- ============================================================================
-- 2. 帕鲁详情 1:1 表
-- ============================================================================

-- pal_stats — 基础属性 (pals.json stats)
CREATE TABLE IF NOT EXISTS pal_stats (
    pal_id             INTEGER PRIMARY KEY REFERENCES pal(id) ON DELETE CASCADE,
    hp                 INTEGER,
    melee_attack       INTEGER,
    shot_attack        INTEGER,
    defense            INTEGER,
    support            INTEGER,
    craft_speed        INTEGER,
    stamina            INTEGER,
    food_amount        INTEGER,
    max_full_stomach   INTEGER,
    capture_rate       NUMERIC(6,3),
    exp_ratio          NUMERIC(6,3),
    price              INTEGER,
    male_probability   INTEGER,
    slow_walk_speed    INTEGER,
    walk_speed         INTEGER,
    run_speed          INTEGER,
    ride_sprint_speed  INTEGER,
    transport_speed    INTEGER,
    swim_speed         INTEGER
);

-- pal_friendship — 好感度成长
CREATE TABLE IF NOT EXISTS pal_friendship (
    pal_id       INTEGER PRIMARY KEY REFERENCES pal(id) ON DELETE CASCADE,
    hp           NUMERIC(6,2),
    shot_attack  NUMERIC(6,2),
    defense      NUMERIC(6,2)
);

-- pal_enemy_scaling — 敌方缩放
CREATE TABLE IF NOT EXISTS pal_enemy_scaling (
    pal_id         INTEGER PRIMARY KEY REFERENCES pal(id) ON DELETE CASCADE,
    receive_damage NUMERIC(6,2)
);

-- pal_partner_skill — 伙伴技能
CREATE TABLE IF NOT EXISTS pal_partner_skill (
    pal_id        INTEGER PRIMARY KEY REFERENCES pal(id) ON DELETE CASCADE,
    action_name   VARCHAR(64),
    effect_time   INTEGER,
    cool_time     INTEGER,
    exec_cost     INTEGER,
    idle_cost     INTEGER,
    toggle        BOOLEAN,
    can_throw_pal BOOLEAN
);

-- ============================================================================
-- 3. 技能
-- ============================================================================

-- skill — 技能主表 (activeSkills 聚合)
CREATE TABLE IF NOT EXISTS skill (
    id            SERIAL PRIMARY KEY,
    waza_id       VARCHAR(64) UNIQUE NOT NULL,
    element       VARCHAR(16),
    category      VARCHAR(16),
    power         INTEGER,
    cool_time     INTEGER,
    min_range     INTEGER,
    max_range     INTEGER,
    strength      VARCHAR(16),
    effect_type   VARCHAR(32),
    effect_value  INTEGER,
    cn_name       VARCHAR(32),
    description   TEXT
);

-- pal_skill — 帕鲁可学技能 (含学习等级)
CREATE TABLE IF NOT EXISTS pal_skill (
    pal_id      INTEGER NOT NULL REFERENCES pal(id) ON DELETE CASCADE,
    skill_id    INTEGER NOT NULL REFERENCES skill(id) ON DELETE CASCADE,
    learn_level INTEGER NOT NULL,
    PRIMARY KEY (pal_id, skill_id)
);

-- ============================================================================
-- 4. 被动技能
-- ============================================================================

-- passive — 被动主表
CREATE TABLE IF NOT EXISTS passive (
    id             SERIAL PRIMARY KEY,
    passive_id     VARCHAR(64) UNIQUE NOT NULL,
    rank           INTEGER,
    lottery_weight INTEGER,
    cn_name        VARCHAR(32)
);

-- passive_effect — 被动效果 (effects[])
CREATE TABLE IF NOT EXISTS passive_effect (
    id            SERIAL PRIMARY KEY,
    passive_id    INTEGER NOT NULL REFERENCES passive(id) ON DELETE CASCADE,
    effect_type   VARCHAR(64),
    effect_value  NUMERIC(10,2),
    effect_target VARCHAR(16)
);

-- passive_invoke — 被动触发方式 (invoke[], 数组拆行)
CREATE TABLE IF NOT EXISTS passive_invoke (
    id         SERIAL PRIMARY KEY,
    passive_id INTEGER NOT NULL REFERENCES passive(id) ON DELETE CASCADE,
    invoke     VARCHAR(32) NOT NULL
);

-- pal_passive — 帕鲁固有被动
CREATE TABLE IF NOT EXISTS pal_passive (
    pal_id     INTEGER NOT NULL REFERENCES pal(id) ON DELETE CASCADE,
    passive_id INTEGER NOT NULL REFERENCES passive(id) ON DELETE CASCADE,
    PRIMARY KEY (pal_id, passive_id)
);

-- ============================================================================
-- 5. 物品
-- ============================================================================

-- item — 物品主表
CREATE TABLE IF NOT EXISTS item (
    id          SERIAL PRIMARY KEY,
    item_id     VARCHAR(64) UNIQUE NOT NULL,
    type_a      VARCHAR(32),
    type_b      VARCHAR(32),
    sort_id     INTEGER,
    rarity      INTEGER,
    rank        INTEGER,
    weight      NUMERIC(8,2),
    price       INTEGER,
    max_stack   INTEGER,
    handcraft   BOOLEAN NOT NULL DEFAULT FALSE,
    cn_name     VARCHAR(64),
    description TEXT
);

-- item_recipe — 配方
CREATE TABLE IF NOT EXISTS item_recipe (
    id            SERIAL PRIMARY KEY,
    item_id       INTEGER NOT NULL REFERENCES item(id) ON DELETE CASCADE,
    work          INTEGER,
    product_count INTEGER
);

-- item_recipe_station — 配方制作设施 (craftedAt[], 数组拆行)
CREATE TABLE IF NOT EXISTS item_recipe_station (
    id        SERIAL PRIMARY KEY,
    recipe_id INTEGER NOT NULL REFERENCES item_recipe(id) ON DELETE CASCADE,
    station   VARCHAR(64) NOT NULL
);

-- item_recipe_material — 配方材料
CREATE TABLE IF NOT EXISTS item_recipe_material (
    id                SERIAL PRIMARY KEY,
    recipe_id         INTEGER NOT NULL REFERENCES item_recipe(id) ON DELETE CASCADE,
    material_item_id  INTEGER NOT NULL REFERENCES item(id) ON DELETE CASCADE,
    count             INTEGER NOT NULL
);

-- item_source — 物品来源 (sources[])
CREATE TABLE IF NOT EXISTS item_source (
    id      SERIAL PRIMARY KEY,
    item_id INTEGER NOT NULL REFERENCES item(id) ON DELETE CASCADE,
    kind    VARCHAR(16),
    area    VARCHAR(32),
    grade   INTEGER,
    chance  INTEGER
);

-- pal_drop — 帕鲁掉落 (drops[] + bossDrops[], is_boss 区分)
CREATE TABLE IF NOT EXISTS pal_drop (
    id        SERIAL PRIMARY KEY,
    pal_id    INTEGER NOT NULL REFERENCES pal(id) ON DELETE CASCADE,
    item_id   INTEGER NOT NULL REFERENCES item(id) ON DELETE CASCADE,
    rate      INTEGER,
    min       INTEGER,
    max       INTEGER,
    min_level INTEGER,
    is_boss   BOOLEAN NOT NULL DEFAULT FALSE,
    -- drops 与 bossDrops 物品重叠，需 (pal,item,is_boss) 区分
    UNIQUE (pal_id, item_id, is_boss)
);

-- pal_summon — 帕鲁召唤 (summonLevel + summonMaterials, 依赖 item)
CREATE TABLE IF NOT EXISTS pal_summon (
    pal_id            INTEGER NOT NULL REFERENCES pal(id) ON DELETE CASCADE,
    material_item_id  INTEGER NOT NULL REFERENCES item(id) ON DELETE CASCADE,
    level             INTEGER,
    count             INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (pal_id, material_item_id)
);

-- ============================================================================
-- 6. 索引
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_pal_skill_pal    ON pal_skill(pal_id);
CREATE INDEX IF NOT EXISTS idx_pal_skill_skill  ON pal_skill(skill_id);
CREATE INDEX IF NOT EXISTS idx_skill_element    ON skill(element);
CREATE INDEX IF NOT EXISTS idx_passive_cn       ON passive(cn_name);
CREATE INDEX IF NOT EXISTS idx_pal_passive_pal  ON pal_passive(pal_id);
CREATE INDEX IF NOT EXISTS idx_pal_passive_pas  ON pal_passive(passive_id);
CREATE INDEX IF NOT EXISTS idx_passive_effect_pas ON passive_effect(passive_id);
CREATE INDEX IF NOT EXISTS idx_passive_invoke_pas ON passive_invoke(passive_id);
CREATE INDEX IF NOT EXISTS idx_pal_drop_pal     ON pal_drop(pal_id);
CREATE INDEX IF NOT EXISTS idx_pal_drop_item    ON pal_drop(item_id);
CREATE INDEX IF NOT EXISTS idx_recipe_item      ON item_recipe(item_id);
CREATE INDEX IF NOT EXISTS idx_recipe_station_rcp ON item_recipe_station(recipe_id);
CREATE INDEX IF NOT EXISTS idx_recipe_mat_rcp   ON item_recipe_material(recipe_id);
CREATE INDEX IF NOT EXISTS idx_recipe_mat_item  ON item_recipe_material(material_item_id);
CREATE INDEX IF NOT EXISTS idx_item_source_item ON item_source(item_id);
CREATE INDEX IF NOT EXISTS idx_pal_summon_pal   ON pal_summon(pal_id);

COMMIT;

-- ============================================================================
-- 验证
-- ============================================================================
-- SELECT 'pal' AS tbl, count(*) FROM pal
-- UNION ALL SELECT 'pal_stats', count(*) FROM pal_stats
-- UNION ALL SELECT 'skill', count(*) FROM skill
-- UNION ALL SELECT 'passive', count(*) FROM passive
-- UNION ALL SELECT 'item', count(*) FROM item
-- UNION ALL SELECT 'pal_drop', count(*) FROM pal_drop;
