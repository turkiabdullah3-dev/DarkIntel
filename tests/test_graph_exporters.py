import json
import xml.etree.ElementTree as ET

from darkintel.graph.exporters import export_cytoscape, export_graphml, export_json
from darkintel.graph.models import GraphEdge, GraphNode, GraphNodeType, GraphRelationship

CASE = "CASE-2026-0001"


def graph():
    a = GraphNode.generated(CASE, GraphNodeType.DOMAIN, "example.com", "<script>&")
    b = GraphNode.generated(CASE, GraphNodeType.PROVIDER, "local")
    edge = GraphEdge.generated(CASE, a.node_id, b.node_id, GraphRelationship.ENRICHED_BY, 0.9, ["a&b"])
    return [a, b], [edge]


def test_json_and_cytoscape_export():
    nodes, edges = graph()
    assert json.loads(export_json(CASE, nodes, edges, []))["case_id"] == CASE
    cyto = json.loads(export_cytoscape(nodes, edges))["elements"]
    assert len(cyto["nodes"]) == 2 and cyto["edges"][0]["data"]["relationship"] == "enriched_by"


def test_graphml_is_valid_and_xml_escaped():
    nodes, edges = graph()
    output = export_graphml(nodes, edges)
    assert "<script>" not in output and "&lt;script&gt;&amp;" in output
    assert ET.fromstring(output).tag.endswith("graphml")
