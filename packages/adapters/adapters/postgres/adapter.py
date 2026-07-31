"""PostgresWriter — write Pal entities to PostgreSQL."""

from __future__ import annotations

import logging

import asyncpg

from pl_agent.core.schema import Pal

from .config import PostgresConfig

logger = logging.getLogger(__name__)

# UPSERT template: all 27 columns
UPSERT_PAL = """
INSERT INTO pals (
    id, number, cn_name, en_name, combi_rank, elements, rarity, is_wild,
    handiwork, kindling, watering, planting,
    generating_electricity, gathering, lumbering, mining,
    cooling, medicine, transporting, farming,
    aliases, image_url, wiki_url, spawn_locations,
    data_source, incomplete
) VALUES (
    $1, $2, $3, $4, $5, $6, $7, $8,
    $9, $10, $11, $12, $13, $14, $15, $16,
    $17, $18, $19, $20,
    $21, $22, $23, $24,
    $25, $26
)
ON CONFLICT (id) DO UPDATE SET
    number = EXCLUDED.number,
    cn_name = EXCLUDED.cn_name,
    en_name = EXCLUDED.en_name,
    combi_rank = EXCLUDED.combi_rank,
    elements = EXCLUDED.elements,
    rarity = EXCLUDED.rarity,
    is_wild = EXCLUDED.is_wild,
    handiwork = EXCLUDED.handiwork,
    kindling = EXCLUDED.kindling,
    watering = EXCLUDED.watering,
    planting = EXCLUDED.planting,
    generating_electricity = EXCLUDED.generating_electricity,
    gathering = EXCLUDED.gathering,
    lumbering = EXCLUDED.lumbering,
    mining = EXCLUDED.mining,
    cooling = EXCLUDED.cooling,
    medicine = EXCLUDED.medicine,
    transporting = EXCLUDED.transporting,
    farming = EXCLUDED.farming,
    aliases = EXCLUDED.aliases,
    image_url = EXCLUDED.image_url,
    wiki_url = EXCLUDED.wiki_url,
    spawn_locations = EXCLUDED.spawn_locations,
    data_source = EXCLUDED.data_source,
    incomplete = EXCLUDED.incomplete
""".strip()


class PostgresWriter:
    """批量写入 Pal 到 PostgreSQL."""

    def __init__(self, config: PostgresConfig | None = None):
        self.config = config or PostgresConfig.from_env()
        self._pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        """建立连接池."""
        if self._pool is None:
            self._pool = await asyncpg.create_pool(
                dsn=self.config.dsn,
                min_size=1,
                max_size=4,
            )
            logger.info(
                "connected to PostgreSQL: %s:%d/%s",
                self.config.host,
                self.config.port,
                self.config.database,
            )

    async def close(self) -> None:
        """关闭连接池."""
        if self._pool:
            await self._pool.close()
            self._pool = None

    async def upsert_pal(self, pal: Pal) -> None:
        """单条 UPSERT."""
        await self._ensure_pool()
        ws = pal.work_suitability

        async with self._pool.acquire() as conn:
            await conn.execute(
                UPSERT_PAL,
                pal.id,
                pal.number,
                pal.cn_name,
                pal.en_name,
                pal.combi_rank,
                [e.value for e in pal.elements],
                pal.rarity,
                pal.is_wild,
                ws.handiwork,
                ws.kindling,
                ws.watering,
                ws.planting,
                ws.generating_electricity,
                ws.gathering,
                ws.lumbering,
                ws.mining,
                ws.cooling,
                ws.medicine,
                ws.transporting,
                ws.farming,
                pal.aliases,
                pal.image_url,
                pal.wiki_url,
                pal.spawn_locations,
                pal._source or "paldb.cc",
                pal._incomplete,
            )

    async def upsert_all(self, pals: list[Pal]) -> int:
        """批量 UPSERT.

        Returns:
            写入的条数.
        """
        await self._ensure_pool()
        count = 0
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                for pal in pals:
                    await self.upsert_pal(pal)
                    count += 1
        logger.info("upserted %d pals to PostgreSQL", count)
        return count

    async def count(self) -> int:
        """查询已存储的帕鲁数量."""
        await self._ensure_pool()
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow("SELECT count(*) FROM pals")
            return row[0] if row else 0

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    async def _ensure_pool(self) -> None:
        if self._pool is None:
            await self.connect()
