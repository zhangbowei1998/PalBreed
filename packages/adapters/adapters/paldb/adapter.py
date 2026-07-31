"""paldb.cc adapter — orchestrates scraper + parser, outputs canonical schema.Pal."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from pl_agent.core.schema import BreedingRules, Element, Pal, WorkSuitability

from ..base import BreedingRulesAdapter, PalDataSourceAdapter
from ..validator import DataValidator
from .parser import PalDBParser
from .scraper import PalDBScraper

logger = logging.getLogger(__name__)


class PalDBAdapter(PalDataSourceAdapter):
    """paldb.cc 数据源适配器.

    完整流程:
      1. Scraper.fetch_pal_list()     → 获取帕鲁列表
      2. Scraper.fetch_all()          → 下载所有 HTML
      3. Parser.parse_all()           → 解析 HTML → dict 列表
      4. _dict_to_pal()               → dict → schema.Pal
      5. Validator.validate()         → 数据校验
      6. save to JSON                 → 持久化
    """

    SOURCE = "paldb.cc"
    _RAW_DIR = "data/raw/pages"
    _OUTPUT_DIR = "data/processed"

    def __init__(
        self,
        raw_dir: str | Path = "data/raw/pages",
        output_dir: str | Path = "data/processed",
    ):
        self.raw_dir = Path(raw_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self._scraper = PalDBScraper(output_dir=self.raw_dir)
        self._parser = PalDBParser()
        self._validator = DataValidator()
        self._version: str | None = None

    # ------------------------------------------------------------------
    # PalDataSourceAdapter implementation
    # ------------------------------------------------------------------

    @property
    def source_name(self) -> str:
        return self.SOURCE

    @property
    def source_version(self) -> str:
        return self._version or "unknown"

    async def fetch_all(self) -> list[Pal]:
        """从 paldb.cc 获取全部帕鲁数据并转换为 canonical 格式.

        这是一次性离线操作。日常开发使用 build_and_save() 后加载 JSON。
        """
        # step 1 + 2: fetch pal list and download all pages
        pal_list = await self._scraper.fetch_pal_list()
        success, failed = await self._scraper.fetch_all(pal_list)

        logger.info(
            "scrape done: %d/%d pages fetched, %d failed",
            success, len(pal_list), len(failed),
        )

        # step 3: parse all HTML
        parsed = self._parser.parse_all(self.raw_dir, pal_list)

        # step 4: convert to schema.Pal
        pals = [self._dict_to_pal(p) for p in parsed]

        # step 5: validate
        result = self._validator.validate(pals)
        if result.has_errors:
            for e in result.errors:
                logger.error("validation error: %s", e)
        for w in result.warnings:
            logger.warning("validation warning: %s", w)
        for i in result.info:
            logger.info("validation info: %s", i)

        logger.info("adapter produced %d canonical Pal entities", len(pals))
        return pals

    async def build_and_save(self) -> list[Pal]:
        """完整构建流程: 抓取 → 解析 → 校验 → 保存 JSON."""
        pals = await self.fetch_all()

        # save pal_data.json
        output_data = {p.id: p.to_dict() for p in pals}
        output_path = self.output_dir / "pal_data.json"
        output_path.write_text(
            json.dumps(output_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info("saved %d pals to %s", len(pals), output_path)

        # save metadata
        meta = await self.fetch_meta()
        meta.total_pals = len(pals)
        if meta.generated_at == "":
            from datetime import datetime, timezone
            meta.generated_at = datetime.now(timezone.utc).isoformat()

        meta_path = self.output_dir / "pal_meta.json"
        meta_path.write_text(
            json.dumps({
                "game_version": meta.game_version,
                "generated_at": meta.generated_at,
                "total_pals": meta.total_pals,
                "wild_pals": meta.wild_pals,
                "field_completeness": meta.field_completeness,
                "source": meta.source,
            }, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        return pals

    def load_from_json(self, path: str | Path = "data/processed/pal_data.json") -> list[Pal]:
        """从已构建的 JSON 文件加载 Pal 列表 (运行时使用)."""
        path = Path(path)
        raw = json.loads(path.read_text(encoding="utf-8"))
        return [Pal.from_dict(p) for p in raw.values()]

    # ------------------------------------------------------------------
    # dict → Pal conversion
    # ------------------------------------------------------------------

    def _dict_to_pal(self, raw: dict) -> Pal:
        """将解析后的字典转换为 canonical Pal 实体."""
        # elements
        elements: list[Element] = []
        for key in ("element_type1", "element_type2"):
            val = raw.get(key)
            if val and val != "None":
                try:
                    elements.append(Element(val))
                except ValueError:
                    elements.append(Element.NEUTRAL)

        # work suitability
        ws_dict = raw.get("work_suitability", {})
        ws = WorkSuitability.from_dict(ws_dict)

        # build pal
        pal = Pal(
            id=raw["id"],
            number=raw["number"],
            cn_name=raw.get("cn_name", raw["id"]),
            en_name=raw.get("en_name") or raw["id"],
            combi_rank=raw["combi_rank"],
            elements=elements,
            rarity=raw.get("rarity", 1),
            work_suitability=ws,
            is_wild=raw.get("is_wild", False),
            image_url=raw.get("image_url"),
            wiki_url=raw.get("wiki_url"),
            spawn_locations=raw.get("spawn_locations", []),
            _source=self.SOURCE,
            _incomplete=raw.get("_incomplete", False),
        )

        # attach parse warnings to _suspicious_fields
        warnings = raw.get("_parse_warnings", [])
        if warnings:
            pal._suspicious = True
            pal._suspicious_fields = warnings

        return pal


# ============================================================================
# BreedingRules adapter (manual rules file → schema)
# ============================================================================

class BreedingRulesFileAdapter(BreedingRulesAdapter):
    """从本地 JSON 文件加载配种规则."""

    def __init__(self, rules_path: str | Path = "data/processed/breeding_rules.json"):
        self.rules_path = Path(rules_path)

    async def fetch_rules(self) -> BreedingRules:
        if not self.rules_path.exists():
            logger.warning(
                "breeding_rules.json not found at %s, returning empty rules",
                self.rules_path,
            )
            return BreedingRules(
                game_version="unknown",
                last_updated="",
            )
        raw = json.loads(self.rules_path.read_text(encoding="utf-8"))
        return BreedingRules.from_dict(raw)

        )
