"""Tests for paldb.cc HTML parser."""

from adapters.paldb.parser import PalDBParser  # noqa: E402

# sample HTML fragment mimicking a real paldb.cc Anubis page
SAMPLE_ANUBIS_HTML = """
<html>
<body>
TAnubisiconnormal 阿努比斯 #139
CombiRank 480
ElementType1 Earth
Rarity 10
<a href="/cn/Handiwork">手工作业</a> Lv6  <a href="/cn/Mining">采矿</a> Lv6  <a href="/cn/Transporting">搬运</a> Lv4
Code Anubis
Spawner:
TAnubisiconnormal 阿努比斯 | Lv. 68–72 | desertisland_1 (Wild)
<img src="https://cdn.paldb.cc/image/Pal/Texture/PalIcon/Normal/T_Anubis_icon_normal.webp"/>
<a href="https://palworld.fandom.com/wiki/Anubis">Wiki</a>
</body>
</html>
"""


class TestPalDBParser:
    """Parser unit tests."""

    def setup_method(self):
        self.parser = PalDBParser()

    def test_parse_anubis_basic(self):
        """should parse all basic fields from Anubis page."""
        result = self.parser.parse(SAMPLE_ANUBIS_HTML, "Anubis")

        assert result["id"] == "Anubis"
        assert result["cn_name"] == "阿努比斯"
        assert result["number"] == 139
        assert result["combi_rank"] == 480
        assert result["element_type1"] == "Earth"
        assert result["rarity"] == 10
        assert result["is_wild"] is True
        assert result["en_name"] == "Anubis"

    def test_parse_work_suitability(self):
        """should extract work suitabilities with correct levels."""
        result = self.parser.parse(SAMPLE_ANUBIS_HTML, "Anubis")

        ws = result["work_suitability"]
        assert ws["handiwork"] == 6
        assert ws["mining"] == 6
        assert ws["transporting"] == 4
        # should not have false positives
        assert ws.get("kindling", 0) == 0

    def test_parse_image_url(self):
        """should extract cdn.paldb.cc image."""
        result = self.parser.parse(SAMPLE_ANUBIS_HTML, "Anubis")
        assert "cdn.paldb.cc" in (result.get("image_url") or "")

    def test_parse_wild_false(self):
        """is_wild should be false when no (Wild) marker."""
        html_no_wild = SAMPLE_ANUBIS_HTML.replace("(Wild)", "")
        result = self.parser.parse(html_no_wild, "Anubis")
        assert result["is_wild"] is False

    def test_parse_missing_combi_rank_raises_error(self):
        """should raise ParseError when CombiRank is missing."""
        from pl_agent.core.errors import ParseError

        html = SAMPLE_ANUBIS_HTML.replace("CombiRank 480", "")
        try:
            self.parser.parse(html, "Anubis")
            assert False, "should have raised"
        except ParseError as e:
            assert e.field == "combi_rank"
