"""Workflow node helpers."""

from __future__ import annotations

from ..clients.breeding_api_client import BreedingApiClient
from ..common.constants import MODE_EXPLORED_ONLY
from ..interaction.actions import (
    build_confirm_action,
    build_expand_action,
    build_summarize_action,
)
from ..interaction.message_templates import (
    parent_pairs_message,
    repeated_node_message,
    route_message,
    top_candidates_message,
)
from ..state.models import Edge, SessionState, TargetCandidate
from ..state.repository import SessionRepository
from ..summarizer.formatters import to_text_tree
from ..summarizer.route_builder import build_route_graph
from ..summarizer.serializers import to_graph_json


async def resolve_top_candidates(
    *,
    session_id: str,
    state: SessionState,
    repository: SessionRepository,
    client: BreedingApiClient,
    top_n: int,
) -> tuple[list[str], list[dict]]:
    candidates = await client.query_top_suitability("handiwork", 1, top_n)
    if not candidates:
        return ["未找到手工候选帕鲁。"], []

    model_candidates = [
        TargetCandidate(
            pal_id=item.pal.id,
            cn_name=item.pal.cn_name,
            score=item.matched_level,
            reason=f"手工 Lv{item.matched_level}",
        )
        for item in candidates
    ]
    state.target_candidates = model_candidates
    await repository.save(session_id, state)

    if len(model_candidates) == 1:
        winner = model_candidates[0]
        state.target_pal = winner.pal_id
        state.confirmed_target_pal = winner.pal_id
        await repository.save(session_id, state)
        return [f"目标唯一：{winner.cn_name}，正在查询父母。"], []

    lines = [f"- {c.cn_name} ({c.reason})" for c in model_candidates]
    actions = [build_confirm_action(c.pal_id, c.cn_name) for c in model_candidates]
    return [top_candidates_message(lines)], actions


async def query_parents_and_record(
    *,
    session_id: str,
    state: SessionState,
    repository: SessionRepository,
    client: BreedingApiClient,
    pal_id: str,
) -> tuple[list[str], list[dict]]:
    pairs = await client.get_parent_pairs(pal_id)
    current_depth = state.node_depths.get(pal_id, 0)
    state.explored_nodes = sorted(set(state.explored_nodes + [pal_id]))
    if pal_id not in state.node_depths:
        state.node_depths[pal_id] = current_depth
    await repository.save(session_id, state)

    seen_actions: set[str] = set()
    actions: list[dict] = []
    for pair in pairs:
        parent_a = str(pair.get("parent_a", "")).strip()
        parent_b = str(pair.get("parent_b", "")).strip()
        method = str(pair.get("method", "breed"))
        if not parent_a or not parent_b:
            continue

        pa_detail = await client.resolve_pal(parent_a)
        pb_detail = await client.resolve_pal(parent_b)
        parent_a_id = pa_detail.get("id", parent_a)
        parent_b_id = pb_detail.get("id", parent_b)
        parent_a_name = pa_detail.get("cn_name", parent_a)
        parent_b_name = pb_detail.get("cn_name", parent_b)
        next_depth = current_depth + 1

        edge = Edge(
            child_pal_id=pal_id,
            parent_a_id=parent_a_id,
            parent_a_name=parent_a_name,
            parent_b_id=parent_b_id,
            parent_b_name=parent_b_name,
            method=method,
            depth=next_depth,
        )
        await repository.append_edge(session_id, edge)
        state.node_depths[parent_a_id] = min(
            state.node_depths.get(parent_a_id, next_depth), next_depth
        )
        state.node_depths[parent_b_id] = min(
            state.node_depths.get(parent_b_id, next_depth), next_depth
        )

        if parent_a_id not in seen_actions:
            actions.append(build_expand_action(parent_a_id))
            seen_actions.add(parent_a_id)
        if parent_b_id not in seen_actions:
            actions.append(build_expand_action(parent_b_id))
            seen_actions.add(parent_b_id)

    await repository.save(session_id, state)
    state = await repository.get(session_id) or state
    actions.append(build_summarize_action(session_id))
    return [parent_pairs_message(pal_id, pairs)], actions


async def summarize_route(
    state: SessionState, mode: str = MODE_EXPLORED_ONLY
) -> tuple[list[str], dict]:
    if mode != MODE_EXPLORED_ONLY:
        mode = MODE_EXPLORED_ONLY

    graph = build_route_graph(state)
    text = to_text_tree(graph)
    graph_json = to_graph_json(graph)
    return [route_message(text, partial=False)], graph_json


def build_reused_node_response(pal_id: str) -> list[str]:
    return [repeated_node_message(pal_id)]
