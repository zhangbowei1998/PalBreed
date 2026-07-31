"""PostgresLoader — load breeding-critical hot fields from PG into memory."""

from __future__ import annotations

from dataclasses import dataclass, field
import logging

import asyncpg

from pl_agent.core.schema import Pal, WorkSuitability

from .config import PostgresConfig

logger = logging.getLogger(__name__)

# ── lightweight index for breeding engine ──────────────────────────


@dataclass
class BreedingIndex:
    """热缓存 — 配种引擎 BFS 所需的 O(1) 内存索引.

    只包含配种计算必需的字段: id, combi_rank, is_wild, work_suitability.
    展示字段 (image_url, wiki_url 等) 保留 PG 按需查询.
    """
    pals: list[Pal] = field(default_factory=list)
    by_id: dict[str, Pal] = field(default_factory=dict)
    by_rank: list[Pal] = field(default_factory=list)          # 按 CombiRank 排序

    def __len__(self) -> int:
        return len(self.pals)

    @property
    def wild_ids(self) -> set[str]:
        return {p.id for p in self.pals if p.is_wild}


# ── loader ────────────────────────────────────────────────────────

# 只 SELECT 热字段
HOT_FIELDS_SQL = """
SELECT
    id, combi_rank, is_wild,
    handiwork, kindling, watering, planting,
    generating_electricity, gathering, lumbering, mining,
    cooling, medicine, transporting, farming,
    number, cn_name, en_name, elements, rarity
FROM pals
ORDER BY combi_rank
""".strip()

# 单条冷字段查询
COLD_FIELDS_SQL = """
SELECT image_url, wiki_url, spawn_locations, aliases
FROM pals WHERE id = $1
""".strip()


class PostgresLoader:
    """从 PostgreSQL 加载热缓存到内存."""

    def __init__(self, config: PostgresConfig | None = None):
        self.config = config or PostgresConfig.from_env()
        self._pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        if self._pool is None:
            self._pool = await asyncpg.create_pool(
                dsn=self.config.dsn, min_size=1, max_size=4,
            )

    async def close(self) -> None:
        if self._pool:
            await self._pool.close()
            self._pool = None

    # ── hot cache ──────────────────────────────────────────────

    async def load_hot(self) -> BreedingIndex:
        """启动时加载配种核心字段到 BreedingIndex (~10KB).

        冷字段 (image_url 等) 留在 PG，运行时按需查询.
        """
        await self._ensure_pool()

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(HOT_FIELDS_SQL)

        pals: list[Pal] = []
        for r in rows:
            ws = WorkSuitability(
                handiwork=r["handiwork"],
                kindling=r["kindling"],
                watering=r["watering"],
                planting=r["planting"],
                generating_electricity=r["generating_electricity"],
                gathering=r["gathering"],
                lumbering=r["lumbering"],
                mining=r["mining"],
                cooling=r["cooling"],
                medicine=r["medicine"],
                transporting=r["transporting"],
                farming=r["farming"],
            )
            # elements: JSONB → list[str] → list[Element]
            from pl_agent.core.schema import Element
            elements_raw = r["elements"] or []
            elements = []
            for e in elements_raw:
                try:
                    elements.append(Element(e))
                except ValueError:
                    elements.append(Element.NEUTRAL)

            pal = Pal(
                id=r["id"],
                number=r["number"],
                cn_name=r["cn_name"],
                en_name=r["en_name"],
                combi_rank=r["combi_rank"],
                elements=elements,
                rarity=r["rarity"],
                work_suitability=ws,
                is_wild=r["is_wild"],
                # cold fields: leave as defaults (PG 按需查询)
            )
            pals.append(pal)

        index = BreedingIndex(
            pals=pals,
            by_id={p.id: p for p in pals},
            by_rank=sorted(pals, key=lambda p: p.combi_rank),
        )

        logger.info(
            "loaded %d pals from PG (hot cache, %.1f KB)",
            len(pals),
            sum(len(p.id) + 20 for p in pals) / 1024,
        )
        return index

    # ── cold query ─────────────────────────────────────────────

    async def get_detail(self, pal_id: str) -> dict | None:
        """按需从 PG 查询冷字段 (image_url, wiki_url 等)."""
        await self._ensure_pool()
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(COLD_FIELDS_SQL, pal_id)
        if row is None:
            return None
        return {
            "image_url": row["image_url"],
            "wiki_url": row["wiki_url"],
            "spawn_locations": row["spawn_locations"] or [],
            "aliases": row["aliases"] or [],
        }

    async def query_suitability(
        self, work_type: str, min_level: int, limit: int = 20
    ) -> list[dict]:
        """PG 冷查询: 按工作适应性筛选.

        利用 SQL 索引, 比 Python 遍历更快.
        """
        await self._ensure_pool()
        # 白名单校验列名防止 SQL 注入
        valid = {
            "handiwork", "kindling", "watering", "planting",
            "generating_electricity", "gathering", "lumbering", "mining",
            "cooling", "medicine", "transporting", "farming",
        }
        if work_type not in valid:
            return []

        sql = (
            f'SELECT id, cn_name, number, {work_type} AS lv '
            f'FROM pals WHERE {work_type} >= $1 '
            f'ORDER BY {work_type} DESC LIMIT $2'
        )
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(sql, min_level, limit)
        return [{"id": r["id"], "cn_name": r["cn_name"],
                 "number": r["number"], "level": r["lv"]} for r in rows]

    # ── helpers ────────────────────────────────────────────────

    async def _ensure_pool(self) -> None:
        if self._pool is None:
            await self.connect()
