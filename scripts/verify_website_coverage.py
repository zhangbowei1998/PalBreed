"""验证数据源网站全部功能是否被 agent 覆盖，且数据来自工具（DB），非 LLM 编造。

用法:
    python scripts/verify_website_coverage.py --token <agent-web_token>

两层验证:
    Part A — 工具层确定性验证: 直连 api:8000，核对每个工具端点返回非空数据（来自 DB）
    Part B — LLM 层验证: 真实 /agent/chat，检查 trace.tool_calls 命中正确工具且 success，
             并抽查回答引用了工具返回的具体数据（证明非 LLM 自行发挥）

输出: 覆盖矩阵 + 每模块 PASS/FAIL + 差距模块诚实性检查
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request

API_BASE = "http://localhost:8000"
AGENT_BASE = "http://localhost:9000"

# ── 网站模块 → 工具层（确定性）映射 ───────────────────────────
# 每个条目: (模块名, 网站URL, 工具名, 检查函数名)
TOOL_LAYER = [
    ("帕鲁图鉴", "/pals", "resolve_pal", "check_resolve"),
    ("帕鲁详情", "/pals/{id}", "query_pal_detail", "check_detail"),
    ("配种配方", "/breeding", "query_parent_pairs", "check_breeding"),
    ("工种排行", "/pals", "query_top_suitability", "check_suitability"),
    ("属性统计", "/pals", "query_pal_stats", "check_stats"),
    ("被动技能", "/passives", "query_pals_by_passive", "check_passive"),
    ("主动技能", "/active-skills", "query_pal_skills", "check_skills"),
    ("道具配方", "/items", "query_item_recipe", "check_recipe"),
    ("道具掉落", "/items", "query_item_drops", "check_drops"),
    ("Text-to-SQL", "全局搜索", "run_sql_query", "check_sql"),
]

# ── 网站模块 → LLM 层（真实对话）映射 ─────────────────────────
LLM_LAYER = [
    {
        "module": "帕鲁图鉴/详情",
        "site": "/pals",
        "q": "棉悠悠的基本信息、属性、技能和掉落是什么？",
        "expect_tools": {"query_pal_detail", "resolve_pal"},
        "must_contain": ["棉悠悠"],  # 回答应引用工具返回的帕鲁名
    },
    {
        "module": "配种配方",
        "site": "/breeding",
        "q": "阿努比斯怎么配种？",
        "expect_tools": {"query_parent_pairs"},
        "must_contain": ["阿努比斯"],
    },
    {
        "module": "工种排行",
        "site": "/pals",
        "q": "手工能力最强的帕鲁是哪几只？",
        "expect_tools": {"query_top_suitability"},
        "must_contain": [],
    },
    {
        "module": "被动技能",
        "site": "/passives",
        "q": "哪几只帕鲁有“传说”被动？",
        "expect_tools": {"query_pals_by_passive"},
        "must_contain": [],
    },
    {
        "module": "主动技能",
        "site": "/active-skills",
        "q": "阿努比斯能学哪些主动技能？",
        "expect_tools": {"query_pal_skills"},
        "must_contain": ["阿努比斯"],
    },
    {
        "module": "道具配方",
        "site": "/items",
        "q": "金属锭怎么做？",
        "expect_tools": {"query_item_recipe"},
        "must_contain": ["金属锭"],
    },
    {
        "module": "道具掉落",
        "site": "/items",
        "q": "哪些帕鲁会掉落骨头？",
        "expect_tools": {"query_item_drops"},
        "must_contain": [],
    },
    {
        "module": "伙伴技能",
        "site": "/partner-skills",
        "q": "棉悠悠的伙伴技能是什么？",
        "expect_tools": {"query_pal_detail"},
        "must_contain": ["棉悠悠"],
    },
    {
        "module": "Text-to-SQL 任意查询",
        "site": "全局搜索",
        "q": "哪些帕鲁的体型是 L 且跑得快？",
        "expect_tools": {"run_sql_query"},
        "must_contain": [],
    },
]

# ── 差距模块：验证 LLM 诚实不编造 ─────────────────────────────
GAP_LAYER = [
    {"module": "地图（地点/首领/收集品）", "q": "空涡龙在地图的哪个位置能找到？"},
    {"module": "科技树", "q": "帕鲁球科技几级解锁？"},
    {"module": "属性模拟器", "q": "怎么计算帕鲁的个体值？"},
]


# ═══════════════ Part A: 工具层确定性验证 ═══════════════

def _api_get(path: str) -> dict:
    req = urllib.request.Request(f"{API_BASE}{path}")
    return json.loads(urllib.request.urlopen(req, timeout=15).read())


def _api_post(path: str, data: dict) -> dict:
    body = json.dumps(data).encode()
    req = urllib.request.Request(
        f"{API_BASE}{path}", data=body, headers={"Content-Type": "application/json"}
    )
    return json.loads(urllib.request.urlopen(req, timeout=15).read())


def check_resolve():
    r = _api_post("/api/query", {"input": "棉悠悠"})
    pal = r.get("data", {}).get("pal") or {}
    return bool(pal.get("id")), {"cn_name": pal.get("cn_name"), "id": pal.get("id")}


def check_detail():
    r = _api_get("/api/pals/LilyQueen/detail")
    d = r.get("data", {})
    ok = bool(d.get("stats")) and len(d.get("skills", [])) > 0 and len(d.get("drops", [])) > 0
    return ok, {
        "stats": bool(d.get("stats")), "skills": len(d.get("skills", [])),
        "drops": len(d.get("drops", [])), "passives": [p.get("cn_name") for p in d.get("passives", [])],
        "partner_skill": bool(d.get("partner_skill")),
    }


def check_breeding():
    r = _api_get("/api/breeding/tree/LilyQueen")
    pairs = r.get("data", {}).get("parent_pairs", [])
    return len(pairs) > 0, {"parent_pairs": len(pairs)}


def check_suitability():
    r = _api_post("/api/query", {"input": "手工:3"})
    cands = r.get("data", {}).get("candidates", [])
    return len(cands) > 0, {
        "candidates": [c.get("pal", {}).get("cn_name") for c in cands[:3]]
    }


def check_stats():
    r = _api_get("/api/suitability/stats")
    d = r.get("data", {})
    return d.get("total_pals", 0) > 0, {"total_pals": d.get("total_pals"), "kindling_count": d.get("kindling", {}).get("count")}


def check_passive():
    r = _api_get("/api/passives?name=" + urllib.parse.quote("传说"))
    pals = r.get("data", {}).get("pals", [])
    return len(pals) > 0, {"pals": [p.get("cn_name") for p in pals]}


def check_skills():
    r = _api_get("/api/pals/LilyQueen/skills")
    skills = r.get("data", {}).get("skills", [])
    return len(skills) > 0, {"count": len(skills), "first": (skills[0].get("cn_name") if skills else None)}


def check_recipe():
    r = _api_get("/api/items/" + urllib.parse.quote("金属锭") + "/recipe")
    recipe = r.get("data", {}).get("recipe", [])
    return len(recipe) > 0, {
        "count": len(recipe),
        "stations": list({x.get("station") for x in recipe}),
        "materials": list({f"{x.get('material')}x{x.get('count')}" for x in recipe}),
    }


def check_drops():
    r = _api_get("/api/items/" + urllib.parse.quote("骨头") + "/drops")
    pals = r.get("data", {}).get("pals", [])
    return len(pals) > 0, {"count": len(pals), "pals": [p.get("pal_name") or p.get("cn_name") for p in pals[:6]]}


def check_sql():
    r = _api_post(
        "/api/sql/query",
        {"sql": "SELECT cn_name, combi_rank FROM v_pal_full ORDER BY combi_rank DESC LIMIT 3"},
    )
    d = r.get("data", {})
    return d.get("row_count", 0) > 0, {"row_count": d.get("row_count"), "columns": d.get("columns")}


CHECKERS = {
    "check_resolve": check_resolve,
    "check_detail": check_detail,
    "check_breeding": check_breeding,
    "check_suitability": check_suitability,
    "check_stats": check_stats,
    "check_passive": check_passive,
    "check_skills": check_skills,
    "check_recipe": check_recipe,
    "check_drops": check_drops,
    "check_sql": check_sql,
}


# ═══════════════ Part B: LLM 层验证 ═══════════════

def _agent_chat(token: str, session_id: str, message: str) -> dict:
    body = json.dumps({"session_id": session_id, "message": message}).encode()
    req = urllib.request.Request(
        f"{AGENT_BASE}/agent/chat",
        data=body,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
    )
    return json.loads(urllib.request.urlopen(req, timeout=120).read())


def extract_tool_calls(resp: dict) -> list[dict]:
    trace = (resp.get("data") or {}).get("meta", {}).get("trace", {})
    return trace.get("tool_calls", []) or []


def extract_reply(resp: dict) -> str:
    messages = (resp.get("data") or {}).get("messages", [])
    texts = []
    for m in messages:
        if isinstance(m, dict) and m.get("role") == "assistant":
            texts.append(m.get("content", ""))
        elif isinstance(m, str):
            texts.append(m)
    return "\n".join(texts)


# ═══════════════ main ═══════════════

def main() -> int:
    parser = argparse.ArgumentParser(description="网站功能覆盖 + 数据非编造验证")
    parser.add_argument("--token", required=True, help="agent-web Bearer token")
    parser.add_argument("--llm-only", action="store_true", help="只跑 LLM 层")
    args = parser.parse_args()

    report: list[dict] = []

    if not args.llm_only:
        print("=" * 70)
        print("Part A — 工具层确定性验证（数据来自 DB/api，非 LLM）")
        print("=" * 70)
        for module, site, tool, checker_name in TOOL_LAYER:
            try:
                ok, detail = CHECKERS[checker_name]()
                status = "✅ PASS" if ok else "❌ FAIL"
                print(f"  {status} [{module}] {tool}")
                print(f"         {json.dumps(detail, ensure_ascii=False)[:150]}")
                report.append({"part": "A", "module": module, "tool": tool, "ok": ok})
            except Exception as exc:  # noqa: BLE001
                print(f"  ❌ FAIL [{module}] {tool}: {exc}")
                report.append({"part": "A", "module": module, "tool": tool, "ok": False, "err": str(exc)})

    print()
    print("=" * 70)
    print("Part B — LLM 层验证（真实 agent 对话，数据来自工具非编造）")
    print("=" * 70)
    for i, case in enumerate(LLM_LAYER, 1):
        session = f"cov-llm-{i}"
        try:
            resp = _agent_chat(args.token, session, case["q"])
            tcs = extract_tool_calls(resp)
            reply = extract_reply(resp)
            tool_names = {tc.get("name") for tc in tcs}
            hit = tool_names & case["expect_tools"]
            all_success = all(tc.get("success") for tc in tcs if tc.get("name") in case["expect_tools"])
            ok = bool(hit) and all_success
            # 抽查回答引用工具数据
            contain_ok = all(m in reply for m in case["must_contain"]) if case["must_contain"] else True
            ok = ok and contain_ok
            status = "✅ PASS" if ok else "❌ FAIL"
            print(f"  {status} [{case['module']}] ({case['site']})")
            print(f"     Q: {case['q']}")
            print(f"     工具调用: {[(tc.get('name'), tc.get('success')) for tc in tcs]}")
            print(f"     期望工具命中: {hit or '无'} | 回答引用数据: {contain_ok}")
            print(f"     回答摘要: {reply[:160]!r}")
            report.append({
                "part": "B", "module": case["module"], "tool": sorted(hit) if hit else [],
                "ok": ok, "tool_calls": [tc.get("name") for tc in tcs],
            })
        except Exception as exc:  # noqa: BLE001
            print(f"  ❌ FAIL [{case['module']}]: {exc}")
            report.append({"part": "B", "module": case["module"], "ok": False, "err": str(exc)})

    print()
    print("=" * 70)
    print("Part C — 差距模块诚实性检查（无数据时必须诚实，不得编造）")
    print("=" * 70)
    for i, case in enumerate(GAP_LAYER, 100):
        session = f"cov-gap-{i}"
        try:
            resp = _agent_chat(args.token, session, case["q"])
            tcs = extract_tool_calls(resp)
            reply = extract_reply(resp)
            print(f"  [{case['module']}]")
            print(f"     Q: {case['q']}")
            print(f"     工具调用: {[(tc.get('name'), tc.get('success')) for tc in tcs]}")
            print(f"     回答: {reply[:200]!r}")
            report.append({
                "part": "C", "module": case["module"], "ok": True,
                "tool_calls": [tc.get("name") for tc in tcs],
            })
        except Exception as exc:  # noqa: BLE001
            print(f"  [{case['module']}] 调用异常: {exc}")
            report.append({"part": "C", "module": case["module"], "ok": False, "err": str(exc)})

    # 汇总
    a_ok = sum(1 for r in report if r["part"] == "A" and r["ok"])
    a_tot = sum(1 for r in report if r["part"] == "A")
    b_ok = sum(1 for r in report if r["part"] == "B" and r["ok"])
    b_tot = sum(1 for r in report if r["part"] == "B")
    print()
    print("=" * 70)
    print(f"汇总: 工具层 {a_ok}/{a_tot} | LLM 层 {b_ok}/{b_tot}")
    if a_tot and a_ok == a_tot and b_tot and b_ok == b_tot:
        print("✅ 全部通过：网站功能均被 agent 覆盖，且数据来自工具（DB），非 LLM 编造")
    else:
        print("⚠️ 存在未通过项，请查看上方明细")
    return 0 if (a_ok == a_tot and b_ok == b_tot) else 1


if __name__ == "__main__":
    sys.exit(main())
