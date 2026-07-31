"""Test suite for DataValidator."""

import pytest

from pl_agent.core.schema import Element, Pal, WorkSuitability
from adapters.validator import DataValidator, ValidationResult


def _pal(
    id: str,
    num: int,
    rank: int = 100,
    wild: bool = True,
    rarity: int = 5,
    elements=None,
    cn_name=None,
    **ws,
) -> Pal:
    return Pal(
        id=id,
        number=num,
        cn_name=cn_name or id,
        en_name=id,
        combi_rank=rank,
        elements=elements or [Element.NEUTRAL],
        rarity=rarity,
        is_wild=wild,
        work_suitability=WorkSuitability(**ws),
    )


# ── ValidationResult ───────────────────────────────────────────────


class TestValidationResult:
    def test_has_errors(self):
        r = ValidationResult(errors=["bad"])
        assert r.has_errors is True

    def test_no_errors(self):
        r = ValidationResult(warnings=["meh"])
        assert r.has_errors is False

    def test_is_clean_true(self):
        r = ValidationResult()
        assert r.is_clean is True

    def test_is_clean_false_with_errors(self):
        r = ValidationResult(errors=["e"])
        assert r.is_clean is False

    def test_is_clean_false_with_warnings(self):
        r = ValidationResult(warnings=["w"])
        assert r.is_clean is False


# ── DataValidator ──────────────────────────────────────────────────


class TestDataValidator:
    @pytest.fixture
    def v(self):
        return DataValidator()

    def test_clean_pals_pass(self, v):
        pals = [
            _pal("a", 1, rank=100),
            _pal("b", 2, rank=200),
            _pal("c", 3, rank=300),
            _pal("d", 4, rank=400),
        ]
        r = v.validate(pals)
        assert r.has_errors is False
        assert r.is_clean is True

    # V1-V2: uniqueness
    def test_duplicate_number(self, v):
        pals = [_pal("a", 1), _pal("b", 1)]
        r = v.validate(pals)
        assert any("V1" in e for e in r.errors)

    def test_duplicate_id(self, v):
        pals = [_pal("a", 1), _pal("a", 2)]
        r = v.validate(pals)
        assert any("V2" in e for e in r.errors)

    # V3: combi_rank > 0
    def test_combi_rank_zero_or_negative(self, v):
        pals = [
            _pal("a", 1, rank=0),
            _pal("b", 2, rank=-5),
        ]
        r = v.validate(pals)
        assert len(r.errors) >= 2

    # V4: empty cn_name
    def test_empty_cn_name(self, v):
        pal = _pal("a", 1, cn_name=None)
        pal.cn_name = ""  # bypass fixture default
        r = v.validate([pal])
        assert any("V4" in e for e in r.errors)

    # V5: elements
    def test_empty_elements(self, v):
        pal = _pal("a", 1, elements=None)
        pal.elements = []  # bypass fixture default
        r = v.validate([pal])
        assert any("V5" in e for e in r.errors)

    # V6: rarity range
    def test_rarity_out_of_range_warns(self, v):
        pals = [_pal("a", 1, rarity=15)]
        r = v.validate(pals)
        assert any("V6" in e for e in r.warnings)

    def test_rarity_zero_warns(self, v):
        pals = [_pal("a", 1, rarity=0)]
        r = v.validate(pals)
        assert any("V6" in e for e in r.warnings)

    # V7: work suitability
    def test_work_level_above_10_warns(self, v):
        pals = [_pal("a", 1, handiwork=15)]
        r = v.validate(pals)
        assert any("V7" in e for e in r.warnings)

    # V8: wild ratio
    def test_low_wild_ratio_warns(self, v):
        pals = [
            _pal("a", 1, wild=True),
            _pal("b", 2, wild=False),
            _pal("c", 3, wild=False),
            _pal("d", 4, wild=False),
        ]
        r = v.validate(pals)
        assert any("V8" in e for e in r.warnings)

    # V10: rank jump
    def test_large_rank_jump_info(self, v):
        pals = [
            _pal("a", 1, rank=100),
            _pal("b", 2, rank=700),  # jump 600 > 500
        ]
        r = v.validate(pals)
        assert any("V10" in e for e in r.info)
