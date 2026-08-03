"""ORM models mapped to normalized PostgreSQL tables."""

from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class PalModel(Base):
    """pal main table."""

    __tablename__ = "pal"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    game_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    zukan_index: Mapped[int] = mapped_column(Integer, nullable=False)
    cn_name: Mapped[str] = mapped_column(String(32), nullable=False)
    en_name: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    combi_rank: Mapped[int] = mapped_column(Integer, nullable=False)
    rarity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_wild: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    breed_child: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    zukan_index_suffix: Mapped[str] = mapped_column(String(16), nullable=False, default="")
    genus: Mapped[str | None] = mapped_column(String(32), nullable=True)
    size: Mapped[str | None] = mapped_column(String(8), nullable=True)
    egg: Mapped[str | None] = mapped_column(String(64), nullable=True)
    nocturnal: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    reaction: Mapped[str | None] = mapped_column(String(32), nullable=True)
    best_work: Mapped[str | None] = mapped_column(String(32), nullable=True)
    summonable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    predator: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    boss_first_defeat_reward: Mapped[str | None] = mapped_column(String(64), nullable=True)
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    wiki_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    elements: Mapped[list[PalElementModel]] = relationship(
        back_populates="pal", cascade="all, delete-orphan"
    )
    aliases: Mapped[list[PalAliasModel]] = relationship(
        back_populates="pal", cascade="all, delete-orphan"
    )
    work_suitabilities: Mapped[list[WorkSuitabilityModel]] = relationship(
        back_populates="pal", cascade="all, delete-orphan"
    )


class PalElementModel(Base):
    """pal_element table."""

    __tablename__ = "pal_element"

    pal_id: Mapped[int] = mapped_column(ForeignKey("pal.id"), primary_key=True)
    element_type: Mapped[str] = mapped_column(String(16), primary_key=True)

    pal: Mapped[PalModel] = relationship(back_populates="elements")


class PalAliasModel(Base):
    """pal_aliase table."""

    __tablename__ = "pal_aliase"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pal_id: Mapped[int] = mapped_column(ForeignKey("pal.id"), nullable=False)
    alias: Mapped[str] = mapped_column(String(64), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="community")

    pal: Mapped[PalModel] = relationship(back_populates="aliases")


class WorkSuitabilityModel(Base):
    """work_suitability table."""

    __tablename__ = "work_suitability"

    pal_id: Mapped[int] = mapped_column(ForeignKey("pal.id"), primary_key=True)
    work_type: Mapped[str] = mapped_column(String(32), primary_key=True)
    level: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    pal: Mapped[PalModel] = relationship(back_populates="work_suitabilities")


class BreedingRuleModel(Base):
    """breeding_rule table."""

    __tablename__ = "breeding_rule"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    child_id: Mapped[int] = mapped_column(ForeignKey("pal.id"), nullable=False)
    parent_a_id: Mapped[int | None] = mapped_column(ForeignKey("pal.id"), nullable=True)
    parent_b_id: Mapped[int | None] = mapped_column(ForeignKey("pal.id"), nullable=True)
    rule_type: Mapped[str] = mapped_column(String(32), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


# =============================================================================
# tc-imba 扩展表 ORM 模型 (v2.0 22 表)
# =============================================================================


class PalStatsModel(Base):
    """pal_stats table (1:1 pal)."""

    __tablename__ = "pal_stats"

    pal_id: Mapped[int] = mapped_column(ForeignKey("pal.id"), primary_key=True)
    hp: Mapped[int | None] = mapped_column(Integer, nullable=True)
    melee_attack: Mapped[int | None] = mapped_column(Integer, nullable=True)
    shot_attack: Mapped[int | None] = mapped_column(Integer, nullable=True)
    defense: Mapped[int | None] = mapped_column(Integer, nullable=True)
    support: Mapped[int | None] = mapped_column(Integer, nullable=True)
    craft_speed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stamina: Mapped[int | None] = mapped_column(Integer, nullable=True)
    food_amount: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_full_stomach: Mapped[int | None] = mapped_column(Integer, nullable=True)
    capture_rate: Mapped[float | None] = mapped_column(Numeric(6, 3), nullable=True)
    exp_ratio: Mapped[float | None] = mapped_column(Numeric(6, 3), nullable=True)
    price: Mapped[int | None] = mapped_column(Integer, nullable=True)
    male_probability: Mapped[int | None] = mapped_column(Integer, nullable=True)
    slow_walk_speed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    walk_speed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    run_speed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ride_sprint_speed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    transport_speed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    swim_speed: Mapped[int | None] = mapped_column(Integer, nullable=True)


class PalFriendshipModel(Base):
    """pal_friendship table (1:1 pal)."""

    __tablename__ = "pal_friendship"

    pal_id: Mapped[int] = mapped_column(ForeignKey("pal.id"), primary_key=True)
    hp: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)
    shot_attack: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)
    defense: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)


class PalEnemyScalingModel(Base):
    """pal_enemy_scaling table (1:1 pal)."""

    __tablename__ = "pal_enemy_scaling"

    pal_id: Mapped[int] = mapped_column(ForeignKey("pal.id"), primary_key=True)
    receive_damage: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)


class PalPartnerSkillModel(Base):
    """pal_partner_skill table (1:1 pal)."""

    __tablename__ = "pal_partner_skill"

    pal_id: Mapped[int] = mapped_column(ForeignKey("pal.id"), primary_key=True)
    action_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    effect_time: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cool_time: Mapped[int | None] = mapped_column(Integer, nullable=True)
    exec_cost: Mapped[int | None] = mapped_column(Integer, nullable=True)
    idle_cost: Mapped[int | None] = mapped_column(Integer, nullable=True)
    toggle: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    can_throw_pal: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class PalSummonModel(Base):
    """pal_summon table (N:M pal-item)."""

    __tablename__ = "pal_summon"

    pal_id: Mapped[int] = mapped_column(ForeignKey("pal.id"), primary_key=True)
    material_item_id: Mapped[int] = mapped_column(ForeignKey("item.id"), primary_key=True)
    level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class SkillModel(Base):
    """skill table."""

    __tablename__ = "skill"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    waza_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    element: Mapped[str | None] = mapped_column(String(16), nullable=True)
    category: Mapped[str | None] = mapped_column(String(16), nullable=True)
    power: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cool_time: Mapped[int | None] = mapped_column(Integer, nullable=True)
    min_range: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_range: Mapped[int | None] = mapped_column(Integer, nullable=True)
    strength: Mapped[str | None] = mapped_column(String(16), nullable=True)
    effect_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    effect_value: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cn_name: Mapped[str | None] = mapped_column(String(32), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class PalSkillModel(Base):
    """pal_skill table (N:M pal-skill)."""

    __tablename__ = "pal_skill"

    pal_id: Mapped[int] = mapped_column(ForeignKey("pal.id"), primary_key=True)
    skill_id: Mapped[int] = mapped_column(ForeignKey("skill.id"), primary_key=True)
    learn_level: Mapped[int] = mapped_column(Integer, nullable=False)


class PassiveModel(Base):
    """passive table."""

    __tablename__ = "passive"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    passive_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    lottery_weight: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cn_name: Mapped[str | None] = mapped_column(String(32), nullable=True)


class PassiveEffectModel(Base):
    """passive_effect table (N passive effects)."""

    __tablename__ = "passive_effect"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    passive_id: Mapped[int] = mapped_column(ForeignKey("passive.id"), nullable=False)
    effect_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    effect_value: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    effect_target: Mapped[str | None] = mapped_column(String(16), nullable=True)


class PassiveInvokeModel(Base):
    """passive_invoke table (invoke[] 拆行)."""

    __tablename__ = "passive_invoke"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    passive_id: Mapped[int] = mapped_column(ForeignKey("passive.id"), nullable=False)
    invoke: Mapped[str] = mapped_column(String(32), nullable=False)


class PalPassiveModel(Base):
    """pal_passive table (N:M pal-passive)."""

    __tablename__ = "pal_passive"

    pal_id: Mapped[int] = mapped_column(ForeignKey("pal.id"), primary_key=True)
    passive_id: Mapped[int] = mapped_column(ForeignKey("passive.id"), primary_key=True)


class ItemModel(Base):
    """item table."""

    __tablename__ = "item"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    item_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    type_a: Mapped[str | None] = mapped_column(String(32), nullable=True)
    type_b: Mapped[str | None] = mapped_column(String(32), nullable=True)
    sort_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rarity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    weight: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)
    price: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_stack: Mapped[int | None] = mapped_column(Integer, nullable=True)
    handcraft: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    cn_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class ItemRecipeModel(Base):
    """item_recipe table."""

    __tablename__ = "item_recipe"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("item.id"), nullable=False)
    work: Mapped[int | None] = mapped_column(Integer, nullable=True)
    product_count: Mapped[int | None] = mapped_column(Integer, nullable=True)


class ItemRecipeStationModel(Base):
    """item_recipe_station table (craftedAt[] 拆行)."""

    __tablename__ = "item_recipe_station"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    recipe_id: Mapped[int] = mapped_column(ForeignKey("item_recipe.id"), nullable=False)
    station: Mapped[str] = mapped_column(String(64), nullable=False)


class ItemRecipeMaterialModel(Base):
    """item_recipe_material table (recipe materials)."""

    __tablename__ = "item_recipe_material"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    recipe_id: Mapped[int] = mapped_column(ForeignKey("item_recipe.id"), nullable=False)
    material_item_id: Mapped[int] = mapped_column(ForeignKey("item.id"), nullable=False)
    count: Mapped[int] = mapped_column(Integer, nullable=False)


class ItemSourceModel(Base):
    """item_source table (sources[] 拆行)."""

    __tablename__ = "item_source"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("item.id"), nullable=False)
    kind: Mapped[str | None] = mapped_column(String(16), nullable=True)
    area: Mapped[str | None] = mapped_column(String(32), nullable=True)
    grade: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chance: Mapped[int | None] = mapped_column(Integer, nullable=True)


class PalDropModel(Base):
    """pal_drop table (drops[] + bossDrops[])."""

    __tablename__ = "pal_drop"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pal_id: Mapped[int] = mapped_column(ForeignKey("pal.id"), nullable=False)
    item_id: Mapped[int] = mapped_column(ForeignKey("item.id"), nullable=False)
    rate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    min_level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_boss: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
