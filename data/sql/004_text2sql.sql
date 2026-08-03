-- 004_text2sql.sql
-- Text-to-SQL 兜底能力的白名单宽表视图（PostgreSQL）
-- 使用: psql -d pl_agent -f data/sql/004_text2sql.sql
-- 幂等: 用 CREATE OR REPLACE VIEW（PG 不支持 CREATE VIEW IF NOT EXISTS）

-- ============================================================================
-- v_pal_full — 帕鲁全量宽表（1 行 = 1 只帕鲁）
-- 供 Agent Text-to-SQL 查询长尾问题（按属性/体型/种族/被动/技能筛选）
-- ============================================================================
CREATE OR REPLACE VIEW v_pal_full AS
SELECT
    p.id AS pal_id,
    p.game_id,
    p.cn_name,
    p.en_name,
    p.zukan_index,
    p.zukan_index_suffix,
    p.combi_rank,
    p.rarity,
    p.is_wild,
    p.size,
    p.genus,
    p.egg,
    p.nocturnal,
    p.predator,
    p.summonable,
    p.best_work,
    p.image_url,
    s.hp,
    s.melee_attack,
    s.shot_attack,
    s.defense,
    s.run_speed,
    s.ride_sprint_speed,
    s.capture_rate,
    (SELECT string_agg(e.element_type, ',' ORDER BY e.element_type)
       FROM pal_element e WHERE e.pal_id = p.id) AS element_list,
    (SELECT string_agg(ws.work_type || ':' || ws.level, ' ' ORDER BY ws.level DESC)
       FROM work_suitability ws WHERE ws.pal_id = p.id) AS work_summary,
    (SELECT string_agg(pas.cn_name, ',' ORDER BY pas.cn_name)
       FROM pal_passive pp JOIN passive pas ON pas.id = pp.passive_id
      WHERE pp.pal_id = p.id) AS passive_list,
    (SELECT count(*) FROM pal_skill ps WHERE ps.pal_id = p.id) AS skill_count,
    (SELECT string_agg(pa.alias, ',' ORDER BY pa.alias)
       FROM pal_aliase pa WHERE pa.pal_id = p.id) AS alias_list
FROM pal p
LEFT JOIN pal_stats s ON s.pal_id = p.id;

-- ============================================================================
-- v_item_drop — 物品掉落来源（从掉落事实出发，避免无掉落物品产生空行）
-- ============================================================================
CREATE OR REPLACE VIEW v_item_drop AS
SELECT i.item_id,
       i.cn_name AS item_cn,
       p.cn_name AS pal_cn,
       p.game_id AS pal_game_id,
       d.rate,
       d.is_boss
FROM pal_drop d
JOIN item i ON i.id = d.item_id
JOIN pal p ON p.id = d.pal_id;

-- ============================================================================
-- v_skill_learn — 帕鲁可学技能（命名避开已存在的 pal_skill 表）
-- ============================================================================
CREATE OR REPLACE VIEW v_skill_learn AS
SELECT p.game_id,
       p.cn_name AS pal_cn,
       sk.waza_id,
       sk.cn_name AS skill_cn,
       sk.element,
       sk.power,
       ps.learn_level
FROM pal_skill ps
JOIN pal p ON p.id = ps.pal_id
JOIN skill sk ON sk.id = ps.skill_id;
