# ⚠️ DEPRECATED — 引擎层已移除 (v0.2), 此 demo 依赖已删除的模块
# 如需验证配种功能, 启动 API 后调用 POST /api/query {"input": "阿努比斯"}
"""Quick demo of the breeding engine with built-in test data."""

# from pl_agent.core.schema import Pal, WorkSuitability, BreedingRules, Element
# from pl_agent.core.breeding_engine import BreedingEngine
# from pl_agent.core.breeding_tree import BreedingTreeBuilder
# from pl_agent.core.suitability_query import SuitabilityQuery
# from pl_agent.core.path_optimizer import PathOptimizer
if __name__ == "__main__":
    print(
        "⚠️ 引擎层已移除。请使用 API 测试配种: make serve && python packages/api/pl_agent/api/__tests__/test_api_smoke.py"
    )
    import sys

    sys.exit(1)

pals_demo = [
    Pal(
        id="Lamball",
        number=1,
        cn_name="棉悠悠",
        en_name="Lamball",
        combi_rank=1470,
        elements=[Element.NEUTRAL],
        rarity=1,
        work_suitability=WorkSuitability(handiwork=1, transporting=1, farming=1),
        is_wild=True,
    ),
    Pal(
        id="Cattiva",
        number=2,
        cn_name="捣蛋猫",
        en_name="Cattiva",
        combi_rank=1460,
        elements=[Element.NEUTRAL],
        rarity=1,
        work_suitability=WorkSuitability(handiwork=1, gathering=1, mining=1),
        is_wild=True,
    ),
    Pal(
        id="Chikipi",
        number=3,
        cn_name="鸡",
        en_name="Chikipi",
        combi_rank=1500,
        elements=[Element.NEUTRAL],
        rarity=1,
        work_suitability=WorkSuitability(farming=1),
        is_wild=True,
    ),
    Pal(
        id="Anubis",
        number=139,
        cn_name="阿努比斯",
        en_name="Anubis",
        combi_rank=480,
        elements=[Element.EARTH],
        rarity=10,
        work_suitability=WorkSuitability(handiwork=6, mining=6, transporting=4),
        is_wild=False,
    ),
    Pal(
        id="Fenglope",
        number=83,
        cn_name="烽歌龙",
        en_name="Fenglope",
        combi_rank=560,
        elements=[Element.NEUTRAL],
        rarity=3,
        work_suitability=WorkSuitability(gathering=3, transporting=3),
        is_wild=True,
    ),
    Pal(
        id="Fenglope Lux",
        number=83,
        cn_name="雷隐鹿",
        en_name="Fenglope Lux",
        combi_rank=550,
        elements=[Element.ELECTRIC],
        rarity=3,
        work_suitability=WorkSuitability(gathering=3, transporting=3),
        is_wild=True,
    ),
    Pal(
        id="Vanwyrm",
        number=84,
        cn_name="焰皇",
        en_name="Vanwyrm",
        combi_rank=620,
        elements=[Element.FIRE],
        rarity=5,
        work_suitability=WorkSuitability(kindling=3, transporting=3),
        is_wild=True,
    ),
    Pal(
        id="Foxparks",
        number=5,
        cn_name="火狐",
        en_name="Foxparks",
        combi_rank=1400,
        elements=[Element.FIRE],
        rarity=3,
        work_suitability=WorkSuitability(kindling=1),
        is_wild=True,
    ),
    Pal(
        id="Pengullet",
        number=10,
        cn_name="企丸丸",
        en_name="Pengullet",
        combi_rank=1350,
        elements=[Element.WATER],
        rarity=1,
        work_suitability=WorkSuitability(watering=1, cooling=1),
        is_wild=True,
    ),
]
rules = BreedingRules(
    game_version="v1.0.2",
    last_updated="2026-07-31",
    special_combinations=[],
    self_only=[],
    unbreedable=[],
    breeding_excluded=[],
)
engine = BreedingEngine(pals=pals, rules=rules)

print("=== 正向配种示例 ===")
lamball = engine.get_pal("Lamball")
cattiva = engine.get_pal("Cattiva")
print(
    f"{lamball.cn_name} + {cattiva.cn_name} = {engine.forward_breed(lamball, cattiva).cn_name}"
)

print("\n=== 反向配种示例 ===")
anubis = engine.get_pal("Anubis")
for a, b in engine.reverse_breed(anubis)[:5]:
    print(f"  {a.cn_name} + {b.cn_name}")

print("\n=== 工作适应性查询 ===")
sq = SuitabilityQuery(pals)
for p, lv in sq.query("handiwork", 3):
    print(f"  {p.cn_name} Lv{lv}")

print("\n=== 配种树 ===")
tree = BreedingTreeBuilder(engine, max_depth=5).build(anubis)
PathOptimizer(engine).optimize(tree)
print(f"阿努比斯配种树: {tree.total_paths} 条路径")
if tree.best_path:
    print(
        f"最优路径: {tree.best_path.total_steps} 步, {len(tree.best_path.leaf_pals)} 个基础帕鲁"
    )
    for s in tree.best_path.steps:
        print(f"  {s.parent_a.cn_name} + {s.parent_b.cn_name} = {s.child.cn_name}")
    print(f'基础帕鲁: {", ".join(p.cn_name for p in tree.best_path.leaf_pals)}')
