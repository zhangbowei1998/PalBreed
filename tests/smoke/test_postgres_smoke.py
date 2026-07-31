"""Integration smoke test — end-to-end PostgreSQL pipeline.

Prerequisites:
  - PostgreSQL running on localhost:5432
  - Database 'pl_agent_test' created: createdb pl_agent_test
  - Schema applied: psql -d pl_agent_test -f data/sql/001_create_pals.sql

Run:
  PGDATABASE=pl_agent_test uv run pytest tests/smoke/test_postgres_smoke.py -v

Skips automatically if PG is not available.
"""

import asyncio

import pytest

from pl_agent.core.schema import Element, Pal, WorkSuitability
from pl_agent.core.data_loader import DataLoader

# ── check PG availability ──────────────────────────────────────────


def _pg_available():
    try:
        import asyncpg

        return True
    except ImportError:
        return False


async def _can_connect(db="pl_agent_test"):
    try:
        conn = await asyncpg.connect(
            database=db, user="postgres", host="localhost", port=5432
        )
        await conn.close()
        return True
    except Exception:
        return False


# ── fixtures ───────────────────────────────────────────────────────


@pytest.fixture
def demo_pals():
    return [
        Pal(
            id="melpaca",
            cn_name="棉悠悠",
            en_name="Melpaca",
            number=1,
            combi_rank=1460,
            elements=[Element.NEUTRAL],
            rarity=1,
            is_wild=True,
            work_suitability=WorkSuitability(farming=1),
        ),
        Pal(
            id="pengullet",
            cn_name="企丸丸",
            en_name="Pengullet",
            number=10,
            combi_rank=1350,
            elements=[Element.WATER, Element.ICE],
            rarity=1,
            is_wild=True,
            work_suitability=WorkSuitability(
                watering=1, cooling=1, handiwork=1, transporting=1
            ),
        ),
        Pal(
            id="anubis",
            cn_name="阿努比斯",
            en_name="Anubis",
            number=100,
            combi_rank=570,
            elements=[Element.EARTH],
            rarity=5,
            is_wild=False,
            work_suitability=WorkSuitability(mining=4, handiwork=4, transporting=2),
        ),
    ]


# ── tests ──────────────────────────────────────────────────────────


@pytest.mark.skipif(not _pg_available(), reason="asyncpg not installed")
class TestPostgresPipeline:
    """End-to-end: write → read → engine."""

    async def test_write_and_read_hot(self, demo_pals):
        if not await _can_connect():
            pytest.skip("PostgreSQL not available")

        from adapters.postgres.adapter import PostgresWriter
        from adapters.postgres.loader import PostgresLoader

        # 1. Write to PG
        writer = PostgresWriter()
        await writer.connect()
        await writer.upsert_all(demo_pals)
        count = await writer.count()
        assert count == len(demo_pals)
        await writer.close()

        # 2. Read hot cache
        loader = PostgresLoader()
        index = await loader.load_hot()
        assert len(index) == len(demo_pals)

        # 3. Verify hot fields populated
        anubis = index.by_id["anubis"]
        assert anubis.cn_name == "阿努比斯"
        assert anubis.combi_rank == 570
        assert anubis.work_suitability.mining == 4
        assert anubis.is_wild is False

        # 4. Verify cold fields (not in hot cache, fetch on demand)
        detail = await loader.get_detail("anubis")
        assert detail is not None

        await loader.close()

    async def test_engine_from_hot_cache(self, demo_pals):
        if not await _can_connect():
            pytest.skip("PostgreSQL not available")

        from adapters.postgres.adapter import PostgresWriter
        from adapters.postgres.loader import PostgresLoader
        from pl_agent.core.breeding_engine import BreedingEngine
        from pl_agent.core.schema import BreedingRules

        # Write
        writer = PostgresWriter()
        await writer.connect()
        await writer.upsert_all(demo_pals)
        await writer.close()

        # Load → Engine
        loader = PostgresLoader()
        index = await loader.load_hot()

        rules = BreedingRules(game_version="v1.0", last_updated="2026-07-31")
        engine = BreedingEngine(pals=index.pals, rules=rules)

        # Forward breed
        melpaca = engine.get_pal("melpaca")
        pengullet = engine.get_pal("pengullet")
        child = engine.forward_breed(melpaca, pengullet)
        assert child is not None

        # Reverse breed
        anubis = engine.get_pal("anubis")
        parents = engine.reverse_breed(anubis)
        assert isinstance(parents, list)

        await loader.close()

    async def test_query_suitability_from_pg(self, demo_pals):
        if not await _can_connect():
            pytest.skip("PostgreSQL not available")

        from adapters.postgres.adapter import PostgresWriter
        from adapters.postgres.loader import PostgresLoader

        writer = PostgresWriter()
        await writer.connect()
        await writer.upsert_all(demo_pals)
        await writer.close()

        loader = PostgresLoader()
        await loader.connect()

        results = await loader.query_suitability("handiwork", 3)
        # anubis has handiwork=4
        assert any(r["id"] == "anubis" for r in results)

        # pengullet has handiwork=1 → not in results for level >=3
        assert not any(r["id"] == "pengullet" for r in results)

        await loader.close()

    async def test_json_fallback_works(self, demo_pals, tmp_path):
        """Verify JSON fallback still works when PG is expected to fail."""
        import json

        # Save demo pals as JSON
        data = {p.id: p.to_dict() for p in demo_pals}
        path = tmp_path / "pal_data.json"
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

        loader = DataLoader()
        loader.load(path)
        assert len(loader) == 3

        from pl_agent.core.breeding_engine import BreedingEngine
        from pl_agent.core.schema import BreedingRules

        rules = BreedingRules(game_version="v1.0", last_updated="2026-07-31")
        engine = BreedingEngine(pals=loader.get_all(), rules=rules)
        assert len(engine.all_pals) == 3
