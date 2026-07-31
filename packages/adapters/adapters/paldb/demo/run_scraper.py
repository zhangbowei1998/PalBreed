"""Demo: run the full paldb.cc scraping pipeline.

Usage:
    uv run python packages/adapters/adapters/paldb/demo/run_scraper.py

This will:
  1. Fetch all Pal URLs from paldb.cc/Breed page
  2. Download all HTML pages to data/raw/pages/
  3. Parse HTML → extracted dicts
  4. Convert to canonical schema.Pal
  5. Validate
  6. Save to data/processed/pal_data.json
"""

import asyncio
import logging
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

from adapters.paldb.adapter import PalDBAdapter  # noqa: E402

logger = logging.getLogger("demo")


async def main():
    adapter = PalDBAdapter()

    # Step 1: get pal list (safe, no heavy download)
    scraper = adapter._scraper
    logger.info("Fetching pal list from paldb.cc...")
    pal_list = await scraper.fetch_pal_list()
    logger.info("Found %d pals", len(pal_list))
    for p in pal_list[:5]:
        logger.info("  %s → /cn/%s", p["internal_id"], p["url_name"])

    # Step 2+: run full pipeline (uncomment to download + parse + save)
    # logger.info("Downloading %d pages...", len(pal_list))
    # success, failed = await scraper.fetch_all(pal_list)
    # logger.info("Downloaded: %d ok, %d failed", success, len(failed))
    #
    # pals = await adapter.build_and_save()
    # logger.info("Saved %d pals to JSON + PostgreSQL", len(pals))


if __name__ == "__main__":
    asyncio.run(main())
