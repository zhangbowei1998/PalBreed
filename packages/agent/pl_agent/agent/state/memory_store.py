"""In-memory repository implementation."""

from __future__ import annotations

from collections import defaultdict

from .models import ClickEvent, Edge, SessionState
from .repository import SessionRepository


class InMemorySessionRepository(SessionRepository):
    def __init__(self) -> None:
        self._store: dict[str, SessionState] = {}
        self._expand_counts: dict[tuple[str, str], int] = defaultdict(int)

    async def get(self, session_id: str) -> SessionState | None:
        return self._store.get(session_id)

    async def save(self, session_id: str, state: SessionState) -> SessionState:
        state.touch()
        self._store[session_id] = state
        return state

    async def upsert(self, session_id: str, patch: dict) -> SessionState:
        state = self._store.get(session_id) or SessionState(session_id=session_id)
        for key, value in patch.items():
            setattr(state, key, value)
        state.touch()
        self._store[session_id] = state
        return state

    async def append_edge(self, session_id: str, edge: Edge) -> SessionState:
        state = self._store.get(session_id) or SessionState(session_id=session_id)
        duplicate = any(
            e.child_pal_id == edge.child_pal_id
            and e.parent_a_id == edge.parent_a_id
            and e.parent_b_id == edge.parent_b_id
            for e in state.edges
        )
        if not duplicate:
            state.edges.append(edge)
            if edge.parent_a_id not in state.pending_frontier:
                state.pending_frontier.append(edge.parent_a_id)
            if edge.parent_b_id not in state.pending_frontier:
                state.pending_frontier.append(edge.parent_b_id)
        state.touch()
        self._store[session_id] = state
        return state

    async def append_click(
        self, session_id: str, click_event: ClickEvent
    ) -> SessionState:
        state = self._store.get(session_id) or SessionState(session_id=session_id)
        state.click_trace.append(click_event)
        state.pending_frontier = [
            item for item in state.pending_frontier if item != click_event.pal_id
        ]
        self._expand_counts[(session_id, click_event.pal_id)] += 1
        state.touch()
        self._store[session_id] = state
        return state

    async def reset(self, session_id: str) -> None:
        self._store.pop(session_id, None)
        keys_to_remove = [k for k in self._expand_counts if k[0] == session_id]
        for key in keys_to_remove:
            self._expand_counts.pop(key, None)

    def get_expand_count(self, session_id: str, pal_id: str) -> int:
        return self._expand_counts[(session_id, pal_id)]
