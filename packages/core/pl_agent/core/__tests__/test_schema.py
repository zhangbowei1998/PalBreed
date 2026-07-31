"""Test suite for schema models — WorkSuitability, BreedingRules, Pal roundtrip."""

import pytest

from pl_agent.core.schema import (
    BreedingRules,
    Element,
    MutationRule,
    Pal,
    SelfOnly,
    SpecialCombination,
    Unbreedable,
    WorkSuitability,
)

# ── WorkSuitability ────────────────────────────────────────────────


class TestWorkSuitability:
    def test_max_level(self):
        ws = WorkSuitability(handiwork=4, mining=6, farming=1)
        assert ws.max_level() == 6

    def test_max_level_all_zero(self):
        ws = WorkSuitability()
        assert ws.max_level() == 0

    def test_has_type_true(self):
        ws = WorkSuitability(handiwork=4)
        assert ws.has_type("handiwork") is True

    def test_has_type_false(self):
        ws = WorkSuitability(handiwork=4)
        assert ws.has_type("mining") is False

    def test_has_type_zero(self):
        ws = WorkSuitability(handiwork=0)
        assert ws.has_type("handiwork") is False

    def test_non_zero_filters_zeros(self):
        ws = WorkSuitability(handiwork=4, mining=0, kindling=2)
        d = ws.non_zero()
        assert d == {"handiwork": 4, "kindling": 2}

    def test_non_zero_all_zero(self):
        ws = WorkSuitability()
        assert ws.non_zero() == {}

    def test_to_dict_same_as_non_zero(self):
        ws = WorkSuitability(handiwork=3, farming=1)
        assert ws.to_dict() == ws.non_zero()

    def test_from_dict_partial(self):
        ws = WorkSuitability.from_dict({"handiwork": 5, "mining": 3})
        assert ws.handiwork == 5
        assert ws.mining == 3
        assert ws.kindling == 0  # missing → default 0

    def test_from_dict_empty(self):
        ws = WorkSuitability.from_dict({})
        assert ws.max_level() == 0

    def test_roundtrip(self):
        ws = WorkSuitability(handiwork=4, transporting=3, farming=1)
        ws2 = WorkSuitability.from_dict(ws.to_dict())
        assert ws2.handiwork == 4
        assert ws2.transporting == 3
        assert ws2.mining == 0


# ── Pal roundtrip ──────────────────────────────────────────────────


class TestPalRoundtrip:
    def test_to_dict_excludes_internal_fields(self, sample_pal):
        d = sample_pal.to_dict()
        assert "_incomplete" not in d
        assert "_source" not in d
        assert "_suspicious" not in d

    def test_roundtrip(self, sample_pal):
        d = sample_pal.to_dict()
        pal2 = Pal.from_dict(d)
        assert pal2.id == sample_pal.id
        assert pal2.cn_name == sample_pal.cn_name
        assert pal2.work_suitability.handiwork == 4

    def test_from_dict_with_string_elements(self):
        d = {
            "id": "test",
            "number": 1,
            "cn_name": "测试",
            "en_name": "Test",
            "combi_rank": 500,
            "elements": ["Fire", "Earth"],
            "rarity": 3,
            "is_wild": True,
            "work_suitability": {"handiwork": 2},
        }
        pal = Pal.from_dict(d)
        assert pal.elements == [Element.FIRE, Element.EARTH]

    def test_from_dict_minimal(self):
        d = {
            "id": "min",
            "number": 99,
            "cn_name": "最小",
            "en_name": "Min",
            "combi_rank": 100,
            "elements": [],
            "is_wild": False,
        }
        pal = Pal.from_dict(d)
        assert pal.rarity == 1  # default
        assert pal.aliases == []


# ── BreedingRules ──────────────────────────────────────────────────


class TestBreedingRules:
    def test_to_dict(self):
        rules = BreedingRules(
            game_version="v1.0",
            last_updated="2026-01-01",
            special_combinations=[
                SpecialCombination("a", "b", "c", note="test"),
            ],
            self_only=[SelfOnly("legend")],
            unbreedable=[Unbreedable("boss")],
            mutations=[MutationRule("x", "y", "z")],
        )
        d = rules.to_dict()
        assert d["game_version"] == "v1.0"
        assert len(d["special_combinations"]) == 1
        assert d["special_combinations"][0]["child"] == "c"
        assert d["unbreedable"] == [{"pal_id": "boss", "note": ""}]

    def test_from_dict_minimal(self):
        d = {
            "game_version": "v2.0",
            "last_updated": "2026-07-31",
        }
        rules = BreedingRules.from_dict(d)
        assert rules.game_version == "v2.0"
        assert rules.special_combinations == []
        assert rules.self_only == []

    def test_from_dict_full(self):
        d = {
            "game_version": "v1.0",
            "last_updated": "2026-01-01",
            "special_combinations": [
                {"parent_a": "a", "parent_b": "b", "child": "c"},
            ],
            "self_only": [{"pal_id": "x"}],
            "unbreedable": [{"pal_id": "y"}],
            "mutations": [{"parent_a": "m1", "parent_b": "m2", "child": "m3"}],
        }
        rules = BreedingRules.from_dict(d)
        assert len(rules.special_combinations) == 1
        assert rules.special_combinations[0].child == "c"
        assert rules.self_only[0].pal_id == "x"
        assert rules.mutations[0].child == "m3"

    def test_roundtrip(self):
        rules = BreedingRules(
            game_version="v1.0",
            last_updated="2026-01-01",
            special_combinations=[SpecialCombination("a", "b", "c")],
            self_only=[SelfOnly("legend")],
        )
        d = rules.to_dict()
        rules2 = BreedingRules.from_dict(d)
        assert rules2.game_version == "v1.0"
        assert rules2.special_combinations[0].parent_a == "a"
        assert rules2.self_only[0].pal_id == "legend"


# ── fixtures ───────────────────────────────────────────────────────


@pytest.fixture
def sample_pal() -> Pal:
    return Pal(
        id="test_pal",
        number=42,
        cn_name="测试帕鲁",
        en_name="TestPal",
        combi_rank=500,
        elements=[Element.NEUTRAL],
        rarity=5,
        is_wild=True,
        work_suitability=WorkSuitability(handiwork=4, mining=2),
        aliases=["alias1"],
        image_url="http://img.png",
        wiki_url="http://wiki",
        spawn_locations=["zone1"],
    )
