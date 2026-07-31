"""Adapter abstract interfaces — all external data sources implement these."""

from abc import ABC, abstractmethod

from pl_agent.core.schema import BreedingRules, DatasetMeta, Pal


class PalDataSourceAdapter(ABC):
    """帕鲁数据源适配器 — 所有数据源必须实现此接口.

    职责: 从外部数据源获取原始数据, 转换为 canonical `Pal` 实体列表.
    """

    @abstractmethod
    async def fetch_all(self) -> list[Pal]:
        """获取全部帕鲁数据, 返回 canonical Pal 列表."""
        ...

    @property
    @abstractmethod
    def source_name(self) -> str:
        """数据源名称."""
        ...

    @property
    @abstractmethod
    def source_version(self) -> str:
        """数据源版本."""
        ...

    async def fetch_meta(self) -> DatasetMeta:
        """获取数据集元信息 (可选覆写)."""
        pals = await self.fetch_all()
        wild_count = sum(1 for p in pals if p.is_wild)
        return DatasetMeta(
            game_version=self.source_version,
            total_pals=len(pals),
            wild_pals=wild_count,
            source=self.source_name,
        )


class BreedingRulesAdapter(ABC):
    """配种规则适配器."""

    @abstractmethod
    async def fetch_rules(self) -> BreedingRules:
        """获取配种规则."""
        ...
