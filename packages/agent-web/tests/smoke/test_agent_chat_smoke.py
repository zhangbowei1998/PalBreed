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

    select_payload = None
    for action in r2.json()["data"]["actions"]:
        if action["action"] == "select_parent_pair":
            select_payload = action["payload"]
            break
    assert select_payload is not None

    r3 = test_client.post(
        "/agent/action",
        json={
            "session_id": "smoke-1",
            "action": "select_parent_pair",
            "child_pal_id": select_payload["child_pal_id"],
            "pair_index": select_payload["pair_index"],
        },
    )
    assert r3.status_code == 200

    continue_payload = None
    for action in r3.json()["data"]["actions"]:
        if action["action"] == "continue_from_parent":
            continue_payload = action["payload"]
            break
    assert continue_payload is not None

    r4 = test_client.post(
        "/agent/action",
        json={
            "session_id": "smoke-1",
            "action": "continue_from_parent",
            "pal_id": continue_payload["pal_id"],
        },
    )
    assert r4.status_code == 200

    select_again = [
        a for a in r4.json()["data"]["actions"] if a["action"] == "select_parent_pair"
    ]
    assert select_again
