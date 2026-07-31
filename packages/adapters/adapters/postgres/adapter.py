"""PostgresWriter - write Pal entities to normalized PostgreSQL (5 tables)."""

from __future__ import annotations

import logging

import asyncpg

from pl_agent.core.schema import Pal

from .config import PostgresConfig

logger = logging.getLogger(__name__)

# -- multi-table UPSERT --

UPSERT_PAL = """
INSERT INTO pal (game_id, zukan_index, cn_name, en_name,
                 combi_rank, rarity, is_wild, image_url, wiki_url)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
ON CONFLICT (game_id) DO UPDATE SET
    zukan_index = EXCLUDED.zukan_index,
    cn_name = EXCLUDED.cn_name,
    en_name = EXCLUDED.en_name,
    combi_rank = EXCLUDED.combi_rank,
    rarity = EXCLUDED.rarity,
    is_wild = EXCLUDED.is_wild,
    image_url = EXCLUDED.image_url,
    wiki_url = EXCLUDED.wiki_url
RETURNING id
""".strip()

DELETE_ELEMENTS = "DELETE FROM pal_element WHERE pal_id = $1"
INSERT_ELEMENT = (
    "INSERT INTO pal_element (pal_id, element_type) "
    "VALUES ($1, $2) ON CONFLICT DO NOTHING"
)

DELETE_ALIASES = "DELETE FROM pal_aliase WHERE pal_id = $1"
INSERT_ALIAS = (
    "INSERT INTO pal_aliase (pal_id, alias, source) "
    "VALUES ($1, $2, 'community') ON CONFLICT DO NOTHING"
)

UPSERT_WORK = """
INSERT INTO work_suitability (pal_id, work_type, level)
VALUES ($1, $2, $3)
ON CONFLICT (pal_id, work_type) DO UPDATE SET level = EXCLUDED.level
""".strip()


class PostgresWriter:
    """Write Pal entities to PostgreSQL (4 tables per pal)."""

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
            logger.info(
                "connected to PostgreSQL: %s:%d/%s",
                self.config.host,
                self.config.port,
                self.config.database,
            )

    async def close(self) -> None:
        if self._pool:
            await self._pool.close()
            self._pool = None

    async def upsert_pal(self, pal: Pal) -> int:
        """Upsert single Pal into 4 tables. Returns pal.id (SERIAL)."""
        await self._ensure_pool()
        ws = pal.work_suitability

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                # 1. pal main table -> returns SERIAL id
                row = await conn.fetchrow(
                    UPSERT_PAL,
                    pal.id,  # game_id
                    pal.number,
                    pal.cn_name,
                    pal.en_name,
                    pal.combi_rank,
                    pal.rarity,
                    pal.is_wild,
                    pal.image_url,
                    pal.wiki_url,
                )
                pal_db_id = row["id"]

                # 2. pal_element - delete old, insert new
                await conn.execute(DELETE_ELEMENTS, pal_db_id)
                for e in pal.elements:
                    await conn.execute(INSERT_ELEMENT, pal_db_id, e.value)

                # 3. pal_aliase - delete old, insert new
                await conn.execute(DELETE_ALIASES, pal_db_id)
                for alias in pal.aliases:
                    await conn.execute(INSERT_ALIAS, pal_db_id, alias)

                # 4. work_suitability - upsert non-zero work types
                for work_type, level in ws.non_zero().items():
                    await conn.execute(UPSERT_WORK, pal_db_id, work_type, level)

        return pal_db_id

    async def upsert_all(self, pals: list[Pal]) -> int:
        """Batch upsert all pals."""
        await self._ensure_pool()
        count = 0
        for pal in pals:
            await self.upsert_pal(pal)
            count += 1
        logger.info("upserted %d pals to PostgreSQL", count)
        return count

    async def count(self) -> int:
        """Count stored pals."""
        await self._ensure_pool()
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow("SELECT count(*) FROM pal")
            return row[0] if row else 0

    async def _ensure_pool(self) -> None:
        if self._pool is None:
            await self.connect()
