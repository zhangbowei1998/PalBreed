"""从 tc-imba (palworld.tc-imba.com, 游戏文件提取) 生成系统 pal_data.json。

数据源:
- pals.json        完整帕鲁属性 (elements/rarity/work 等)
- breeding.json    配种数据 (rank/breedChild/独特组合)
- locales/zh-CN/pals.json  中文名
- locales/en-US/pals.json  英文名

用法: python scripts/convert_tcimba.py [input_dir] [output_path]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# ---- 字段映射 ----
WORK_MAP = {
    "Handcraft": "handiwork",
    "EmitFlame": "kindling",
    "Watering": "watering",
    "Seeding": "planting",
    "GenerateElectricity": "generating_electricity",
    "Collection": "gathering",
    "Deforest": "lumbering",
    "Mining": "mining",
    "Cool": "cooling",
    "ProductMedicine": "medicine",
    "Transport": "transporting",
    "MonsterFarm": "farming",
}

ELEMENT_MAP = {
    "Normal": "Neutral",
    "Fire": "Fire",
    "Water": "Water",
    "Electricity": "Electric",
    "Leaf": "Grass",
    "Ice": "Ice",
    "Dark": "Dark",
    "Dragon": "Dragon",
    "Earth": "Earth",
    "None": "Neutral",
}


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def convert(input_dir: Path, output_path: Path, old_path: Path | None = None) -> dict:
    pals_attr = {p["id"]: p for p in load_json(input_dir / "pals.json")["pals"]}
    breeding = load_json(input_dir / "breeding.json")
    br_rank = {p["id"]: p for p in breeding["pals"]}
    zh = load_json(input_dir / "pals_zh.json")
    en = load_json(input_dir / "pals_en.json")

    # 旧数据（保留 is_wild / number / aliases 等未提供的字段）
    old = {}
    if old_path and old_path.exists():
        old = load_json(old_path)

    out = {}
    for pid in sorted(br_rank.keys()):
        attr = pals_attr.get(pid, {})
        br = br_rank[pid]
        old_pal = old.get(pid, {})

        elements = [ELEMENT_MAP.get(e, e) for e in attr.get("elements", [])]
        work_raw = attr.get("work", {})
        work = {
            WORK_MAP[k]: v
            for k, v in work_raw.items()
            if k in WORK_MAP and v
        }

        number = br.get("zukanIndex", old_pal.get("number", 0))
        # 变种 B 后缀避免 number 冲突：如 121B -> 121（与本体同号时用 suffix 区分）
        # 简单策略：number = zukanIndex（若与已分配冲突且唯一性要求，可由后续逻辑处理）

        icon = br.get("icon", "")
        image_url = (
            f"https://resource-palworld.tc-imba.com/icons/{icon}.webp"
            if icon
            else old_pal.get("image_url")
        )

        out[pid] = {
            "id": pid,
            "number": number,
            "cn_name": zh.get(pid, {}).get("name", pid),
            "en_name": en.get(pid, {}).get("name", pid),
            "combi_rank": br["rank"],
            "elements": elements,
            "rarity": attr.get("rarity", old_pal.get("rarity", 1)),
            "work_suitability": work,
            "is_wild": old_pal.get("is_wild", True),
            "breed_child": br.get("breedChild", True),
            "aliases": old_pal.get("aliases", []),
            "image_url": image_url,
            "wiki_url": f"https://palworld.tc-imba.com/pals/{pid}",
            "spawn_locations": old_pal.get("spawn_locations", []),
            "data_source": "tc-imba",
        }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return out


def main() -> None:
    base = Path(__file__).resolve().parent.parent
    input_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/tmp/tc_data")
    output = (
        Path(sys.argv[2]) if len(sys.argv) > 2 else base / "data/processed/pal_data.json"
    )
    old = base / "data/processed/pal_data.json"
    pals = convert(input_dir, output, old if old.exists() and old != output else None)
    print(f"✅ 生成 {len(pals)} 只帕鲁 -> {output}")


if __name__ == "__main__":
    main()
