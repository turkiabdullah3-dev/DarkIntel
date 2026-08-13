from pathlib import Path

from darkintel.graph import GraphQuery, GraphStore

from .common import case_path


def graph_data(root: Path, case_id: str, node_type: str | None, relationship: str | None,
               min_confidence: float, origin: str | None, value: str | None,
               max_nodes: int) -> dict[str, object]:
    case_path(root, case_id)
    graph = GraphStore(root).load(case_id)
    nodes = [node for node in graph.nodes if (not node_type or node.node_type.value == node_type)
             and (not origin or node.attributes.get("origin") == origin)
             and (not value or node.value == value)]
    truncated = len(nodes) > max_nodes
    nodes = nodes[:max_nodes]
    ids = {node.node_id for node in nodes}
    edges = [edge for edge in graph.edges if edge.source_node_id in ids and edge.target_node_id in ids
             and (not relationship or edge.relationship.value == relationship)
             and edge.confidence >= min_confidence]
    return {"elements": {"nodes": [{"data": {"id": node.node_id, "label": node.label,
                                                "type": node.node_type.value, "value": node.value,
                                                "origin": node.attributes.get("origin")}} for node in nodes],
                         "edges": [{"data": {"id": edge.edge_id, "source": edge.source_node_id,
                                              "target": edge.target_node_id,
                                              "relationship": edge.relationship.value,
                                              "confidence": edge.confidence}} for edge in edges]},
            "summary": GraphStore.summary(graph), "truncated": truncated, "max_nodes": max_nodes}


def node_detail(root: Path, case_id: str, node_id: str) -> dict[str, object]:
    case_path(root, case_id)
    graph = GraphStore(root).load(case_id)
    node = next((node for node in graph.nodes if node.node_id == node_id), None)
    if node is None:
        raise LookupError("Graph node does not exist.")
    connected = [edge for edge in graph.edges if node_id in {edge.source_node_id, edge.target_node_id}][:500]
    nodes = {item.node_id: item for item in graph.nodes}
    relationships = []
    for edge in connected:
        neighbor_id = edge.target_node_id if edge.source_node_id == node_id else edge.source_node_id
        relationships.append({"edge": edge.to_dict(), "neighbor": nodes[neighbor_id].to_dict()})
    return {"node": node.to_dict(), "relationships": relationships, "truncated": len(connected) == 500}


def path(root: Path, case_id: str, source: str, target: str, max_depth: int) -> dict[str, object]:
    case_path(root, case_id)
    graph = GraphStore(root).load(case_id)
    return {"nodes": [node.to_dict() for node in GraphQuery(graph.nodes, graph.edges)
                       .path_between(source, target, max_depth)]}
