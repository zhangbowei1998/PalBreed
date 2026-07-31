"""FastAPI application — Palworld breeding agent API."""

from contextlib import asynccontextmanager
from pathlib import Path

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
    """启动加载数据 (PG 优先, JSON 降级)."""
    from .parser import QueryParser

    all_pals: list = []
    pg_loader = None

    # ── 1. PostgreSQL ────────────────────────────────────────
    try:
        from adapters.postgres.loader import PostgresLoader

        pg_loader = PostgresLoader()
        index = await pg_loader.load_hot()
        all_pals = index.pals
        application.state.pg_loader = pg_loader
        print(f"✅ PG hot cache: {len(all_pals)} pals")
    except Exception as e:
        print(f"⚠ PG unavailable ({e}), JSON fallback...")
        from pl_agent.core.data_loader import DataLoader

        loader = DataLoader()
        data_path = Path("data/processed/pal_data.json")
        if data_path.exists():
            loader.load(data_path)
            all_pals = loader.get_all()
            print(f"✅ JSON: {len(all_pals)} pals")
        else:
            all_pals = _demo_pals()
            print(f"✅ Demo: {len(all_pals)} pals")

    # ── 2. 输入解析器 ────────────────────────────────────────
    application.state.parser = QueryParser(all_pals)
    print(f"🚀 API ready: {len(all_pals)} pals")
    yield
    if pg_loader:
        await pg_loader.close()


app.router.lifespan_context = lifespan

from .routes.query import router  # noqa: E402

app.include_router(router)


@app.get("/health")
async def health(request: Request):
    parser = getattr(request.app.state, "parser", None)
    return {"status": "ok", "pals_loaded": len(parser._all_pals) if parser else 0}
    return {"status": "ok", "pals_loaded": len(engine.all_pals)}


# ── demo data (PG + JSON 都不可用时的最终兜底) ───────────────────


def _demo_pals() -> list:
    """内置 demo 数据 — 开发/测试用."""
    from pl_agent.core.schema import Element, Pal, WorkSuitability

    return [
        Pal(
            id="melpaca",
            cn_name="棉悠悠",
            en_name="Melpaca",
            number=1,
            combi_rank=1460,
            elements=[Element.NEUTRAL],
            rarity=1,
            is_wild=True,
            work_suitability=WorkSuitability(farming=1),
        ),
        Pal(
            id="pengullet",
            cn_name="企丸丸",
            en_name="Pengullet",
            number=10,
            combi_rank=1350,
            elements=[Element.WATER, Element.ICE],
            rarity=1,
            is_wild=True,
            work_suitability=WorkSuitability(
                watering=1, cooling=1, handiwork=1, transporting=1
            ),
        ),
        Pal(
            id="mossanda_lux",
            cn_name="暴电熊",
            en_name="Mossanda Lux",
            number=32,
            combi_rank=430,
            elements=[Element.ELECTRIC],
            rarity=3,
            is_wild=True,
            work_suitability=WorkSuitability(
                generating_electricity=2, handiwork=2, lumbering=2, transporting=3
            ),
        ),
        Pal(
            id="anubis",
            cn_name="阿努比斯",
            en_name="Anubis",
            number=100,
            combi_rank=570,
            elements=[Element.EARTH],
            rarity=5,
            is_wild=False,
            work_suitability=WorkSuitability(mining=4, handiwork=4, transporting=2),
        ),
        Pal(
            id="celaray",
            cn_name="苍焰狼",
            en_name="Celaray",
            number=14,
            combi_rank=870,
            elements=[Element.FIRE],
            rarity=2,
            is_wild=True,
            work_suitability=WorkSuitability(kindling=1, transporting=1),
        ),
        Pal(
            id="caprity",
            cn_name="草熊猫",
            en_name="Caprity",
            number=7,
            combi_rank=930,
            elements=[Element.GRASS],
            rarity=2,
            is_wild=True,
            work_suitability=WorkSuitability(planting=2, farming=1),
        ),
    ]
