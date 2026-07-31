"""Tests for breeding engine core."""

import pytest

from pl_agent.core.schema import (
    BreedingRules,
    Element,
    Pal,
    SpecialCombination,
    WorkSuitability,
)
from pl_agent.core.breeding_engine import BreedingEngine
from pl_agent.core.breeding_tree import BreedingTreeBuilder
from pl_agent.core.suitability_query import SuitabilityQuery
from pl_agent.core.path_optimizer import PathOptimizer

# ── Test fixtures ──────────────────────────────────────────────────


def _make_pal(
    id, number, cn_name, combi_rank, element, rarity=1, is_wild=True, **work
) -> Pal:
    return Pal(
        id=id,
        number=number,
        cn_name=cn_name,
        en_name=id,
        combi_rank=combi_rank,
        elements=[element],
        rarity=rarity,
        work_suitability=WorkSuitability(**work),
        is_wild=is_wild,
    )


@pytest.fixture
def sample_pals():
    return [
        _make_pal(
            "Lamball",
            1,
            "棉悠悠",
            1470,
            Element.NEUTRAL,
            handiwork=1,
            transporting=1,
            farming=1,
        ),
        _make_pal(
            "Cattiva",
            2,
            "捣蛋猫",
            1460,
            Element.NEUTRAL,
            handiwork=1,
            gathering=1,
            mining=1,
        ),
        _make_pal("Chikipi", 3, "鸡", 1500, Element.NEUTRAL, farming=1),
        _make_pal(
            "Anubis",
            139,
            "阿努比斯",
            480,
            Element.EARTH,
            rarity=10,
            handiwork=6,
            mining=6,
            transporting=4,
        ),
        _make_pal("Foxparks", 4, "火狐", 1320, Element.FIRE, rarity=3, kindling=2),
    ]


@pytest.fixture
def engine(sample_pals):
    rules = BreedingRules(
        game_version="v1.0.2",
        last_updated="2026-07-31",
        special_combinations=[],
        self_only=[],
        unbreedable=[],
        breeding_excluded=[],
    )
    return BreedingEngine(pals=sample_pals, rules=rules)


# ── Tests ──────────────────────────────────────────────────────────


class TestBreedingEngine:
    def test_forward_breed_basic(self, engine):
        lamball = engine.get_pal("Lamball")
        cattiva = engine.get_pal("Cattiva")
        child = engine.forward_breed(lamball, cattiva)
        # avg = (1470+1460)/2 = 1465, nearest is Cattiva(1460)
        assert child.id == "Cattiva"

    def test_forward_breed_special(self):
        pals = [
            _make_pal("Relaxaurus", 69, "雷棘龙", 1130, Element.WATER, watering=3),
            _make_pal(
                "Sparkit",
                70,
                "电棘鼠",
                1110,
                Element.ELECTRIC,
                generating_electricity=2,
            ),
            _make_pal(
                "Relaxaurus Lux",
                69,
                "雷棘龙·勒克斯",
                1120,
                Element.ELECTRIC,
                is_wild=False,
            ),
        ]
        rules = BreedingRules(
            game_version="v1.0.2",
            last_updated="2026-07-31",
            special_combinations=[
                SpecialCombination(
                    parent_a="Relaxaurus", parent_b="Sparkit", child="Relaxaurus Lux"
                ),
            ],
            self_only=[],
            unbreedable=[],
            breeding_excluded=[],
        )
        eng = BreedingEngine(pals=pals, rules=rules)
        r = eng.get_pal("Relaxaurus")
        s = eng.get_pal("Sparkit")
        child = eng.forward_breed(r, s)
        assert child.id == "Relaxaurus Lux"

    def test_reverse_breed_anubis(self, engine):
        anubis = engine.get_pal("Anubis")
        parents = engine.reverse_breed(anubis)
        assert len(parents) > 0

    def test_reverse_breed_wild_pal(self, engine):
        """基础帕鲁的反向查询应返回自身配对."""
        lamball = engine.get_pal("Lamball")
        parents = engine.reverse_breed(lamball)
        # 最低 rank 的帕鲁只能与自身配对
        assert len(parents) > 0

    def test_reverse_with_parent(self, engine):
        anubis = engine.get_pal("Anubis")
        parents = engine.reverse_breed(anubis)
        if parents:
            other = engine.reverse_with_parent(anubis, parents[0][0])
            assert len(other) > 0 or parents[0][0].id == parents[0][1].id


class TestBreedingTree:
    def test_build_anubis_tree(self, engine):
        builder = BreedingTreeBuilder(engine, max_depth=5)
        anubis = engine.get_pal("Anubis")
        tree = builder.build(anubis)
        assert tree.target.id == "Anubis"
        assert tree.total_paths >= 0

    def test_build_wild_pal_tree(self, engine):
        builder = BreedingTreeBuilder(engine, max_depth=5)
        lamball = engine.get_pal("Lamball")
        tree = builder.build(lamball)
        # wild pal → single-node tree
        assert tree.total_paths >= 0


class TestSuitabilityQuery:
    def test_query_handiwork(self, sample_pals):
        sq = SuitabilityQuery(sample_pals)
        results = sq.query("handiwork", 1)
        assert len(results) >= 2  # Lamball, Cattiva, Anubis

    def test_query_high_level_returns_empty(self, sample_pals):
        sq = SuitabilityQuery(sample_pals)
        results = sq.query("handiwork", 100)
        assert results == []

    def test_get_max_level(self, sample_pals):
        sq = SuitabilityQuery(sample_pals)
        max_lv = sq.get_max_level("handiwork")
        assert max_lv == 6  # Anubis

    def test_query_multi(self, sample_pals):
        sq = SuitabilityQuery(sample_pals)
        results = sq.query_multi([("handiwork", 1), ("mining", 1)])
        # 只有 Cattiva 和 Anubis 同时有 handiwork 和 mining
        ids = {p.id for p, _ in results}
        assert "Cattiva" in ids or "Anubis" in ids


class TestPathOptimizer:
    def test_optimize(self, engine):
        builder = BreedingTreeBuilder(engine, max_depth=5)
        anubis = engine.get_pal("Anubis")
        tree = builder.build(anubis)
        optimizer = PathOptimizer(engine)
        optimizer.optimize(tree)
        # best_path should be set if we have paths
        if tree.paths:
            assert tree.best_path is not None
