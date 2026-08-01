from __future__ import annotations


def test_chat_top3_then_confirm_then_expand(test_client):
    chat = test_client.post(
        "/agent/chat",
        json={"session_id": "it-1", "message": "手工等级最高的帕鲁怎么配种"},
    )
    assert chat.status_code == 200
    data = chat.json()["data"]
    actions = data["actions"]
    confirm = [a for a in actions if a["action"] == "confirm_target"]
    assert len(confirm) >= 2

    confirm_resp = test_client.post(
        "/agent/action",
        json={
            "session_id": "it-1",
            "action": "confirm_target",
            "pal_id": "anubis",
        },
    )
    assert confirm_resp.status_code == 200
    confirm_data = confirm_resp.json()["data"]
    expand_actions = [
        a for a in confirm_data["actions"] if a["action"] == "expand_parent"
    ]
    assert expand_actions

    first_expand = expand_actions[0]["payload"]["pal_id"]
    expand_resp = test_client.post(
        "/agent/action",
        json={
            "session_id": "it-1",
            "action": "expand_parent",
            "pal_id": first_expand,
            "source_message_id": "m-1",
        },
    )
    assert expand_resp.status_code == 200
    assert expand_resp.json()["success"] is True
