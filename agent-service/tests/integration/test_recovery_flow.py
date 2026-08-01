from __future__ import annotations


def test_session_recovery_snapshot(test_client):
    test_client.post(
        "/agent/chat",
        json={"session_id": "it-recovery", "message": "手工等级最高的帕鲁怎么配种"},
    )

    test_client.post(
        "/agent/action",
        json={
            "session_id": "it-recovery",
            "action": "confirm_target",
            "pal_id": "anubis",
        },
    )

    snapshot = test_client.get("/agent/session/it-recovery")
    assert snapshot.status_code == 200
    state = snapshot.json()["data"]["state_snapshot"]
    assert state["target_pal"] == "anubis"
    assert isinstance(state["edges"], list)
