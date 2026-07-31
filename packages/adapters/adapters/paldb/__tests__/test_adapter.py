"""Test suite for PalDBAdapter — _dict_to_pal and load_from_json."""

import json
import tempfile
from pathlib import Path

import pytest

from pl_agent.core.schema import Element, Pal, WorkSuitability

# We import the adapter module to test its conversion methods directly
# (no network needed for _dict_to_pal and load_from_json)
from adapters.paldb.adapter import PalDBAdapter


@pytest.fixture
def adapter():
    return PalDBAdapter()


@pytest.fixture
def raw_dict():
    return {
        "id": "Anubis",
        "number": 100,
        "cn_name": "阿努比斯",
        "en_name": "Anubis",
        "combi_rank": 570,
        "element_type1": "Earth",
        "element_type2": "None",
        "rarity": 5,
        "is_wild": False,
        "work_suitability": {
            "handiwork": 4,
            "mining": 4,
            "transporting": 2,
        },
        "image_url": "https://cdn.paldb.cc/anubis.webp",
        "wiki_url": "https://wiki/anubis",
        "spawn_locations": [],
        "_incomplete": False,
    }


class TestDictToPal:
    def test_basic_conversion(self, adapter, raw_dict):
        pal = adapter._dict_to_pal(raw_dict)
        assert pal.id == "Anubis"
        assert pal.number == 100
        assert pal.cn_name == "阿努比斯"
        assert pal.en_name == "Anubis"
        assert pal.combi_rank == 570
        assert pal.rarity == 5
        assert pal.is_wild is False
        assert pal.work_suitability.handiwork == 4
        assert pal.work_suitability.mining == 4
        assert pal._source == "paldb.cc"

    def test_elements_single(self, adapter):
        d = {
            "id": "F",
            "number": 1,
            "cn_name": "火",
            "en_name": "Fire",
            "combi_rank": 100,
            "element_type1": "Fire",
            "element_type2": "None",
            "rarity": 1,
            "is_wild": True,
            "work_suitability": {},
        }
        pal = adapter._dict_to_pal(d)
        assert pal.elements == [Element.FIRE]

    def test_elements_dual(self, adapter):
        d = {
            "id": "FW",
            "number": 2,
            "cn_name": "火水",
            "en_name": "FireWater",
            "combi_rank": 200,
            "element_type1": "Fire",
            "element_type2": "Water",
            "rarity": 1,
            "is_wild": True,
            "work_suitability": {},
        }
        pal = adapter._dict_to_pal(d)
        assert pal.elements == [Element.FIRE, Element.WATER]

    def test_invalid_element_falls_back_to_neutral(self, adapter):
        d = {
            "id": "Bad",
            "number": 3,
            "cn_name": "坏",
            "en_name": "Bad",
            "combi_rank": 300,
            "element_type1": "InvalidType",
            "element_type2": "None",
            "rarity": 1,
            "is_wild": True,
            "work_suitability": {},
        }
        pal = adapter._dict_to_pal(d)
        assert pal.elements == [Element.NEUTRAL]

    def test_missing_cn_name_uses_id(self, adapter):
        d = {
            "id": "NoName",
            "number": 4,
            "en_name": "NoName",
            "combi_rank": 400,
            "element_type1": "Neutral",
            "element_type2": "None",
            "rarity": 1,
            "is_wild": True,
            "work_suitability": {},
        }
        pal = adapter._dict_to_pal(d)
        assert pal.cn_name == "NoName"

    def test_parse_warnings_attached(self, adapter):
        d = {
            "id": "Warn",
            "number": 5,
            "cn_name": "警告",
            "en_name": "Warn",
            "combi_rank": 500,
            "element_type1": "Neutral",
            "element_type2": "None",
            "rarity": 1,
            "is_wild": True,
            "work_suitability": {},
            "_parse_warnings": ["missing spawn data"],
        }
        pal = adapter._dict_to_pal(d)
        assert pal._suspicious is True
        assert "missing spawn data" in pal._suspicious_fields


class TestLoadFromJson:
    def test_load_roundtrip(self, adapter, tmp_path):
        # write test JSON
        data = {
            "Anubis": {
                "id": "Anubis",
                "number": 100,
                "cn_name": "阿努比斯",
                "en_name": "Anubis",
                "combi_rank": 570,
                "elements": ["Earth"],
                "rarity": 5,
                "work_suitability": {"handiwork": 4, "mining": 4},
                "is_wild": False,
                "aliases": [],
                "image_url": None,
                "wiki_url": None,
                "spawn_locations": [],
            },
            "Melpaca": {
                "id": "Melpaca",
                "number": 1,
                "cn_name": "棉悠悠",
                "en_name": "Melpaca",
                "combi_rank": 1460,
                "elements": ["Neutral"],
                "rarity": 1,
                "work_suitability": {"farming": 1},
                "is_wild": True,
                "aliases": [],
                "image_url": None,
                "wiki_url": None,
                "spawn_locations": [],
            },
        }
        path = tmp_path / "pal_data.json"
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

        pals = adapter.load_from_json(path)
        assert len(pals) == 2
        assert {p.id for p in pals} == {"Anubis", "Melpaca"}
        assert all(isinstance(p, Pal) for p in pals)
