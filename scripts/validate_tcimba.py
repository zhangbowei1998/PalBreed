"""校验 tc-imba 数据完整性，输出报告。

用法: python scripts/validate_tcimba.py [data_dir]
默认: data/tc-imba/

检查项:
1. 各文件存在性 + 条目数
2. 唯一性 (breeding/pals/passives/items id + 中文名)
3. 引用完整性 (activeSkills/drops/bossDrops/summonMaterials/combos)
4. 数组字段确认 (passives.invoke / items.recipe.craftedAt)
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

EXPECTED = {
    "pals": 299,
    "breeding_pals": 299,
    "combos": 250,
    "passives": 115,  # passives.json 可获取被动（zh_passives 152 含装备被动）
    "items": 2433,
}


def load(base: Path, name: str):
    p = base / name
    if not p.exists():
        raise FileNotFoundError(f"缺失文件: {name}")
    return json.loads(p.read_text(encoding="utf-8"))


def main() -> int:
    base = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/tc-imba")
    issues: list[str] = []
    checks: list[str] = []

    def check(desc: str, cond: bool, detail: str = "") -> None:
        mark = "✅" if cond else "❌"
        checks.append(f"{mark} {desc}" + (f" {detail}" if detail else ""))
        if not cond:
            issues.append(desc)

    # ---- 1. 文件 + 条目数 ----
    pals = load(base, "pals.json")["pals"]
    breeding = load(base, "breeding.json")
    passives = load(base, "passives.json")["passives"]
    items = load(base, "items.json")["items"]
    zh = load(base, "pals_zh.json")
    en = load(base, "pals_en.json")
    try:
        zh_passives = load(base, "zh_passives.json")
    except FileNotFoundError:
        zh_passives = {}
    try:
        zh_skills = load(base, "zh_skills.json")
    except FileNotFoundError:
        zh_skills = {}
    try:
        zh_items = load(base, "zh_items.json")
    except FileNotFoundError:
        zh_items = {}

    check(f"pals 条目数 = {EXPECTED['pals']}", len(pals) == EXPECTED["pals"], f"(实际 {len(pals)})")
    check(
        f"breeding pals 条目数 = {EXPECTED['breeding_pals']}",
        len(breeding["pals"]) == EXPECTED["breeding_pals"],
        f"(实际 {len(breeding['pals'])})",
    )
    check(
        f"combos 条目数 = {EXPECTED['combos']}",
        len(breeding["combos"]) == EXPECTED["combos"],
        f"(实际 {len(breeding['combos'])})",
    )
    check(
        f"passives 条目数 = {EXPECTED['passives']}",
        len(passives) == EXPECTED["passives"],
        f"(实际 {len(passives)})",
    )
    check(
        f"items 条目数 = {EXPECTED['items']}",
        len(items) == EXPECTED["items"],
        f"(实际 {len(items)})",
    )
    check("zh pals 覆盖", len(zh) == len(pals), f"({len(zh)}/{len(pals)})")
    check("en pals 覆盖", len(en) == len(pals), f"({len(en)}/{len(pals)})")
    ps_ids = [p["id"] for p in passives]  # 提前定义，供 zh 覆盖检查使用
    if zh_passives:
        # 方向: passives 每个 id 都应能在 zh 中找到中文名
        miss_pas = set(ps_ids) - set(zh_passives.keys())
        check("passives 均有中文名", not miss_pas, f"(缺失 {sorted(miss_pas)[:10]})")
    check("zh_items 覆盖", len(zh_items) == len(items), f"({len(zh_items)}/{len(items)})")

    # ---- 2. 唯一性 ----
    br_ids = [p["id"] for p in breeding["pals"]]
    p_ids = [p["id"] for p in pals]
    it_ids = [i["id"] for i in items]
    check("breeding pals id 唯一", len(set(br_ids)) == len(br_ids))
    check("pals id 唯一", len(set(p_ids)) == len(p_ids))
    check("passives id 唯一", len(set(ps_ids)) == len(ps_ids))
    check("items id 唯一", len(set(it_ids)) == len(it_ids))
    check("breeding 与 pals id 集合一致", set(br_ids) == set(p_ids))

    names = [v.get("name") for v in zh.values()]
    dup = {k: v for k, v in Counter(names).items() if v > 1}
    check("中文名无重复", len(dup) == 0, f"(重复 {dup})")

    # ---- 3. 引用完整性 ----
    waza_ids = {s["wazaId"] for p in pals for s in p.get("activeSkills", [])}
    passive_ids = set(ps_ids)
    item_ids = set(it_ids)

    missing_skill = [
        s["wazaId"] for p in pals for s in p.get("activeSkills", [])
        if s.get("effect") and s["effect"].get("type") not in zh_skills and s["wazaId"] not in zh_skills
    ]
    # 中文名缺失检查（zh_skills 存在时）
    if zh_skills:
        miss_skill_name = sorted(waza_ids - set(zh_skills.keys()))
        check("所有技能有中文名", not miss_skill_name, f"(缺失 {len(miss_skill_name)})")
    if zh_passives:
        miss_pas_name = sorted(passive_ids - set(zh_passives.keys()))
        check("所有被动有中文名", not miss_pas_name, f"(缺失 {len(miss_pas_name)})")
    if zh_items:
        miss_item_name = sorted(item_ids - set(zh_items.keys()))
        check("所有物品有中文名", not miss_item_name, f"(缺失 {len(miss_item_name)})")

    # 帕鲁固有被动是否在 passives.json 中
    pal_passives = {ps for p in pals for ps in p.get("passives", [])}
    check("帕鲁固有被动均在 passives 中", pal_passives <= passive_ids,
          f"(未知 {sorted(pal_passives - passive_ids)[:10]})")

    # 掉落物品引用（大小写归一化: 掉落可能用小写 'poppy', items 用 'Poppy'）
    item_lower = {i.lower(): i for i in item_ids}
    drop_items = {d["item"] for p in pals for d in p.get("drops", []) + p.get("bossDrops", [])}
    miss_drop = sorted(di for di in drop_items if di.lower() not in item_lower)
    check("掉落物品均在 items 中（忽略大小写）", not miss_drop, f"(未知 {miss_drop[:10]})")

    # 召唤材料引用
    summon_items = {m["item"] for p in pals for m in p.get("summonMaterials", [])}
    check("召唤材料均在 items 中", summon_items <= item_ids,
          f"(未知 {sorted(summon_items - item_ids)[:10]})")

    # combos 引用
    combo_ids = {c["a"] for c in breeding["combos"]} | {c["b"] for c in breeding["combos"]} | {c["c"] for c in breeding["combos"]}
    check("combos 均在 breeding pals 中", combo_ids <= set(br_ids),
          f"(未知 {sorted(combo_ids - set(br_ids))[:10]})")

    # ---- 4. 数组字段确认 ----
    inv_types = {type(p.get("invoke")).__name__ for p in passives}
    check("passives.invoke 均为 list", inv_types == {"list"}, f"(类型 {inv_types})")
    craft_types = {type(i["recipe"]["craftedAt"]).__name__ for i in items if "recipe" in i and "craftedAt" in i["recipe"]}
    check("items.craftedAt 均为 list", craft_types == {"list"}, f"(类型 {craft_types})")

    # ---- 报告 ----
    print("\n===== tc-imba 数据校验报告 =====")
    for c in checks:
        print(" ", c)
    print(f"\n结果: {'✅ 全部通过' if not issues else f'❌ {len(issues)} 项问题'}")
    return 0 if not issues else 1


if __name__ == "__main__":
    sys.exit(main())
