"""API routes — breeding queries via normalized PostgreSQL."""

from dataclasses import dataclass, field

from fastapi import APIRouter, Request

from .. import QueryRequest
from ..parser import QueryKind, QueryParser

router = APIRouter(prefix="/api")


# ── lightweight data classes ──────────────────────────────────


@dataclass
class ParentPair:
    parent_a: dict
    parent_b: dict
    child: dict
    method: str = "breed"


@dataclass
class BreedingResult:
    pal: dict
    parent_pairs: list[ParentPair] = field(default_factory=list)
    total: int = 0


# ── PostgreSQL SQL (normalized tables) ────────────────────────

BREED_PARENTS_SQL = """
SELECT a.cn_name AS pa_cn, a.game_id AS pa_id, a.combi_rank AS pa_rank, a.is_wild AS pa_wild,
       b.cn_name AS pb_cn, b.game_id AS pb_id, b.combi_rank AS pb_rank, b.is_wild AS pb_wild
FROM pal a, pal b
WHERE round((a.combi_rank + b.combi_rank) / 2.0) = $1
  AND a.game_id != $2 AND b.game_id != $2
  AND a.id <= b.id
ORDER BY a.combi_rank
"""

SUITABILITY_SQL = """
SELECT p.game_id AS id, p.cn_name, p.zukan_index, p.combi_rank, p.is_wild, ws.level
FROM work_suitability ws
JOIN pal p ON ws.pal_id = p.id
WHERE ws.work_type = $1 AND ws.level >= $2
ORDER BY ws.level DESC
LIMIT $3
"""

WORK_STATS_SQL = """
SELECT work_type,
       MAX(level)            AS max_level,
       ROUND(AVG(level), 1)  AS avg_level,
       COUNT(*) FILTER (WHERE level > 0) AS pal_count
FROM work_suitability
GROUP BY work_type
ORDER BY max_level DESC
"""

BREEDING_RULE_SQL = """
SELECT br.rule_type, br.parent_a_id, br.parent_b_id, br.description
FROM breeding_rule br
JOIN pal p ON br.child_id = p.id
WHERE p.game_id = $1
"""

# ── helpers ───────────────────────────────────────────────────


def _pal_to_dict(pal) -> dict:
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


# ── routes ────────────────────────────────────────────────────


@router.post("/query")
async def smart_query(request: Request):
    """智能查询入口."""
    body = QueryRequest.model_validate(await request.json())
    if not body.input:
        from ..formatter import format_error

        return format_error("INVALID_INPUT", "输入不能为空")

    parser: QueryParser = request.app.state.parser
    parsed = parser.parse(body.input)

    if parsed.kind == QueryKind.NAME and parsed.pal:
        return await _breeding_query(request, parsed.pal)

    if parsed.kind == QueryKind.SUITABILITY and parsed.work_conditions:
        return await _suitability_query(request, body.input, parsed.work_conditions)

    from ..formatter import format_success, format_error

    candidates = parsed.fuzzy_candidates or parser._match_fuzzy(body.input)
    if candidates:
        return format_success(
            {
                "type": "fuzzy",
                "query": body.input,
                "candidates": [
                    {"pal": {"id": p.id, "cn_name": p.cn_name, "number": p.number}}
                    for p in candidates[:10]
                ],
                "total": len(candidates),
            }
        )
    return format_error("PAL_NOT_FOUND", f"未找到帕鲁: '{body.input}'")


@router.get("/pal/{pal_id}")
async def get_pal(request: Request, pal_id: str):
    parser: QueryParser = request.app.state.parser
    pal = parser._match_exact(pal_id)
    if pal is None:
        from ..formatter import format_error

        return format_error("PAL_NOT_FOUND", f"未找到帕鲁: '{pal_id}'")
    from ..formatter import format_pal_summary, format_success

    return format_success(format_pal_summary(pal))


@router.get("/breeding/tree/{pal_id}")
async def get_breeding_tree(request: Request, pal_id: str, all: bool = False):
    parser: QueryParser = request.app.state.parser
    pal = parser._match_exact(pal_id)
    if pal is None:
        from ..formatter import format_error

        return format_error("PAL_NOT_FOUND", f"未找到帕鲁: '{pal_id}'")
    return await _breeding_query(request, pal, show_all=all)


@router.get("/suitability/stats")
async def get_stats(request: Request):
    pg_loader = getattr(request.app.state, "pg_loader", None)
    if pg_loader:
        stats_rows = await pg_loader.get_work_stats()
        stats = {
            r["work_type"]: {
                "max_level": r["max_level"],
                "avg_level": r["avg_level"],
                "count": r["pal_count"],
            }
            for r in stats_rows
        }
        parser: QueryParser = request.app.state.parser
        from ..formatter import format_success

        return format_success({"total_pals": len(parser._all_pals), **stats})

    parser: QueryParser = request.app.state.parser
    from ..formatter import format_success

    return format_success({"total_pals": len(parser._all_pals)})


# ── internal helpers ──────────────────────────────────────────


async def _breeding_query(request: Request, pal, show_all: bool = False):
    pg_loader = getattr(request.app.state, "pg_loader", None)
    pal_dict = _pal_to_dict(pal)
    pairs = []

    if pg_loader:
        await pg_loader._ensure_pool()
        async with pg_loader._pool.acquire() as conn:
            # 第 0 步: 查特殊配种规则
            rules = await conn.fetch(BREEDING_RULE_SQL, pal.id)
            for r in rules:
                if r["rule_type"] == "unbreedable":
                    pairs = []
                    break
                if r["rule_type"] == "same_species":
                    pairs.append(
                        ParentPair(
                            parent_a={"cn_name": pal.cn_name, "id": pal.id},
                            parent_b={"cn_name": pal.cn_name, "id": pal.id},
                            child=pal_dict,
                            method="same_species",
                        )
                    )
                    break
                if r["rule_type"] == "fixed_pair":
                    pa = await conn.fetchrow(
                        "SELECT cn_name, game_id AS id, combi_rank, is_wild FROM pal WHERE id = $1",
                        r["parent_a_id"],
                    )
                    pb = await conn.fetchrow(
                        "SELECT cn_name, game_id AS id, combi_rank, is_wild FROM pal WHERE id = $1",
                        r["parent_b_id"],
                    )
                    if pa and pb:
                        pairs.append(
                            ParentPair(
                                parent_a=dict(pa),
                                parent_b=dict(pb),
                                child=pal_dict,
                                method="fixed_pair",
                            )
                        )
                    break

            # 第 1 步: CombiRank 公式 (仅当无特殊规则命中时)
            if not rules or all(
                r["rule_type"] not in ("unbreedable", "same_species", "fixed_pair")
                for r in rules
            ):
                rows = await conn.fetch(BREED_PARENTS_SQL, pal.combi_rank, pal.id)
                for r in rows:
                    pairs.append(
                        ParentPair(
                            parent_a={
                                "cn_name": r["pa_cn"],
                                "id": r["pa_id"],
                                "combi_rank": r["pa_rank"],
                                "is_wild": r["pa_wild"],
                            },
                            parent_b={
                                "cn_name": r["pb_cn"],
                                "id": r["pb_id"],
                                "combi_rank": r["pb_rank"],
                                "is_wild": r["pb_wild"],
                            },
                            child=pal_dict,
                        )
                    )

    result = BreedingResult(pal=pal_dict, parent_pairs=pairs, total=len(pairs))
    from ..formatter import format_success

    return format_success(
        {
            "type": "name_query",
            "pal": pal_dict,
            "parent_pairs": [
                {
                    "parent_a": p.parent_a["cn_name"],
                    "parent_b": p.parent_b["cn_name"],
                    "method": p.method,
                }
                for p in pairs
            ],
            "total_pairs": result.total,
        }
    )


async def _suitability_query(
    request: Request, raw_input: str, conds: list[tuple[str, int]]
):
    """属性查询 — 参数化 SQL, 无动态列名插值."""
    from ..formatter import (
        format_success,
        format_suitability_candidates,
        format_out_of_range,
    )

    pg_loader = getattr(request.app.state, "pg_loader", None)
    cond = conds[0]  # v1: 仅支持单工种
    work_type, min_level = cond

    if pg_loader:
        results = await pg_loader.query_suitability(work_type, min_level, limit=50)
        if not results:
            # 超范围: 查最高等级
            top_results = await pg_loader.query_suitability(work_type, 1, limit=10)
            max_lv = top_results[0]["level"] if top_results else 0
            return format_out_of_range(raw_input, work_type, max_lv, top_results)
        return format_suitability_candidates(raw_input, work_type, results)

    # JSON 降级: Python 遍历
    parser: QueryParser = request.app.state.parser
    pals = parser._all_pals
    matched = []
    for p in pals:
        lv = getattr(p.work_suitability, work_type, 0)
        if lv >= min_level:
            matched.append((p, lv))
    matched.sort(key=lambda x: (-x[1], x[0].combi_rank))
    results = [
        {
            "id": p.id,
            "cn_name": p.cn_name,
            "number": p.number,
            "combi_rank": p.combi_rank,
            "is_wild": p.is_wild,
            "level": lv,
        }
        for p, lv in matched[:50]
    ]
    if not results:
        all_lv = sorted(
            [(p, getattr(p.work_suitability, work_type, 0)) for p in pals],
            key=lambda x: -x[1],
        )[:10]
        max_lv = all_lv[0][1] if all_lv else 0
        top_results = [
            {
                "id": p.id,
                "cn_name": p.cn_name,
                "number": p.number,
                "combi_rank": p.combi_rank,
                "level": lv,
            }
            for p, lv in all_lv
        ]
        return format_out_of_range(raw_input, work_type, max_lv, top_results)
    return format_suitability_candidates(raw_input, work_type, results)
