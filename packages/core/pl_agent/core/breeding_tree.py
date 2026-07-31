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
        """构建目标帕鲁的完整配种树."""
        tree = BreedingTree(target=target)

        # 目标本身就是基础帕鲁 → 单节点
        if target.is_wild:
            path = BreedingPath(
                leaf_pals=[target],
                total_steps=0,
                avg_rarity=float(target.rarity),
            )
            tree.paths = [path]
            tree.best_path = path
            tree.total_paths = 1
            tree.max_depth_reached = 0
            return tree

        # step 1 + 2: BFS 构建 parent_map
        parent_map: dict[str, list[tuple[Pal, Pal]]] = {}
        visited: set[str] = set()
        queue: deque[tuple[Pal, int]] = deque([(target, 0)])
        max_depth_seen = 0

        while queue:
            current, depth = queue.popleft()
            max_depth_seen = max(max_depth_seen, depth)

            if current.id in visited:
                continue
            visited.add(current.id)

            # 终止条件
            if current.is_wild:
                continue
            if depth >= self.max_depth:
                logger.debug("max_depth reached for %s at depth %d", current.id, depth)
                continue
            if self._engine.is_unbreedable(current.id):
                continue
            if self._engine.is_excluded(current.id):
                continue

            # 获取父母对
            try:
                parent_pairs = self._engine.reverse_breed(current)
            except Exception:
                logger.exception("reverse_breed failed for %s", current.id)
                continue

            if not parent_pairs:
                continue

            # 过滤: 去掉包含自身的对 + 排除 excluded
            filtered: list[tuple[Pal, Pal]] = []
            for a, b in parent_pairs:
                if a.id == current.id and b.id == current.id:
                    continue
                if self._engine.is_excluded(a.id) or self._engine.is_excluded(b.id):
                    continue
                filtered.append((a, b))

            if filtered:
                parent_map[current.id] = filtered
            else:
                parent_map[current.id] = []

            # 将父母加入队列
            for a, b in filtered:
                if a.id not in visited:
                    queue.append((a, depth + 1))
                if b.id not in visited:
                    queue.append((b, depth + 1))

        tree.max_depth_reached = max_depth_seen

        # step 3: 递归回溯构建路径
        if target.id in parent_map:
            raw_paths = self._backtrack(target.id, parent_map, visited_path=[])
            # 去重
            seen_hashes = set()
            unique_paths: list[BreedingPath] = []
            for rp in raw_paths:
                h = self._path_hash(rp)
                if h not in seen_hashes:
                    seen_hashes.add(h)
                    unique_paths.append(rp)
            tree.paths = unique_paths
            tree.total_paths = len(unique_paths)

        return tree

    # ------------------------------------------------------------------
    # backtracking
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

        # 叶子: 基础帕鲁或不可配种
        if pal.is_wild or pal_id not in parent_map:
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
        """计算路径哈希 (用于去重)."""
        ids = tuple(s.child.id for s in path.steps)
        return hash(ids)
