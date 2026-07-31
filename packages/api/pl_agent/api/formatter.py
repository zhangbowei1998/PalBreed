"""Response formatter — results → JSON API responses."""

from __future__ import annotations

from pl_agent.core.schema import Pal

# ── Chinese work type labels ──────────────────────────────────

_WORK_TYPE_CN = {
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


def format_success(data: dict) -> dict:
    return {"success": True, "data": data}


def format_error(code: str, message: str) -> dict:
    return {"success": False, "error": {"code": code, "message": message}}


def format_suitability_candidates(
    query: str,
    work_type: str,
    results: list[dict],
) -> dict:
    """候选列表 — results 来自 loader.query_suitability() 或 Python 遍历."""
    candidates = [
        {
            "pal": {"id": r["id"], "cn_name": r["cn_name"], "number": r["number"]},
            "matched_level": r["level"],
        }
        for r in results
    ]
    return format_success(
        {
            "type": "suitability_query",
            "query": query,
            "result_type": "candidates",
            "candidates": candidates,
            "total": len(candidates),
            "hint": "请选择一个帕鲁名，再次查询获取配种方案",
        }
    )


def format_out_of_range(
    query: str,
    work_type: str,
    max_level: int,
    fallback: list[dict],
) -> dict:
    cn = _WORK_TYPE_CN.get(work_type, work_type)
    fallback_candidates = [
        {
            "pal": {"id": r["id"], "cn_name": r["cn_name"], "number": r["number"]},
            "matched_level": r["level"],
        }
        for r in fallback
    ]
    return format_success(
        {
            "type": "suitability_query",
            "query": query,
            "result_type": "out_of_range",
            "max_available": max_level,
            "candidates": [],
            "message": f"{cn}最高等级为 Lv{max_level}，已为您展示所有{cn}帕鲁",
            "fallback_candidates": fallback_candidates,
            "total": len(fallback_candidates),
        }
    )
