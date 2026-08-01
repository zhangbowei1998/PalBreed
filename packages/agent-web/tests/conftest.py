from __future__ import annotations

from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient

from pl_agent.agent_web.app import app
from pl_agent.agent.clients.schemas import SuitabilityCandidate, UpstreamPal


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
        workflow = client.app.state.workflow
        workflow._client = FakeUpstreamClient()
        # 集成测试锁定到规则模式（不依赖真实 LLM），保持确定性。
        workflow._agent_loop = None

        # 注册测试用户并注入 Authorization 头：接口现已强制登录。
        # 用户名固定，重复运行时注册返回 409，改走登录拿新 token。
        reg = client.post(
            "/auth/register",
            json={"username": "it_user", "password": "itpass123456"},
        )
        if reg.status_code == 409:
            reg = client.post(
                "/auth/login",
                json={"username": "it_user", "password": "itpass123456"},
            )
        token = reg.json()["data"]["token"]
        client.headers.update({"Authorization": f"Bearer {token}"})
        yield client
