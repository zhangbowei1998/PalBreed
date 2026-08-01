from __future__ import annotations


def test_action_response_contract(test_client):
    test_client.post(
        "/agent/chat",
        json={"session_id": "contract-1", "message": "手工等级最高的帕鲁怎么配种"},
    )

    resp = test_client.post(
        "/agent/action",
        json={
            "session_id": "contract-1",
            "action": "confirm_target",
            "pal_id": "anubis",
        },
    )
    assert resp.status_code == 200
    payload = resp.json()

    assert payload["success"] is True
    data = payload["data"]
    assert isinstance(data.get("messages"), list)
    assert isinstance(data.get("actions"), list)
    assert isinstance(data.get("state_snapshot"), dict)
    assert isinstance(data.get("meta"), dict)


def test_invalid_expand_contract(test_client):
    resp = test_client.post(
        "/agent/action",
        json={
            "session_id": "contract-2",
            "action": "expand_parent",
            "pal_id": "anubis",
        },
    )
    assert resp.status_code == 400
