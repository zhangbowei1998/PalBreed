"""SqlGuard 安全校验纯单元测试 — 无需真实数据库。"""

from __future__ import annotations

import pytest

from pl_agent.api.routes.sql_query import SqlGuard


def _ok(sql: str) -> str:
    ok, code, final = SqlGuard.validate(sql)
    assert ok, f"expected ok, got code={code} for: {sql}"
    assert final is not None
    return final


def _blocked(sql: str) -> str:
    ok, code, _ = SqlGuard.validate(sql)
    assert not ok, f"expected blocked, got ok for: {sql}"
    assert code == "SQL_BLOCKED", f"expected SQL_BLOCKED, got {code}"
    return code


def _syntax(sql: str) -> str:
    ok, code, _ = SqlGuard.validate(sql)
    assert not ok, f"expected syntax error for: {sql}"
    assert code == "SQL_SYNTAX", f"expected SQL_SYNTAX, got {code}"
    return code


# ── 允许 ────────────────────────────────────────────────────


def test_select_allowed():
    final = _ok("SELECT cn_name, combi_rank FROM v_pal_full LIMIT 5")
    assert "LIMIT 5" in final or "limit 5" in final.lower()


def test_select_with_where_order():
    _ok(
        "SELECT cn_name FROM v_pal_full WHERE rarity >= 10 "
        "ORDER BY combi_rank DESC LIMIT 10"
    )


def test_select_all_three_views():
    _ok("SELECT * FROM v_item_drop LIMIT 5")
    _ok("SELECT * FROM v_skill_learn LIMIT 5")


def test_missing_limit_auto_append():
    final = _ok("SELECT cn_name FROM v_pal_full")
    assert "LIMIT 100" in final or "limit 100" in final.lower()


def test_limit_capped_at_200():
    final = _ok("SELECT cn_name FROM v_pal_full LIMIT 9999")
    assert "LIMIT 200" in final or "limit 200" in final.lower()


def test_with_cte_allowed():
    final = _ok(
        "WITH big AS (SELECT cn_name, rarity FROM v_pal_full) "
        "SELECT * FROM big LIMIT 10"
    )
    assert "LIMIT 10" in final or "limit 10" in final.lower()


# ── 拦截：非 SELECT ──────────────────────────────────────────


def test_delete_blocked():
    _blocked("DELETE FROM v_pal_full")


def test_drop_blocked():
    _blocked("DROP TABLE v_pal_full")


def test_update_blocked():
    _blocked("UPDATE v_pal_full SET cn_name='x'")


def test_insert_blocked():
    _blocked("INSERT INTO v_pal_full (cn_name) VALUES ('x')")


def test_alter_blocked():
    _blocked("ALTER TABLE v_pal_full ADD COLUMN x int")


# ── 拦截：多语句 / 非白名单 / OFFSET ─────────────────────────


def test_multi_statement_blocked():
    _blocked("SELECT 1 FROM v_pal_full; DROP TABLE v_pal_full")


def test_non_whitelist_table_blocked():
    _blocked("SELECT * FROM pal")
    _blocked("SELECT * FROM pal_stats")


def test_offset_deep_paging_blocked():
    # offset 900 + limit 100 = 1000 > 500 → 拦截
    _blocked("SELECT cn_name FROM v_pal_full LIMIT 100 OFFSET 900")


def test_offset_within_limit_allowed():
    # offset 300 + limit 100 = 400 ≤ 500 → 允许
    _ok("SELECT cn_name FROM v_pal_full LIMIT 100 OFFSET 300")


# ── 语法错误 ─────────────────────────────────────────────────


def test_syntax_error_returns_syntax_code():
    _syntax("SELEC cn_name FROM v_pal_full")
