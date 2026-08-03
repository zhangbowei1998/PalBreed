"""Centralized ORM query service for API routes."""

from __future__ import annotations

from sqlalchemy import and_, func, select, text, true
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import aliased, selectinload

from pl_agent.core.schema import Element, Pal, WorkSuitability

from .models import (
    BreedingRuleModel,
    ItemModel,
    ItemRecipeMaterialModel,
    ItemRecipeModel,
    ItemRecipeStationModel,
    ItemSourceModel,
    PalDropModel,
    PalEnemyScalingModel,
    PalFriendshipModel,
    PalModel,
    PalPartnerSkillModel,
    PalPassiveModel,
    PalSkillModel,
    PalStatsModel,
    PalSummonModel,
    PassiveEffectModel,
    PassiveInvokeModel,
    PassiveModel,
    SkillModel,
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

    async def execute_raw_sql(self, sql: str) -> dict:
        """执行一条只读 SQL（Text-to-SQL 兜底用），返回 {columns, rows, row_count}。

        调用方（路由安全层）已校验：单条 SELECT、白名单视图、强制 LIMIT。
        """
        async with self._session_factory() as session:
            result = await session.execute(text(sql))
            columns = list(result.keys())
            rows = [list(r) for r in result.all()]
            return {"columns": columns, "rows": rows, "row_count": len(rows)}

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
        """按 Palworld 配种规则查询子代的可选父母组合（反向）。

        规则: avg = (A.rank + B.rank) / 2, 子代 = rank 最接近 avg 的
        breed_child=True 帕鲁（不可配种子代不会作为结果产出, 并列取 rank 较小者）。

        因此子代 C 的独占 rank 区间为:
            prev_r + C.rank < A.rank + B.rank <= C.rank + next_r
        其中 prev_r / next_r 为 C 在 breed_child=True 帕鲁排序中的相邻 rank。
        """
        pa = aliased(PalModel)
        pb = aliased(PalModel)

        async with self._session_factory() as session:
            # 1. 子代是否可配种（breed_child=False 仅能通过独特组合获得）
            child_ok = await session.execute(
                select(PalModel.breed_child).where(
                    PalModel.game_id == child_game_id
                )
            )
            if child_ok.scalar() is False:
                return []

            # 2. 所有可配种帕鲁的 rank（升序）→ 计算 C 的独占区间
            rank_rows = await session.execute(
                select(PalModel.combi_rank)
                .where(PalModel.breed_child.is_(True))
                .order_by(PalModel.combi_rank)
            )
            breedable = [r[0] for r in rank_rows.all()]
            if combi_rank not in breedable:
                return []
            idx = breedable.index(combi_rank)
            prev_r = breedable[idx - 1] if idx > 0 else None
            next_r = breedable[idx + 1] if idx + 1 < len(breedable) else None
            sum_min = prev_r + combi_rank + 1 if prev_r is not None else None
            sum_max = combi_rank + next_r if next_r is not None else None

            # 3. 查询父母对: A+B ∈ [sum_min, sum_max]
            conds = [
                pa.game_id != child_game_id,
                pb.game_id != child_game_id,
                pa.id <= pb.id,
            ]
            if sum_min is not None:
                conds.append(pa.combi_rank + pb.combi_rank >= sum_min)
            if sum_max is not None:
                conds.append(pa.combi_rank + pb.combi_rank <= sum_max)

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
                .where(and_(*conds))
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

    # =========================================================================
    # S6-S10: tc-imba 扩展查询
    # =========================================================================

    async def query_pals_by_passive(self, cn_name: str) -> list[dict]:
        """S6: 按被动中文名查帕鲁（配种被动传承）。"""
        async with self._session_factory() as session:
            stmt = (
                select(
                    PalModel.game_id.label("id"),
                    PalModel.cn_name,
                    PalModel.combi_rank,
                    PalModel.is_wild,
                    PassiveModel.passive_id,
                    PassiveModel.cn_name.label("passive_cn"),
                    PassiveModel.rank.label("passive_rank"),
                )
                .join(PalPassiveModel, PalPassiveModel.pal_id == PalModel.id)
                .join(PassiveModel, PassiveModel.id == PalPassiveModel.passive_id)
                .where(PassiveModel.cn_name == cn_name)
                .order_by(PassiveModel.rank.desc())
            )
            rows = await session.execute(stmt)
            return [dict(r) for r in rows.mappings().all()]

    async def query_pal_skills(self, game_id: str) -> list[dict]:
        """S7: 帕鲁可学技能（含学习等级）。"""
        async with self._session_factory() as session:
            pal_id = (
                select(PalModel.id).where(PalModel.game_id == game_id).scalar_subquery()
            )
            stmt = (
                select(
                    SkillModel.waza_id,
                    SkillModel.cn_name,
                    SkillModel.element,
                    SkillModel.category,
                    SkillModel.power,
                    SkillModel.cool_time,
                    PalSkillModel.learn_level,
                )
                .join(PalSkillModel, PalSkillModel.skill_id == SkillModel.id)
                .where(PalSkillModel.pal_id == pal_id)
                .order_by(PalSkillModel.learn_level)
            )
            rows = await session.execute(stmt)
            return [dict(r) for r in rows.mappings().all()]

    async def query_pal_drops(self, game_id: str) -> list[dict]:
        """S8a: 帕鲁的掉落物（普通 + Boss）。"""
        async with self._session_factory() as session:
            pal_id = (
                select(PalModel.id).where(PalModel.game_id == game_id).scalar_subquery()
            )
            stmt = (
                select(
                    ItemModel.item_id,
                    ItemModel.cn_name,
                    PalDropModel.rate,
                    PalDropModel.min,
                    PalDropModel.max,
                    PalDropModel.min_level,
                    PalDropModel.is_boss,
                )
                .join(PalDropModel, PalDropModel.item_id == ItemModel.id)
                .where(PalDropModel.pal_id == pal_id)
                .order_by(PalDropModel.rate.desc())
            )
            rows = await session.execute(stmt)
            return [dict(r) for r in rows.mappings().all()]

    async def query_pals_dropping_item(self, item_name: str) -> list[dict]:
        """S8b: 掉落某物品的帕鲁（材料反查）。

        物品名匹配策略：先精确匹配 cn_name；无结果时回退到模糊匹配
        （cn_name 包含输入），仍无结果返回空列表。
        """
        async with self._session_factory() as session:
            item_id = await self._resolve_item_id(session, item_name)
            if item_id is None:
                return []
            stmt = (
                select(
                    PalModel.game_id.label("pal_id"),
                    PalModel.cn_name.label("pal_cn"),
                    PalDropModel.rate,
                    PalDropModel.min,
                    PalDropModel.max,
                    PalDropModel.is_boss,
                )
                .join(PalDropModel, PalDropModel.pal_id == PalModel.id)
                .where(PalDropModel.item_id == item_id)
                .order_by(PalDropModel.rate.desc())
            )
            rows = await session.execute(stmt)
            return [dict(r) for r in rows.mappings().all()]

    async def query_recipe_chain(self, item_name: str) -> list[dict]:
        """S9: 物品配方链（产出 + 设施 + 材料）。

        物品名匹配策略：先精确匹配 cn_name；无结果时回退到模糊匹配。
        """
        async with self._session_factory() as session:
            item_id = await self._resolve_item_id(session, item_name)
            if item_id is None:
                return []
            material_item = aliased(ItemModel)
            stmt = (
                select(
                    ItemModel.item_id,
                    ItemModel.cn_name.label("product"),
                    ItemRecipeModel.work,
                    ItemRecipeModel.product_count,
                    ItemRecipeStationModel.station,
                    material_item.cn_name.label("material"),
                    ItemRecipeMaterialModel.count,
                )
                .join(ItemRecipeModel, ItemRecipeModel.item_id == ItemModel.id)
                .where(ItemModel.id == item_id)
                .outerjoin(
                    ItemRecipeStationModel,
                    ItemRecipeStationModel.recipe_id == ItemRecipeModel.id,
                )
                .outerjoin(
                    ItemRecipeMaterialModel,
                    ItemRecipeMaterialModel.recipe_id == ItemRecipeModel.id,
                )
                .outerjoin(
                    material_item,
                    ItemRecipeMaterialModel.material_item_id == material_item.id,
                )
            )
            rows = await session.execute(stmt)
            return [dict(r) for r in rows.mappings().all()]

    async def _resolve_item_id(self, session, item_name: str) -> int | None:
        """解析物品名 → item.id（精确优先，模糊回退）。

        精确匹配 cn_name；无结果时用 cn_name LIKE '%kw%' 模糊匹配（取第一条）。
        """
        from sqlalchemy import or_

        kw = item_name.strip()
        if not kw:
            return None
        exact = (
            await session.execute(
                select(ItemModel.id).where(ItemModel.cn_name == kw).limit(1)
            )
        ).scalars().first()
        if exact is not None:
            return exact
        fuzzy = (
            await session.execute(
                select(ItemModel.id)
                .where(ItemModel.cn_name.like(f"%{kw}%"))
                .order_by(ItemModel.sort_id)
                .limit(1)
            )
        ).scalars().first()
        return fuzzy

    async def query_pal_detail_full(self, game_id: str) -> dict | None:
        """S10: 帕鲁全量详情聚合。"""
        async with self._session_factory() as session:
            pal = (
                await session.execute(
                    select(PalModel).where(PalModel.game_id == game_id)
                )
            ).scalars().first()
            if pal is None:
                return None
            result: dict = {
                "id": pal.game_id,
                "cn_name": pal.cn_name,
                "en_name": pal.en_name,
                "number": pal.zukan_index,
                "combi_rank": pal.combi_rank,
                "rarity": pal.rarity,
                "is_wild": pal.is_wild,
                "breed_child": pal.breed_child,
                "genus": pal.genus,
                "size": pal.size,
                "egg": pal.egg,
                "nocturnal": pal.nocturnal,
                "reaction": pal.reaction,
                "best_work": pal.best_work,
                "summonable": pal.summonable,
                "predator": pal.predator,
                "boss_first_defeat_reward": pal.boss_first_defeat_reward,
                "image_url": pal.image_url,
                "wiki_url": pal.wiki_url,
            }
            # 1:1 详情
            st = (await session.execute(
                select(PalStatsModel).where(PalStatsModel.pal_id == pal.id)
            )).scalars().first()
            result["stats"] = _row_to_dict(st, exclude={"pal_id"}) if st else {}
            fr = (await session.execute(
                select(PalFriendshipModel).where(PalFriendshipModel.pal_id == pal.id)
            )).scalars().first()
            result["friendship"] = _row_to_dict(fr, exclude={"pal_id"}) if fr else {}
            es = (await session.execute(
                select(PalEnemyScalingModel).where(PalEnemyScalingModel.pal_id == pal.id)
            )).scalars().first()
            result["enemy_scaling"] = _row_to_dict(es, exclude={"pal_id"}) if es else {}
            psk = (await session.execute(
                select(PalPartnerSkillModel).where(PalPartnerSkillModel.pal_id == pal.id)
            )).scalars().first()
            result["partner_skill"] = _row_to_dict(psk, exclude={"pal_id"}) if psk else {}
            # 关联集合
            result["skills"] = await self.query_pal_skills(game_id)
            result["drops"] = await self.query_pal_drops(game_id)
            result["passives"] = await self._query_pal_passives(pal.id)
            result["summon"] = await self._query_pal_summon(pal.id)
            return result

    async def _query_pal_passives(self, pal_db_id: int) -> list[dict]:
        async with self._session_factory() as session:
            stmt = (
                select(
                    PassiveModel.passive_id,
                    PassiveModel.cn_name,
                    PassiveModel.rank,
                    PassiveModel.lottery_weight,
                    PassiveEffectModel.effect_type,
                    PassiveEffectModel.effect_value,
                )
                .join(PalPassiveModel, PalPassiveModel.passive_id == PassiveModel.id)
                .outerjoin(
                    PassiveEffectModel, PassiveEffectModel.passive_id == PassiveModel.id
                )
                .where(PalPassiveModel.pal_id == pal_db_id)
                .order_by(PassiveModel.rank.desc())
            )
            rows = await session.execute(stmt)
            return [dict(r) for r in rows.mappings().all()]

    async def _query_pal_summon(self, pal_db_id: int) -> list[dict]:
        async with self._session_factory() as session:
            stmt = (
                select(
                    ItemModel.item_id,
                    ItemModel.cn_name,
                    PalSummonModel.level,
                    PalSummonModel.count,
                )
                .join(PalSummonModel, PalSummonModel.material_item_id == ItemModel.id)
                .where(PalSummonModel.pal_id == pal_db_id)
            )
            rows = await session.execute(stmt)
            return [dict(r) for r in rows.mappings().all()]


def _row_to_dict(obj, exclude: set[str] | None = None) -> dict:
    """SQLAlchemy 对象 → dict（排除指定列，去掉内部状态键）。"""
    exclude = exclude or set()
    out = {}
    for col in obj.__table__.columns:
        if col.name in exclude:
            continue
        out[col.name] = getattr(obj, col.name)
    return out
