from __future__ import annotations

import pytest

from pl_agent_agent.graph.guards import GuardViolation, ensure_expand_allowed
from pl_agent_agent.state.models import SessionState


def test_guard_blocks_when_duplicate_limit_reached():
    state = SessionState(session_id="g1")
    with pytest.raises(GuardViolation):
        ensure_expand_allowed(
            state,
            duplicate_count=3,
            duplicate_limit=3,
            current_depth=0,
        )


def test_guard_blocks_when_depth_limit_reached():
    state = SessionState(session_id="g2")
    state.limits.max_depth = 2
    with pytest.raises(GuardViolation):
        ensure_expand_allowed(
            state,
            duplicate_count=0,
            duplicate_limit=3,
            current_depth=2,
        )
