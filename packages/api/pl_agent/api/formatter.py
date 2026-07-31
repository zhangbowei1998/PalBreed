"""Response formatter — engine results → JSON API responses."""

from __future__ import annotations

from pl_agent.core.breeding_tree import BreedingPath, BreedingTree
from pl_agent.core.schema import Pal, WorkType
from pl_agent.core.suitability_query import LevelStats


def format_pal_summary(pal: Pal) -> dict:
    return {
        "id": pal.id,
        "number": pal.number,
        "cn_name": pal.cn_name,
        "en_name": pal.en_name,
        "combi_rank": pal.combi_rank,
        "elements": [e.value for e in pal.elements],
        "rarity": pal.rarity,
        "is_wild": pal.is_wild,
        "work_suitability": pal.work_suitability.to_dict(),
    }


def format_name_query(pal: Pal, tree: BreedingTree) -> dict:
    best = tree.best_path
    return {
        "type": "name_query",
        "pal": format_pal_summary(pal),
        "breeding_tree": {
            "total_paths": tree.total_paths,
            "max_depth": tree.max_depth_reached,
            "best_path": _format_path(tree.best_path, pal) if best else None,
            "alternative_paths": max(0, tree.total_paths - 1),
            "all_paths_url": f"/api/breeding/tree/{pal.id}?all=true",
        },
    }


def format_suitability_candidates(
    query: str,
    results: list[tuple[Pal, int]],
    work_type: str,
) -> dict:
    candidates = [
        {
            "pal": format_pal_summary(p),
            "matched_level": lv,
            "all_suitabilities": p.work_suitability.to_dict(),
        }
        for p, lv in results
    ]
    return {
        "type": "suitability_query",
        "query": query,
        "result_type": "candidates",
        "candidates": candidates,
        "total": len(candidates),
        "hint": "请选择一个帕鲁名，再次查询获取配种方案",
    }


def format_out_of_range(
    query: str,
    work_type: str,
    max_level: int,
    fallback: list[tuple[Pal, int]],
) -> dict:
    fallback_candidates = [
        {"pal": format_pal_summary(p), "matched_level": lv} for p, lv in fallback
    ]
    cn_names = {
        "handiwork": "手工",
        "kindling": "生火",
        "watering": "浇水",
        "planting": "播种",
        "generating_electricity": "发电",
        "gathering": "采集",
        "lumbering": "伐木",
        "mining": "采矿",
        "cooling": "冷却",
        "medicine": "制药",
        "transporting": "搬运",
        "farming": "牧场",
    }
    cn = cn_names.get(work_type, work_type)
    return {
        "type": "suitability_query",
        "query": query,
        "result_type": "out_of_range",
        "max_available": max_level,
        "candidates": [],
        "message": f"{cn}最高等级为 Lv{max_level}，已为您展示所有{cn}帕鲁",
        "fallback_candidates": fallback_candidates,
        "total": len(fallback_candidates),
    }


def format_stats(stats: dict[str, LevelStats]) -> dict:
    return {
        wt: {"max_level": s.max_level, "avg_level": s.avg_level, "count": s.count}
        for wt, s in stats.items()
    }


def format_error(code: str, message: str, **extra) -> dict:
    return {
        "success": False,
        "data": None,
        "error": {"code": code, "message": message, **extra},
    }


def format_success(data: dict) -> dict:
    return {"success": True, "data": data, "error": None}


def generate_display_text(path: BreedingPath, target: Pal) -> str:
    """将配种路径转为可读文本."""
    lines: list[str] = []

    # 1. 叶子帕鲁
    if path.leaf_pals:
        leaves = "、".join(p.cn_name for p in path.leaf_pals)
        lines.append(f"🌿 野外捕获: {leaves}")

    # 2. 配种步骤 (BFS 顺序, 从叶子到根)
    for step in path.steps:
        lines.append(
            f"🥚 {step.parent_a.cn_name} + {step.parent_b.cn_name} = {step.child.cn_name}"
        )

    # 3. 目标
    lines.append(f"🎯 {target.cn_name}")

    return "\n".join(lines)


# ── internal helpers ──────────────────────────────────────────────


def _format_path(path: BreedingPath | None, target: Pal) -> dict | None:
    if path is None:
        return None
    return {
        "total_steps": path.total_steps,
        "leaf_pals": [format_pal_summary(p) for p in path.leaf_pals],
        "steps": [
            {
                "parent_a": format_pal_summary(s.parent_a),
                "parent_b": format_pal_summary(s.parent_b),
                "child": format_pal_summary(s.child),
                "method": s.method,
            }
            for s in path.steps
        ],
        "display_text": generate_display_text(path, target),
    }
