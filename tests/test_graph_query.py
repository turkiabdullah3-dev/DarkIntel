import pytest

from darkintel.graph.models import GraphEdge, GraphNode, GraphNodeType, GraphRelationship
from darkintel.graph.query import GraphQuery

CASE = "CASE-2026-0001"


def graph():
    nodes = [GraphNode.generated(CASE, GraphNodeType.DOMAIN, f"n{i}.test") for i in range(4)]
    edges = [GraphEdge.generated(CASE, nodes[i].node_id, nodes[i + 1].node_id,
                                 GraphRelationship.RELATED_TO, 1, ["test"]) for i in range(3)]
    return nodes, edges, GraphQuery(nodes, edges)


def test_neighbors_type_relationship_and_find():
    nodes, _, query = graph()
    assert query.neighbors(nodes[1].node_id) == sorted([nodes[0], nodes[2]], key=lambda node: node.node_id)
    assert len(query.nodes_by_type("domain")) == 4
    assert len(query.edges_by_relationship("related_to")) == 3
    assert query.find_node("domain", "n2.test") == nodes[2]


def test_bounded_path_search_and_depth_limit():
    nodes, _, query = graph()
    assert [node.node_id for node in query.path_between(nodes[0].node_id, nodes[3].node_id, 3)] == [
        node.node_id for node in nodes]
    assert query.path_between(nodes[0].node_id, nodes[3].node_id, 2) == []
    with pytest.raises(ValueError):
        query.path_between(nodes[0].node_id, nodes[3].node_id, 7)
