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
    USER_AGENT = "PlAgent/1.0 (pal-breeding-agent; +https://github.com/pl-agent)"

    def __init__(self, output_dir: str | Path = "data/raw/pages"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._failed: list[str] = []
        self._sem: asyncio.Semaphore | None = None

    # ------------------------------------------------------------------
    # Step 1: fetch Pal list from Breed page
    # ------------------------------------------------------------------

    async def fetch_pal_list(self) -> list[dict[str, str | int]]:
        """从 /cn/Pals 页面提取帕鲁列表.

        利用 pal 图标文件名 (T_xxx_icon_normal) 识别帕鲁条目,
        从父 <a> 标签的 href 获取 paldb.cc URL 名称.

        Returns:
            [{"url_name": "Lamball", "internal_id": "SheepBall"}, ...]
        """
        url = f"{self.BASE_URL}/Pals"
        async with self._build_client() as client:
            resp = await client.get(url, follow_redirects=True, timeout=self.TIMEOUT)
            resp.raise_for_status()
            html = resp.text

        soup = BeautifulSoup(html, "html.parser")
        pals: list[dict[str, str | int]] = []
        seen: set[str] = set()

        for img in soup.find_all("img"):
            src = img.get("src", "")
            # pal icons: T_SheepBall_icon_normal.webp
            # skip work type icons: T_icon_palwork_*
            if "_icon_normal" not in src or "T_icon_palwork" in src:
                continue
            match = re.search(r"T_(\w+?)_icon_normal", src)
            if not match:
                continue
            internal_id = match.group(1)

            # get URL name from parent <a> tag
            parent_a = img.find_parent("a")
            href = parent_a.get("href", "") if parent_a else ""
            url_name = href.rsplit("/", 1)[-1].strip()
            if not url_name:
                continue

            if url_name in seen:
                continue
            seen.add(url_name)

            pals.append({"url_name": url_name, "internal_id": internal_id})

        logger.info("fetched %d unique pals from /cn/Pals page", len(pals))
        return pals

    # ------------------------------------------------------------------
    # Step 2: batch fetch all detail pages
    # ------------------------------------------------------------------

    async def fetch_all(
        self, pal_list: list[dict[str, str | int]] | None = None
    ) -> tuple[int, list[str]]:
        """批量抓取所有帕鲁页面.

        Args:
            pal_list: [{"url_name": "Lamball", "internal_id": "SheepBall"}, ...]

        Returns:
            (成功数, 失败 url_name 列表).
        """
        if pal_list is None:
            pal_list = await self.fetch_pal_list()

        self._failed = []
        self._sem = asyncio.Semaphore(self.CONCURRENCY)

        async with self._build_client() as client:
            tasks = [self._fetch_with_semaphore(client, p) for p in pal_list]
            results = await asyncio.gather(*tasks)

        success = sum(1 for r in results if r)
        logger.info(
            "batch fetch complete: %d/%d succeeded, %d failed",
            success,
            len(pal_list),
            len(self._failed),
        )
        return success, list(self._failed)

    async def _fetch_with_semaphore(
        self,
        client: httpx.AsyncClient,
        pal: dict[str, str | int],
    ) -> bool:
        async with self._sem:  # type: ignore[union-attr]
            await asyncio.sleep(1.0)  # polite delay
            return await self.fetch_page(
                str(pal["url_name"]),  # for URL
                str(pal.get("internal_id", pal["url_name"])),  # for filename
                client,
            )

    async def fetch_page(
        self,
        url_name: str,
        internal_id: str,
        client: httpx.AsyncClient,
    ) -> bool:
        """抓取单个帕鲁页面, 保存 HTML. 返回 True 成功 / False 失败."""
        url = f"{self.BASE_URL}/{url_name}"
        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                resp = await client.get(
                    url,
                    follow_redirects=True,
                    timeout=self.TIMEOUT,
                )

                # check for ad redirect
                if self._is_ad_redirect(resp):
                    logger.debug(
                        "ad redirect detected for %s, retrying",
                        internal_id,
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
                    internal_id,
                    e.response.status_code,
                    attempt,
                    self.MAX_RETRIES,
                    delay,
                )
                if attempt < self.MAX_RETRIES:
                    await asyncio.sleep(delay)
            except Exception as e:
                delay = self._retry_delay(attempt)
                logger.warning(
                    "fetch %s attempt %d/%d failed: %s, retrying in %.1fs",
                    internal_id,
                    attempt,
                    self.MAX_RETRIES,
                    e,
                    delay,
                )
                if attempt < self.MAX_RETRIES:
                    await asyncio.sleep(delay)

        self._failed.append(internal_id)
        logger.error(
            "fetch %s FAILED after %d attempts",
            internal_id,
            self.MAX_RETRIES,
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
