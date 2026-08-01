"""HTTP client for the existing breeding API."""

from __future__ import annotations

import asyncio

import httpx

from ..config import work_type_to_cn
from .errors import InvalidPayloadError, PalNotFoundError, UpstreamServiceError
from .schemas import SuitabilityCandidate, UpstreamEnvelope


class BreedingApiClient:
    def __init__(self, base_url: str, timeout_s: float = 8.0, retries: int = 1) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_s
        self._retries = retries

    async def _request(self, method: str, path: str, **kwargs) -> dict:
        url = f"{self._base_url}{path}"
        attempt = 0
        while True:
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    response = await client.request(method, url, **kwargs)
                if response.status_code >= 500:
                    raise UpstreamServiceError(f"upstream 5xx: {response.status_code}")
                if response.status_code >= 400:
                    raise UpstreamServiceError(f"upstream 4xx: {response.status_code}")
                payload = response.json()
                envelope = UpstreamEnvelope.model_validate(payload)
                if not envelope.success:
                    code = (envelope.error or {}).get("code")
                    if code == "PAL_NOT_FOUND":
                        raise PalNotFoundError("pal not found")
                    raise UpstreamServiceError(str(envelope.error))
                return envelope.data
            except httpx.TimeoutException as exc:
                if attempt >= self._retries:
                    raise UpstreamServiceError("upstream timeout") from exc
                attempt += 1
                await asyncio.sleep(0.05)
            except ValueError as exc:
                raise InvalidPayloadError("invalid JSON payload") from exc

    async def query_top_suitability(
        self,
        work_type: str,
        level: int,
        top_n: int,
    ) -> list[SuitabilityCandidate]:
        cn_type = work_type_to_cn(work_type)
        data = await self._request(
            "POST", "/api/query", json={"input": f"{cn_type}:{level}"}
        )
        candidates = data.get("candidates")
        if not isinstance(candidates, list):
            raise InvalidPayloadError("missing candidates")

        parsed = [SuitabilityCandidate.model_validate(item) for item in candidates]
        if not parsed:
            return []

        max_level = max(item.matched_level for item in parsed)
        best = [item for item in parsed if item.matched_level == max_level]
        return best[:top_n]

    async def get_parent_pairs(self, pal_id: str) -> list[dict]:
        data = await self._request("GET", f"/api/breeding/tree/{pal_id}")
        pairs = data.get("parent_pairs", [])
        if not isinstance(pairs, list):
            raise InvalidPayloadError("parent_pairs should be a list")
        return pairs

    async def get_pal_detail(self, pal_id: str) -> dict:
        return await self._request("GET", f"/api/pal/{pal_id}")

    async def resolve_pal(self, token: str) -> dict:
        return await self.get_pal_detail(token)
