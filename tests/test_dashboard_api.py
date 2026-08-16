
import pytest
from fastapi.testclient import TestClient

from dashboard.backend.app import create_app
from dashboard.backend.dependencies import cases_root
from darkintel.cases import CaseStore
from darkintel.graph.models import GraphEdge, GraphNode, GraphNodeType, GraphRelationship, GraphResult
from darkintel.graph.store import GraphStore
from darkintel.timeline.models import TimelineEvent, TimelineEventType
from darkintel.timeline.store import TimelineStore
from darkintel.utils import write_json


@pytest.fixture
def dashboard(tmp_path):
    root = tmp_path / "cases"
    case = CaseStore(root).create_case("Dashboard Case", "<script>alert(1)</script>", ["cti"])
    case_path = root / case.case_id
    write_json(case_path / "results" / "evidence.json", {"url": "http://example.onion/",
        "observed_at": "2026-08-13T00:00:00Z", "content_type": "text/html", "status_code": 200,
        "sha256": "a" * 64, "response_time_ms": 12.5, "title": "=CMD()"})
    write_json(case_path / "extracted_iocs" / "indicators.json", {"indicators": [
        {"type": "domain", "value": "<img src=x onerror=alert(1)>.example.com",
         "normalized_value": "example.com", "confidence": .9, "first_seen": "2026-08-13T00:00:00Z",
         "observation_count": 2, "sources": ["evidence-1"], "tags": []},
        {"type": "ipv4", "value": "8.8.8.8", "normalized_value": "8.8.8.8", "confidence": 1,
         "first_seen": "2026-08-13T00:00:00Z", "observation_count": 1, "sources": [], "tags": []}]})
    write_json(case_path / "enrichment" / "records.json", {"results": [{"indicator": {
        "type": "domain", "normalized_value": "example.com"}, "records": [{"provider": "local",
        "indicator_type": "domain", "normalized_value": "example.com", "success": True, "cached": False,
        "queried_at": "2026-08-13T01:00:00Z", "summary": {"labels": 2}}]}]})
    event = TimelineEvent.generated(case_id=case.case_id, event_type=TimelineEventType.IOC_EXTRACTED,
        timestamp="2026-08-13T00:00:00Z", title="Domain extracted", object_type="domain",
        object_value="example.com", source="evidence-1")
    TimelineStore(root).save(case.case_id, [event])
    case_node = GraphNode.generated(case.case_id, GraphNodeType.CASE, case.case_id)
    domain = GraphNode.generated(case.case_id, GraphNodeType.DOMAIN, "example.com", "<script>domain</script>")
    edge = GraphEdge.generated(case.case_id, domain.node_id, case_node.node_id,
        GraphRelationship.BELONGS_TO_CASE, 1, ["case.json"])
    GraphStore(root).save(GraphResult(case.case_id, [case_node, domain], [edge]))
    app = create_app()
    app.dependency_overrides[cases_root] = lambda: root
    return TestClient(app, raise_server_exceptions=False), case.case_id, root, domain.node_id, case_node.node_id


def test_case_listing_detail_overview_and_no_path_leak(dashboard):
    client, case_id, root, _, _ = dashboard
    listing = client.get("/api/v1/cases").json()["items"]
    assert listing[0]["case_id"] == case_id and listing[0]["indicator_count"] == 2
    detail = client.get(f"/api/v1/cases/{case_id}").json()
    assert detail["overview"]["graph_nodes"] == 2
    assert str(root) not in str(detail)


def test_case_path_validation_and_consistent_404(dashboard):
    client, _, _, _, _ = dashboard
    response = client.get("/api/v1/cases/%2E%2E%2Fescape")
    assert response.status_code in {400, 404}
    missing = client.get("/api/v1/cases/CASE-2026-9999")
    assert missing.status_code == 404 and missing.json()["error"]["code"] == "CASE_NOT_FOUND"


def test_bounded_local_case_search(dashboard, monkeypatch):
    client, case_id, root, _, _ = dashboard
    monkeypatch.setattr("requests.Session.get", lambda *args, **kwargs: pytest.fail("network called"))
    result = client.get(f"/api/v1/cases/{case_id}/search?q=example&limit=2").json()
    assert result["total"] == 2 and len(result["items"]) == 2
    assert str(root) not in str(result)
    assert client.get(f"/api/v1/cases/{case_id}/search?q={'x'*201}").status_code == 422


def test_evidence_pagination_search_and_hostile_text_is_data(dashboard):
    client, case_id, _, _, _ = dashboard
    response = client.get(f"/api/v1/cases/{case_id}/evidence?limit=1&offset=0&search=example")
    assert response.status_code == 200 and response.json()["total"] == 1
    assert "body" not in response.json()["items"][0]
    assert client.get(f"/api/v1/cases/{case_id}/evidence?limit=1001").status_code == 422


def test_indicator_filter_and_safe_encoded_detail(dashboard):
    client, case_id, _, _, _ = dashboard
    result = client.get(f"/api/v1/cases/{case_id}/indicators?type=domain&min_confidence=.8&enriched=true").json()
    assert result["total"] == 1 and result["items"][0]["normalized_value"] == "example.com"
    detail = client.get(f"/api/v1/cases/{case_id}/indicators/domain/example.com")
    assert detail.status_code == 200 and detail.json()["enrichment"][0]["provider"] == "local"


def test_timeline_filter_pagination_and_note(dashboard):
    client, case_id, _, _, _ = dashboard
    result = client.get(f"/api/v1/cases/{case_id}/timeline?event_type=ioc_extracted&limit=1").json()
    assert result["total"] == 1
    note = client.post(f"/api/v1/cases/{case_id}/timeline/notes",
        json={"title": "Analyst note", "description": "Local finding", "timestamp": "2026-08-13T10:30:00+03:00"})
    assert note.status_code == 201 and note.json()["event_type"] == "analyst_note"
    assert note.json()["timestamp"] == "2026-08-13T07:30:00Z"


def test_enrichment_filters_never_trigger_requests(dashboard, monkeypatch):
    client, case_id, _, _, _ = dashboard
    monkeypatch.setattr("requests.Session.get", lambda *args, **kwargs: pytest.fail("network called"))
    result = client.get(f"/api/v1/cases/{case_id}/enrichment?provider=local&success=true").json()
    assert result["total"] == 1 and result["items"][0]["provider"] == "local"


def test_graph_summary_filter_node_path_and_large_guard(dashboard):
    client, case_id, _, domain_id, case_node_id = dashboard
    result = client.get(f"/api/v1/cases/{case_id}/graph?max_nodes=1").json()
    assert result["truncated"] is True and len(result["elements"]["nodes"]) == 1
    node = client.get(f"/api/v1/cases/{case_id}/graph/nodes/{domain_id}")
    assert node.status_code == 200 and node.json()["node"]["label"] == "<script>domain</script>"
    path = client.get(f"/api/v1/cases/{case_id}/graph/path?from={domain_id}&to={case_node_id}&max_depth=2")
    assert len(path.json()["nodes"]) == 2
    exact = client.get(f"/api/v1/cases/{case_id}/graph?value=example.com").json()
    assert len(exact["elements"]["nodes"]) == 1


def test_manual_graph_writes_and_cross_case_endpoint_rejection(dashboard):
    client, case_id, _, domain_id, _ = dashboard
    node = client.post(f"/api/v1/cases/{case_id}/graph/nodes",
                       json={"type": "threat_actor", "value": "Example Group", "label": "Example Group"})
    assert node.status_code == 201
    edge = client.post(f"/api/v1/cases/{case_id}/graph/edges", json={"source": node.json()["node_id"],
        "target": domain_id, "relationship": "associated_with", "confidence": .75})
    assert edge.status_code == 201 and edge.json()["attributes"]["origin"] == "analyst"
    bad = client.post(f"/api/v1/cases/{case_id}/graph/edges", json={"source": "00000000-0000-0000-0000-000000000000",
        "target": domain_id, "relationship": "associated_with"})
    assert bad.status_code == 400


def test_cors_and_loopback_defaults(dashboard):
    client, _, _, _, _ = dashboard
    allowed = client.options("/api/v1/cases", headers={"Origin": "http://127.0.0.1:5173",
        "Access-Control-Request-Method": "GET"})
    assert allowed.headers.get("access-control-allow-origin") == "http://127.0.0.1:5173"
    denied = client.options("/api/v1/cases", headers={"Origin": "https://evil.example",
        "Access-Control-Request-Method": "GET"})
    assert denied.headers.get("access-control-allow-origin") is None
    assert client.app.state.default_host == "127.0.0.1"


def test_invalid_queries_and_node_ids_are_bounded(dashboard):
    client, case_id, _, _, _ = dashboard
    assert client.get(f"/api/v1/cases/{case_id}/timeline?search={'x'*501}").status_code == 422
    assert client.get(f"/api/v1/cases/{case_id}/graph/nodes/not-a-uuid").status_code == 404
    assert client.get(f"/api/v1/cases/{case_id}/graph/path?from=x&to=y&max_depth=99").status_code == 422
