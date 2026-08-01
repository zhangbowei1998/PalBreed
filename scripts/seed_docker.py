"""Seed PostgreSQL from processed JSON — used by Docker init.

用法: 在 api 容器启动前运行, 从 data/processed/pal_data.json 灌入 288 只帕鲁.
依赖环境变量: DATABASE_URL (默认 postgresql://postgres@postgres:5432/pl_agent)
"""

from __future__ import annotations

import asyncio
import os
import sys

# 命名空间包根目录（与 Docker PYTHONPATH 一致）
for p in [
    "/app/packages/core",
    "/app/packages/adapters",
    "/app/packages/api",
    "/app/packages",
]:
    if p not in sys.path:
        sys.path.insert(0, p)

from pl_agent.core.data_loader import DataLoader  # noqa: E402


async def main() -> None:
    # 数据库连接配置
    url = os.getenv("DATABASE_URL", "postgresql://postgres@postgres:5432/pl_agent")
    os.environ["DATABASE_URL"] = url

    # 从 JSON 加载帕鲁
    loader = DataLoader("/app/data/processed")
    count = loader.load()
    pals = loader.get_all()
    print(f"📦 从 pal_data.json 加载 {count} 只帕鲁")

    # 灌入 PostgreSQL
    from adapters.postgres.adapter import PostgresWriter  # noqa: E402

    writer = PostgresWriter()
    await writer.connect()
    try:
        written = await writer.upsert_all(pals)
        total = await writer.count()
        print(f"✅ 灌入 {written} 只帕鲁, 当前总数 {total}")
    finally:
        await writer.close()


if __name__ == "__main__":
    asyncio.run(main())
