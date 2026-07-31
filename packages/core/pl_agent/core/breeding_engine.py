"""Breeding engine — forward/reverse CombiRank breeding calculations.

Core algorithm:
  child_rank = round((parent_a.combi_rank + parent_b.combi_rank) / 2)
  child = the Pal with the nearest CombiRank value.
"""

from __future__ import annotations

import itertools
import logging
from typing import Optional

from pl_agent.core.errors import (
    BreedingLoopError,
    DataIntegrityError,
    PalNotFoundError,
)
from pl_agent.core.schema import BreedingRules, Pal

logger = logging.getLogger(__name__)


class BreedingEngine:
    """配种计算引擎 — 正向/反向 CombiRank 计算."""

    def __init__(
        self,
        pals: list[Pal],
        rules: BreedingRules,
    ):
        # 按 CombiRank 升序排列
        self._pals_by_rank = sorted(pals, key=lambda p: p.combi_rank)
        # 快速索引
        self._pal_map: dict[str, Pal] = {p.id: p for p in pals}
        self._pal_map_num: dict[int, Pal] = {p.number: p for p in pals}

        self._rules = rules
        self._wild_ids = {p.id for p in pals if p.is_wild}

        # 预计算快速查找表
        self._special_map: dict[tuple[str, str], str] = {}
        for s in rules.special_combinations:
            a, b = sorted([s.parent_a, s.parent_b])
            self._special_map[(a, b)] = s.child

        self._self_only_ids = {s.pal_id for s in rules.self_only}
        self._unbreedable_ids = {u.pal_id for u in rules.unbreedable}
        self._excluded_ids = set(rules.breeding_excluded)

        # CombiRank 索引 (用于快速反向查询)
        self._rank_to_pals: dict[int, list[Pal]] = {}
        for p in self._pals_by_rank:
            self._rank_to_pals.setdefault(p.combi_rank, []).append(p)

        # 预计算: 排除不可配种帕鲁后的列表 (避免每次 _enumerate 重新排序)
        self._eligible_pals = [
            p for p in self._pals_by_rank if p.id not in self._excluded_ids
        ]
        self._eligible_ranks = [p.combi_rank for p in self._eligible_pals]
        # rank → index 快速查找
        self._eligible_rank_to_idx: dict[int, int] = {}
        for i, p in enumerate(self._eligible_pals):
            self._eligible_rank_to_idx[p.combi_rank] = i

    # ------------------------------------------------------------------
    # forward: parents → child
    # ------------------------------------------------------------------

    def forward_breed(self, parent_a: Pal, parent_b: Pal) -> Pal:
        """正向计算: 父母 → 子代.

        Raises:
            DataIntegrityError: 父代在 breeding_excluded 中.
        """
        # 检查排除列表
        if parent_a.id in self._excluded_ids or parent_b.id in self._excluded_ids:
            raise DataIntegrityError(
                f"parent {parent_a.id} or {parent_b.id} is in breeding_excluded"
            )

        # 1. 查特殊组合表
        pair = tuple(sorted([parent_a.id, parent_b.id]))
        special_child_id = self._special_map.get(pair)
        if special_child_id:
            return self._require_pal(special_child_id)

        # 2. 查 self_only
        if parent_a.id == parent_b.id and parent_a.id in self._self_only_ids:
            return parent_a

        # 3. 标准 CombiRank 计算
        target_rank = round((parent_a.combi_rank + parent_b.combi_rank) / 2)
        return self._find_nearest_rank(target_rank)

    # ------------------------------------------------------------------
    # reverse: child → all possible parent pairs
    # ------------------------------------------------------------------

    def reverse_breed(self, child: Pal) -> list[tuple[Pal, Pal]]:
        """反向计算: 子代 → 所有可能父母对.

        Returns:
            空列表表示该子代不可配种.
        """
        # 1. 特殊组合 (child 是特殊组合的产物)
        for s in self._rules.special_combinations:
            if s.child == child.id:
                parent_a = self._require_pal(s.parent_a)
                parent_b = self._require_pal(s.parent_b)
                # 特殊组合的子代还可通过 (child, child) 产生同类
                return [(child, child), (parent_a, parent_b)]

        # 2. self_only
        if child.id in self._self_only_ids:
            return [(child, child)]

        # 3. unbreedable or breeding_excluded
        if child.id in self._unbreedable_ids or child.id in self._excluded_ids:
            return []

        # 4. 找 child 前后的 CombiRank 帕鲁 (排除 excluded)
        prev_pal = self._find_prev_rank(child.combi_rank)
        next_pal = self._find_next_rank(child.combi_rank)

        if prev_pal is None or next_pal is None:
            return [(child, child)]

        return self._enumerate_parent_pairs(child, prev_pal, next_pal)

    def reverse_with_parent(self, child: Pal, parent: Pal) -> list[Pal]:
        """反向+筛选: 子代 + 一方父母 → 另一方."""
        all_pairs = self.reverse_breed(child)
        result: list[Pal] = []
        for a, b in all_pairs:
            if a.id == parent.id:
                result.append(b)
            elif b.id == parent.id:
                result.append(a)
        return result

    # ------------------------------------------------------------------
    # helpers: find nearest rank
    # ------------------------------------------------------------------

    def _find_nearest_rank(self, target_rank: float) -> Pal:
        """找到 CombiRank 最接近 target_rank 的帕鲁."""
        if not self._pals_by_rank:
            raise DataIntegrityError("no pals loaded")

        # 精确匹配
        int_target = round(target_rank)
        exact_matches = self._rank_to_pals.get(int_target)
        if exact_matches:
            # 同值时取图鉴编号小的
            return min(exact_matches, key=lambda p: p.number)

        nearest = self._pals_by_rank[0]
        min_diff = abs(nearest.combi_rank - target_rank)
        for p in self._pals_by_rank[1:]:
            diff = abs(p.combi_rank - target_rank)
            if diff < min_diff:
                nearest = p
                min_diff = diff
            elif diff > min_diff:
                break  # 已过最优区间
        return nearest

    def _find_prev_rank(self, rank: int) -> Pal | None:
        """找 CombiRank <= rank 的最接近帕鲁 (排除 excluded)."""
        prev: Pal | None = None
        for p in self._pals_by_rank:
            if p.id in self._excluded_ids:
                continue
            if p.combi_rank <= rank:
                prev = p
            else:
                break
        return prev

    def _find_next_rank(self, rank: int) -> Pal | None:
        """找 CombiRank >= rank 的最接近帕鲁 (排除 excluded)."""
        for p in self._pals_by_rank:
            if p.id in self._excluded_ids:
                continue
            if p.combi_rank >= rank:
                return p
        return None

    # ------------------------------------------------------------------
    # helpers: enumerate
    # ------------------------------------------------------------------

    def _enumerate_parent_pairs(
        self,
        child: Pal,
        prev_pal: Pal,
        next_pal: Pal,
    ) -> list[tuple[Pal, Pal]]:
        """枚举所有可能的父母对 (预计算索引, O(k²) where k << n)."""
        result: list[tuple[Pal, Pal]] = []

        prev_sum = child.combi_rank + prev_pal.combi_rank
        next_sum = child.combi_rank + next_pal.combi_rank

        # 使用预计算索引 (避免每次重新排序)
        eligible = self._eligible_pals
        ranks = self._eligible_ranks
        child_idx = self._eligible_rank_to_idx.get(child.combi_rank, -1)
        prev_idx = self._eligible_rank_to_idx.get(prev_pal.combi_rank, -1)
        next_idx = self._eligible_rank_to_idx.get(next_pal.combi_rank, -1)

        prev_equal = prev_idx >= child_idx
        next_equal = next_idx >= child_idx

        # 只枚举总和在 [prev_sum, next_sum] 范围内的 rank 对
        eligible_rank_pairs: set[tuple[int, int]] = set()
        for i, r1 in enumerate(ranks):
            for j in range(i, len(ranks)):
                r2 = ranks[j]
                rank_sum = r1 + r2
                low_ok = rank_sum >= prev_sum if prev_equal else rank_sum > prev_sum
                high_ok = rank_sum <= next_sum if next_equal else rank_sum < next_sum
                if not (low_ok and high_ok):
                    continue
                if round(rank_sum / 2) != child.combi_rank:
                    continue
                eligible_rank_pairs.add((min(r1, r2), max(r1, r2)))

        # 构建 Pal 对
        for r1, r2 in eligible_rank_pairs:
            pals_r1 = [p for p in eligible if p.combi_rank == r1]
            pals_r2 = [p for p in eligible if p.combi_rank == r2]
            for p1 in pals_r1:
                for p2 in pals_r2:
                    if p1.id == child.id and p2.id == child.id:
                        continue
                    result.append((p1, p2))

        if not result:
            result.append((child, child))

        return result

    # ------------------------------------------------------------------
    # helpers: rules
    # ------------------------------------------------------------------

    def is_special(self, parent_a: str, parent_b: str) -> str | None:
        """检查是否为特殊组合, 返回子代 ID 或 None."""
        pair = tuple(sorted([parent_a, parent_b]))
        return self._special_map.get(pair)

    def is_self_only(self, pal_id: str) -> bool:
        return pal_id in self._self_only_ids

    def is_unbreedable(self, pal_id: str) -> bool:
        return pal_id in self._unbreedable_ids

    def is_excluded(self, pal_id: str) -> bool:
        return pal_id in self._excluded_ids

    def is_wild(self, pal_id: str) -> bool:
        return pal_id in self._wild_ids

    # ------------------------------------------------------------------
    # helpers: lookup
    # ------------------------------------------------------------------

    def _require_pal(self, pal_id: str) -> Pal:
        """查找 Pal, 不存在则抛出 PalNotFoundError."""
        pal = self._pal_map.get(pal_id)
        if pal is None:
            raise PalNotFoundError(pal_id)
        return pal

    def get_pal(self, pal_id: str) -> Pal | None:
        return self._pal_map.get(pal_id)

    @property
    def all_pals(self) -> list[Pal]:
        return list(self._pal_map.values())

    @property
    def wild_pals(self) -> list[Pal]:
        return [p for p in self._pal_map.values() if self.is_wild(p.id)]
