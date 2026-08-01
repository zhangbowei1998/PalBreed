"""Format graph into readable text tree."""

from __future__ import annotations

from collections import defaultdict

from .route_builder import RouteGraph


def to_text_tree(graph: RouteGraph) -> str:
    if not graph.roots:
        return "暂无可汇总路径"

    names = {node["id"]: node.get("name", node["id"]) for node in graph.nodes}
    children: dict[str, list[str]] = defaultdict(list)
    for edge in graph.edges:
        parent = edge["source"]
        child = edge["target"]
        if parent not in children[child]:
            children[child].append(parent)

    root = graph.roots[0]
    lines: list[str] = [names.get(root, root)]

    def render(node_id: str, prefix: str, path: set[str]) -> None:
        items = sorted(children.get(node_id, []), key=lambda x: names.get(x, x))
        for idx, child_id in enumerate(items):
            last = idx == len(items) - 1
            branch = "└─ " if last else "├─ "
            if child_id in path:
                lines.append(f"{prefix}{branch}{names.get(child_id, child_id)} (loop)")
                continue
            lines.append(f"{prefix}{branch}{names.get(child_id, child_id)}")
            next_prefix = prefix + ("   " if last else "│  ")
            render(child_id, next_prefix, path | {child_id})

    render(root, "", {root})
    return "\n".join(lines)
