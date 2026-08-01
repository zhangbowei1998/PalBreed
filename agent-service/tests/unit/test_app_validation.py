from __future__ import annotations

from fastapi.testclient import TestClient

from pl_agent_agent.app import app


def test_action_validation_requires_mode_for_summarize_route():
    client = TestClient(app)
    response = client.post(
        "/agent/action",
        json={"session_id": "s1", "action": "summarize_route"},
    )
    assert response.status_code == 400


def test_chat_validation_requires_message():
    client = TestClient(app)
    response = client.post(
        "/agent/chat",
        json={"session_id": "s1", "message": "   "},
    )
    assert response.status_code == 400
