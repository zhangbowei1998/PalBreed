"""Build a route graph from explored edges."""

from __future__ import annotations

from collections import deque

from ..state.models import Edge, SessionState


class RouteGraph:
    def __init__(self, nodes: list[dict], edges: list[dict], roots: list[str]) -> None:
        self.nodes = nodes
        self.edges = edges
        self.roots = roots


def _resolve_target_name(state: SessionState) -> str:
    if not state.target_pal:
        return ""
    for candidate in state.target_candidates:
        if candidate.pal_id == state.target_pal and candidate.cn_name:
            return candidate.cn_name
    return state.target_pal


def build_route_graph(state: SessionState) -> RouteGraph:
    if not state.target_pal:
        raise ValueError("missing target_pal")

    max_nodes = max(1, int(getattr(state.limits, "max_nodes", 200) or 200))

    nodes_by_id: dict[str, dict] = {
        state.target_pal: {
            "id": state.target_pal,
            "name": _resolve_target_name(state),
            "depth": 0,
            "status": "target",
        }
    }
    graph_edges: list[dict] = []
    edge_seen: set[tuple[str, str, str]] = set()

    queue = deque([(state.target_pal, 0)])
    expanded_nodes: set[str] = set()
    by_child: dict[str, list[Edge]] = {}
    for edge in state.edges:
        by_child.setdefault(edge.child_pal_id, []).append(edge)

    while queue:
        child, depth = queue.popleft()
        if child in expanded_nodes:
            continue
        expanded_nodes.add(child)

        for edge in by_child.get(child, []):
            for parent_id, parent_name in [
                (edge.parent_a_id, edge.parent_a_name),
                (edge.parent_b_id, edge.parent_b_name),
            ]:
                if parent_id not in nodes_by_id:
                    if len(nodes_by_id) >= max_nodes:
                        continue
                    nodes_by_id[parent_id] = {
                        "id": parent_id,
                        "name": parent_name,
                        "depth": depth + 1,
                        "status": (
                            "explored"
                            if parent_id in state.explored_nodes
                            else "unknown"
                        ),
                    }

                edge_key = (parent_id, child, edge.method)
                if edge_key not in edge_seen:
                    edge_seen.add(edge_key)
                    graph_edges.append(
                        {"source": parent_id, "target": child, "method": edge.method}
                    )

                if parent_id not in expanded_nodes and len(nodes_by_id) < max_nodes:
                    queue.append((parent_id, depth + 1))

    return RouteGraph(
        nodes=list(nodes_by_id.values()), edges=graph_edges, roots=[state.target_pal]
    )
