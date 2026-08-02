"""BreedingApiClient 扩展方法（S6-S10）单元测试 — mock _request，不依赖真实 API。"""

from unittest.mock import AsyncMock

import pytest

from pl_agent.agent.clients.breeding_api_client import BreedingApiClient
from pl_agent.agent.clients.errors import InvalidPayloadError


def _client(request_result):
    c = BreedingApiClient("http://api:8000")
    c._request = AsyncMock(return_value=request_result)
    return c


@pytest.mark.asyncio
async def test_get_pal_detail_full():
    c = _client({"id": "Anubis", "cn_name": "阿努比斯", "stats": {"hp": 120}})
    r = await c.get_pal_detail_full("Anubis")
    assert r["id"] == "Anubis"
    assert r["stats"]["hp"] == 120
    c._request.assert_awaited_once_with("GET", "/api/pals/Anubis/detail")


@pytest.mark.asyncio
async def test_get_pal_skills():
    c = _client({
        "pal_id": "Anubis",
        "skills": [{"cn_name": "碎石霰弹", "learn_level": 1}],
        "total": 1,
    })
    r = await c.get_pal_skills("Anubis")
    assert r[0]["cn_name"] == "碎石霰弹"
    c._request.assert_awaited_once_with("GET", "/api/pals/Anubis/skills")


@pytest.mark.asyncio
async def test_query_pals_by_passive():
    c = _client({"passive": "重量级", "pals": [{"id": "KingAlpaca", "cn_name": "君王美露帕"}], "total": 1})
    r = await c.query_pals_by_passive("重量级")
    assert r[0]["id"] == "KingAlpaca"
    c._request.assert_awaited_once_with("GET", "/api/passives", params={"name": "重量级"})


@pytest.mark.asyncio
async def test_get_item_recipe():
    c = _client({"item": "金属锭", "recipe": [{"material": "金属矿石", "count": 2, "station": "BlastFurnace"}]})
    r = await c.get_item_recipe("金属锭")
    assert r[0]["material"] == "金属矿石"
    assert r[0]["station"] == "BlastFurnace"


@pytest.mark.asyncio
async def test_get_item_drops():
    c = _client({"item": "骨头", "pals": [{"pal_id": "Garm", "pal_cn": "加姆", "rate": 3}], "total": 1})
    r = await c.get_item_drops("骨头")
    assert r[0]["pal_cn"] == "加姆"


@pytest.mark.asyncio
async def test_skills_invalid_payload():
    c = _client({})
    with pytest.raises(InvalidPayloadError):
        await c.get_pal_skills("Anubis")


@pytest.mark.asyncio
async def test_drops_invalid_payload():
    c = _client({"pals": "not-a-list"})
    with pytest.raises(InvalidPayloadError):
        await c.get_item_drops("骨头")
