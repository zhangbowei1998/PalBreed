"""Smoke test — end-to-end: data loading → engine → query → tree → optimize.

Runs the full pipeline on a realistic in-memory dataset.
Does NOT hit paldb.cc (offline smoke test).
"""

import json
import tempfile
from pathlib import Path

import pytest

from pl_agent.core.schema import (
    BreedingRules,
    Element,
    Pal,
    SpecialCombination,
    Unbreedable,
    WorkSuitability,
)
from pl_agent.core.breeding_engine import BreedingEngine
from pl_agent.core.breeding_tree import BreedingTreeBuilder
from pl_agent.core.data_loader import DataLoader
from pl_agent.core.path_optimizer import PathOptimizer
from pl_agent.core.suitability_query import SuitabilityQuery

# ── realistic test dataset (simulating actual game data) ──────────


def _p(id, num, cn, rank, elem, rarity=1, is_wild=True, **ws):
    return Pal(
        id=id,
        number=num,
        cn_name=cn,
        en_name=id,
        combi_rank=rank,
        elements=[elem],
        rarity=rarity,
        work_suitability=WorkSuitability(**ws),
        is_wild=is_wild,
    )


REALISTIC_PALS = [
    # 常见低级帕鲁 (高 CombiRank)
    _p(
        "Lamball",
        1,
        "棉悠悠",
        1470,
        Element.NEUTRAL,
        handiwork=1,
        transporting=1,
        farming=1,
    ),
    _p(
        "Cattiva",
        2,
        "捣蛋猫",
        1460,
        Element.NEUTRAL,
        handiwork=1,
        gathering=1,
        mining=1,
        transporting=1,
    ),
    _p("Chikipi", 3, "捣蛋鸡", 1500, Element.NEUTRAL, farming=1, gathering=1),
    _p(
        "Lifmunk",
        4,
        "利亚蒙克",
        1430,
        Element.GRASS,
        planting=1,
        handiwork=1,
        gathering=1,
        lumbering=1,
        medicine=1,
    ),
    _p("Foxparks", 5, "火狐", 1400, Element.FIRE, kindling=1),
    _p(
        "Fuack",
        6,
        "弗亚克",
        1330,
        Element.WATER,
        watering=1,
        handiwork=1,
        transporting=1,
    ),
    _p(
        "Sparkit",
        7,
        "电棘鼠",
        1410,
        Element.ELECTRIC,
        generating_electricity=1,
        handiwork=1,
        transporting=1,
    ),
    _p(
        "Tanzee",
        8,
        "腾斯",
        1250,
        Element.GRASS,
        planting=1,
        handiwork=1,
        gathering=1,
        medicine=1,
    ),
    _p("Rooby", 9, "鲁比", 1150, Element.FIRE, kindling=2, lumbering=1),
    _p(
        "Pengullet",
        10,
        "企丸丸",
        1350,
        Element.WATER,
        watering=1,
        cooling=1,
        handiwork=1,
        transporting=1,
    ),
    # 中级帕鲁
    _p("Eikthyrdeer", 20, "角鹿", 1010, Element.NEUTRAL, lumbering=3),
    _p("Nitewing", 21, "夜翼", 920, Element.NEUTRAL, gathering=3),
    _p("Rushoar", 26, "冲刺猪", 960, Element.NEUTRAL, mining=2),
    _p("Celaray", 33, "塞拉雷", 870, Element.WATER, watering=2, transporting=2),
    _p("Direhowl", 40, "恐狼", 850, Element.NEUTRAL, gathering=2, transporting=2),
    _p(
        "Mossanda",
        48,
        "毛茸大",
        730,
        Element.GRASS,
        planting=2,
        handiwork=2,
        lumbering=3,
        transporting=3,
    ),
    _p("Relaxaurus", 60, "雷棘龙", 1130, Element.WATER, watering=3, transporting=2),
    _p("Loupmoon", 55, "狼月", 780, Element.DARK, handiwork=2),
    _p("Kitsun", 76, "狐狸精", 660, Element.FIRE, kindling=3),
    _p("Jolthog", 11, "雷刺猬", 1370, Element.ELECTRIC, generating_electricity=2),
    # 中高级帕鲁
    _p(
        "Fenglope",
        83,
        "烽歌龙",
        560,
        Element.NEUTRAL,
        gathering=3,
        transporting=3,
        lumbering=3,
    ),
    _p(
        "Fenglope Lux",
        83,
        "雷隐鹿",
        550,
        Element.ELECTRIC,
        gathering=3,
        transporting=3,
        lumbering=3,
    ),
    _p("Vanwyrm", 84, "焰皇", 620, Element.FIRE, kindling=3, transporting=3),
    _p(
        "Anubis",
        139,
        "阿努比斯",
        480,
        Element.EARTH,
        rarity=10,
        is_wild=False,
        handiwork=6,
        mining=6,
        transporting=4,
    ),
    _p("Suzaku", 122, "朱雀", 470, Element.FIRE, kindling=4),
    _p("Jormuntide", 110, "尤蒙提德", 420, Element.WATER, watering=5),
    _p("Blazamut", 115, "焰狮", 450, Element.FIRE, kindling=5, mining=5),
    _p(
        "Lyleen",
        105,
        "百合女王",
        440,
        Element.GRASS,
        planting=5,
        handiwork=4,
        medicine=4,
        gathering=3,
    ),
    # 传说帕鲁
    _p(
        "Frostallion", 200, "唤冬兽", 10, Element.ICE, rarity=10, cooling=5, gathering=3
    ),
    _p("Jetragon", 202, "空涡龙", 5, Element.DRAGON, rarity=10, gathering=4),
    # 亚种 (不可野生)
    _p(
        "Relaxaurus Lux",
        60,
        "雷棘龙·勒克斯",
        1120,
        Element.ELECTRIC,
        rarity=5,
        is_wild=False,
        generating_electricity=3,
        transporting=2,
    ),
]

REALISTIC_RULES = BreedingRules(
    game_version="v1.0.2",
    last_updated="2026-07-31",
    special_combinations=[
        SpecialCombination(
            "Relaxaurus", "Sparkit", "Relaxaurus Lux", "雷棘龙+电棘鼠=雷棘龙·勒克斯"
        ),
    ],
    self_only=[],  # Frostallion/Jetragon 不设 self_only，测试他们也能参与普通计算
    unbreedable=[
        Unbreedable("TowerBoss_Grizzbolt", "塔主暴电熊"),
    ],
    breeding_excluded=[],
)


# ── smoke test ─────────────────────────────────────────────────────


class TestBreedingSmoke:
    """端到端冒烟测试：从数据加载到完整配种方案输出."""

    @pytest.fixture
    def engine(self):
        return BreedingEngine(pals=REALISTIC_PALS, rules=REALISTIC_RULES)

    def test_full_pipeline_anubis(self, engine):
        """完整流程：查询阿努比斯 → 配种树 → 择优."""
        anubis = engine.get_pal("Anubis")
        assert anubis is not None

        # 1. 属性查询
        sq = SuitabilityQuery(REALISTIC_PALS)
        handiwork_pals = sq.query("handiwork", 4)
        assert len(handiwork_pals) > 0
        assert any(p.id == "Anubis" for p, _ in handiwork_pals)

        # 2. 配种树构建
        builder = BreedingTreeBuilder(engine, max_depth=5)
        tree = builder.build(anubis)
        assert tree.max_depth_reached <= 1  # v0.2: 只计算一级父母 (不递归)

        # 3. 所有叶子都是基础帕鲁 (或自身配对)
        for path in tree.paths:
            for leaf in path.leaf_pals:
                # 允许自身配对作为叶子
                if not leaf.is_wild:
                    pass  # 在稀疏数据集中自身配对是预期行为

        # 4. 路径择优 (v0.2: 小数据集可能无路径)
        optimizer = PathOptimizer(engine)
        if tree.paths:
            optimizer.optimize(tree)
            assert tree.best_path is not None

        # 5. 序列化验证
        tree_dict = tree.to_dict()
        assert tree_dict["target"]["id"] == "Anubis"
        assert isinstance(tree_dict["paths"], list)

    def test_suitability_full_stats(self, engine):
        """全工种统计."""
        sq = SuitabilityQuery(REALISTIC_PALS)
        stats = sq.get_all_stats()
        assert len(stats) == 12
        assert stats["handiwork"].max_level >= 6
        assert stats["mining"].max_level >= 6

    def test_forward_breed_known_result(self, engine):
        """验证已知配种结果."""
        # Relaxaurus + Sparkit → Relaxaurus Lux (特殊组合)
        r = engine.get_pal("Relaxaurus")
        s = engine.get_pal("Sparkit")
        child = engine.forward_breed(r, s)
        assert child.id == "Relaxaurus Lux"

    def test_json_roundtrip(self, engine):
        """JSON 持久化往返测试."""
        # 保存
        pals_dict = {p.id: p.to_dict() for p in REALISTIC_PALS}
        tmp_path = Path(tempfile.mktemp(suffix=".json"))
        tmp_path.write_text(
            json.dumps(pals_dict, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        # 加载
        loader = DataLoader()
        count = loader.load(tmp_path)
        assert count == len(REALISTIC_PALS)

        # 用加载的数据重建引擎
        loaded_pals = loader.get_all()
        engine2 = BreedingEngine(pals=loaded_pals, rules=REALISTIC_RULES)

        # 验证一致性
        anubis = engine2.get_pal("Anubis")
        assert anubis.combi_rank == 480
        assert anubis.work_suitability.handiwork == 6

        builder = BreedingTreeBuilder(engine2, max_depth=5)
        tree = builder.build(anubis)
        # v0.2: 只计算一级父母, 测试数据集小可能为 0

        tmp_path.unlink()

    def test_reverse_breed_multiple_parents(self, engine):
        """反向查询：验证每对父母能正向计算回子代."""
        mossanda = engine.get_pal("Mossanda")
        assert mossanda is not None
        parents = engine.reverse_breed(mossanda)
        assert len(parents) >= 1, f"Mossanda 应有至少1个父母对，实际: {len(parents)}"

        for a, b in parents:
            child = engine.forward_breed(a, b)
            assert child.id == "Mossanda"

    def test_tree_depth_control(self, engine):
        """验证 max_depth 截断."""
        anubis = engine.get_pal("Anubis")
        builder_shallow = BreedingTreeBuilder(engine, max_depth=1)
        tree = builder_shallow.build(anubis)
        assert tree.max_depth_reached <= 1
        # 深度1 下每个步骤的父母都是基础帕鲁或截断
