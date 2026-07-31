"""Debug: why 墨罗娜 shows 0 breeding paths."""

import sys

sys.path.insert(0, "packages/core")
sys.path.insert(0, "packages/adapters")
sys.path.insert(0, "packages/api")
sys.path.insert(0, "packages")

from pl_agent.core.data_loader import DataLoader
from pl_agent.core.breeding_engine import BreedingEngine
from pl_agent.core.breeding_tree import BreedingTreeBuilder
from pl_agent.core.schema import BreedingRules

loader = DataLoader()
loader.load("data/processed/pal_data.json")
all_pals = loader.get_all()
rules = BreedingRules(game_version="v1.0", last_updated="2026-07-31")
engine = BreedingEngine(pals=all_pals, rules=rules)

mono = engine.get_pal("MonochromeQueen")
print(f"墨罗娜: rank={mono.combi_rank}, wild={mono.is_wild}")

# reverse breed
parents = engine.reverse_breed(mono)
print(f"reverse_breed → {len(parents)} pairs")
for a, b in parents[:3]:
    print(
        f"  {a.cn_name}({a.combi_rank}) + {b.cn_name}({b.combi_rank}) = child at {round((a.combi_rank+b.combi_rank)/2)}"
    )

# forward verify
kabuki = engine.get_pal("KabukiMan")
deer = engine.get_pal("WhiteDeer_Dark")
if kabuki and deer:
    child = engine.forward_breed(kabuki, deer)
    print(
        f"forward: {kabuki.cn_name}({kabuki.combi_rank}) + {deer.cn_name}({deer.combi_rank}) = {child.cn_name}({child.combi_rank})"
    )

# tree
builder = BreedingTreeBuilder(engine, max_depth=5)
tree = builder.build(mono)
print(f"Tree: {tree.total_paths} paths")
for p in tree.paths[:3]:
    for s in p.steps:
        print(f"  {s.parent_a.cn_name} + {s.parent_b.cn_name} = {s.child.cn_name}")
