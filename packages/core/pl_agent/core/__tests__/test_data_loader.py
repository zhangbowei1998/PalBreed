"""Test suite for DataLoader — JSON → memory loading with multi-index."""

import json
import tempfile
from pathlib import Path

import pytest

from pl_agent.core.data_loader import DataLoader
from pl_agent.core.schema import Element, Pal, WorkSuitability

# ── fixtures ──────────────────────────────────────────────────────


def _make_pal(id: str, number: int, rank: int, wild: bool = True, **ws) -> Pal:
    return Pal(
        id=id,
        number=number,
        cn_name=id,
        en_name=id,
        combi_rank=rank,
        elements=[Element.NEUTRAL],
        rarity=1,
        is_wild=wild,
        work_suitability=WorkSuitability(**ws),
    )


@pytest.fixture
def sample_pals() -> list[Pal]:
    return [
        _make_pal("a", 1, 100, wild=True, handiwork=3),
        _make_pal("b", 2, 200, wild=True),
        _make_pal("c", 3, 300, wild=False, mining=5),
        _make_pal("d", 4, 150, wild=True, kindling=2),
    ]


@pytest.fixture
def pal_json(sample_pals, tmp_path) -> Path:
    data = {p.id: p.to_dict() for p in sample_pals}
    path = tmp_path / "pal_data.json"
    path.write_text(json.dumps(data, ensure_ascii=False))
    return path


# ── load ──────────────────────────────────────────────────────────


class TestDataLoaderLoad:
    def test_load_returns_count(self, pal_json):
        loader = DataLoader()
        n = loader.load(pal_json)
        assert n == 4

    def test_load_missing_file_raises(self):
        loader = DataLoader()
        with pytest.raises(FileNotFoundError):
            loader.load("nonexistent.json")

    def test_len_after_load(self, pal_json):
        loader = DataLoader()
        loader.load(pal_json)
        assert len(loader) == 4


# ── query ─────────────────────────────────────────────────────────


class TestDataLoaderQuery:
    def test_get_by_id(self, pal_json):
        loader = DataLoader()
        loader.load(pal_json)
        assert loader.get_by_id("a").cn_name == "a"
        assert loader.get_by_id("z") is None

    def test_get_by_number(self, pal_json):
        loader = DataLoader()
        loader.load(pal_json)
        assert loader.get_by_number(2).id == "b"
        assert loader.get_by_number(99) is None

    def test_get_all(self, pal_json):
        loader = DataLoader()
        loader.load(pal_json)
        pals = loader.get_all()
        assert len(pals) == 4

    def test_get_all_sorted_by_rank(self, pal_json):
        loader = DataLoader()
        loader.load(pal_json)
        pals = loader.get_all_sorted_by_rank()
        assert [p.id for p in pals] == ["a", "d", "b", "c"]

    def test_get_wild_pals(self, pal_json):
        loader = DataLoader()
        loader.load(pal_json)
        wild = loader.get_wild_pals()
        assert len(wild) == 3
        assert all(p.is_wild for p in wild)

    def test_wild_count(self, pal_json):
        loader = DataLoader()
        loader.load(pal_json)
        assert loader.wild_count() == 3

    def test_find_nearest_rank_exact(self, pal_json):
        loader = DataLoader()
        loader.load(pal_json)
        p = loader.find_nearest_rank(100)
        assert p.id == "a"

    def test_find_nearest_rank_between(self, pal_json):
        loader = DataLoader()
        loader.load(pal_json)
        # d:150, b:200 both equally close to 175. First wins.
        p = loader.find_nearest_rank(175)
        assert p.id == "d"

    def test_find_nearest_rank_before_first(self, pal_json):
        loader = DataLoader()
        loader.load(pal_json)
        p = loader.find_nearest_rank(0)
        assert p.id == "a"

    def test_find_nearest_rank_after_last(self, pal_json):
        loader = DataLoader()
        loader.load(pal_json)
        p = loader.find_nearest_rank(999)
        assert p.id == "c"

    def test_find_nearest_rank_empty_raises(self):
        loader = DataLoader()
        loader._loaded = True
        loader._pals_by_rank = []
        with pytest.raises(ValueError, match="no pals loaded"):
            loader.find_nearest_rank(100)


# ── ensure_loaded ─────────────────────────────────────────────────


def test_ensure_loaded_raises_if_not_loaded(tmp_path):
    loader = DataLoader(data_dir=str(tmp_path))
    with pytest.raises(FileNotFoundError):
        loader.get_by_id("any")


def test_init_default_dir():
    loader = DataLoader()
    assert loader.data_dir == Path("data/processed")
