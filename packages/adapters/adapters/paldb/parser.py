"""paldb.cc HTML parser — extracts structured fields from raw HTML."""

from __future__ import annotations

import logging
import re
from pathlib import Path

from bs4 import BeautifulSoup

from pl_agent.core.errors import ParseError

logger = logging.getLogger(__name__)


class PalDBParser:
    """paldb.cc HTML 解析器 — 从原始 HTML 提取字段字典.

    字段提取映射:
      cn_name + number:  页面标题 "{中文名} #{编号}"
      en_name:           Code 字段
      combi_rank:        CombiRank {数值}
      work_suitability:  {工种} Lv{等级}
      elements:          ElementType1 {属性} [, ElementType2 {属性}]
      rarity:            Rarity {数值}
      is_wild:           Spawner 区域含 "(Wild)" 标记
      image_url:         cdn.paldb.cc/image/...webp
    """

    # 工种中文关键词 → schema 字段名
    WORK_KEYWORDS: dict[str, str] = {
        "手工作业": "handiwork",
        "生火": "kindling",
        "浇水": "watering",
        "播种": "planting",
        "发电": "generating_electricity",
        "采集": "gathering",
        "伐木": "lumbering",
        "采矿": "mining",
        "冷却": "cooling",
        "制药": "medicine",
        "搬运": "transporting",
        "牧场": "farming",
    }

    # element names in paldb.cc → schema Element enum values
    _ELEMENT_ALIASES: dict[str, str] = {
        "Fire": "Fire",
        "Water": "Water",
        "Grass": "Grass",
        "Earth": "Earth",
        "Electric": "Electric",
        "Ice": "Ice",
        "Dragon": "Dragon",
        "Dark": "Dark",
        "Neutral": "Neutral",
        "Leaf": "Grass",
        "Ground": "Earth",
        "Thunder": "Electric",
        "Normal": "Neutral",
        "None": "Neutral",
    }

    def parse(self, html: str, internal_id: str) -> dict:
        """解析单个帕鲁页面 HTML.

        Returns:
            dict ready for PalDBAdapter to convert to schema.Pal.
        Raises:
            ParseError: on critical field (P0) failure.
        """
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text(separator="\n")
        warnings: list[str] = []

        result: dict = {"id": internal_id}
        result["_parse_warnings"] = warnings
        result["_source"] = "paldb.cc"

        # ── P0 fields (must succeed) ────────────────────────────

        # cn_name + number from page title
        cn_name, number = self._extract_title(text, internal_id)
        if not cn_name:
            raise ParseError(internal_id, "cn_name")
        if not number:
            raise ParseError(internal_id, "number")
        result["cn_name"] = cn_name
        result["number"] = number

        # combi_rank
        cr = self._extract_combi_rank(text)
        if cr is None:
            raise ParseError(internal_id, "combi_rank")
        result["combi_rank"] = cr

        # elements
        result["element_type1"] = self._extract_element1(text, internal_id, warnings)
        result["element_type2"] = self._extract_element2(text)

        # is_wild
        result["is_wild"] = self._extract_is_wild(text)

        # ── P1 fields (best effort) ─────────────────────────────

        # en_name from Code field
        result["en_name"] = self._extract_code_name(text, internal_id, cn_name)

        # rarity
        result["rarity"] = self._extract_rarity(text, internal_id, warnings)

        # work suitability
        result["work_suitability"] = self._extract_work_suitability(text)

        # ── P2 fields (optional) ────────────────────────────────

        result["image_url"] = self._extract_image_url(soup, internal_id, warnings)
        result["wiki_url"] = self._extract_wiki_url(soup)
        result["spawn_locations"] = self._extract_spawn_locations(text)

        return result

    # ------------------------------------------------------------------
    # field extractors
    # ------------------------------------------------------------------

    def _extract_title(
        self, text: str, internal_id: str
    ) -> tuple[str | None, int | None]:
        """extract cn_name and number from page header.
        pattern: '{中文名} #{编号}'   e.g. '阿努比斯 #139'
        """
        # look for the title pattern: Chinese chars followed by #digits
        m = re.search(r"([^\n#]+?)\s*#(\d+)", text)
        if not m:
            return None, None
        name = m.group(1).strip()
        # clean up internal icon prefix like "TAnubisiconnormal "
        name = re.sub(r"^T\w*icon\w*\s*", "", name).strip()
        number = int(m.group(2))
        return name, number

    def _extract_combi_rank(self, text: str) -> int | None:
        """CombiRank {数值}"""
        m = re.search(r"CombiRank\s+(\d+)", text)
        return int(m.group(1)) if m else None

    def _extract_element1(
        self,
        text: str,
        internal_id: str,
        warnings: list[str],
    ) -> str:
        """ElementType1 {属性}"""
        m = re.search(r"ElementType1\s+(\w+)", text)
        if m:
            raw = m.group(1)
            mapped = self._ELEMENT_ALIASES.get(raw, raw)
            return mapped
        warnings.append(f"{internal_id}: ElementType1 not found")
        return "Neutral"

    def _extract_element2(self, text: str) -> str | None:
        """ElementType2 {属性} (双属性帕鲁)"""
        m = re.search(r"ElementType2\s+(\w+)", text)
        if m:
            raw = m.group(1)
            return self._ELEMENT_ALIASES.get(raw, raw)
        return None

    def _extract_rarity(
        self,
        text: str,
        internal_id: str,
        warnings: list[str],
    ) -> int:
        """Rarity {数值}"""
        m = re.search(r"Rarity\s+(\d+)", text)
        if m:
            r = int(m.group(1))
            if not (1 <= r <= 10):
                warnings.append(f"{internal_id}: rarity={r} outside 1-10")
            return r
        warnings.append(f"{internal_id}: rarity not found, defaulting to 1")
        return 1

    def _extract_is_wild(self, text: str) -> bool:
        """check Spawner area for '(Wild)' marker"""
        return "(Wild)" in text

    def _extract_code_name(
        self,
        text: str,
        internal_id: str,
        cn_name: str | None,
    ) -> str | None:
        """Code {英文名} — the official English name."""
        m = re.search(r"Code\s+(\w+)", text)
        if m:
            return m.group(1)
        # fallback: try to find an english name pattern near the title
        fallback = re.search(rf'{re.escape(cn_name or "")}\s+(\w+)\s+\#', text)
        if fallback:
            return fallback.group(1)
        return None

    def _extract_work_suitability(self, text: str) -> dict[str, int]:
        """{工种} Lv{等级} — 遍历 12 种工种匹配"""
        result: dict[str, int] = {}
        for cn_keyword, field_name in self.WORK_KEYWORDS.items():
            m = re.search(rf"{cn_keyword}\s+Lv(\d+)", text)
            if m:
                result[field_name] = int(m.group(1))
        return result

    def _extract_image_url(
        self,
        soup: BeautifulSoup,
        internal_id: str,
        warnings: list[str],
    ) -> str | None:
        """first cdn.paldb.cc image"""
        for img in soup.find_all("img"):
            src = img.get("src", "")
            if "cdn.paldb.cc/image" in src:
                if not src.startswith("http"):
                    src = "https:" + src if src.startswith("//") else f"https://{src}"
                return src
        warnings.append(f"{internal_id}: image_url not found")
        return None

    def _extract_wiki_url(self, soup: BeautifulSoup) -> str | None:
        """fandom wiki link"""
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "palworld.fandom.com/wiki" in href:
                return href
        return None

    def _extract_spawn_locations(self, text: str) -> list[str]:
        """extract spawn location names from Spawner section"""
        locations: list[str] = []
        # match lines after 'Spawner' that contain location patterns
        spawner_section = re.search(
            r"Spawner.*?\n(.*?)(?=\n\S|\Z)",
            text,
            re.DOTALL,
        )
        if not spawner_section:
            return locations
        section_text = spawner_section.group(0)
        # extract location names like "desertisland_1" or "worldtree_9_55_WorldTreeAura"
        for m in re.finditer(r"\|\s*([a-zA-Z_][a-zA-Z0-9_]*)", section_text):
            loc = m.group(1).strip()
            if loc and len(loc) > 2:
                locations.append(loc)
        return locations

    # ------------------------------------------------------------------
    # batch parse
    # ------------------------------------------------------------------

    def parse_all(
        self,
        pages_dir: str | Path,
        pal_list: list[dict[str, str | int]],
    ) -> list[dict]:
        """批量解析所有已下载的 HTML 页面.

        Args:
            pages_dir: 存放 .html 文件的目录.
            pal_list: 帕鲁列表 (用于关联 internal_id).

        Returns:
            解析成功的 dict 列表.
        """
        pages_dir = Path(pages_dir)
        results: list[dict] = []
        failed: list[str] = []

        for pal in pal_list:
            pid = str(pal["internal_id"])
            html_path = pages_dir / f"{pid}.html"
            if not html_path.exists():
                logger.warning("HTML not found for %s, skipping", pid)
                failed.append(pid)
                continue

            try:
                html = html_path.read_text(encoding="utf-8")
                parsed = self.parse(html, pid)
                # carry over cn_name from pal_list if not parsed
                if not parsed.get("cn_name") and pal.get("cn_name"):
                    parsed["cn_name"] = pal["cn_name"]
                results.append(parsed)
                logger.debug("parsed %s (%s)", pid, parsed.get("cn_name", "?"))
            except ParseError as e:
                logger.error("parse error for %s: %s", pid, e)
                failed.append(pid)
            except Exception as e:
                logger.exception("unexpected error parsing %s: %s", pid, e)
                failed.append(pid)

        logger.info(
            "parse_all: %d success, %d failed",
            len(results),
            len(failed),
        )
        if failed:
            logger.warning("failed pal IDs: %s", ", ".join(failed))

        return results
