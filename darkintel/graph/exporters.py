"""Safe deterministic graph exports."""

from __future__ import annotations

import json
# B405 rationale: ElementTree is used only to construct exports and never parses untrusted XML.
import xml.etree.ElementTree as ET  # nosec B405

from .models import GraphEdge, GraphNode


def export_json(case_id: str, nodes: list[GraphNode], edges: list[GraphEdge], warnings: list[str]) -> str:
    return json.dumps({"case_id": case_id, "nodes": [node.to_dict() for node in sorted(nodes, key=lambda n: n.node_id)],
                       "edges": [edge.to_dict() for edge in sorted(edges, key=lambda e: e.edge_id)],
                       "warnings": warnings}, indent=2, ensure_ascii=False) + "\n"


def export_cytoscape(nodes: list[GraphNode], edges: list[GraphEdge]) -> str:
    payload = {"elements": {
        "nodes": [{"data": {"id": node.node_id, "label": node.label, "type": node.node_type.value,
                              "value": node.value}} for node in sorted(nodes, key=lambda n: n.node_id)],
        "edges": [{"data": {"id": edge.edge_id, "source": edge.source_node_id,
                              "target": edge.target_node_id, "relationship": edge.relationship.value,
                              "confidence": edge.confidence}}
                  for edge in sorted(edges, key=lambda e: e.edge_id)],
    }}
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def export_graphml(nodes: list[GraphNode], edges: list[GraphEdge]) -> str:
    namespace = "http://graphml.graphdrawing.org/xmlns"
    ET.register_namespace("", namespace)
    root = ET.Element(f"{{{namespace}}}graphml")
    for key_id, target, name in (("node_type", "node", "node_type"), ("label", "node", "label"),
                                 ("value", "node", "value"), ("attributes", "node", "attributes"),
                                 ("relationship", "edge", "relationship"),
                                 ("confidence", "edge", "confidence"),
                                 ("provenance", "edge", "provenance")):
        ET.SubElement(root, f"{{{namespace}}}key", id=key_id, **{"for": target, "attr.name": name,
                                                                  "attr.type": "string"})
    graph = ET.SubElement(root, f"{{{namespace}}}graph", id="G", edgedefault="directed")
    for node in sorted(nodes, key=lambda item: item.node_id):
        element = ET.SubElement(graph, f"{{{namespace}}}node", id=node.node_id)
        for key, value in (("node_type", node.node_type.value), ("label", node.label), ("value", node.value),
                           ("attributes", json.dumps(node.attributes, sort_keys=True, ensure_ascii=False))):
            ET.SubElement(element, f"{{{namespace}}}data", key=key).text = value
    for edge in sorted(edges, key=lambda item: item.edge_id):
        element = ET.SubElement(graph, f"{{{namespace}}}edge", id=edge.edge_id,
                                source=edge.source_node_id, target=edge.target_node_id)
        for key, value in (("relationship", edge.relationship.value), ("confidence", str(edge.confidence)),
                           ("provenance", json.dumps(edge.provenance, ensure_ascii=False))):
            ET.SubElement(element, f"{{{namespace}}}data", key=key).text = value
    return ET.tostring(root, encoding="unicode", xml_declaration=True) + "\n"
