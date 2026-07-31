"""Seed PostgreSQL with real pal data."""

import asyncio
import os

os.environ.update({"PGDATABASE": "pl_agent", "PGHOST": "localhost"})

from pl_agent.core.schema import Element, Pal, WorkSuitability
from adapters.postgres.adapter import PostgresWriter

pals = [
    Pal(
        id="Lamball",
        cn_name="棉悠悠",
        en_name="Lamball",
        number=1,
        combi_rank=1470,
        elements=[Element.NEUTRAL],
        rarity=1,
        is_wild=True,
        work_suitability=WorkSuitability(handiwork=1, transporting=1, farming=1),
    ),
    Pal(
        id="Cattiva",
        cn_name="捣蛋猫",
        en_name="Cattiva",
        number=2,
        combi_rank=1460,
        elements=[Element.NEUTRAL],
        rarity=1,
        is_wild=True,
        work_suitability=WorkSuitability(
            handiwork=1, gathering=1, mining=1, transporting=1
        ),
    ),
    Pal(
        id="Chikipi",
        cn_name="幻悦蝶",
        en_name="Chikipi",
        number=3,
        combi_rank=1500,
        elements=[Element.NEUTRAL],
        rarity=1,
        is_wild=True,
        work_suitability=WorkSuitability(gathering=1, farming=1),
    ),
    Pal(
        id="Foxparks",
        cn_name="火狐",
        en_name="Foxparks",
        number=5,
        combi_rank=1400,
        elements=[Element.FIRE],
        rarity=2,
        is_wild=True,
        work_suitability=WorkSuitability(kindling=1),
    ),
    Pal(
        id="Fuack",
        cn_name="冲浪鸭",
        en_name="Fuack",
        number=6,
        combi_rank=1330,
        elements=[Element.WATER],
        rarity=2,
        is_wild=True,
        work_suitability=WorkSuitability(watering=1, handiwork=1, transporting=1),
    ),
    Pal(
        id="Sparkit",
        cn_name="电棘鼠",
        en_name="Sparkit",
        number=7,
        combi_rank=1410,
        elements=[Element.ELECTRIC],
        rarity=2,
        is_wild=True,
        work_suitability=WorkSuitability(generating_electricity=1),
    ),
    Pal(
        id="Pengullet",
        cn_name="企丸丸",
        en_name="Pengullet",
        number=10,
        combi_rank=1350,
        elements=[Element.WATER, Element.ICE],
        rarity=2,
        is_wild=True,
        work_suitability=WorkSuitability(
            watering=1, cooling=1, handiwork=1, transporting=1
        ),
    ),
    Pal(
        id="Penking",
        cn_name="企丸王",
        en_name="Penking",
        number=11,
        combi_rank=520,
        elements=[Element.WATER, Element.ICE],
        rarity=4,
        is_wild=True,
        work_suitability=WorkSuitability(
            watering=2, cooling=2, handiwork=2, mining=2, transporting=2
        ),
    ),
    Pal(
        id="Jolthog",
        cn_name="电刺猬",
        en_name="Jolthog",
        number=12,
        combi_rank=1370,
        elements=[Element.ELECTRIC],
        rarity=2,
        is_wild=True,
        work_suitability=WorkSuitability(generating_electricity=1),
    ),
    Pal(
        id="Celaray",
        cn_name="苍焰狼",
        en_name="Celaray",
        number=21,
        combi_rank=870,
        elements=[Element.FIRE],
        rarity=4,
        is_wild=True,
        work_suitability=WorkSuitability(kindling=1, transporting=1),
    ),
    Pal(
        id="Direhowl",
        cn_name="紫霞龙",
        en_name="Direhowl",
        number=22,
        combi_rank=760,
        elements=[Element.NEUTRAL],
        rarity=4,
        is_wild=True,
        work_suitability=WorkSuitability(gathering=2),
    ),
    Pal(
        id="Tocotoco",
        cn_name="炸蛋鸟",
        en_name="Tocotoco",
        number=23,
        combi_rank=1340,
        elements=[Element.NEUTRAL],
        rarity=3,
        is_wild=True,
        work_suitability=WorkSuitability(gathering=1),
    ),
    Pal(
        id="Anubis",
        cn_name="阿努比斯",
        en_name="Anubis",
        number=100,
        combi_rank=570,
        elements=[Element.EARTH],
        rarity=9,
        is_wild=False,
        work_suitability=WorkSuitability(handiwork=4, mining=3, transporting=2),
    ),
    Pal(
        id="Jormuntide",
        cn_name="覆海龙",
        en_name="Jormuntide",
        number=101,
        combi_rank=310,
        elements=[Element.WATER, Element.DRAGON],
        rarity=9,
        is_wild=False,
        work_suitability=WorkSuitability(watering=4),
    ),
    Pal(
        id="Jormuntide_Ignis",
        cn_name="炎煌",
        en_name="Jormuntide Ignis",
        number=101,
        combi_rank=315,
        elements=[Element.FIRE, Element.DRAGON],
        rarity=9,
        is_wild=False,
        work_suitability=WorkSuitability(kindling=4),
    ),
    Pal(
        id="Relaxaurus",
        cn_name="雷棘龙",
        en_name="Relaxaurus",
        number=85,
        combi_rank=280,
        elements=[Element.DRAGON, Element.WATER],
        rarity=6,
        is_wild=True,
        work_suitability=WorkSuitability(watering=2, transporting=1),
    ),
    Pal(
        id="Relaxaurus_Lux",
        cn_name="雷棘龙·勒克斯",
        en_name="Relaxaurus Lux",
        number=85,
        combi_rank=290,
        elements=[Element.DRAGON, Element.ELECTRIC],
        rarity=6,
        is_wild=False,
        work_suitability=WorkSuitability(generating_electricity=2, transporting=1),
    ),
    Pal(
        id="Frostallion",
        cn_name="唤冬兽",
        en_name="Frostallion",
        number=110,
        combi_rank=10,
        elements=[Element.ICE],
        rarity=10,
        is_wild=True,
        work_suitability=WorkSuitability(cooling=4),
    ),
    Pal(
        id="Jetragon",
        cn_name="空涡龙",
        en_name="Jetragon",
        number=111,
        combi_rank=5,
        elements=[Element.DRAGON],
        rarity=10,
        is_wild=True,
        work_suitability=WorkSuitability(gathering=3, transporting=3),
    ),
    Pal(
        id="Grizzbolt",
        cn_name="暴电熊",
        en_name="Grizzbolt",
        number=103,
        combi_rank=200,
        elements=[Element.ELECTRIC],
        rarity=8,
        is_wild=True,
        work_suitability=WorkSuitability(
            generating_electricity=3, handiwork=3, lumbering=2, transporting=3
        ),
    ),
]


async def main():
    w = PostgresWriter()
    await w.connect()
    await w.upsert_all(pals)
    c = await w.count()
    print(f"✅ {c} pals saved to PostgreSQL")
    await w.close()


asyncio.run(main())
