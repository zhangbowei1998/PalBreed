"""Workflow node helpers."""

from __future__ import annotations

from ..clients.breeding_api_client import BreedingApiClient
from ..config import work_type_to_cn
from ..interaction.actions import (
    build_confirm_action,
    build_continue_action,
    build_select_pair_action,
)
from ..interaction.message_templates import (
    parent_pairs_message,
    repeated_node_message,
    selected_pair_message,
    top_candidates_message,
)
from ..state.models import Edge, SessionState, TargetCandidate
from ..state.repository import SessionRepository


async def resolve_top_candidates(
    *,
    session_id: str,
    state: SessionState,
    repository: SessionRepository,
    client: BreedingApiClient,
    top_n: int,
    work_type: str = "handiwork",
) -> tuple[list[str], list[dict]]:
    candidates = await client.query_top_suitability(work_type, 1, top_n)
    if not candidates:
        cn = work_type_to_cn(work_type)
        return [f"未找到{cn}候选帕鲁。"], []

    cn = work_type_to_cn(work_type)
    model_candidates = [
        TargetCandidate(
            pal_id=item.pal.id,
            cn_name=item.pal.cn_name,
            score=item.matched_level,
            reason=f"{cn} Lv{item.matched_level}",
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
    state.current_focus_pal = pal_id
    state.explored_nodes = sorted(set(state.explored_nodes + [pal_id]))
    if pal_id not in state.node_depths:
        state.node_depths[pal_id] = current_depth
    await repository.save(session_id, state)

    rendered_pairs: list[dict] = []
    option_edges: list[Edge] = []
    actions: list[dict] = []
    for idx, pair in enumerate(pairs):
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
        option_edges.append(edge)
        rendered_pairs.append(
            {
                "parent_a": parent_a_name,
                "parent_b": parent_b_name,
                "method": method,
            }
        )
        await repository.append_edge(session_id, edge)
        state.node_depths[parent_a_id] = min(
            state.node_depths.get(parent_a_id, next_depth), next_depth
        )
        state.node_depths[parent_b_id] = min(
            state.node_depths.get(parent_b_id, next_depth), next_depth
        )

        actions.append(
            build_select_pair_action(
                child_pal_id=pal_id,
                pair_index=idx,
                parent_a_name=parent_a_name,
                parent_b_name=parent_b_name,
            )
        )

    state.candidate_pairs[pal_id] = option_edges

    await repository.save(session_id, state)
    state = await repository.get(session_id) or state
    return [parent_pairs_message(pal_id, rendered_pairs)], actions


async def select_parent_pair(
    *,
    session_id: str,
    state: SessionState,
    repository: SessionRepository,
    child_pal_id: str,
    pair_index: int,
) -> tuple[list[str], list[dict]]:
    options = state.candidate_pairs.get(child_pal_id, [])
    if not options:
        raise ValueError(f"{child_pal_id} 当前没有可选父母组合")
    if pair_index < 0 or pair_index >= len(options):
        raise ValueError("pair_index 超出范围")

    selected = options[pair_index]
    state.selected_pairs = [
        edge for edge in state.selected_pairs if edge.child_pal_id != child_pal_id
    ]
    state.selected_pairs.append(selected)
    state.current_focus_pal = child_pal_id
    await repository.save(session_id, state)

    messages = [
        selected_pair_message(
            child_name=child_pal_id,
            parent_a_name=selected.parent_a_name,
            parent_b_name=selected.parent_b_name,
        )
    ]
    actions = [
        build_continue_action(selected.parent_a_id, selected.parent_a_name),
        build_continue_action(selected.parent_b_id, selected.parent_b_name),
    ]
    return messages, actions


def build_reused_node_response(pal_id: str) -> list[str]:
    return [repeated_node_message(pal_id)]
