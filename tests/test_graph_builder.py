
from darkintel.cases import CaseStore
from darkintel.graph.builder import RelationshipGraphBuilder
from darkintel.graph.models import GraphNodeType, GraphRelationship
from darkintel.utils import write_json


def prepare(tmp_path):
    case = CaseStore(tmp_path).create_case("Build Graph")
    root = tmp_path / case.case_id
    onion = "a" * 56 + ".onion"
    write_json(root / "results" / "result.json", {"url": f"http://{onion}/", "is_live": True,
                                                    "status_code": 200, "sha256": "b" * 64,
                                                    "evidence_file": "evidence/body.bin",
                                                    "observed_at": "2026-01-01T00:00:00Z"})
    write_json(root / "extracted_iocs" / "indicators.json", {"indicators": [
        {"type": "domain", "normalized_value": "example.com", "source": "evidence/body.bin",
         "sources": ["evidence/body.bin"], "confidence": 0.8},
        {"type": "sha256", "normalized_value": "b" * 64, "source": "evidence/body.bin"},
    ]})
    write_json(root / "enrichment" / "records.json", {"results": [{
        "indicator": {"type": "domain", "normalized_value": "example.com"},
        "records": [{"provider": "virustotal", "indicator_type": "domain",
                     "normalized_value": "example.com", "success": True,
                     "summary": {"malicious": 2}}]}]})
    write_json(root / "timeline" / "events.json", {"events": [{
        "event_id": "11111111-1111-1111-1111-111111111111", "title": "IOC observed",
        "event_type": "ioc_observed", "timestamp": "2026-01-01T00:00:00Z",
        "object_type": "domain", "object_value": "example.com",
    }]})
    return case, root


def test_builder_creates_core_nodes_relationships_and_provenance(tmp_path):
    case, _ = prepare(tmp_path)
    graph = RelationshipGraphBuilder(tmp_path).build_case_graph(case.case_id)
    node_types = {node.node_type for node in graph.nodes}
    assert {GraphNodeType.CASE, GraphNodeType.TARGET, GraphNodeType.ONION, GraphNodeType.EVIDENCE,
            GraphNodeType.DOMAIN, GraphNodeType.SHA256, GraphNodeType.PROVIDER,
            GraphNodeType.ENRICHMENT_RECORD, GraphNodeType.TIMELINE_EVENT} <= node_types
    relationships = {edge.relationship for edge in graph.edges}
    assert {GraphRelationship.DERIVED_FROM, GraphRelationship.HASHED_AS, GraphRelationship.CONTAINS,
            GraphRelationship.ENRICHED_BY, GraphRelationship.REPORTED_BY,
            GraphRelationship.REFERENCES, GraphRelationship.BELONGS_TO_CASE} <= relationships
    contains = next(edge for edge in graph.edges if edge.relationship == GraphRelationship.CONTAINS)
    assert contains.provenance and contains.confidence == 0.95


def test_exact_hash_enrichment_and_timeline_correlation(tmp_path):
    case, _ = prepare(tmp_path)
    graph = RelationshipGraphBuilder(tmp_path).build_case_graph(case.case_id)
    nodes = {node.node_id: node for node in graph.nodes}
    hashed = [edge for edge in graph.edges if edge.relationship == GraphRelationship.HASHED_AS]
    assert any(nodes[edge.target_node_id].value == "b" * 64 for edge in hashed)
    references = [edge for edge in graph.edges if edge.relationship == GraphRelationship.REFERENCES]
    assert any(nodes[edge.source_node_id].node_type == GraphNodeType.TIMELINE_EVENT
               and nodes[edge.target_node_id].value == "example.com" for edge in references)


def test_build_idempotency_and_manual_persistence(tmp_path):
    case, _ = prepare(tmp_path)
    builder = RelationshipGraphBuilder(tmp_path)
    first = builder.build_case_graph(case.case_id)
    from darkintel.graph.store import GraphStore
    manual = GraphStore(tmp_path).add_node(case.case_id, "organization", "Example Inc", "Example Inc")
    second = builder.build_case_graph(case.case_id)
    assert {node.node_id for node in first.nodes} <= {node.node_id for node in second.nodes}
    assert manual.node_id in {node.node_id for node in second.nodes}
    assert {edge.edge_id for edge in first.edges} <= {edge.edge_id for edge in second.edges}


def test_malformed_source_isolated_and_limits_warn(tmp_path):
    case, root = prepare(tmp_path)
    (root / "results" / "bad.json").write_text("{bad", encoding="utf-8")
    graph = RelationshipGraphBuilder(tmp_path, max_nodes=3, max_edges=3).build_case_graph(case.case_id)
    assert len(graph.nodes) <= 3 and len(graph.edges) <= 3
    assert any("Malformed" in warning for warning in graph.warnings)
    assert any("limit" in warning for warning in graph.warnings)
