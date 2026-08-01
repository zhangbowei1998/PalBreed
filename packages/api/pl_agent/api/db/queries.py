"""Centralized ORM query service for API routes."""

from __future__ import annotations

from sqlalchemy import and_, func, select, true
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import aliased, selectinload

from pl_agent.core.schema import Element, Pal, WorkSuitability

from .models import (
    BreedingRuleModel,
    PalModel,
    WorkSuitabilityModel,
)
from .session import create_engine_and_sessionmaker


class OrmQueryService:
    """Encapsulates all database queries used by API runtime."""

    def __init__(
        self,
        engine: AsyncEngine,
        session_factory: async_sessionmaker[AsyncSession],
    ):
        self._engine = engine
        self._session_factory = session_factory

    @classmethod
    def from_env(cls) -> "OrmQueryService":
        engine, session_factory = create_engine_and_sessionmaker()
        return cls(engine, session_factory)

    async def close(self) -> None:
        await self._engine.dispose()

    async def load_all_pals(self) -> list[Pal]:
        """Load all pals with related element/alias/work rows."""
        async with self._session_factory() as session:
            stmt = (
                select(PalModel)
                .options(
                    selectinload(PalModel.elements),
                    selectinload(PalModel.aliases),
                    selectinload(PalModel.work_suitabilities),
                )
                .order_by(PalModel.combi_rank)
            )
            rows = await session.scalars(stmt)
            models = rows.all()
        return [self._model_to_pal(m) for m in models]

    async def query_suitability(
        self, work_type: str, min_level: int, limit: int = 20
    ) -> list[dict]:
        async with self._session_factory() as session:
            stmt = (
                select(
                    PalModel.game_id.label("id"),
                    PalModel.cn_name,
                    PalModel.zukan_index,
                    PalModel.combi_rank,
                    PalModel.is_wild,
                    WorkSuitabilityModel.level,
                )
                .join(WorkSuitabilityModel, WorkSuitabilityModel.pal_id == PalModel.id)
                .where(
                    and_(
                        WorkSuitabilityModel.work_type == work_type,
                        WorkSuitabilityModel.level >= min_level,
                    )
                )
                .order_by(WorkSuitabilityModel.level.desc())
                .limit(limit)
            )
            rows = await session.execute(stmt)
            items = rows.mappings().all()

        return [
            {
                "id": r["id"],
                "cn_name": r["cn_name"],
                "number": r["zukan_index"],
                "combi_rank": r["combi_rank"],
                "is_wild": r["is_wild"],
                "level": r["level"],
            }
            for r in items
        ]

    async def get_work_stats(self) -> list[dict]:
        async with self._session_factory() as session:
            stmt = (
                select(
                    WorkSuitabilityModel.work_type,
                    func.max(WorkSuitabilityModel.level).label("max_level"),
                    func.round(func.avg(WorkSuitabilityModel.level), 1).label(
                        "avg_level"
                    ),
                    func.count()
                    .filter(WorkSuitabilityModel.level > 0)
                    .label("pal_count"),
                )
                .group_by(WorkSuitabilityModel.work_type)
                .order_by(func.max(WorkSuitabilityModel.level).desc())
            )
            rows = await session.execute(stmt)
            items = rows.mappings().all()

        return [
            {
                "work_type": r["work_type"],
                "max_level": r["max_level"] or 0,
                "avg_level": float(r["avg_level"] or 0),
                "pal_count": r["pal_count"] or 0,
            }
            for r in items
        ]

    async def get_breeding_rules_by_game_id(self, game_id: str) -> list[dict]:
        async with self._session_factory() as session:
            child_id_subquery = (
                select(PalModel.id).where(PalModel.game_id == game_id).scalar_subquery()
            )
            stmt = select(
                BreedingRuleModel.rule_type,
                BreedingRuleModel.parent_a_id,
                BreedingRuleModel.parent_b_id,
                BreedingRuleModel.description,
            ).where(BreedingRuleModel.child_id == child_id_subquery)
            rows = await session.execute(stmt)
            return [dict(r) for r in rows.mappings().all()]

    async def get_pal_pair_by_db_id(self, pal_db_id: int) -> dict | None:
        async with self._session_factory() as session:
            stmt = select(
                PalModel.cn_name,
                PalModel.game_id.label("id"),
                PalModel.combi_rank,
                PalModel.is_wild,
            ).where(PalModel.id == pal_db_id)
            row = await session.execute(stmt)
            hit = row.mappings().first()
        return dict(hit) if hit else None

    async def query_parent_pairs_by_rank(
        self, combi_rank: int, child_game_id: str
    ) -> list[dict]:
        pa = aliased(PalModel)
        pb = aliased(PalModel)

        async with self._session_factory() as session:
            stmt = (
                select(
                    pa.cn_name.label("pa_cn"),
                    pa.game_id.label("pa_id"),
                    pa.combi_rank.label("pa_rank"),
                    pa.is_wild.label("pa_wild"),
                    pb.cn_name.label("pb_cn"),
                    pb.game_id.label("pb_id"),
                    pb.combi_rank.label("pb_rank"),
                    pb.is_wild.label("pb_wild"),
                )
                .select_from(pa)
                .join(pb, true())
                .where(
                    and_(
                        func.round((pa.combi_rank + pb.combi_rank) / 2.0) == combi_rank,
                        pa.game_id != child_game_id,
                        pb.game_id != child_game_id,
                        pa.id <= pb.id,
                    )
                )
                .order_by(pa.combi_rank)
            )
            rows = await session.execute(stmt)
            return [dict(r) for r in rows.mappings().all()]

    @staticmethod
    def _model_to_pal(model: PalModel) -> Pal:
        elements: list[Element] = []
        for item in model.elements:
            try:
                elements.append(Element(item.element_type))
            except ValueError:
                elements.append(Element.NEUTRAL)

        ws = WorkSuitability.from_dict(
            {item.work_type: int(item.level) for item in model.work_suitabilities}
        )

        return Pal(
            id=model.game_id,
            number=model.zukan_index,
            cn_name=model.cn_name,
            en_name=model.en_name,
            combi_rank=model.combi_rank,
            elements=elements,
            rarity=model.rarity,
            work_suitability=ws,
            is_wild=model.is_wild,
            aliases=[a.alias for a in model.aliases if a.alias],
            image_url=model.image_url,
            wiki_url=model.wiki_url,
        )
