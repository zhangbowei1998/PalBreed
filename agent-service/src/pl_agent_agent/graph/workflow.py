"""Agent workflow entrypoints."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from ..clients.breeding_api_client import BreedingApiClient
from ..common.constants import (
    ACTION_CONFIRM_TARGET,
    ACTION_EXPAND_PARENT,
    ACTION_SUMMARIZE_ROUTE,
)
from ..config import Settings
from ..interaction.click_protocol import is_route_command, parse_expand_fallback
from ..interaction.presenter import build_response
from ..state.memory_store import InMemorySessionRepository
from ..state.models import ClickEvent, SessionState
from .guards import GuardViolation, ensure_expand_allowed, ensure_summary_allowed
from .nodes import (
    build_reused_node_response,
    query_parents_and_record,
    resolve_top_candidates,
    summarize_route,
)
from .routes import is_top_handiwork_query
from ..summarizer.formatters import to_text_tree
from ..summarizer.route_builder import build_route_graph
from ..summarizer.serializers import to_graph_json


class StateConflictError(Exception):
    pass


@dataclass
class ChatInput:
    session_id: str
    message: str


@dataclass
class ActionInput:
    session_id: str
    action: str
    pal_id: str | None = None
    source_message_id: str | None = None
    mode: str | None = None


class AgentWorkflow:
    def __init__(
        self,
        *,
        settings: Settings,
        repository: InMemorySessionRepository,
        client: BreedingApiClient,
    ) -> None:
        self._settings = settings
        self._repository = repository
        self._client = client

    async def _load_or_create_state(self, session_id: str) -> SessionState:
        state = await self._repository.get(session_id)
        if state:
            return state
        state = SessionState(session_id=session_id)
        state.limits.max_depth = self._settings.max_depth
        state.limits.max_nodes = self._settings.max_nodes
        return await self._repository.save(session_id, state)

    async def handle_chat(self, data: ChatInput) -> dict:
        state = await self._load_or_create_state(data.session_id)

        fallback_expand = parse_expand_fallback(data.message)
        if fallback_expand:
            return await self.handle_action(
                ActionInput(
                    session_id=data.session_id,
                    action=ACTION_EXPAND_PARENT,
                    pal_id=fallback_expand,
                    source_message_id="fallback_command",
                )
            )

        if is_route_command(data.message):
            return await self.handle_action(
                ActionInput(
                    session_id=data.session_id,
                    action=ACTION_SUMMARIZE_ROUTE,
                    mode="explored_only",
                )
            )

        if is_top_handiwork_query(data.message):
            messages, actions = await resolve_top_candidates(
                session_id=data.session_id,
                state=state,
                repository=self._repository,
                client=self._client,
                top_n=self._settings.top_candidates,
            )
            state = await self._repository.get(data.session_id) or state
            if state.target_pal:
                pm, pa = await query_parents_and_record(
                    session_id=data.session_id,
                    state=state,
                    repository=self._repository,
                    client=self._client,
                    pal_id=state.target_pal,
                )
                messages.extend(pm)
                actions.extend(pa)
                state = await self._repository.get(data.session_id) or state
            return build_response(messages=messages, actions=actions, state=state)

        return build_response(
            messages=["当前仅支持‘手工最高’查询、点击展开和 /route 汇总。"],
            actions=[],
            state=state,
        )

    async def handle_action(self, data: ActionInput) -> dict:
        state = await self._load_or_create_state(data.session_id)

        if data.action == ACTION_CONFIRM_TARGET:
            if not data.pal_id:
                raise ValueError("pal_id is required")
            state.target_pal = data.pal_id
            state.confirmed_target_pal = data.pal_id
            await self._repository.save(data.session_id, state)
            messages, actions = await query_parents_and_record(
                session_id=data.session_id,
                state=state,
                repository=self._repository,
                client=self._client,
                pal_id=data.pal_id,
            )
            state = await self._repository.get(data.session_id) or state
            return build_response(messages=messages, actions=actions, state=state)

        if data.action == ACTION_EXPAND_PARENT:
            if not data.pal_id:
                raise ValueError("pal_id is required")
            if not state.target_pal:
                raise StateConflictError("请先确认目标帕鲁再展开")

            duplicate_count = self._repository.get_expand_count(
                data.session_id, data.pal_id
            )
            current_depth = state.node_depths.get(data.pal_id, 0)
            ensure_expand_allowed(
                state,
                duplicate_count=duplicate_count,
                duplicate_limit=self._settings.duplicate_expand_limit,
                current_depth=current_depth,
            )

            if data.pal_id in state.explored_nodes:
                return build_response(
                    messages=build_reused_node_response(data.pal_id),
                    actions=[],
                    state=state,
                )

            await self._repository.append_click(
                data.session_id,
                ClickEvent(pal_id=data.pal_id),
            )
            messages, actions = await query_parents_and_record(
                session_id=data.session_id,
                state=state,
                repository=self._repository,
                client=self._client,
                pal_id=data.pal_id,
            )
            state = await self._repository.get(data.session_id) or state
            return build_response(messages=messages, actions=actions, state=state)

        if data.action == ACTION_SUMMARIZE_ROUTE:
            ensure_summary_allowed(state)
            try:
                messages, graph_json = await asyncio.wait_for(
                    summarize_route(state, mode=data.mode or "explored_only"),
                    timeout=self._settings.route_timeout_ms / 1000,
                )
            except TimeoutError:
                graph = build_route_graph(state)
                graph_json = to_graph_json(graph)
                messages = [f"路线生成超时，返回部分结果：\n{to_text_tree(graph)}"]
            response = build_response(messages=messages, actions=[], state=state)
            response["graph_json"] = graph_json
            return response

        raise ValueError(f"unsupported action: {data.action}")
