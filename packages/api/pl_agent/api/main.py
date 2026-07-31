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
    """启动加载引擎, 关闭清理."""
    from pl_agent.core.breeding_engine import BreedingEngine
    from pl_agent.core.breeding_tree import BreedingTreeBuilder
    from pl_agent.core.data_loader import DataLoader
    from pl_agent.core.path_optimizer import PathOptimizer
    from pl_agent.core.schema import BreedingRules
    from pl_agent.core.suitability_query import SuitabilityQuery

    from .parser import QueryParser

    loader = DataLoader()
    data_path = Path("data/processed/pal_data.json")

    if data_path.exists():
        loader.load(data_path)
        print(f"Loaded {len(loader)} pals from {data_path}")
    else:
        # fallback: use smoke test demo data
        from pl_agent.core.schema import Element, Pal, WorkSuitability

        _demo_pals = [
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
                    watering=1,
                    cooling=1,
                    handiwork=1,
                    transporting=1,
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
                    generating_electricity=2,
                    handiwork=2,
                    lumbering=2,
                    transporting=3,
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
                work_suitability=WorkSuitability(
                    mining=4,
                    handiwork=4,
                    transporting=2,
                ),
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
                work_suitability=WorkSuitability(
                    kindling=1,
                    transporting=1,
                ),
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
                work_suitability=WorkSuitability(
                    planting=2,
                    farming=1,
                ),
            ),
        ]
        loader._pals = {p.id: p for p in _demo_pals}
        loader._loaded = True
        print(f"pal_data.json not found, using {len(loader)} demo pals")

    rules_path = Path("data/processed/breeding_rules.json")
    if rules_path.exists():
        import json

        rules = BreedingRules.from_dict(json.loads(rules_path.read_text("utf-8")))
    else:
        rules = BreedingRules(
            game_version="v1.0.2",
            last_updated="2026-07-31",
        )

    all_pals = loader.get_all()

    application.state.engine = BreedingEngine(pals=all_pals, rules=rules)
    application.state.builder = BreedingTreeBuilder(
        application.state.engine,
        max_depth=5,
    )
    application.state.suitability = SuitabilityQuery(all_pals)
    application.state.optimizer = PathOptimizer(application.state.engine)
    application.state.parser = QueryParser(all_pals)

    print(
        f"API ready: {len(all_pals)} pals, "
        f"engine={type(application.state.engine).__name__}"
    )
    yield


app.router.lifespan_context = lifespan

from .routes.query import router  # noqa: E402

app.include_router(router)


@app.get("/health")
async def health(request: Request):
    engine = request.app.state.engine
    return {"status": "ok", "pals_loaded": len(engine.all_pals)}
