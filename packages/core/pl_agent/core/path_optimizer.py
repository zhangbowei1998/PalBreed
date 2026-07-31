"""Path optimizer — ranks breeding paths by quality."""

from __future__ import annotations

import logging

from .breeding_engine import BreedingEngine
from .breeding_tree import BreedingPath, BreedingTree

logger = logging.getLogger(__name__)


class PathOptimizer:
    """配种路径排序与择优.

    排序策略 (优先级从高到低):
      1. 步数最少 (total_steps)
      2. 基础帕鲁最少 (leaf_pals 数量)
      3. 稀有度最低 (avg_rarity)
      4. 不含传说/Boss (self_only 或 unbreedable)
      5. 最先发现 (保持 BFS 原始顺序)
    """

    def __init__(self, engine: BreedingEngine):
        self._engine = engine

    def optimize(self, tree: BreedingTree) -> BreedingTree:
        """对配种树中的所有路径排序, 标记最优路径."""
        if not tree.paths:
            return tree

        # 计算评分并排序
        scored: list[tuple[float, int, BreedingPath]] = []
        for idx, path in enumerate(tree.paths):
            score = self._score(path, idx)
            scored.append((score, idx, path))

        scored.sort(key=lambda x: (x[0], x[1]))
        tree.paths = [item[2] for item in scored]
        tree.best_path = tree.paths[0] if tree.paths else None

        return tree

    # ------------------------------------------------------------------
    # scoring
    # ------------------------------------------------------------------

    def _score(self, path: BreedingPath, original_index: int) -> float:
        """计算路径评分 (越低越好).

        score = total_steps × 100 + leaf_count × 10 + avg_rarity + legendary_penalty
        """
        score = path.total_steps * 100.0
        score += len(path.leaf_pals) * 10.0
        score += path.avg_rarity * 1.0

        # 传说/Boss 惩罚
        if self._contains_legendary_or_boss(path):
            score += 1000.0

        return score

    def _contains_legendary_or_boss(self, path: BreedingPath) -> bool:
        """检查路径中是否包含传说/Boss 帕鲁."""
        all_ids = set()
        for step in path.steps:
            all_ids.add(step.parent_a.id)
            all_ids.add(step.parent_b.id)
            all_ids.add(step.child.id)
        for pal_id in path.leaf_pals:
            all_ids.add(pal_id.id)

        for pid in all_ids:
            if self._engine.is_self_only(pid):
                return True
            if self._engine.is_unbreedable(pid):
                return True
        return False
