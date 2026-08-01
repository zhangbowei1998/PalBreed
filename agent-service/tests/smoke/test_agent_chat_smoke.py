from __future__ import annotations


def test_main_chat_flow_smoke(test_client):
    r1 = test_client.post(
        "/agent/chat",
        json={"session_id": "smoke-1", "message": "手工等级最高的帕鲁怎么配种"},
    )
    assert r1.status_code == 200

    r2 = test_client.post(
        "/agent/action",
        json={
            "session_id": "smoke-1",
            "action": "confirm_target",
            "pal_id": "anubis",
        },
    )
    assert r2.status_code == 200

    expand_payload = None
    for action in r2.json()["data"]["actions"]:
        if action["action"] == "expand_parent":
            expand_payload = action["payload"]
            break
    assert expand_payload is not None

    r3 = test_client.post(
        "/agent/action",
        json={
            "session_id": "smoke-1",
            "action": "expand_parent",
            "pal_id": expand_payload["pal_id"],
            "source_message_id": "smoke-msg",
        },
    )
    assert r3.status_code == 200

    r4 = test_client.post(
        "/agent/action",
        json={
            "session_id": "smoke-1",
            "action": "summarize_route",
            "mode": "explored_only",
        },
    )
    assert r4.status_code == 200
    assert "graph_json" in r4.json()["data"]
