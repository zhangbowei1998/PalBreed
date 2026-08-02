"""从 tc-imba breeding.json 导入独特组合到 breeding_rule 表。

规则映射:
- a == b == c  → same_species (只能同种配)
- a != b       → fixed_pair (固定配方)

用法: python scripts/seed_breeding_rules.py [breeding.json]
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

for p in [
    "/app/packages/core",
    "/app/packages/adapters",
    "/app/packages/api",
    "/app/packages",
]:
    if p not in sys.path:
        sys.path.insert(0, p)

from pl_agent.core.schema import BreedingRuleRow  # noqa: E402


def load_combos(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("combos", [])


async def main() -> None:
    url = os.getenv("DATABASE_URL", "postgresql://postgres@postgres:5432/pl_agent")
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/app/data/tc_breeding.json")
    combos = load_combos(src)
    print(f"📦 加载 {len(combos)} 条独特组合")

    # 连接 DB
    import asyncpg  # noqa: E402

    conn = await asyncpg.connect(url)
    try:
        # game_id -> pal.id 映射
        rows = await conn.fetch("SELECT id, game_id FROM pal")
        id_by_game = {r["game_id"]: r["id"] for r in rows}
        missing = set()

        inserted = 0
        for c in combos:
            a, b, child = c["a"], c["b"], c["c"]
            aid, bid, cid = id_by_game.get(a), id_by_game.get(b), id_by_game.get(child)
            if not (aid and bid and cid):
                missing.update(x for x in (a, b, child) if x not in id_by_game)
                continue
            if a == b and b == child:
                rule_type = "same_species"
            else:
                rule_type = "fixed_pair"
            await conn.execute(
                "INSERT INTO breeding_rule (child_id, parent_a_id, parent_b_id, rule_type, description) "
                "VALUES ($1, $2, $3, $4, $5) "
                "ON CONFLICT (child_id, parent_a_id, parent_b_id) DO UPDATE SET "
                "rule_type = EXCLUDED.rule_type, description = EXCLUDED.description",
                cid, aid, bid, rule_type,
                "同种配对" if rule_type == "same_species" else "固定配方",
            )
            inserted += 1

        print(f"✅ 写入 {inserted} 条 breeding_rule")
        if missing:
            print(f"⚠️ 未匹配的帕鲁: {sorted(missing)[:20]}")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
