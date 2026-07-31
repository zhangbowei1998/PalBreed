-- 002_normalize.sql
-- 数据库规范化 — 单表宽列 → 5 表规范化
-- 使用: psql -d pl_agent -f data/sql/002_normalize.sql
-- ⚠️ 执行前请 pg_dump 备份!

BEGIN;

-- ============================================================================
-- 1. 建新表
-- ============================================================================

-- pal — 主表 (SERIAL PK, game_id 变 UK)
CREATE TABLE pal (
    id          SERIAL PRIMARY KEY,
    game_id     VARCHAR(64) UNIQUE NOT NULL,
    zukan_index INTEGER NOT NULL,
    cn_name     VARCHAR(32) UNIQUE NOT NULL,
    en_name     VARCHAR(64),
    combi_rank  INTEGER NOT NULL,
    rarity      INTEGER NOT NULL DEFAULT 1,
    is_wild     BOOLEAN NOT NULL DEFAULT FALSE,
    image_url   TEXT,
    wiki_url    TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- pal_aliase — 别名
CREATE TABLE pal_aliase (
    id      SERIAL PRIMARY KEY,
    pal_id  INTEGER NOT NULL REFERENCES pal(id) ON DELETE CASCADE,
    alias   VARCHAR(64) NOT NULL,
    source  VARCHAR(32) DEFAULT 'community'
);

-- pal_element — 属性
CREATE TABLE pal_element (
    pal_id       INTEGER NOT NULL REFERENCES pal(id) ON DELETE CASCADE,
    element_type VARCHAR(16) NOT NULL,
    PRIMARY KEY (pal_id, element_type)
);

-- work_suitability — 工作适应性
CREATE TABLE work_suitability (
    pal_id    INTEGER NOT NULL REFERENCES pal(id) ON DELETE CASCADE,
    work_type VARCHAR(32) NOT NULL,
    level     INTEGER NOT NULL DEFAULT 0 CHECK (level >= 0),
    PRIMARY KEY (pal_id, work_type)
);

-- breeding_rule — 配种特殊规则 (覆盖旧的 breeding_rules)
CREATE TABLE breeding_rule (
    id           SERIAL PRIMARY KEY,
    child_id     INTEGER NOT NULL REFERENCES pal(id) ON DELETE CASCADE,
    parent_a_id  INTEGER REFERENCES pal(id),
    parent_b_id  INTEGER REFERENCES pal(id),
    rule_type    VARCHAR(32) NOT NULL,
    description  TEXT
);

-- ============================================================================
-- 2. 迁移数据
-- ============================================================================

-- 2a. 主表
INSERT INTO pal (game_id, zukan_index, cn_name, en_name,
                 combi_rank, rarity, is_wild, image_url, wiki_url)
SELECT id, number, cn_name, en_name,
       combi_rank, rarity, is_wild, image_url, wiki_url
FROM pals;

-- 2b. 别名 (JSONB → 行)
INSERT INTO pal_aliase (pal_id, alias, source)
SELECT pn.id, a.value, 'community'
FROM pals p
JOIN pal pn ON pn.game_id = p.id
CROSS JOIN LATERAL jsonb_array_elements_text(p.aliases) AS a(value)
WHERE jsonb_array_length(p.aliases) > 0;

-- 2c. 属性 (JSONB → 行)
INSERT INTO pal_element (pal_id, element_type)
SELECT pn.id, e.value
FROM pals p
JOIN pal pn ON pn.game_id = p.id
CROSS JOIN LATERAL jsonb_array_elements_text(p.elements) AS e(value)
WHERE jsonb_array_length(p.elements) > 0;

-- 2d. 工作适应性 (宽列 → 行, 12 行/帕鲁)
INSERT INTO work_suitability (pal_id, work_type, level)
SELECT pn.id, t.work_type, t.level
FROM pals p
JOIN pal pn ON pn.game_id = p.id
CROSS JOIN LATERAL (VALUES
    ('handiwork',               p.handiwork),
    ('kindling',                p.kindling),
    ('watering',                p.watering),
    ('planting',                p.planting),
    ('generating_electricity',  p.generating_electricity),
    ('gathering',               p.gathering),
    ('lumbering',               p.lumbering),
    ('mining',                  p.mining),
    ('cooling',                 p.cooling),
    ('medicine',                p.medicine),
    ('transporting',            p.transporting),
    ('farming',                 p.farming)
) AS t(work_type, level);

-- 2e. 配种规则 (从 breeding_rules 迁移)
INSERT INTO breeding_rule (child_id, parent_a_id, parent_b_id, rule_type, description)
SELECT
    pc.id AS child_id,
    pa.id AS parent_a_id,
    pb.id AS parent_b_id,
    br.rule_type,
    br.note
FROM breeding_rules br
LEFT JOIN pal pc ON pc.game_id = br.child
LEFT JOIN pal pa ON pa.game_id = br.parent_a
LEFT JOIN pal pb ON pb.game_id = br.parent_b
WHERE br.child IS NOT NULL;

-- ============================================================================
-- 3. 建索引
-- ============================================================================

CREATE INDEX idx_pal_combi_rank ON pal(combi_rank);
CREATE INDEX idx_pal_cn_name ON pal(cn_name);
CREATE INDEX idx_pal_zukan_index ON pal(zukan_index);

CREATE INDEX idx_aliase_pal_id ON pal_aliase(pal_id);
CREATE INDEX idx_aliase_alias ON pal_aliase(alias);

CREATE INDEX idx_element_type ON pal_element(element_type);

CREATE INDEX idx_ws_type_level ON work_suitability(work_type, level DESC);

CREATE INDEX idx_rule_child ON breeding_rule(child_id);
CREATE UNIQUE INDEX idx_rule_child_type ON breeding_rule(child_id, rule_type);

-- ============================================================================
-- 4. 触发器
-- ============================================================================

CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_pal_updated_at
    BEFORE UPDATE ON pal
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

-- ============================================================================
-- 5. 替换旧表 (保留 pals 为视图做兼容，后续可删除)
-- ============================================================================

-- 先备份旧表
ALTER TABLE pals RENAME TO pals_old;
ALTER TABLE breeding_rules RENAME TO breeding_rules_old;

-- 创建兼容视图让旧代码可过渡运行
CREATE VIEW pals AS
SELECT
    p.id::text AS id,
    p.zukan_index AS number,
    p.cn_name,
    p.en_name,
    p.combi_rank,
    p.rarity,
    p.is_wild,
    COALESCE(ws.handiwork, 0)               AS handiwork,
    COALESCE(ws.kindling, 0)                 AS kindling,
    COALESCE(ws.watering, 0)                 AS watering,
    COALESCE(ws.planting, 0)                 AS planting,
    COALESCE(ws.generating_electricity, 0)   AS generating_electricity,
    COALESCE(ws.gathering, 0)                AS gathering,
    COALESCE(ws.lumbering, 0)                AS lumbering,
    COALESCE(ws.mining, 0)                   AS mining,
    COALESCE(ws.cooling, 0)                  AS cooling,
    COALESCE(ws.medicine, 0)                 AS medicine,
    COALESCE(ws.transporting, 0)             AS transporting,
    COALESCE(ws.farming, 0)                  AS farming,
    COALESCE(elems.elements, '[]'::jsonb)    AS elements,
    COALESCE(als.aliases, '[]'::jsonb)       AS aliases,
    p.image_url,
    p.wiki_url,
    '[]'::jsonb                              AS spawn_locations,
    'paldb.cc'::text                         AS data_source,
    FALSE                                    AS incomplete,
    p.created_at,
    p.updated_at
FROM pal p
LEFT JOIN LATERAL (
    SELECT jsonb_object_agg(ws2.work_type, ws2.level) AS work_json
    FROM work_suitability ws2 WHERE ws2.pal_id = p.id
) ws_data ON TRUE
LEFT JOIN LATERAL (
    SELECT COALESCE(ws_data.work_json->>'handiwork', '0')::int AS handiwork,
           COALESCE(ws_data.work_json->>'kindling', '0')::int AS kindling,
           COALESCE(ws_data.work_json->>'watering', '0')::int AS watering,
           COALESCE(ws_data.work_json->>'planting', '0')::int AS planting,
           COALESCE(ws_data.work_json->>'generating_electricity', '0')::int AS generating_electricity,
           COALESCE(ws_data.work_json->>'gathering', '0')::int AS gathering,
           COALESCE(ws_data.work_json->>'lumbering', '0')::int AS lumbering,
           COALESCE(ws_data.work_json->>'mining', '0')::int AS mining,
           COALESCE(ws_data.work_json->>'cooling', '0')::int AS cooling,
           COALESCE(ws_data.work_json->>'medicine', '0')::int AS medicine,
           COALESCE(ws_data.work_json->>'transporting', '0')::int AS transporting,
           COALESCE(ws_data.work_json->>'farming', '0')::int AS farming
) ws ON TRUE
LEFT JOIN LATERAL (
    SELECT jsonb_agg(element_type) AS elements
    FROM pal_element WHERE pal_id = p.id
) elems ON TRUE
LEFT JOIN LATERAL (
    SELECT jsonb_agg(alias) AS aliases
    FROM pal_aliase WHERE pal_id = p.id
) als ON TRUE;

-- 验证
SELECT 'pal' AS tbl, count(*) FROM pal
UNION ALL SELECT 'pal_aliase', count(*) FROM pal_aliase
UNION ALL SELECT 'pal_element', count(*) FROM pal_element
UNION ALL SELECT 'work_suitability', count(*) FROM work_suitability
UNION ALL SELECT 'breeding_rule', count(*) FROM breeding_rule;

COMMIT;

-- ============================================================================
-- 清理 (所有代码迁移完成后执行)
-- ============================================================================
-- DROP VIEW IF EXISTS pals;
-- DROP TABLE IF EXISTS pals_old;
-- DROP TABLE IF EXISTS breeding_rules_old;
