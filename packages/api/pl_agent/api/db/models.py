"""ORM models mapped to normalized PostgreSQL tables."""

from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
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
