"""Unit tests for tc-imba extension queries (S6-S10).

Mock AsyncSession — run without a real database.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from pl_agent.api.db.models import (
    PalModel,
    PalPartnerSkillModel,
    PalStatsModel,
)
from pl_agent.api.db.queries import OrmQueryService


class _FakeMappings:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows

    def first(self):
        return self._rows[0] if self._rows else None


class _FakeScalars:
    def __init__(self, item):
        self._item = item

    def first(self):
        return self._item


class _FakeResult:
    """execute() 返回 — 同时支持 mappings() 与 scalars().first()."""

    def __init__(self, rows, scalar_item=None):
        self._rows = rows
        self._scalar_item = scalar_item

    def mappings(self):
        return _FakeMappings(self._rows)

    def scalars(self):
        return _FakeScalars(self._scalar_item)


class _FakeSession:
    def __init__(self, queue):
        self._queue = list(queue)
        self._call = 0

    async def execute(self, _stmt):
        item = self._queue[self._call] if self._call < len(self._queue) else []
        self._call += 1
        if isinstance(item, tuple):
            rows, scalar_item = item
            return _FakeResult(rows, scalar_item)
        return _FakeResult(item, None)


class _FakeCtx:
    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *args):
        return False


def _service(queue):
    engine = SimpleNamespace(dispose=AsyncMock())
    session = _FakeSession(queue)
    return OrmQueryService(engine, lambda: _FakeCtx(session))


@pytest.mark.asyncio
async def test_query_pals_by_passive():
    svc = _service([
        [{"id": "KingAlpaca", "cn_name": "君王美露帕", "combi_rank": 2220,
          "is_wild": True, "passive_id": "Deffence_up2_2",
          "passive_cn": "重量级", "passive_rank": 2}],
    ])
    res = await svc.query_pals_by_passive("重量级")
    assert len(res) == 1
    assert res[0]["id"] == "KingAlpaca"
    assert res[0]["passive_cn"] == "重量级"


@pytest.mark.asyncio
async def test_query_pal_skills():
    svc = _service([
        [{"waza_id": "AirCanon", "cn_name": "空气弹", "element": "Normal",
          "category": "Shot", "power": 30, "cool_time": 2, "learn_level": 1}],
    ])
    res = await svc.query_pal_skills("SheepBall")
    assert res[0]["learn_level"] == 1
    assert res[0]["cn_name"] == "空气弹"


@pytest.mark.asyncio
async def test_query_pal_drops():
    svc = _service([
        [{"item_id": "Ruby", "cn_name": "红宝石", "rate": 3, "min": 1, "max": 1,
          "min_level": None, "is_boss": False}],
    ])
    res = await svc.query_pal_drops("Garm")
    assert res[0]["item_id"] == "Ruby"
    assert res[0]["is_boss"] is False


@pytest.mark.asyncio
async def test_query_pals_dropping_item():
    # 队列第 1 个 = _resolve_item_id 精确匹配返回 item.id（scalars().first()=5）
    svc = _service([
        (None, 5),  # rows=None, scalar_item=5
        [{"pal_id": "Garm", "pal_cn": "加姆", "rate": 3, "min": 1, "max": 1,
          "is_boss": False}],
    ])
    res = await svc.query_pals_dropping_item("红宝石")
    assert res[0]["pal_cn"] == "加姆"


@pytest.mark.asyncio
async def test_query_pals_dropping_item_fuzzy():
    """精确匹配无结果 → 模糊匹配回退（如 '帕鲁油' → '优质帕鲁油'）。"""
    # 第 1 个 execute = 精确匹配返回 None；第 2 个 = 模糊匹配返回 item.id；第 3 个 = 主查询
    svc = _service([
        (None, None),
        (None, 7),
        [{"pal_id": "LazyCatfish", "pal_cn": "趴趴鲶", "rate": 1, "min": 1,
          "max": 1, "is_boss": False}],
    ])
    res = await svc.query_pals_dropping_item("帕鲁油")
    assert res[0]["pal_cn"] == "趴趴鲶"


@pytest.mark.asyncio
async def test_query_recipe_chain():
    # 队列第 1 个 = _resolve_item_id 精确匹配返回 item.id（scalars().first()=3）
    svc = _service([
        (None, 3),  # rows=None, scalar_item=3
        [{"item_id": "CopperIngot", "product": "金属锭", "work": 1000,
          "product_count": 1, "station": "BlastFurnace",
          "material": "金属矿石", "count": 2}],
    ])
    res = await svc.query_recipe_chain("金属锭")
    assert res[0]["material"] == "金属矿石"
    assert res[0]["station"] == "BlastFurnace"


@pytest.mark.asyncio
async def test_query_pal_detail_full():
    pal = PalModel(id=1, game_id="Anubis", zukan_index=139, cn_name="阿努比斯",
                   en_name="Anubis", combi_rank=480, rarity=10, is_wild=False,
                   breed_child=True, genus="Humanoid", size="L", predator=False)
    stats = PalStatsModel(pal_id=1, hp=120, melee_attack=130, capture_rate=1.0)
    partner = PalPartnerSkillModel(pal_id=1, action_name="StatusUp_GiveElement",
                                   effect_time=30, cool_time=50)
    svc = _service([
        ([], pal),                       # 1. pal
        ([], stats),                     # 2. stats
        ([], None),                      # 3. friendship
        ([], None),                      # 4. enemy_scaling
        ([], partner),                   # 5. partner_skill
        [{"waza_id": "AirCanon", "cn_name": "空气弹", "element": "Normal",
          "category": "Shot", "power": 30, "cool_time": 2, "learn_level": 1}],  # 6. skills
        [{"item_id": "Bone", "cn_name": "骨头", "rate": 100, "min": 3, "max": 5,
          "min_level": None, "is_boss": False}],                               # 7. drops
        [{"passive_id": "Rare", "cn_name": "稀有", "rank": 3,
          "lottery_weight": None, "effect_type": None, "effect_value": None}],  # 8. passives
        [{"item_id": "PalSummon_X", "cn_name": "召唤物", "level": 55, "count": 4}],  # 9. summon
    ])
    res = await svc.query_pal_detail_full("Anubis")
    assert res is not None
    assert res["cn_name"] == "阿努比斯"
    assert res["genus"] == "Humanoid"
    assert res["predator"] is False
    assert res["stats"]["hp"] == 120
    assert res["partner_skill"]["action_name"] == "StatusUp_GiveElement"
    assert len(res["skills"]) == 1
    assert len(res["drops"]) == 1
    assert len(res["passives"]) == 1
    assert res["summon"][0]["level"] == 55
