"""Data loader — loads canonical Pal data from JSON into memory."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from pl_agent.core.schema import Pal

logger = logging.getLogger(__name__)


class DataLoader:
    """加载 processed JSON 数据到内存, 提供多维度索引."""

    def __init__(self, data_dir: str | Path = "data/processed"):
        self.data_dir = Path(data_dir)
        self._pals: dict[str, Pal] = {}                # id → Pal
        self._pals_by_number: dict[int, Pal] = {}       # number → Pal
        self._pals_by_rank: list[Pal] = []              # sorted by combi_rank
        self._loaded = False

    # ------------------------------------------------------------------
    # load
    # ------------------------------------------------------------------

    def load(self, filepath: str | Path | None = None) -> int:
        """加载 pal_data.json 到内存.

        Returns:
            加载的帕鲁数量.
        """
        path = Path(filepath) if filepath else self.data_dir / "pal_data.json"
        if not path.exists():
            raise FileNotFoundError(
                f"pal_data.json not found at {path}. "
                f"Run 'adapter.build_and_save()' first to generate it."
            )

        raw = json.loads(path.read_text(encoding="utf-8"))
        pals = [Pal.from_dict(p) for p in raw.values()]

        self._pals = {p.id: p for p in pals}
        self._pals_by_number = {p.number: p for p in pals}
        self._pals_by_rank = sorted(pals, key=lambda p: p.combi_rank)
        self._loaded = True

        logger.info(
            "loaded %d pals (wild: %d) from %s",
            len(pals), self.wild_count(), path,
        )
        return len(pals)

    # ------------------------------------------------------------------
    # query
    # ------------------------------------------------------------------

    def get_by_id(self, pal_id: str) -> Pal | None:
        """按 ID 查询."""
        self._ensure_loaded()
        return self._pals.get(pal_id)

    def get_by_number(self, number: int) -> Pal | None:
        """按图鉴编号查询."""
        self._ensure_loaded()
        return self._pals_by_number.get(number)

    def get_all(self) -> list[Pal]:
        """获取所有帕鲁 (不排序)."""
        self._ensure_loaded()
        return list(self._pals.values())

    def get_all_sorted_by_rank(self) -> list[Pal]:
        """按 CombiRank 升序排列."""
        self._ensure_loaded()
        return list(self._pals_by_rank)

    def get_wild_pals(self) -> list[Pal]:
        """获取所有野外可捕获的基础帕鲁."""
        self._ensure_loaded()
        return [p for p in self._pals.values() if p.is_wild]

    def find_nearest_rank(self, target_rank: float) -> Pal:
        """找到 CombiRank 最接近 target_rank 的帕鲁."""
        self._ensure_loaded()
        if not self._pals_by_rank:
            raise ValueError("no pals loaded")

        nearest = self._pals_by_rank[0]
        min_diff = abs(nearest.combi_rank - target_rank)
        for p in self._pals_by_rank[1:]:
            diff = abs(p.combi_rank - target_rank)
            if diff < min_diff:
                nearest = p
                min_diff = diff
            elif diff > min_diff:
                # since list is sorted, diff will only increase from here
                break
        return nearest

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def wild_count(self) -> int:
        return sum(1 for p in self._pals.values() if p.is_wild)

    def _ensure_loaded(self) -> None:
        if not self._loaded:
            self.load()

    def __len__(self) -> int:
        return len(self._pals)
