"""Case-isolated relationship graph persistence and manual objects."""

from __future__ import annotations

from collections import Counter, deque
from pathlib import Path
import logging

from .correlation import merge_edges, validate_graph
from .exporters import export_cytoscape, export_graphml
from .models import GraphEdge, GraphNode, GraphNodeType, GraphRelationship, GraphResult
from ..models import utc_now
from ..utils import read_json, validate_case_id, write_json

LOGGER = logging.getLogger(__name__)
MAX_GRAPH_NODES = 100_000
MAX_GRAPH_EDGES = 250_000


class GraphStore:
    def __init__(self, root: str | Path = "cases") -> None:
        self.root = Path(root)

    def directory(self, case_id: str) -> Path:
        validate_case_id(case_id)
        case_path = self.root / case_id
        if not (case_path / "case.json").is_file():
            raise FileNotFoundError(f"case not found: {case_id}")
        directory = case_path / "graph"
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    def load(self, case_id: str) -> GraphResult:
        path = self.directory(case_id) / "graph.json"
        if not path.is_file():
            return GraphResult(case_id, [], [])
        payload = read_json(path)
        nodes = [GraphNode.from_dict(item) for item in payload.get("nodes", [])]
        edges = [GraphEdge.from_dict(item) for item in payload.get("edges", [])]
        validate_graph(case_id, nodes, edges)
        return GraphResult(case_id, sorted(nodes, key=lambda node: node.node_id),
                           sorted(edges, key=lambda edge: edge.edge_id), payload.get("warnings", []))

    def save(self, result: GraphResult) -> GraphResult:
        existing = self.load(result.case_id)
        manual_nodes = [node for node in existing.nodes if node.attributes.get("origin") == "analyst"]
        existing_nodes = {node.node_id: node for node in existing.nodes}
        for node in result.nodes:
            previous = existing_nodes.get(node.node_id)
            if previous:
                node.source_ids = sorted(set(node.source_ids + previous.source_ids))[:1_000]
        node_map = {node.node_id: node for node in result.nodes + manual_nodes}
        manual_edges = [edge for edge in existing.edges if edge.attributes.get("origin") == "analyst"]
        existing_edges = {edge.edge_id: edge for edge in existing.edges}
        for edge in result.edges:
            previous = existing_edges.get(edge.edge_id)
            if previous:
                edge.provenance = sorted(set(edge.provenance + previous.provenance))[:1_000]
        edges = merge_edges(result.edges + manual_edges)
        warnings = list(result.warnings)
        if len(node_map) > MAX_GRAPH_NODES:
            warnings.append(f"Graph node limit reached at {MAX_GRAPH_NODES}")
            kept = dict(list(sorted(node_map.items()))[:MAX_GRAPH_NODES])
            node_map = kept
            edges = [edge for edge in edges if edge.source_node_id in kept and edge.target_node_id in kept]
        if len(edges) > MAX_GRAPH_EDGES:
            warnings.append(f"Graph edge limit reached at {MAX_GRAPH_EDGES}")
            edges = edges[:MAX_GRAPH_EDGES]
        nodes = sorted(node_map.values(), key=lambda node: node.node_id)
        validate_graph(result.case_id, nodes, edges)
        stored = GraphResult(result.case_id, nodes, edges, warnings[:100])
        directory = self.directory(result.case_id)
        write_json(directory / "nodes.json", {"case_id": result.case_id,
                                               "nodes": [node.to_dict() for node in nodes]})
        write_json(directory / "edges.json", {"case_id": result.case_id,
                                               "edges": [edge.to_dict() for edge in edges]})
        payload = stored.to_dict()
        payload["generated_at"] = utc_now().isoformat().replace("+00:00", "Z")
        write_json(directory / "graph.json", payload)
        write_json(directory / "summary.json", self.summary(stored))
        return stored

    def add_node(self, case_id: str, node_type: str, value: str, label: str) -> GraphNode:
        graph = self.load(case_id)
        node = GraphNode.analyst(case_id, GraphNodeType(node_type), value, label)
        graph.nodes.append(node)
        self.save(graph)
        LOGGER.info("manual node created: case=%s node=%s", case_id, node.node_id)
        return node

    def add_edge(self, case_id: str, source: str, target: str, relationship: str,
                 confidence: float = 0.75) -> GraphEdge:
        graph = self.load(case_id)
        node_ids = {node.node_id for node in graph.nodes}
        if source not in node_ids or target not in node_ids:
            raise ValueError("manual edge endpoints must exist in the same case")
        edge = GraphEdge.analyst(case_id, source, target, GraphRelationship(relationship), confidence)
        graph.edges.append(edge)
        self.save(graph)
        LOGGER.info("manual edge created: case=%s edge=%s", case_id, edge.edge_id)
        return edge

    def export(self, case_id: str, format_name: str) -> Path:
        graph = self.load(case_id)
        directory = self.directory(case_id)
        if format_name == "json":
            path = directory / "graph.json"
        elif format_name == "graphml":
            path = directory / "graph.graphml"
            path.write_text(export_graphml(graph.nodes, graph.edges), encoding="utf-8")
        elif format_name == "cytoscape":
            path = directory / "cytoscape.json"
            path.write_text(export_cytoscape(graph.nodes, graph.edges), encoding="utf-8")
        else:
            raise ValueError("unsupported graph export format")
        LOGGER.info("graph exported: case=%s format=%s", case_id, format_name)
        return path

    @staticmethod
    def summary(graph: GraphResult) -> dict[str, object]:
        node_types = Counter(node.node_type.value for node in graph.nodes)
        relationships = Counter(edge.relationship.value for edge in graph.edges)
        adjacency = {node.node_id: set() for node in graph.nodes}
        for edge in graph.edges:
            adjacency[edge.source_node_id].add(edge.target_node_id)
            adjacency[edge.target_node_id].add(edge.source_node_id)
        isolated = sum(not neighbors for neighbors in adjacency.values())
        components = 0
        unseen = set(adjacency)
        while unseen:
            components += 1
            queue = deque([unseen.pop()])
            while queue:
                current = queue.popleft()
                for neighbor in adjacency[current] & unseen:
                    unseen.remove(neighbor)
                    queue.append(neighbor)
        return {"total_nodes": len(graph.nodes), "total_edges": len(graph.edges),
                "node_types": dict(sorted(node_types.items())),
                "relationship_types": dict(sorted(relationships.items())),
                "isolated_nodes": isolated, "connected_components": components,
                "warnings": graph.warnings[:100]}
