from __future__ import annotations

from fastapi.testclient import TestClient

from pl_agent.agent_web.app import app


def test_action_validation_rejects_removed_summarize_route():
    client = TestClient(app)
    response = client.post(
        "/agent/action",
        json={"session_id": "s1", "action": "summarize_route", "mode": "explored_only"},
    )
    assert response.status_code == 400


def test_chat_validation_requires_message():
    client = TestClient(app)
    response = client.post(
        "/agent/chat",
        json={"session_id": "s1", "message": "   "},
    )
    assert response.status_code == 400


def test_action_validation_requires_fields_for_select_parent_pair():
    client = TestClient(app)
    response = client.post(
        "/agent/action",
        json={"session_id": "s1", "action": "select_parent_pair"},
    )
    assert response.status_code == 400
