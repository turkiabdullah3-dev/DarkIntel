"""Bounded local graph queries."""

from __future__ import annotations

from collections import deque

from .models import GraphEdge, GraphNode, GraphNodeType, GraphRelationship

MAX_PATH_DEPTH = 6
MAX_VISITED_NODES = 50_000


class GraphQuery:
    def __init__(self, nodes: list[GraphNode], edges: list[GraphEdge]) -> None:
        self.nodes = {node.node_id: node for node in nodes}
        self.edges = edges

    def neighbors(self, node_id: str) -> list[GraphNode]:
        if node_id not in self.nodes:
            raise KeyError("node not found")
        ids = {edge.target_node_id if edge.source_node_id == node_id else edge.source_node_id
               for edge in self.edges if node_id in {edge.source_node_id, edge.target_node_id}}
        return sorted((self.nodes[item] for item in ids), key=lambda node: node.node_id)

    def nodes_by_type(self, node_type: str) -> list[GraphNode]:
        kind = GraphNodeType(node_type)
        return sorted((node for node in self.nodes.values() if node.node_type == kind), key=lambda node: node.node_id)

    def edges_by_relationship(self, relationship: str) -> list[GraphEdge]:
        kind = GraphRelationship(relationship)
        return sorted((edge for edge in self.edges if edge.relationship == kind), key=lambda edge: edge.edge_id)

    def find_node(self, node_type: str, value: str) -> GraphNode | None:
        kind = GraphNodeType(node_type)
        return next((node for node in self.nodes.values() if node.node_type == kind and node.value == value), None)

    def path_between(self, start: str, end: str, max_depth: int = 4) -> list[GraphNode]:
        if not 1 <= max_depth <= MAX_PATH_DEPTH:
            raise ValueError(f"max_depth must be between 1 and {MAX_PATH_DEPTH}")
        if start not in self.nodes or end not in self.nodes:
            raise KeyError("node not found")
        queue = deque([(start, [start], 0)])
        visited = {start}
        while queue:
            current, path, depth = queue.popleft()
            if current == end:
                return [self.nodes[item] for item in path]
            if depth >= max_depth:
                continue
            for neighbor in self.neighbors(current):
                if neighbor.node_id not in visited:
                    visited.add(neighbor.node_id)
                    if len(visited) > MAX_VISITED_NODES:
                        raise ValueError("path search visited-node limit reached")
                    queue.append((neighbor.node_id, path + [neighbor.node_id], depth + 1))
        return []
