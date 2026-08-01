from __future__ import annotations

from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient

from pl_agent_agent.app import app
from pl_agent_agent.clients.schemas import SuitabilityCandidate, UpstreamPal


@dataclass
class FakeUpstreamClient:
    async def query_top_suitability(self, work_type: str, level: int, top_n: int):
        items = [
            SuitabilityCandidate(
                pal=UpstreamPal(id="anubis", cn_name="阿努比斯"),
                matched_level=6,
            ),
            SuitabilityCandidate(
                pal=UpstreamPal(id="penking", cn_name="企丸丸"),
                matched_level=6,
            ),
            SuitabilityCandidate(
                pal=UpstreamPal(id="wumpo", cn_name="唔波"),
                matched_level=5,
            ),
        ]
        return items[:top_n]

    async def get_parent_pairs(self, pal_id: str):
        mapping = {
            "anubis": [{"parent_a": "棉悠悠", "parent_b": "捣蛋猫", "method": "breed"}],
            "lamball": [{"parent_a": "企丸丸", "parent_b": "唔波", "method": "breed"}],
            "cattiva": [],
            "penking": [],
            "wumpo": [],
        }
        return mapping.get(pal_id, [])

    async def resolve_pal(self, token: str):
        mapper = {
            "棉悠悠": {"id": "lamball", "cn_name": "棉悠悠"},
            "捣蛋猫": {"id": "cattiva", "cn_name": "捣蛋猫"},
            "企丸丸": {"id": "penking", "cn_name": "企丸丸"},
            "唔波": {"id": "wumpo", "cn_name": "唔波"},
            "anubis": {"id": "anubis", "cn_name": "阿努比斯"},
            "penking": {"id": "penking", "cn_name": "企丸丸"},
            "wumpo": {"id": "wumpo", "cn_name": "唔波"},
            "lamball": {"id": "lamball", "cn_name": "棉悠悠"},
            "cattiva": {"id": "cattiva", "cn_name": "捣蛋猫"},
        }
        return mapper.get(token, {"id": token, "cn_name": token})


@pytest.fixture()
def test_client():
    with TestClient(app) as client:
        client.app.state.workflow._client = FakeUpstreamClient()
        yield client
