"""tc-imba adapter (build_bundle) 测试 — 使用 data/tc-imba 真实数据。"""

from pathlib import Path

import pytest

from adapters.tcimba.adapter import build_bundle

DATA_DIR = Path("data/tc-imba")


@pytest.mark.skipif(not (DATA_DIR / "pals.json").exists(), reason="缺少 data/tc-imba 数据")
class TestBuildBundle:
    def test_counts(self):
        b = build_bundle(DATA_DIR)
        c = b.counts()
        assert c["pal"] == 299
        assert c["passive"] == 115
        assert c["item"] == 2433
        assert c["pal_skill"] > 0
        assert c["item_recipe_station"] > c["item_recipe"]  # 多设施拆行

    def test_pal_fields(self):
        b = build_bundle(DATA_DIR)
        sheep = next(p for p in b.pal_raw if p["id"] == "SheepBall")
        assert sheep["cn_name"] == "棉悠悠"
        assert sheep["predator"] is False
        assert sheep["image_url"].startswith("https://resource-palworld.tc-imba.com/")
        assert sheep["wiki_url"].endswith("/pals/SheepBall")

    def test_poppy_lowercase_in_drops(self):
        b = build_bundle(DATA_DIR)
        # 帕鲁掉落可能用小写 poppy，items 用 Poppy — 确认 bundle 里有该掉落
        drop_items = {d["item"] for p in b.pal_raw for d in p.get("drops", [])}
        assert any(di.lower() == "poppy" for di in drop_items)
