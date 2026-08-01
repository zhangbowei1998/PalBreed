"""Serialize route graph for API output."""

from __future__ import annotations

from .route_builder import RouteGraph


def to_graph_json(graph: RouteGraph) -> dict:
    return {
        "nodes": graph.nodes,
        "edges": graph.edges,
        "roots": graph.roots,
    }
