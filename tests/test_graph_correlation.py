import pytest

from darkintel.graph.correlation import merge_edges, validate_graph
from darkintel.graph.models import GraphEdge, GraphNode, GraphNodeType, GraphRelationship

CASE = "CASE-2026-0001"


def fixture():
    a = GraphNode.generated(CASE, GraphNodeType.EVIDENCE, "evidence/a")
    b = GraphNode.generated(CASE, GraphNodeType.DOMAIN, "example.com")
    return a, b


def test_duplicate_edge_merges_provenance_and_confidence():
    a, b = fixture()
    one = GraphEdge.generated(CASE, a.node_id, b.node_id, GraphRelationship.CONTAINS, 0.9, ["one"])
    two = GraphEdge.generated(CASE, a.node_id, b.node_id, GraphRelationship.CONTAINS, 1.0, ["two"])
    merged = merge_edges([one, two])
    assert len(merged) == 1 and merged[0].provenance == ["one", "two"]
    assert merged[0].confidence == 1.0


def test_dangling_and_cross_case_rejected():
    a, b = fixture()
    edge = GraphEdge.generated(CASE, a.node_id, b.node_id, GraphRelationship.CONTAINS, 1, ["x"])
    with pytest.raises(ValueError, match="dangling"):
        validate_graph(CASE, [a], [edge])
    other = GraphNode.generated("CASE-2026-0002", GraphNodeType.DOMAIN, "other.com")
    with pytest.raises(ValueError, match="cross-case"):
        validate_graph(CASE, [a, other], [])
