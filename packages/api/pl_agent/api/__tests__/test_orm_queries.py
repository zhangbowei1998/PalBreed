"""Unit tests for ORM query service.

These tests mock AsyncSession behavior so they can run without a real database.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from pl_agent.api.db.models import (
    PalAliasModel,
    PalElementModel,
    PalModel,
    WorkSuitabilityModel,
)
from pl_agent.api.db.queries import OrmQueryService


class _FakeScalarsResult:
    def __init__(self, items):
        self._items = items

    def all(self):
        return self._items


class _FakeMappingsResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows

    def first(self):
        return self._rows[0] if self._rows else None


class _FakeExecuteResult:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return _FakeMappingsResult(self._rows)


class _FakeSession:
    def __init__(self, *, scalars_items=None, execute_rows=None):
        self._scalars_items = scalars_items or []
        self._execute_rows = execute_rows or []

    async def scalars(self, _stmt):
        return _FakeScalarsResult(self._scalars_items)

    async def execute(self, _stmt):
        return _FakeExecuteResult(self._execute_rows)


class _FakeSessionContext:
    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakeSessionFactory:
    def __init__(self, session):
        self._session = session

    def __call__(self):
        return _FakeSessionContext(self._session)


def _build_service(*, scalars_items=None, execute_rows=None):
    engine = SimpleNamespace(dispose=AsyncMock())
    session = _FakeSession(scalars_items=scalars_items, execute_rows=execute_rows)
    return OrmQueryService(engine, _FakeSessionFactory(session)), engine


def _build_pal_model() -> PalModel:
    pal = PalModel(
        id=1,
        game_id="Anubis",
        zukan_index=139,
        cn_name="阿努比斯",
        en_name="Anubis",
        combi_rank=480,
        rarity=10,
        is_wild=False,
        image_url="https://cdn.example/anubis.webp",
        wiki_url="https://paldb.cc/cn/Anubis",
    )
    pal.elements = [
        PalElementModel(pal_id=1, element_type="Earth"),
        # Invalid value should fallback to NEUTRAL in converter.
        PalElementModel(pal_id=1, element_type="NotARealElement"),
    ]
    pal.aliases = [
        PalAliasModel(id=1, pal_id=1, alias="狗头", source="community"),
    ]
    pal.work_suitabilities = [
        WorkSuitabilityModel(pal_id=1, work_type="handiwork", level=6),
        WorkSuitabilityModel(pal_id=1, work_type="mining", level=6),
    ]
    return pal


def test_model_to_pal_mapping_handles_invalid_element():
    pal = _build_pal_model()

    converted = OrmQueryService._model_to_pal(pal)

    assert converted.id == "Anubis"
    assert converted.cn_name == "阿努比斯"
    assert converted.work_suitability.handiwork == 6
    assert converted.work_suitability.mining == 6
    assert converted.aliases == ["狗头"]
    # Earth preserved, invalid value downgraded to Neutral.
    assert [e.value for e in converted.elements] == ["Earth", "Neutral"]


@pytest.mark.asyncio
async def test_load_all_pals_returns_domain_objects():
    model = _build_pal_model()
    service, _engine = _build_service(scalars_items=[model])

    pals = await service.load_all_pals()

    assert len(pals) == 1
    assert pals[0].id == "Anubis"
    assert pals[0].number == 139


@pytest.mark.asyncio
async def test_query_suitability_maps_rows():
    rows = [
        {
            "id": "Anubis",
            "cn_name": "阿努比斯",
            "zukan_index": 139,
            "combi_rank": 480,
            "is_wild": False,
            "level": 6,
        }
    ]
    service, _engine = _build_service(execute_rows=rows)

    items = await service.query_suitability("handiwork", 4, limit=50)

    assert items == [
        {
            "id": "Anubis",
            "cn_name": "阿努比斯",
            "number": 139,
            "combi_rank": 480,
            "is_wild": False,
            "level": 6,
        }
    ]


@pytest.mark.asyncio
async def test_get_work_stats_normalizes_nulls():
    rows = [
        {
            "work_type": "handiwork",
            "max_level": None,
            "avg_level": None,
            "pal_count": None,
        }
    ]
    service, _engine = _build_service(execute_rows=rows)

    stats = await service.get_work_stats()

    assert stats == [
        {
            "work_type": "handiwork",
            "max_level": 0,
            "avg_level": 0.0,
            "pal_count": 0,
        }
    ]


@pytest.mark.asyncio
async def test_breeding_rule_and_parent_queries_map_rows():
    service, _engine = _build_service(
        execute_rows=[
            {
                "rule_type": "fixed_pair",
                "parent_a_id": 10,
                "parent_b_id": 20,
                "description": "fixed combo",
            }
        ]
    )

    rules = await service.get_breeding_rules_by_game_id("Anubis")
    assert rules[0]["rule_type"] == "fixed_pair"

    # Rebuild with a new execute payload to test get_pal_pair_by_db_id.
    service, _engine = _build_service(
        execute_rows=[
            {
                "cn_name": "棉悠悠",
                "id": "Lamball",
                "combi_rank": 1470,
                "is_wild": True,
            }
        ]
    )
    parent = await service.get_pal_pair_by_db_id(10)
    assert parent == {
        "cn_name": "棉悠悠",
        "id": "Lamball",
        "combi_rank": 1470,
        "is_wild": True,
    }


@pytest.mark.asyncio
async def test_query_parent_pairs_by_rank_maps_rows():
    service, _engine = _build_service(
        execute_rows=[
            {
                "pa_cn": "棉悠悠",
                "pa_id": "Lamball",
                "pa_rank": 1470,
                "pa_wild": True,
                "pb_cn": "捣蛋猫",
                "pb_id": "Cattiva",
                "pb_rank": 1460,
                "pb_wild": True,
            }
        ]
    )

    pairs = await service.query_parent_pairs_by_rank(1465, "Anubis")

    assert len(pairs) == 1
    assert pairs[0]["pa_id"] == "Lamball"
    assert pairs[0]["pb_id"] == "Cattiva"


@pytest.mark.asyncio
async def test_close_disposes_engine():
    service, engine = _build_service()

    await service.close()

    engine.dispose.assert_awaited_once()
