"""FastAPI application — Palworld breeding agent API."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="幻兽帕鲁配种 Agent",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@asynccontextmanager
async def lifespan(application: FastAPI):
    """启动加载数据 (仅 PostgreSQL)."""
    from .parser import QueryParser
    from .db.queries import OrmQueryService

    orm_service = OrmQueryService.from_env()
    all_pals = await orm_service.load_all_pals()
    application.state.orm_service = orm_service
    print(f"✅ PG: {len(all_pals)} pals")

    # ── 输入解析器 ────────────────────────────────────────
    application.state.parser = QueryParser(all_pals)
    print(f"🚀 API ready: {len(all_pals)} pals")
    yield
    await orm_service.close()


app.router.lifespan_context = lifespan

from .routes.query import router  # noqa: E402
from .routes.sql_query import router as sql_query_router  # noqa: E402

app.include_router(router)
app.include_router(sql_query_router)


@app.get("/health")
async def health(request: Request):
    parser = getattr(request.app.state, "parser", None)
    return {"status": "ok", "pals_loaded": len(parser._all_pals) if parser else 0}
