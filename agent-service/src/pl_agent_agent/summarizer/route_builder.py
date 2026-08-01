"""Build a route graph from explored edges."""

from __future__ import annotations

from collections import deque

from ..state.models import Edge, SessionState


class RouteGraph:
    def __init__(self, nodes: list[dict], edges: list[dict], roots: list[str]) -> None:
        self.nodes = nodes
        self.edges = edges
        self.roots = roots


def build_route_graph(state: SessionState) -> RouteGraph:
    if not state.target_pal:
        raise ValueError("missing target_pal")

    nodes_by_id: dict[str, dict] = {
        state.target_pal: {
            "id": state.target_pal,
            "name": state.target_pal,
            "depth": 0,
            "status": "target",
        }
    }
    graph_edges: list[dict] = []

    queue = deque([(state.target_pal, 0)])
    expanded: set[tuple[str, int]] = set()
    by_child: dict[str, list[Edge]] = {}
    for edge in state.edges:
        by_child.setdefault(edge.child_pal_id, []).append(edge)

    while queue:
        child, depth = queue.popleft()
        if (child, depth) in expanded:
            continue
        expanded.add((child, depth))

        for edge in by_child.get(child, []):
            for parent_id, parent_name in [
                (edge.parent_a_id, edge.parent_a_name),
                (edge.parent_b_id, edge.parent_b_name),
            ]:
                if parent_id not in nodes_by_id:
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
                graph_edges.append(
                    {"source": parent_id, "target": child, "method": edge.method}
                )
                queue.append((parent_id, depth + 1))

    return RouteGraph(
        nodes=list(nodes_by_id.values()), edges=graph_edges, roots=[state.target_pal]
    )
