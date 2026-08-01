"""Session repository abstractions."""

from __future__ import annotations

from typing import Protocol

from .models import ClickEvent, Edge, SessionState


class SessionRepository(Protocol):
    async def get(self, session_id: str) -> SessionState | None: ...

    async def save(self, session_id: str, state: SessionState) -> SessionState: ...

    async def upsert(self, session_id: str, patch: dict) -> SessionState: ...

    async def append_edge(self, session_id: str, edge: Edge) -> SessionState: ...

    async def append_click(
        self, session_id: str, click_event: ClickEvent
    ) -> SessionState: ...

    async def reset(self, session_id: str) -> None: ...

    def get_expand_count(self, session_id: str, pal_id: str) -> int: ...
