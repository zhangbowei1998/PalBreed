"""从 data/tc-imba/ 灌入 22 表全量数据（幂等）— Docker api entrypoint 使用。

流程:
1. 对已有库幂等应用 data/sql/003_tcimba_extend.sql（补表/列，无需 psql）
2. build_bundle 解析 tc-imba json（含旧 pal_data.json 继承 is_wild/aliases）
3. PostgresExtWriter.upsert_ext 写入 22 表

用法: python scripts/seed_tcimba_full.py [data_dir]
依赖环境变量: DATABASE_URL (默认 postgresql://postgres@postgres:5432/pl_agent)
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

# 命名空间包根目录（与 Docker PYTHONPATH 一致）
for p in [
    "/app/packages/core",
    "/app/packages/adapters",
    "/app/packages/api",
    "/app/packages",
]:
    if p not in sys.path:
        sys.path.insert(0, p)

import asyncpg  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DDL_003 = ROOT / "data/sql/003_tcimba_extend.sql"
DDL_004 = ROOT / "data/sql/004_text2sql.sql"


async def _apply_ddl(conn: asyncpg.Connection, path: Path) -> None:
    """幂等执行 003 DDL（拆分语句，跳过注释与事务控制）。"""
    text = path.read_text(encoding="utf-8")
    stmts = []
    for raw in text.split(";"):
        lines = [ln for ln in raw.splitlines() if not ln.strip().startswith("--")]
        s = "\n".join(lines).strip()
        if not s:
            continue
        upper = s.upper()
        if upper in {"BEGIN", "COMMIT", "BEGIN;", "COMMIT;"}:
            continue
        stmts.append(s)
    for s in stmts:
        await conn.execute(s)
    print(f"✅ 应用 DDL: {path.name} ({len(stmts)} 条语句, 幂等)")


async def main() -> None:
    url = os.getenv("DATABASE_URL", "postgresql://postgres@postgres:5432/pl_agent")
    os.environ["DATABASE_URL"] = url

    data_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data/tc-imba"

    # 1. 幂等应用 DDL（对已有库补 22 表 + Text-to-SQL 白名单视图）
    conn = await asyncpg.connect(url)
    try:
        if DDL_003.exists():
            await _apply_ddl(conn, DDL_003)
        else:
            print(f"⚠️ 未找到 {DDL_003}，跳过 DDL")
        if DDL_004.exists():
            await _apply_ddl(conn, DDL_004)
        else:
            print(f"⚠️ 未找到 {DDL_004}，跳过 DDL")
    finally:
        await conn.close()

    # 2. 构建 bundle（继承旧 pal_data.json 缺失字段）
    from adapters.tcimba.adapter import build_bundle, load_old_pal_data  # noqa: E402

    old = load_old_pal_data(ROOT / "data/processed/pal_data.json")
    bundle = build_bundle(data_dir, include_old_pal=old)
    c = bundle.counts()
    print(f"📦 解析完成: {c}")

    # 3. 写入 22 表
    from adapters.postgres.ext_writer import PostgresExtWriter  # noqa: E402

    writer = PostgresExtWriter()
    await writer.connect()
    try:
        stats = await writer.upsert_ext(bundle)
        print(f"✅ 灌入完成: {stats}")
    finally:
        await writer.close()


if __name__ == "__main__":
    asyncio.run(main())
