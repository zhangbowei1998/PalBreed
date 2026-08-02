"""tc-imba parser 单元测试（使用 fixture 小样本，不依赖外部数据）。"""

import pytest

from adapters.tcimba import parser


@pytest.fixture
def pals_json():
    return {
        "pals": [
            {
                "id": "SheepBall",
                "zukanIndex": 1,
                "zukanIndexSuffix": "",
                "icon": "T_SheepBall_icon_normal",
                "elements": ["Normal"],
                "genus": "Humanoid",
                "size": "XS",
                "rarity": 1,
                "egg": "PalEgg_Normal_01",
                "nocturnal": False,
                "reaction": "Friendly",
                "bestWork": "MonsterFarm",
                "summonable": False,
                "predator": False,
                "stats": {"hp": 70, "meleeAttack": 70, "shotAttack": 70, "captureRate": 1.5},
                "friendship": {"hp": 5.5, "shotAttack": 3.7},
                "enemyScaling": {"receiveDamage": 2},
                "work": {"Handcraft": 1, "Transport": 1, "MonsterFarm": 2},
                "activeSkills": [
                    {"wazaId": "AirCanon", "level": 1, "element": "Normal",
                     "category": "Shot", "power": 30, "effect": {"type": "Muddy", "value": 100}},
                    {"wazaId": "AirCanon", "level": 1, "element": "Normal",
                     "category": "Shot", "power": 30},
                ],
                "passives": ["CraftSpeed_up1"],
                "drops": [{"item": "Wool", "rate": 100, "min": 1, "max": 2}],
                "bossDrops": [],
                "summonLevel": None,
                "summonMaterials": [],
            },
            {
                "id": "PinkCat",
                "zukanIndex": 2,
                "elements": ["Fire"],
                "work": {},
                "activeSkills": [{"wazaId": "AirBlade", "level": 7, "element": "Normal",
                                  "category": "Shot", "power": 70}],
                "passives": [],
                "drops": [],
                "bossDrops": [],
                "summonMaterials": [],
            },
        ]
    }


@pytest.fixture
def breeding_json():
    return {
        "pals": [
            {"id": "SheepBall", "rank": 3050, "breedChild": True},
            {"id": "PinkCat", "rank": 4200, "breedChild": False},
        ],
        "combos": [{"a": "SheepBall", "b": "SheepBall", "c": "SheepBall"}],
    }


@pytest.fixture
def zh():
    return {
        "SheepBall": {"name": "棉悠悠", "description": "毛茸茸", "partnerSkill": "技能"},
        "PinkCat": {"name": "捣蛋猫"},
    }


@pytest.fixture
def en():
    return {"SheepBall": {"name": "Lamball"}, "PinkCat": {"name": "Chikipi"}}


@pytest.fixture
def zh_skills():
    return {"AirCanon": {"name": "空气弹", "description": "射空气"}, "AirBlade": {"name": "真空刃"}}


class TestParsePalRaw:
    def test_basic_fields(self, pals_json, breeding_json, zh, en):
        out = parser.parse_pal_raw(pals_json, breeding_json, zh, en)
        assert len(out) == 2
        sheep = next(p for p in out if p["id"] == "SheepBall")
        assert sheep["cn_name"] == "棉悠悠"
        assert sheep["combi_rank"] == 3050
        assert sheep["breed_child"] is True
        assert sheep["predator"] is False
        assert sheep["stats"]["hp"] == 70

    def test_element_work_mapping(self, pals_json, breeding_json, zh, en):
        sheep = next(p for p in parser.parse_pal_raw(pals_json, breeding_json, zh, en)
                     if p["id"] == "SheepBall")
        # Normal -> Neutral, work 键映射
        assert sheep["elements"] == ["Neutral"]
        assert sheep["work_suitability"] == {"handiwork": 1, "transporting": 1, "farming": 2}
        assert sheep["best_work"] == "farming"

    def test_none_element_skipped(self, pals_json, breeding_json, zh, en):
        # PinkCat 无 None 元素测试：直接断言元素为 Fire
        cat = next(p for p in parser.parse_pal_raw(pals_json, breeding_json, zh, en)
                   if p["id"] == "PinkCat")
        assert cat["elements"] == ["Fire"]


class TestParseSkills:
    def test_dedup_and_pal_skills(self, pals_json, breeding_json, zh, en, zh_skills):
        raw = parser.parse_pal_raw(pals_json, breeding_json, zh, en)
        skills, pal_skills = parser.parse_skills(raw, zh_skills)
        # 重复 wazaId 只保留一个 skill
        assert len(skills) == 2
        air = next(s for s in skills if s["waza_id"] == "AirCanon")
        assert air["cn_name"] == "空气弹"
        assert air["effect_type"] == "Muddy"
        assert air["effect_value"] == 100
        # pal_skill 含重复（同一帕鲁同技能出现两次也记录）
        assert len(pal_skills) == 3


class TestParsePassives:
    def test_effects_invokes(self):
        data = {"passives": [
            {"id": "CraftSpeed_up3", "rank": 4, "lotteryWeight": 5,
             "effects": [{"type": "CraftSpeed", "value": 75, "target": "ToSelf"}],
             "invoke": ["always", "riding"]},
            {"id": "Rare", "rank": 3, "effects": [], "invoke": ["always"]},
        ]}
        zh_p = {"CraftSpeed_up3": {"name": "卓绝技艺"}, "Rare": {"name": "稀有"}}
        passives, effects, invokes = parser.parse_passives(data, zh_p)
        assert len(passives) == 2
        assert passives[0]["cn_name"] == "卓绝技艺"
        assert passives[0]["lottery_weight"] == 5
        # invoke[] 数组拆行
        assert len(invokes) == 3
        assert invokes[0] == {"passive_id": "CraftSpeed_up3", "invoke": "always"}
        assert invokes[1] == {"passive_id": "CraftSpeed_up3", "invoke": "riding"}
        # effects
        assert effects[0]["effect_type"] == "CraftSpeed"
        assert effects[0]["effect_value"] == 75


class TestParseItems:
    def test_recipes_stations_materials_sources(self):
        data = {"items": [
            {"id": "Money", "typeA": "Material", "typeB": "Money", "weight": 0.2,
             "handcraft": False,
             "recipe": {"work": 2000000, "productCount": 20000,
                        "craftedAt": ["Factory_Money", "Factory_Second"],
                        "materials": [{"item": "CopperIngot", "count": 30}]},
             "sources": [{"kind": "chest", "area": "Forest", "grade": 1, "chance": 100},
                          {"kind": "merchant", "merchant": "Caravan"}]},
        ]}
        zh_i = {"Money": {"name": "金币", "description": "钱"}}
        items, recipes, stations, materials, sources = parser.parse_items(data, zh_i)
        assert len(items) == 1
        assert items[0]["cn_name"] == "金币"
        assert items[0]["weight"] == 0.2
        # craftedAt[] 拆行
        assert len(stations) == 2
        assert stations[0]["station"] == "Factory_Money"
        # materials
        assert materials[0]["material_item"] == "CopperIngot"
        assert materials[0]["count"] == 30
        # sources
        assert len(sources) == 2
        assert sources[1]["kind"] == "merchant"
