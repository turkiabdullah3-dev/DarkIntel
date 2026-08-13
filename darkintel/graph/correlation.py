"""Graph integrity and deterministic edge merging."""

from __future__ import annotations

from .models import GraphEdge, GraphNode


def merge_edges(edges: list[GraphEdge]) -> list[GraphEdge]:
    merged: dict[tuple[str, str, str], GraphEdge] = {}
    for edge in edges:
        key = (edge.source_node_id, edge.relationship.value, edge.target_node_id)
        current = merged.get(key)
        if current is None:
            merged[key] = edge
        else:
            current.provenance = sorted(set(current.provenance + edge.provenance))[:1_000]
            current.confidence = max(current.confidence, edge.confidence)
    return sorted(merged.values(), key=lambda edge: edge.edge_id)


def validate_graph(case_id: str, nodes: list[GraphNode], edges: list[GraphEdge]) -> list[str]:
    warnings: list[str] = []
    node_ids: set[str] = set()
    for node in nodes:
        if node.case_id != case_id:
            raise ValueError("cross-case node rejected")
        if node.node_id in node_ids:
            raise ValueError("duplicate node ID")
        node_ids.add(node.node_id)
    edge_ids: set[str] = set()
    for edge in edges:
        if edge.case_id != case_id:
            raise ValueError("cross-case edge rejected")
        if edge.edge_id in edge_ids:
            raise ValueError("duplicate edge ID")
        edge_ids.add(edge.edge_id)
        if edge.source_node_id not in node_ids or edge.target_node_id not in node_ids:
            raise ValueError("dangling edge rejected")
    return warnings
