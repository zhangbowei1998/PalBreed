"""PostgresLoader — load Pal entities from normalized PostgreSQL tables."""

from __future__ import annotations

import json
import logging

import asyncpg

from pl_agent.core.schema import Element, Pal, WorkSuitability

from .config import PostgresConfig

logger = logging.getLogger(__name__)

# ── JOIN 查询 — 一次拼装完整 Pal ─────────────────────────────

LOAD_ALL_SQL = """
SELECT
    p.id, p.game_id, p.zukan_index, p.cn_name, p.en_name,
    p.combi_rank, p.rarity, p.is_wild, p.image_url, p.wiki_url,
    COALESCE(
        jsonb_object_agg(ws.work_type, ws.level)
        FILTER (WHERE ws.work_type IS NOT NULL),
        '{}'::jsonb
    ) AS work_json,
    COALESCE(
        array_agg(DISTINCT pe.element_type)
        FILTER (WHERE pe.element_type IS NOT NULL),
        '{}'
    ) AS elements_arr,
    COALESCE(
        array_agg(DISTINCT pa.alias)
        FILTER (WHERE pa.alias IS NOT NULL),
        '{}'
    ) AS aliases_arr
FROM pal p
LEFT JOIN work_suitability ws ON p.id = ws.pal_id
LEFT JOIN pal_element pe ON p.id = pe.pal_id
LEFT JOIN pal_aliase pa ON p.id = pa.pal_id
GROUP BY p.id
ORDER BY p.combi_rank
""".strip()

PAL_DETAIL_SQL = """
SELECT p.*,
       COALESCE(array_agg(DISTINCT pe.element_type)
                FILTER (WHERE pe.element_type IS NOT NULL), '{}') AS elements_arr,
       COALESCE(jsonb_object_agg(ws.work_type, ws.level)
                FILTER (WHERE ws.work_type IS NOT NULL), '{}'::jsonb) AS work_json,
       COALESCE(array_agg(DISTINCT pa.alias)
                FILTER (WHERE pa.alias IS NOT NULL), '{}') AS aliases_arr
FROM pal p
LEFT JOIN pal_element pe ON p.id = pe.pal_id
LEFT JOIN work_suitability ws ON p.id = ws.pal_id
LEFT JOIN pal_aliase pa ON p.id = pa.pal_id
WHERE p.id = $1
GROUP BY p.id
""".strip()

SUITABILITY_SQL = """
SELECT p.game_id AS id, p.cn_name, p.zukan_index, p.combi_rank, p.is_wild, ws.level
FROM work_suitability ws
JOIN pal p ON ws.pal_id = p.id
WHERE ws.work_type = $1 AND ws.level >= $2
ORDER BY ws.level DESC
LIMIT $3
""".strip()

BREEDING_RULE_SQL = """
SELECT rule_type, parent_a_id, parent_b_id, description
FROM breeding_rule
WHERE child_id = $1
""".strip()

WORK_STATS_SQL = """
SELECT work_type,
       MAX(level)            AS max_level,
       ROUND(AVG(level), 1)  AS avg_level,
       COUNT(*) FILTER (WHERE level > 0) AS pal_count
FROM work_suitability
GROUP BY work_type
ORDER BY max_level DESC
""".strip()


def _row_to_pal(row) -> Pal:
    """将 JOIN 查询结果转为 Pal 对象."""
    # elements
    elements_raw = row.get("elements_arr") or row.get("elements") or []
    if isinstance(elements_raw, str):
        elements_raw = json.loads(elements_raw)
    elements = []
    for e in elements_raw:
        try:
            elements.append(Element(e))
        except ValueError:
            elements.append(Element.NEUTRAL)

    # work_suitability
    work_raw = row.get("work_json") or {}
    if isinstance(work_raw, str):
        work_raw = json.loads(work_raw)

    ws_dict = {}
    for k, v in work_raw.items():
        if isinstance(v, str):
            try:
                ws_dict[k] = int(v)
            except ValueError:
                ws_dict[k] = 0
        else:
            ws_dict[k] = int(v) if v else 0

    ws = WorkSuitability.from_dict(ws_dict)

    # aliases
    aliases_raw = row.get("aliases_arr") or row.get("aliases") or []
    if isinstance(aliases_raw, str):
        aliases_raw = json.loads(aliases_raw)
    aliases = [a for a in aliases_raw if a]

    return Pal(
        id=row.get("game_id") or row["id"],
        number=row.get("zukan_index", row.get("number", 0)),
        cn_name=row["cn_name"],
        en_name=row.get("en_name", ""),
        combi_rank=row["combi_rank"],
        elements=elements,
        rarity=row.get("rarity", 1),
        work_suitability=ws,
        is_wild=row.get("is_wild", False),
        aliases=aliases,
        image_url=row.get("image_url"),
        wiki_url=row.get("wiki_url"),
    )


class PostgresLoader:
    """从 PostgreSQL 加载帕鲁数据."""

    def __init__(self, config: PostgresConfig | None = None):
        self.config = config or PostgresConfig.from_env()
        self._pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        if self._pool is None:
            self._pool = await asyncpg.create_pool(
                dsn=self.config.dsn,
                min_size=1,
                max_size=4,
            )

    async def close(self) -> None:
        if self._pool:
            await self._pool.close()
            self._pool = None

    # ── load all ─────────────────────────────────────────────

    async def load_all(self) -> list[Pal]:
        """启动时加载全量 Pal 到内存."""
        await self._ensure_pool()

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(LOAD_ALL_SQL)

        pals = [_row_to_pal(r) for r in rows]
        logger.info("loaded %d pals from PG", len(pals))
        return pals

    # ── detail ───────────────────────────────────────────────

    async def get_detail(self, pal_db_id: int) -> Pal | None:
        """按 SERIAL id 查询单个 Pal."""
        await self._ensure_pool()
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(PAL_DETAIL_SQL, pal_db_id)
        if row is None:
            return None
        return _row_to_pal(row)

    # ── suitability (参数化, 无 SQL 注入) ────────────────────

    async def query_suitability(
        self, work_type: str, min_level: int, limit: int = 20
    ) -> list[dict]:
        """参数化查询 — 安全, 无动态列名插值."""
        await self._ensure_pool()
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(SUITABILITY_SQL, work_type, min_level, limit)
        return [
            {
                "id": r["id"],
                "cn_name": r["cn_name"],
                "number": r["zukan_index"],
                "combi_rank": r["combi_rank"],
                "is_wild": r["is_wild"],
                "level": r["level"],
            }
            for r in rows
        ]

    # ── work stats ───────────────────────────────────────────

    async def get_work_stats(self) -> list[dict]:
        """全工种统计."""
        await self._ensure_pool()
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(WORK_STATS_SQL)
        return [
            {
                "work_type": r["work_type"],
                "max_level": r["max_level"] or 0,
                "avg_level": float(r["avg_level"] or 0),
                "pal_count": r["pal_count"] or 0,
            }
            for r in rows
        ]

    # ── breeding rules ───────────────────────────────────────

    async def get_breeding_rules(self, pal_db_id: int) -> list[dict]:
        """查询特殊配种规则."""
        await self._ensure_pool()
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(BREEDING_RULE_SQL, pal_db_id)
        return [dict(r) for r in rows]

    # ── helpers ──────────────────────────────────────────────

    async def _ensure_pool(self) -> None:
        if self._pool is None:
            await self.connect()
