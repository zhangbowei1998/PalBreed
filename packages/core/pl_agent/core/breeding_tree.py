"""Breeding tree builder — BFS reverse search + recursive backtracking."""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

from pl_agent.core.errors import BreedingLoopError
from pl_agent.core.schema import Pal

from .breeding_engine import BreedingEngine

logger = logging.getLogger(__name__)


# ============================================================================
# data structures
# ============================================================================


@dataclass
class BreedingStep:
    """配种的一个步骤."""

    parent_a: Pal
    parent_b: Pal
    child: Pal
    method: str = "breed"  # "wild" | "breed"

    def to_dict(self) -> dict:
        return {
            "parent_a": self.parent_a.to_dict(),
            "parent_b": self.parent_b.to_dict(),
            "child": self.child.to_dict(),
            "method": self.method,
        }


@dataclass
class BreedingPath:
    """一条完整的配种路径 (从基础帕鲁到目标)."""

    steps: list[BreedingStep] = field(default_factory=list)
    leaf_pals: list[Pal] = field(default_factory=list)
    total_steps: int = 0
    avg_rarity: float = 0.0

    def to_dict(self) -> dict:
        return {
            "steps": [s.to_dict() for s in self.steps],
            "leaf_pals": [p.to_dict() for p in self.leaf_pals],
            "total_steps": self.total_steps,
            "avg_rarity": self.avg_rarity,
        }


@dataclass
class BreedingTree:
    """配种树."""

    target: Pal
    paths: list[BreedingPath] = field(default_factory=list)
    best_path: BreedingPath | None = None
    total_paths: int = 0
    max_depth_reached: int = 0

    def to_dict(self) -> dict:
        return {
            "target": self.target.to_dict(),
            "paths": [p.to_dict() for p in self.paths],
            "best_path": self.best_path.to_dict() if self.best_path else None,
            "total_paths": self.total_paths,
            "max_depth_reached": self.max_depth_reached,
        }


# ============================================================================
# builder
# ============================================================================


class BreedingTreeBuilder:
    """配种树构建器 — BFS 反向搜索 + parent_map + 递归回溯."""

    def __init__(self, engine: BreedingEngine, max_depth: int = 5):
        self._engine = engine
        self.max_depth = max_depth

    def build(self, target: Pal) -> BreedingTree:
        """构建目标帕鲁的配种方案 — 只计算一级父母组合.

        返回所有可能的 (父A, 父B) 对, 不递归展开父代的来源。
        用户可点击任一父代继续查询。
        """
        tree = BreedingTree(target=target)
        tree.max_depth_reached = 1

        parent_pairs = self._engine.reverse_breed(target)

        # 过滤: 排除自身配对 + excluded
        filtered: list[tuple[Pal, Pal]] = []
        for a, b in parent_pairs:
            if a.id == target.id and b.id == target.id:
                continue
            if self._engine.is_excluded(a.id) or self._engine.is_excluded(b.id):
                continue
            filtered.append((a, b))

        if not filtered:
            # 无可配种路径 — 返回空树
            return tree

        paths: list[BreedingPath] = []
        for a, b in filtered:
            leaf_pals: list[Pal] = []
            if a.is_wild:
                leaf_pals.append(a)
            if b.is_wild:
                leaf_pals.append(b)
            step = BreedingStep(parent_a=a, parent_b=b, child=target, method="breed")
            path = BreedingPath(
                steps=[step],
                leaf_pals=leaf_pals if leaf_pals else [a, b],
                total_steps=1,
                avg_rarity=(a.rarity + b.rarity) / 2,
            )
            paths.append(path)

        # 去重
        seen = set()
        unique: list[BreedingPath] = []
        for p in paths:
            h = self._path_hash(p)
            if h not in seen:
                seen.add(h)
                unique.append(p)

        tree.paths = unique
        tree.total_paths = len(unique)
        return tree

    # ------------------------------------------------------------------
    # backtracking (deprecated: kept for reference, unused in v0.2)
    # ------------------------------------------------------------------

    def _backtrack(
        self,
        pal_id: str,
        parent_map: dict[str, list[tuple[Pal, Pal]]],
        visited_path: list[str],
    ) -> list[BreedingPath]:
        """从 parent_map 递归回溯构建 BreedingPath 列表."""
        pal = self._engine.get_pal(pal_id)
        if pal is None:
            return []

        # 循环检测
        if pal_id in visited_path:
            raise BreedingLoopError(visited_path + [pal_id])

        # 叶子: 不在 parent_map 中 (无父母或已到终端)
        if pal_id not in parent_map:
            return [
                BreedingPath(
                    leaf_pals=[pal],
                    total_steps=0,
                    avg_rarity=float(pal.rarity),
                )
            ]

        pairs = parent_map.get(pal_id, [])
        if not pairs:
            return [
                BreedingPath(
                    leaf_pals=[pal],
                    total_steps=0,
                    avg_rarity=float(pal.rarity),
                )
            ]

        result: list[BreedingPath] = []
        for parent_a, parent_b in pairs:
            try:
                left_paths = self._backtrack(
                    parent_a.id,
                    parent_map,
                    visited_path + [pal_id],
                )
                right_paths = self._backtrack(
                    parent_b.id,
                    parent_map,
                    visited_path + [pal_id],
                )
            except BreedingLoopError:
                continue

            for lp in left_paths:
                for rp in right_paths:
                    step = BreedingStep(
                        parent_a=parent_a,
                        parent_b=parent_b,
                        child=pal,
                        method="breed",
                    )
                    # 合并 leaf_pals
                    combined_leaves = list(
                        {p.id: p for p in lp.leaf_pals + rp.leaf_pals}.values()
                    )
                    combined_steps = lp.steps + rp.steps + [step]
                    combined_steps_distinct = self._dedup_steps(combined_steps)

                    avg_r = (
                        sum(p.rarity for p in combined_leaves) / len(combined_leaves)
                        if combined_leaves
                        else 0.0
                    )

                    path = BreedingPath(
                        steps=combined_steps_distinct,
                        leaf_pals=combined_leaves,
                        total_steps=len(combined_steps_distinct),
                        avg_rarity=avg_r,
                    )
                    result.append(path)

        return result

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _dedup_steps(steps: list[BreedingStep]) -> list[BreedingStep]:
        """去重步骤 (按 child 去重, 保留第一次出现)."""
        seen: set[str] = set()
        result: list[BreedingStep] = []
        for s in steps:
            if s.child.id not in seen:
                seen.add(s.child.id)
                result.append(s)
        return result

    @staticmethod
    def _path_hash(path: BreedingPath) -> int:
        """计算路径哈希 (用于去重) — 基于每步的父母对."""
        ids = tuple(tuple(sorted([s.parent_a.id, s.parent_b.id])) for s in path.steps)
        return hash(ids)
