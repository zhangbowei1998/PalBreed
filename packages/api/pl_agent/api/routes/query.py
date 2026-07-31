"""API routes for query and breeding."""

from fastapi import APIRouter, Request

from .. import QueryRequest
from ..parser import QueryKind, QueryParser

router = APIRouter(prefix="/api")


@router.post("/query")
async def smart_query(request: Request):
    """智能查询入口 — 自动判断输入类型."""
    body = QueryRequest.model_validate(await request.json())
    if not body.input:
        from ..formatter import format_error

        return format_error("INVALID_INPUT", "输入不能为空")

    engine = request.app.state.engine
    builder = request.app.state.builder
    suitability = request.app.state.suitability
    optimizer = request.app.state.optimizer
    parser: QueryParser = request.app.state.parser

    parsed = parser.parse(body.input)

    # ── name query ──────────────────────────────────────────
    if parsed.kind == QueryKind.NAME and parsed.pal:
        tree = builder.build(parsed.pal)
        if tree.paths:
            optimizer.optimize(tree)
        from ..formatter import format_name_query, format_success

        return format_success(format_name_query(parsed.pal, tree))

    # ── suitability query ───────────────────────────────────
    if parsed.kind == QueryKind.SUITABILITY and parsed.work_conditions:
        from ..formatter import (
            format_out_of_range,
            format_success,
            format_suitability_candidates,
        )

        conds = parsed.work_conditions
        if len(conds) == 1:
            wt, lv = conds[0]
            results = suitability.query(wt, lv)

            if not results:
                max_lv = suitability.get_max_level(wt)
                fallback = suitability.query(wt, 0) if max_lv > 0 else []
                return format_success(
                    format_out_of_range(body.input, wt, max_lv, fallback[:10])
                )
            return format_success(
                format_suitability_candidates(body.input, results[:20], wt)
            )
        else:
            results = suitability.query_multi(conds)
            return format_success(
                format_suitability_candidates(
                    body.input,
                    results[:20],
                    ",".join(c[0] for c in conds),
                )
            )

    # ── fuzzy ───────────────────────────────────────────────
    if parsed.kind == QueryKind.FUZZY and parsed.fuzzy_candidates:
        from ..formatter import format_success

        return format_success(
            {
                "type": "fuzzy",
                "query": body.input,
                "candidates": [
                    {"pal": {"id": p.id, "cn_name": p.cn_name, "number": p.number}}
                    for p in parsed.fuzzy_candidates
                ],
                "total": len(parsed.fuzzy_candidates),
            }
        )

    # ── not found ───────────────────────────────────────────
    from ..formatter import format_error

    # try fuzzy as fallback
    candidates = parser._match_fuzzy(body.input)
    if candidates:
        return format_success(
            {
                "type": "fuzzy",
                "query": body.input,
                "candidates": [
                    {"pal": {"id": p.id, "cn_name": p.cn_name, "number": p.number}}
                    for p in candidates
                ],
                "total": len(candidates),
            }
        )

    return format_error(
        "PAL_NOT_FOUND",
        f"未找到帕鲁: '{body.input}'",
        suggestions=[p.cn_name for p in parser._match_fuzzy(body.input)[:5]],
    )


@router.get("/pal/{pal_id}")
async def get_pal(request: Request, pal_id: str):
    engine = request.app.state.engine
    pal = engine.get_pal(pal_id)
    if pal is None:
        from ..formatter import format_error

        return format_error("PAL_NOT_FOUND", f"未找到帕鲁: '{pal_id}'")
    from ..formatter import format_pal_summary, format_success

    return format_success(format_pal_summary(pal))


@router.get("/breeding/tree/{pal_id}")
async def get_breeding_tree(
    request: Request, pal_id: str, all: bool = False, max_depth: int = 5
):
    engine = request.app.state.engine
    builder = request.app.state.builder
    optimizer = request.app.state.optimizer

    pal = engine.get_pal(pal_id)
    if pal is None:
        from ..formatter import format_error

        return format_error("PAL_NOT_FOUND", f"未找到帕鲁: '{pal_id}'")

    from pl_agent.core.breeding_tree import BreedingTreeBuilder

    if max_depth != 5:
        builder = BreedingTreeBuilder(engine, max_depth=max_depth)

    tree = builder.build(pal)
    if tree.paths:
        optimizer.optimize(tree)

    from ..formatter import format_name_query, format_success

    if all:
        return format_success(
            {
                "type": "name_query",
                "pal": format_name_query(pal, tree)["pal"],
                "breeding_tree": {
                    "total_paths": tree.total_paths,
                    "max_depth": tree.max_depth_reached,
                    "paths": [
                        {
                            "total_steps": p.total_steps,
                            "leaf_pals": [
                                {"id": lp.id, "cn_name": lp.cn_name}
                                for lp in p.leaf_pals
                            ],
                            "steps": [
                                {
                                    "parent_a": s.parent_a.cn_name,
                                    "parent_b": s.parent_b.cn_name,
                                    "child": s.child.cn_name,
                                }
                                for s in p.steps
                            ],
                        }
                        for p in tree.paths[:10]
                    ],
                },
            }
        )

    return format_success(format_name_query(pal, tree))


@router.get("/suitability/stats")
async def get_stats(request: Request):
    suitability = request.app.state.suitability
    from ..formatter import format_stats, format_success

    return format_success(format_stats(suitability.get_all_stats()))
