"""API routes — breeding queries via PostgreSQL SQL."""

from dataclasses import dataclass, field

from fastapi import APIRouter, Request

from .. import QueryRequest
from ..parser import QueryKind, QueryParser

router = APIRouter(prefix="/api")


# ── lightweight data classes (replacing core.breeding_tree) ──────

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


# ── PostgreSQL SQL ──────────────────────────────────────────────

BREED_PARENTS_SQL = """
SELECT a.cn_name AS pa_cn, a.id AS pa_id, a.combi_rank AS pa_rank, a.is_wild AS pa_wild,
       b.cn_name AS pb_cn, b.id AS pb_id, b.combi_rank AS pb_rank, b.is_wild AS pb_wild
FROM pals a, pals b
WHERE round((a.combi_rank + b.combi_rank) / 2.0) = $1
  AND a.id != $2 AND b.id != $2
  AND a.id <= b.id
ORDER BY a.combi_rank
"""

SUITABILITY_SQL = """
SELECT id, cn_name, number, combi_rank, is_wild, handiwork, kindling, watering,
       planting, generating_electricity, gathering, lumbering, mining,
       cooling, medicine, transporting, farming
FROM pals WHERE {col} >= $1 ORDER BY {col} DESC LIMIT $2
"""

PAL_DETAIL_SQL = "SELECT * FROM pals WHERE id = $1"

WORK_STATS_SQL = """
SELECT 'handiwork' AS wt, max(handiwork) AS mx, avg(handiwork)::numeric(4,1) AS av, count(*) FILTER (WHERE handiwork>0) AS cnt FROM pals
UNION ALL SELECT 'mining', max(mining), avg(mining)::numeric(4,1), count(*) FILTER (WHERE mining>0) FROM pals
UNION ALL SELECT 'kindling', max(kindling), avg(kindling)::numeric(4,1), count(*) FILTER (WHERE kindling>0) FROM pals
UNION ALL SELECT 'watering', max(watering), avg(watering)::numeric(4,1), count(*) FILTER (WHERE watering>0) FROM pals
UNION ALL SELECT 'planting', max(planting), avg(planting)::numeric(4,1), count(*) FILTER (WHERE planting>0) FROM pals
UNION ALL SELECT 'generating_electricity', max(generating_electricity), avg(generating_electricity)::numeric(4,1), count(*) FILTER (WHERE generating_electricity>0) FROM pals
UNION ALL SELECT 'gathering', max(gathering), avg(gathering)::numeric(4,1), count(*) FILTER (WHERE gathering>0) FROM pals
UNION ALL SELECT 'lumbering', max(lumbering), avg(lumbering)::numeric(4,1), count(*) FILTER (WHERE lumbering>0) FROM pals
UNION ALL SELECT 'cooling', max(cooling), avg(cooling)::numeric(4,1), count(*) FILTER (WHERE cooling>0) FROM pals
UNION ALL SELECT 'medicine', max(medicine), avg(medicine)::numeric(4,1), count(*) FILTER (WHERE medicine>0) FROM pals
UNION ALL SELECT 'transporting', max(transporting), avg(transporting)::numeric(4,1), count(*) FILTER (WHERE transporting>0) FROM pals
UNION ALL SELECT 'farming', max(farming), avg(farming)::numeric(4,1), count(*) FILTER (WHERE farming>0) FROM pals
"""

# ── helpers ─────────────────────────────────────────────────────

VALID_WORK_COLS = {
    "handiwork", "kindling", "watering", "planting",
    "generating_electricity", "gathering", "lumbering", "mining",
    "cooling", "medicine", "transporting", "farming",
}


def _pal_row_to_dict(row) -> dict:
    return {
        "id": row["id"], "number": row["number"],
        "cn_name": row["cn_name"], "en_name": row["en_name"],
        "combi_rank": row["combi_rank"], "elements": row["elements"] or [],
        "rarity": row["rarity"], "is_wild": row["is_wild"],
        "work_suitability": {c: row[c] for c in VALID_WORK_COLS},
    }


# ── routes ──────────────────────────────────────────────────────


@router.post("/query")
async def smart_query(request: Request):
    """智能查询入口."""
    body = QueryRequest.model_validate(await request.json())
    if not body.input:
        from ..formatter import format_error
        return format_error("INVALID_INPUT", "输入不能为空")

    parser: QueryParser = request.app.state.parser
    parsed = parser.parse(body.input)

    # ── name query → breeding parents ──────────────────────
    if parsed.kind == QueryKind.NAME and parsed.pal:
        return await _breeding_query(request, parsed.pal)

    # ── suitability query ──────────────────────────────────
    if parsed.kind == QueryKind.SUITABILITY and parsed.work_conditions:
        return await _suitability_query(request, body.input, parsed.work_conditions)

    # ── fuzzy / not found ──────────────────────────────────
    from ..formatter import format_success, format_error
    candidates = parsed.fuzzy_candidates or parser._match_fuzzy(body.input)
    if candidates:
        return format_success({
            "type": "fuzzy", "query": body.input,
            "candidates": [{"pal": {"id": p.id, "cn_name": p.cn_name, "number": p.number}} for p in candidates[:10]],
            "total": len(candidates),
        })
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
        await pg_loader._ensure_pool()
        async with pg_loader._pool.acquire() as conn:
            rows = await conn.fetch(WORK_STATS_SQL)
        stats = {}
        for r in rows:
            stats[r["wt"]] = {"max_level": r["mx"] or 0, "avg_level": float(r["av"] or 0), "count": r["cnt"] or 0}
        from ..formatter import format_success
        return format_success({"total_pals": 0, **stats})  # total_pals from parser

    # fallback: count from parser
    parser: QueryParser = request.app.state.parser
    pals = parser._all_pals
    from ..formatter import format_success
    return format_success({"total_pals": len(pals)})


# ── internal query helpers ──────────────────────────────────────


async def _breeding_query(request: Request, pal, show_all: bool = False):
    pg_loader = getattr(request.app.state, "pg_loader", None)

    # pal summary
    pal_dict = {
        "id": pal.id, "number": pal.number, "cn_name": pal.cn_name,
        "en_name": pal.en_name, "combi_rank": pal.combi_rank,
        "elements": [e.value for e in pal.elements], "rarity": pal.rarity,
        "is_wild": pal.is_wild,
        "work_suitability": pal.work_suitability.to_dict(),
    }

    # breeding parents via PG SQL
    pairs = []
    if pg_loader:
        await pg_loader._ensure_pool()
        async with pg_loader._pool.acquire() as conn:
            rows = await conn.fetch(BREED_PARENTS_SQL, pal.combi_rank, pal.id)
        for r in rows:
            pairs.append(ParentPair(
                parent_a={"cn_name": r["pa_cn"], "id": r["pa_id"], "combi_rank": r["pa_rank"], "is_wild": r["pa_wild"]},
                parent_b={"cn_name": r["pb_cn"], "id": r["pb_id"], "combi_rank": r["pb_rank"], "is_wild": r["pb_wild"]},
                child=pal_dict,
            ))

    result = BreedingResult(pal=pal_dict, parent_pairs=pairs, total=len(pairs))

    # format response
    from ..formatter import format_success
    if show_all:
        return format_success({
            "type": "name_query", "pal": pal_dict,
            "breeding_tree": {
                "total_paths": result.total,
                "max_depth": 1,
                "paths": [{
                    "total_steps": 1,
                    "leaf_pals": [p.parent_a, p.parent_b],
                    "steps": [{
                        "parent_a": p.parent_a["cn_name"],
                        "parent_b": p.parent_b["cn_name"],
                        "child": pal_dict["cn_name"],
                    }],
                } for p in pairs[:50]],
            },
        })
    return format_success({
        "type": "name_query", "pal": pal_dict,
        "breeding_tree": {
            "total_paths": result.total,
            "max_depth": 1,
            "best_path": {
                "total_steps": 1,
                "leaf_pals": [pairs[0].parent_a, pairs[0].parent_b] if pairs else [],
                "steps": [{
                    "parent_a": pairs[0].parent_a["cn_name"],
                    "parent_b": pairs[0].parent_b["cn_name"],
                    "child": pal_dict["cn_name"],
                }] if pairs else [],
                "display_text": f"🌿 野外捕获: {pairs[0].parent_a['cn_name']}, {pairs[0].parent_b['cn_name']}\n🥚 配种: {pairs[0].parent_a['cn_name']}+{pairs[0].parent_b['cn_name']} = 🎯 {pal_dict['cn_name']}" if pairs else "",
            } if pairs else None,
        },
    })


async def _suitability_query(request: Request, raw_input: str, conds: list[tuple[str, int]]):
    from ..formatter import format_success, format_suitability_candidates, format_out_of_range

    pg_loader = getattr(request.app.state, "pg_loader", None)
    wt, lv = conds[0]

    if pg_loader and wt in VALID_WORK_COLS:
        await pg_loader._ensure_pool()
        sql = SUITABILITY_SQL.format(col=wt)
        async with pg_loader._pool.acquire() as conn:
            rows = await conn.fetch(sql, lv, 20)
        if rows:
            candidates = []
            for r in rows:
                pd = _pal_row_to_dict(r)
                candidates.append({
                    "pal": pd, "matched_level": r[wt],
                    "all_suitabilities": pd["work_suitability"],
                })
            return format_success(format_suitability_candidates(raw_input, [], wt) if False else {
                "type": "suitability_query", "query": raw_input,
                "result_type": "candidates", "candidates": candidates,
                "total": len(candidates),
            })
        else:
            max_sql = f"SELECT max({wt}) FROM pals"
            async with pg_loader._pool.acquire() as conn:
                mx_row = await conn.fetchrow(max_sql)
            max_lv = mx_row[0] or 0
            if max_lv > 0:
                fallback_sql = SUITABILITY_SQL.format(col=wt)
                async with pg_loader._pool.acquire() as conn:
                    fb_rows = await conn.fetch(fallback_sql, 0, 10)
                fb = [{"pal": _pal_row_to_dict(r), "matched_level": r[wt]} for r in fb_rows]
                return format_success(format_out_of_range(raw_input, wt, max_lv, []))  # simplified

    # fallback: use parser's in-memory pals
    parser: QueryParser = request.app.state.parser
    pals = parser._all_pals
    results = [(p, getattr(p.work_suitability, wt, 0)) for p in pals if getattr(p.work_suitability, wt, 0) >= lv]
    results.sort(key=lambda x: x[1], reverse=True)
    if results:
        from ..formatter import format_success
        candidates = [{"pal": {"id": p.id, "cn_name": p.cn_name, "number": p.number, "is_wild": p.is_wild, "combi_rank": p.combi_rank, "work_suitability": p.work_suitability.to_dict()}, "matched_level": lv} for p, lv in results[:20]]
        return format_success({"type": "suitability_query", "query": raw_input, "result_type": "candidates", "candidates": candidates, "total": len(candidates)})
    max_lv = max((getattr(p.work_suitability, wt, 0) for p in pals), default=0)
    return format_success(format_out_of_range(raw_input, wt, max_lv, []))
