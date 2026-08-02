-- 001_create_pals.sql
-- 帕鲁数据表 — PostgreSQL 持久化存储
-- 使用: psql -d pl_agent -f data/sql/001_create_pals.sql

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================================
-- pals — 主数据表
-- ============================================================================
CREATE TABLE IF NOT EXISTS pals (
    -- ▲ 热字段 (启动时提取到 BreedingIndex 内存)
    id            TEXT PRIMARY KEY,
    combi_rank    INTEGER NOT NULL,
    is_wild       BOOLEAN NOT NULL DEFAULT FALSE,
    breed_child   BOOLEAN NOT NULL DEFAULT TRUE,
    handiwork               INTEGER NOT NULL DEFAULT 0,
    kindling                INTEGER NOT NULL DEFAULT 0,
    watering                INTEGER NOT NULL DEFAULT 0,
    planting                INTEGER NOT NULL DEFAULT 0,
    generating_electricity  INTEGER NOT NULL DEFAULT 0,
    gathering               INTEGER NOT NULL DEFAULT 0,
    lumbering               INTEGER NOT NULL DEFAULT 0,
    mining                  INTEGER NOT NULL DEFAULT 0,
    cooling                 INTEGER NOT NULL DEFAULT 0,
    medicine                INTEGER NOT NULL DEFAULT 0,
    transporting            INTEGER NOT NULL DEFAULT 0,
    farming                 INTEGER NOT NULL DEFAULT 0,

    -- ▼ 冷字段 (运行时按需从 PG 查询)
    number        INTEGER NOT NULL,
    cn_name       TEXT NOT NULL,
    en_name       TEXT NOT NULL,
    elements      JSONB NOT NULL DEFAULT '[]',
    rarity        INTEGER NOT NULL DEFAULT 1,
    aliases       JSONB NOT NULL DEFAULT '[]',
    image_url     TEXT,
    wiki_url      TEXT,
    spawn_locations JSONB NOT NULL DEFAULT '[]',
    data_source   TEXT NOT NULL DEFAULT 'paldb.cc',
    incomplete    BOOLEAN NOT NULL DEFAULT FALSE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_pals_combi_rank ON pals(combi_rank);
CREATE INDEX IF NOT EXISTS idx_pals_is_wild ON pals(is_wild);
CREATE INDEX IF NOT EXISTS idx_pals_number ON pals(number);
CREATE INDEX IF NOT EXISTS idx_pals_cn_name ON pals(cn_name);
CREATE INDEX IF NOT EXISTS idx_pals_handiwork ON pals(handiwork DESC);
CREATE INDEX IF NOT EXISTS idx_pals_mining ON pals(mining DESC);

-- 自动更新 updated_at
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger WHERE tgname = 'trg_pals_updated_at'
    ) THEN
        CREATE TRIGGER trg_pals_updated_at
            BEFORE UPDATE ON pals
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at();
    END IF;
END $$;

-- ============================================================================
-- breeding_rules — 配种规则表
-- ============================================================================
CREATE TABLE IF NOT EXISTS breeding_rules (
    id            SERIAL PRIMARY KEY,
    game_version  TEXT NOT NULL,
    rule_type     TEXT NOT NULL,
    parent_a      TEXT,
    parent_b      TEXT,
    child         TEXT,
    pal_id        TEXT,
    note          TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_breeding_rules_type ON breeding_rules(rule_type);
