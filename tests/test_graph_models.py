import uuid

import pytest

from darkintel.graph.models import (GraphEdge, GraphNode, GraphNodeType, GraphRelationship,
                                    stable_edge_id, stable_node_id)

CASE = "CASE-2026-0001"


def test_node_serialization_stable_id_and_bounds():
    one = GraphNode.generated(CASE, GraphNodeType.DOMAIN, "example.com", attributes={"x": "y" * 100_000})
    two = GraphNode.generated(CASE, GraphNodeType.DOMAIN, "example.com")
    assert one.node_id == two.node_id == stable_node_id(CASE, "domain", "example.com")
    assert GraphNode.from_dict(one.to_dict()).node_type == GraphNodeType.DOMAIN
    assert one.attributes["bounded"] is True


def test_controlled_node_type_and_manual_origin():
    with pytest.raises(ValueError):
        GraphNode.generated(CASE, "invented", "x")
    manual = GraphNode.analyst(CASE, GraphNodeType.THREAT_ACTOR, "Example Group", "Example Group")
    assert uuid.UUID(manual.node_id) and manual.attributes["origin"] == "analyst"
    with pytest.raises(ValueError):
        GraphNode.analyst(CASE, GraphNodeType.DOMAIN, "x.test", "X")


def test_edge_serialization_stable_id_and_controlled_relationship():
    source = GraphNode.generated(CASE, GraphNodeType.DOMAIN, "example.com")
    target = GraphNode.generated(CASE, GraphNodeType.PROVIDER, "local")
    edge = GraphEdge.generated(CASE, source.node_id, target.node_id, GraphRelationship.ENRICHED_BY,
                               0.9, ["b", "a", "a"])
    assert edge.edge_id == stable_edge_id(CASE, source.node_id, "enriched_by", target.node_id)
    assert edge.provenance == ["a", "b"]
    assert GraphEdge.from_dict(edge.to_dict()).relationship == GraphRelationship.ENRICHED_BY
    with pytest.raises(ValueError):
        GraphEdge.generated(CASE, source.node_id, target.node_id, "invented", 1.0, [])


def test_self_loop_and_bad_confidence_rejected():
    node = GraphNode.generated(CASE, GraphNodeType.DOMAIN, "example.com")
    with pytest.raises(ValueError):
        GraphEdge.generated(CASE, node.node_id, node.node_id, GraphRelationship.RELATED_TO, 1, [])
    target = GraphNode.generated(CASE, GraphNodeType.PROVIDER, "local")
    with pytest.raises(ValueError):
        GraphEdge.generated(CASE, node.node_id, target.node_id, GraphRelationship.RELATED_TO, 2, [])
