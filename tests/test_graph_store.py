import json

import pytest

from darkintel.cases import CaseStore
from darkintel.graph.models import GraphEdge, GraphNode, GraphNodeType, GraphRelationship, GraphResult
from darkintel.graph.store import GraphStore


def setup(tmp_path):
    case = CaseStore(tmp_path).create_case("Graph")
    store = GraphStore(tmp_path)
    case_node = GraphNode.generated(case.case_id, GraphNodeType.CASE, case.case_id)
    domain = GraphNode.generated(case.case_id, GraphNodeType.DOMAIN, "example.com")
    edge = GraphEdge.generated(case.case_id, domain.node_id, case_node.node_id,
                               GraphRelationship.BELONGS_TO_CASE, 1, ["case.json"])
    store.save(GraphResult(case.case_id, [case_node, domain], [edge]))
    return case, store


def test_storage_files_summary_and_components(tmp_path):
    case, store = setup(tmp_path)
    directory = tmp_path / case.case_id / "graph"
    assert all((directory / name).is_file() for name in ("nodes.json", "edges.json", "graph.json", "summary.json"))
    summary = json.loads((directory / "summary.json").read_text())
    assert summary["total_nodes"] == 2 and summary["total_edges"] == 1
    assert summary["connected_components"] == 1 and summary["isolated_nodes"] == 0


def test_manual_node_and_edge_persist_across_rebuild_save(tmp_path):
    case, store = setup(tmp_path)
    actor = store.add_node(case.case_id, "threat_actor", "Example Group", "Example Group")
    graph = store.load(case.case_id)
    domain = next(node for node in graph.nodes if node.node_type == GraphNodeType.DOMAIN)
    manual_edge = store.add_edge(case.case_id, actor.node_id, domain.node_id, "associated_with")
    generated_only = GraphResult(case.case_id,
                                 [node for node in graph.nodes if node.attributes.get("origin") != "analyst"],
                                 [edge for edge in graph.edges if edge.attributes.get("origin") != "analyst"])
    rebuilt = store.save(generated_only)
    assert actor.node_id in {node.node_id for node in rebuilt.nodes}
    assert manual_edge.edge_id in {edge.edge_id for edge in rebuilt.edges}
    assert manual_edge.confidence == 0.75 and manual_edge.attributes["created_by"] == "analyst"


def test_manual_edge_requires_existing_same_case_nodes(tmp_path):
    case, store = setup(tmp_path)
    with pytest.raises(ValueError):
        store.add_edge(case.case_id, "00000000-0000-0000-0000-000000000000",
                       "00000000-0000-0000-0000-000000000001", "related_to")


def test_path_traversal_and_exports(tmp_path):
    case, store = setup(tmp_path)
    with pytest.raises(ValueError):
        store.load("../escape")
    assert store.export(case.case_id, "json").name == "graph.json"
    assert store.export(case.case_id, "graphml").is_file()
    assert store.export(case.case_id, "cytoscape").is_file()
