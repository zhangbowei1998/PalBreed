from __future__ import annotations


def test_chat_top3_then_confirm_then_select_and_continue(test_client):
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
    select_actions = [
        a for a in confirm_data["actions"] if a["action"] == "select_parent_pair"
    ]
    assert select_actions

    select_resp = test_client.post(
        "/agent/action",
        json={
            "session_id": "it-1",
            "action": "select_parent_pair",
            "child_pal_id": "anubis",
            "pair_index": 0,
        },
    )
    assert select_resp.status_code == 200
    assert select_resp.json()["success"] is True

    continue_actions = [
        a
        for a in select_resp.json()["data"]["actions"]
        if a["action"] == "continue_from_parent"
    ]
    assert continue_actions
