"""paldb.cc HTML scraper — fetches raw HTML pages from paldb.cc."""

from __future__ import annotations

import asyncio
import logging
import re
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# known paldb.cc advertising domains that may cause redirects
_AD_DOMAINS = {"sync.inmobi.com", "pbs.nitropay.com", "nitropay.com"}


class PalDBScraper:
    """paldb.cc HTML 页面抓取器.

    抓取策略:
      - 并发数: 3
      - 请求间隔: 1-2 秒
      - 超时: 30 秒
      - 重试: 3 次, 指数退避 (1s → 2s → 4s)
      - 全失败: 标记 failed, 记录日志, 继续下一个
      - 广告重定向: 自动丢弃, 重试
    """

    BASE_URL = "https://paldb.cc/cn"
    BREED_URL = "https://paldb.cc/cn/Breed"
    MAX_RETRIES = 3
    RETRY_BASE_DELAY = 1.0
    CONCURRENCY = 3
    TIMEOUT = 30.0

    # user-agent identifying this project politely
    USER_AGENT = (
        "PlAgent/1.0 (pal-breeding-agent; +https://github.com/pl-agent)"
    )

    def __init__(self, output_dir: str | Path = "data/raw/pages"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._failed: list[str] = []
        self._sem: asyncio.Semaphore | None = None

    # ------------------------------------------------------------------
    # Step 1: fetch Pal list from Breed page
    # ------------------------------------------------------------------

    async def fetch_pal_list(self) -> list[dict[str, str | int]]:
        """从 Breed 页面 Multi-pal Breeder 区域提取帕鲁列表.

        Returns:
            [{"internal_id": "SheepBall", "cn_name": "棉悠悠", "number": 1}, ...]
        """
        url = f"{self.BREED_URL}?child=Lamball"
        async with self._build_client() as client:
            html = await self._fetch_url(client, url, "pal list")

        soup = BeautifulSoup(html, "html.parser")
        pals: list[dict[str, str | int]] = []

        # the Multi-pal Breeder section contains images like
        # <a href="/cn/SheepBall"><img ... alt="棉悠悠"/></a>
        # each image's parent <a> tag wraps the pal link
        for a_tag in soup.select("a[href^='/cn/']"):
            href = a_tag.get("href", "")
            img = a_tag.find("img")
            alt_text = (img.get("alt", "") if img else "").strip()
            if not alt_text:
                continue
            # extract internal_id from href: /cn/SheepBall → SheepBall
            internal_id = href.rsplit("/", 1)[-1].strip()
            if not internal_id:
                continue
            # extract number from image filename pattern: T_xxx_icon_normal
            # the paldb page has numbers inline; we'll get them from detail pages
            pals.append({
                "internal_id": internal_id,
                "cn_name": alt_text,
            })

        # deduplicate by internal_id
        seen: set[str] = set()
        unique: list[dict[str, str | int]] = []
        for p in pals:
            pid = str(p["internal_id"])
            if pid not in seen:
                seen.add(pid)
                unique.append(p)

        logger.info("fetched %d unique pals from Breed page", len(unique))
        return unique

    # ------------------------------------------------------------------
    # Step 2: batch fetch all detail pages
    # ------------------------------------------------------------------

    async def fetch_all(
        self, pal_list: list[dict[str, str | int]] | None = None
    ) -> tuple[int, list[str]]:
        """批量抓取所有帕鲁页面.

        Args:
            pal_list: 帕鲁列表. 为 None 时自动从 Breed 页获取.

        Returns:
            (成功数, 失败 internal_id 列表).
        """
        if pal_list is None:
            pal_list = await self.fetch_pal_list()

        self._failed = []
        self._sem = asyncio.Semaphore(self.CONCURRENCY)

        async with self._build_client() as client:
            tasks = [
                self._fetch_with_semaphore(client, str(p["internal_id"]))
                for p in pal_list
            ]
            results = await asyncio.gather(*tasks)

        success = sum(1 for r in results if r)
        logger.info(
            "batch fetch complete: %d/%d succeeded, %d failed",
            success, len(pal_list), len(self._failed),
        )
        return success, list(self._failed)

    async def _fetch_with_semaphore(
        self, client: httpx.AsyncClient, internal_id: str,
    ) -> bool:
        async with self._sem:  # type: ignore[union-attr]
            await asyncio.sleep(1.0)  # polite delay
            return await self.fetch_page(internal_id, client)

    async def fetch_page(
        self, internal_id: str, client: httpx.AsyncClient,
    ) -> bool:
        """抓取单个帕鲁页面, 保存 HTML. 返回 True 成功 / False 失败."""
        url = f"{self.BASE_URL}/{internal_id}"
        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                resp = await client.get(
                    url, follow_redirects=True, timeout=self.TIMEOUT,
                )

                # check for ad redirect
                if self._is_ad_redirect(resp):
                    logger.debug(
                        "ad redirect detected for %s, retrying", internal_id,
                    )
                    await asyncio.sleep(1.0)
                    continue

                resp.raise_for_status()

                # verify we got a real pal page (not a blank/error page)
                if "CombiRank" not in resp.text and "工作适应性" not in resp.text:
                    logger.warning(
                        "page for %s missing expected markers, may be error page",
                        internal_id,
                    )

                output_path = self.output_dir / f"{internal_id}.html"
                output_path.write_text(resp.text, encoding="utf-8")
                return True

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    logger.warning("fetch %s: 404 not found, skipping", internal_id)
                    self._failed.append(internal_id)
                    return False
                delay = self._retry_delay(attempt)
                logger.warning(
                    "fetch %s HTTP %d attempt %d/%d, retrying in %.1fs",
                    internal_id, e.response.status_code,
                    attempt, self.MAX_RETRIES, delay,
                )
                if attempt < self.MAX_RETRIES:
                    await asyncio.sleep(delay)
            except Exception as e:
                delay = self._retry_delay(attempt)
                logger.warning(
                    "fetch %s attempt %d/%d failed: %s, retrying in %.1fs",
                    internal_id, attempt, self.MAX_RETRIES, e, delay,
                )
                if attempt < self.MAX_RETRIES:
                    await asyncio.sleep(delay)

        self._failed.append(internal_id)
        logger.error(
            "fetch %s FAILED after %d attempts", internal_id, self.MAX_RETRIES,
        )
        return False

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _retry_delay(self, attempt: int) -> float:
        return self.RETRY_BASE_DELAY * (2 ** (attempt - 1))

    @staticmethod
    def _is_ad_redirect(resp: httpx.Response) -> bool:
        """Check if the response redirected to an advertising domain."""
        try:
            from urllib.parse import urlparse
            host = urlparse(str(resp.url)).hostname or ""
            return any(ad in host for ad in _AD_DOMAINS)
        except Exception:
            return False

    def _build_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            headers={"User-Agent": self.USER_AGENT},
            timeout=self.TIMEOUT,
            follow_redirects=True,
        )

    @property
    def failed_pages(self) -> list[str]:
        return self._failed
