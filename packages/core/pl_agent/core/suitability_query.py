"""Work suitability query engine — find Pals by work type and level."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from pl_agent.core.errors import PalNotFoundError
from pl_agent.core.schema import Pal, WorkType

logger = logging.getLogger(__name__)


@dataclass
class LevelStats:
    """工种等级统计."""

    max_level: int
    avg_level: float
    count: int  # 拥有该工种的帕鲁数量


class SuitabilityQuery:
    """工作适应性查询引擎."""

    VALID_WORK_TYPES = frozenset(wt.value for wt in WorkType)

    def __init__(self, pals: list[Pal]):
        self._pals = pals
        self._stats_cache: dict[str, LevelStats] = {}

    # ------------------------------------------------------------------
    # single-condition query
    # ------------------------------------------------------------------

    def query(
        self,
        work_type: str,
        min_level: int = 1,
    ) -> list[tuple[Pal, int]]:
        """按工作适应性 + 最低等级查询.

        Returns:
            (Pal, 该工种的实际等级) 列表, 按等级降序排列.
        """
        self._validate_work_type(work_type)

        results: list[tuple[Pal, int]] = []
        for pal in self._pals:
            level = getattr(pal.work_suitability, work_type, 0)
            if level >= min_level:
                results.append((pal, level))

        results.sort(key=lambda x: x[1], reverse=True)
        return results

    # ------------------------------------------------------------------
    # multi-condition query
    # ------------------------------------------------------------------

    def query_multi(
        self,
        requirements: list[tuple[str, int]],
    ) -> list[tuple[Pal, int]]:
        """多条件查询 — 同时满足所有工种条件.

        Returns:
            (Pal, 最低满足等级) 列表.
        """
        for wt, _ in requirements:
            self._validate_work_type(wt)

        results: list[tuple[Pal, int]] = []
        for pal in self._pals:
            min_satisfied: Optional[int] = None
            all_ok = True
            for wt, min_lv in requirements:
                level = getattr(pal.work_suitability, wt, 0)
                if level < min_lv:
                    all_ok = False
                    break
                if min_satisfied is None or level < min_satisfied:
                    min_satisfied = level
            if all_ok and min_satisfied is not None:
                results.append((pal, min_satisfied))

        results.sort(key=lambda x: x[1], reverse=True)
        return results

    # ------------------------------------------------------------------
    # statistics
    # ------------------------------------------------------------------

    def get_max_level(self, work_type: str) -> int:
        """获取指定工种的最高等级."""
        self._validate_work_type(work_type)
        stats = self._get_stats(work_type)
        return stats.max_level

    def get_level_stats(self, work_type: str) -> LevelStats:
        """获取工种统计."""
        self._validate_work_type(work_type)
        return self._get_stats(work_type)

    def get_all_stats(self) -> dict[str, LevelStats]:
        """获取所有工种统计."""
        return {wt: self._get_stats(wt) for wt in self.VALID_WORK_TYPES}

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _get_stats(self, work_type: str) -> LevelStats:
        if work_type in self._stats_cache:
            return self._stats_cache[work_type]

        levels: list[int] = []
        for pal in self._pals:
            lv = getattr(pal.work_suitability, work_type, 0)
            if lv > 0:
                levels.append(lv)

        if levels:
            stats = LevelStats(
                max_level=max(levels),
                avg_level=round(sum(levels) / len(levels), 1),
                count=len(levels),
            )
        else:
            stats = LevelStats(max_level=0, avg_level=0.0, count=0)

        self._stats_cache[work_type] = stats
        return stats

    def _validate_work_type(self, work_type: str) -> None:
        if work_type not in self.VALID_WORK_TYPES:
            raise PalNotFoundError(
                f"unknown work type: {work_type}. "
                f"Valid types: {sorted(self.VALID_WORK_TYPES)}"
            )
