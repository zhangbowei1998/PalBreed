"""API routes — breeding queries via ORM service."""

from dataclasses import dataclass, field

from fastapi import APIRouter, Request

from .. import QueryRequest
from ..db.queries import OrmQueryService
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


@router.get("/pal/resolve/{name}")
async def resolve_pal_by_name(request: Request, name: str):
    """按中文名/英文名/ID/别名解析帕鲁 profile（含图片），供前端内联展示头像。"""
    parser: QueryParser = request.app.state.parser
    pal = parser._match_exact(name)
    if pal is None:
        from ..formatter import format_error

        return format_error("PAL_NOT_FOUND", f"未找到帕鲁: '{name}'")
    from ..formatter import format_pal_summary, format_success

    return format_success(format_pal_summary(pal))


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
    orm_service: OrmQueryService = request.app.state.orm_service
    stats_rows = await orm_service.get_work_stats()
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


# ── internal helpers ──────────────────────────────────────────


async def _breeding_query(request: Request, pal, show_all: bool = False):
    orm_service: OrmQueryService = request.app.state.orm_service
    pal_dict = _pal_to_dict(pal)
    pairs = []
    unbreedable = False

    # 第 0 步: 查特殊配种规则（独特组合: same_species / fixed_pair）
    rules = await orm_service.get_breeding_rules_by_game_id(pal.id)
    for r in rules:
        if r["rule_type"] == "unbreedable":
            unbreedable = True
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
            continue
        if r["rule_type"] == "fixed_pair":
            if r["parent_a_id"] is None or r["parent_b_id"] is None:
                continue
            pa = await orm_service.get_pal_pair_by_db_id(r["parent_a_id"])
            pb = await orm_service.get_pal_pair_by_db_id(r["parent_b_id"])
            if pa and pb:
                pairs.append(
                    ParentPair(
                        parent_a=pa,
                        parent_b=pb,
                        child=pal_dict,
                        method="fixed_pair",
                    )
                )

    # 第 1 步: CombiRank 公式（不可配种跳过; query_parent_pairs_by_rank
    # 内部已按 breed_child 过滤, breed_child=False 的帕鲁会返回空）
    if not unbreedable:
        rows = await orm_service.query_parent_pairs_by_rank(pal.combi_rank, pal.id)
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

    orm_service: OrmQueryService = request.app.state.orm_service
    cond = conds[0]  # v1: 仅支持单工种
    work_type, min_level = cond

    results = await orm_service.query_suitability(work_type, min_level, limit=50)
    if not results:
        # 超范围: 查最高等级
        top_results = await orm_service.query_suitability(work_type, 1, limit=10)
        max_lv = top_results[0]["level"] if top_results else 0
        return format_out_of_range(raw_input, work_type, max_lv, top_results)
    return format_suitability_candidates(raw_input, work_type, results)


# ── tc-imba 扩展端点 (S6-S10) ─────────────────────────────────


@router.get("/pals/{pal_id}/detail")
async def get_pal_detail(request: Request, pal_id: str):
    """S10: 帕鲁全量详情（属性/技能/被动/掉落/伙伴技能/召唤）。"""
    from ..formatter import format_error, format_success

    orm_service: OrmQueryService = request.app.state.orm_service
    detail = await orm_service.query_pal_detail_full(pal_id)
    if detail is None:
        return format_error("PAL_NOT_FOUND", f"未找到帕鲁: '{pal_id}'")
    return format_success(detail)


@router.get("/pals/{pal_id}/skills")
async def get_pal_skills(request: Request, pal_id: str):
    """S7: 帕鲁可学技能列表（含学习等级）。"""
    from ..formatter import format_error, format_success

    orm_service: OrmQueryService = request.app.state.orm_service
    detail = await orm_service.query_pal_detail_full(pal_id)
    if detail is None:
        return format_error("PAL_NOT_FOUND", f"未找到帕鲁: '{pal_id}'")
    skills = await orm_service.query_pal_skills(pal_id)
    return format_success({"pal_id": pal_id, "skills": skills, "total": len(skills)})


@router.get("/passives")
async def query_passive_pals(request: Request, name: str):
    """S6: 按被动中文名查拥有该被动的帕鲁（配种被动传承）。"""
    from ..formatter import format_success

    orm_service: OrmQueryService = request.app.state.orm_service
    rows = await orm_service.query_pals_by_passive(name)
    return format_success({"passive": name, "pals": rows, "total": len(rows)})


@router.get("/items/{item_name}/recipe")
async def get_item_recipe(request: Request, item_name: str):
    """S9: 物品配方链（产出 + 设施 + 材料）。"""
    from ..formatter import format_error, format_success

    orm_service: OrmQueryService = request.app.state.orm_service
    rows = await orm_service.query_recipe_chain(item_name)
    if not rows:
        return format_error("ITEM_NOT_FOUND", f"未找到物品配方: '{item_name}'")
    return format_success({"item": item_name, "recipe": rows})


@router.get("/items/{item_name}/drops")
async def get_item_drops(request: Request, item_name: str):
    """S8b: 掉落该物品的帕鲁（材料反查）。"""
    from ..formatter import format_error, format_success

    orm_service: OrmQueryService = request.app.state.orm_service
    rows = await orm_service.query_pals_dropping_item(item_name)
    if not rows:
        return format_error("ITEM_NOT_FOUND", f"未找到掉落来源: '{item_name}'")
    return format_success({"item": item_name, "pals": rows, "total": len(rows)})
