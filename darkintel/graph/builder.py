"""Offline deterministic graph construction from case artifacts."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from urllib.parse import urlsplit

from .correlation import merge_edges
from .models import (GraphEdge, GraphNode, GraphNodeType, GraphRelationship, GraphResult,
                     stable_node_id)
from .store import GraphStore, MAX_GRAPH_EDGES, MAX_GRAPH_NODES
from ..utils import read_json, validate_case_id

LOGGER = logging.getLogger(__name__)


class RelationshipGraphBuilder:
    def __init__(self, root: str | Path = "cases", *, max_nodes: int = MAX_GRAPH_NODES,
                 max_edges: int = MAX_GRAPH_EDGES) -> None:
        if not 1 <= max_nodes <= MAX_GRAPH_NODES or not 1 <= max_edges <= MAX_GRAPH_EDGES:
            raise ValueError("graph limits are outside supported bounds")
        self.root = Path(root)
        self.max_nodes = max_nodes
        self.max_edges = max_edges
        self.nodes: dict[str, GraphNode] = {}
        self.edges: list[GraphEdge] = []
        self.warnings: list[str] = []
        self.case_id = ""
        self.case_node: GraphNode | None = None

    def build_case_graph(self, case_id: str) -> GraphResult:
        validate_case_id(case_id)
        case_path = self.root / case_id
        if not (case_path / "case.json").is_file():
            raise FileNotFoundError(f"case not found: {case_id}")
        LOGGER.info("graph build started: case=%s", case_id)
        self.case_id, self.nodes, self.edges, self.warnings = case_id, {}, [], []
        self._case(case_path)
        evidence_by_id, targets = self._verification(case_path)
        iocs = self._iocs(case_path, evidence_by_id)
        self._enrichment(case_path, iocs)
        self._timeline(case_path, iocs, evidence_by_id, targets)
        raw_edge_count = len(self.edges)
        edges = merge_edges(self.edges)
        LOGGER.info("relationships merged: %d", raw_edge_count - len(edges))
        if len(self.nodes) > self.max_nodes:
            self.warnings.append(f"Graph node limit reached at {self.max_nodes}")
            kept = dict(list(sorted(self.nodes.items()))[:self.max_nodes])
            self.nodes = kept
            edges = [edge for edge in edges if edge.source_node_id in kept and edge.target_node_id in kept]
        if len(edges) > self.max_edges:
            self.warnings.append(f"Graph edge limit reached at {self.max_edges}")
            edges = edges[:self.max_edges]
        result = GraphStore(self.root).save(GraphResult(case_id, sorted(self.nodes.values(), key=lambda n: n.node_id),
                                                        edges, self.warnings))
        LOGGER.info("nodes created: %d; edges created: %d", len(result.nodes), len(result.edges))
        LOGGER.info("graph build completed: case=%s", case_id)
        return result

    def _node(self, kind: GraphNodeType, value: str, *, label: str | None = None,
              source: str | None = None, attributes: dict[str, object] | None = None) -> GraphNode:
        node_id = stable_node_id(self.case_id, kind.value, value)
        current = self.nodes.get(node_id)
        if current:
            if source and source not in current.source_ids:
                current.source_ids = sorted(set(current.source_ids + [source]))[:1_000]
            return current
        node = GraphNode.generated(self.case_id, kind, value, label, attributes=attributes,
                                   source_ids=[source] if source else [])
        self.nodes[node.node_id] = node
        if self.case_node and node.node_id != self.case_node.node_id:
            self._edge(node, self.case_node, GraphRelationship.BELONGS_TO_CASE, 1.0,
                       [source or "case.json"])
        return node

    def _edge(self, source: GraphNode, target: GraphNode, relationship: GraphRelationship,
              confidence: float, provenance: list[str]) -> None:
        if source.node_id == target.node_id:
            return
        self.edges.append(GraphEdge.generated(self.case_id, source.node_id, target.node_id,
                                              relationship, confidence, provenance))

    def _case(self, case_path: Path) -> None:
        try:
            record = read_json(case_path / "case.json")
            self.case_node = self._node(GraphNodeType.CASE, self.case_id, label=record.get("name") or self.case_id,
                                        source="case.json", attributes={"status": record.get("status")})
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            self._warn("case.json", exc)
            raise ValueError("case metadata is invalid") from exc

    def _verification(self, case_path: Path) -> tuple[dict[str, GraphNode], dict[str, GraphNode]]:
        evidence: dict[str, GraphNode] = {}
        targets: dict[str, GraphNode] = {}
        for path in sorted((case_path / "results").glob("*.json")):
            try:
                record = read_json(path)
                source = str(path.relative_to(case_path))
                url = record.get("url")
                if not isinstance(url, str) or not url:
                    raise ValueError("verification URL missing")
                target = self._node(GraphNodeType.TARGET, url, source=source,
                                    attributes={"is_live": record.get("is_live"),
                                                "status_code": record.get("status_code")})
                targets[url] = target
                host = urlsplit(url).hostname
                if host and host.endswith(".onion"):
                    onion = self._node(GraphNodeType.ONION, host.lower(), source=source)
                    self._edge(target, onion, GraphRelationship.VERIFIED_AS, 1.0, [source])
                evidence_id = record.get("evidence_file")
                if isinstance(evidence_id, str) and evidence_id:
                    artifact = self._node(GraphNodeType.EVIDENCE, evidence_id, source=source,
                                          attributes={"sha256": record.get("sha256")})
                    evidence[evidence_id] = artifact
                    self._edge(artifact, target, GraphRelationship.DERIVED_FROM, 1.0, [source])
                    digest = record.get("sha256")
                    if isinstance(digest, str) and digest:
                        hash_node = self._node(GraphNodeType.SHA256, digest.lower(), source=source)
                        self._edge(artifact, hash_node, GraphRelationship.HASHED_AS, 1.0, [source])
            except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
                self._warn(str(path), exc)
        return evidence, targets

    def _iocs(self, case_path: Path, evidence: dict[str, GraphNode]) -> dict[tuple[str, str], GraphNode]:
        path = case_path / "extracted_iocs" / "indicators.json"
        iocs: dict[tuple[str, str], GraphNode] = {}
        if not path.is_file():
            return iocs
        try:
            for index, record in enumerate(read_json(path).get("indicators", [])):
                kind = GraphNodeType(record["type"])
                value = record["normalized_value"]
                provenance = f"extracted_iocs/indicators.json#{index}"
                node = self._node(kind, value, source=provenance,
                                  attributes={"extraction_confidence": record.get("confidence")})
                iocs[(kind.value, value)] = node
                sources = list(record.get("sources", []))
                if record.get("source"):
                    sources.append(record["source"])
                for source_id in sorted(set(str(item) for item in sources)):
                    if source_id in evidence:
                        self._edge(evidence[source_id], node, GraphRelationship.CONTAINS, 0.95, [provenance])
                if kind == GraphNodeType.SHA256:
                    for artifact in evidence.values():
                        if artifact.attributes.get("sha256") == value:
                            self._edge(artifact, node, GraphRelationship.HASHED_AS, 1.0, [provenance])
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
            self._warn(str(path), exc)
        return iocs

    def _enrichment(self, case_path: Path, iocs: dict[tuple[str, str], GraphNode]) -> None:
        path = case_path / "enrichment" / "records.json"
        if not path.is_file():
            return
        try:
            for result_index, result in enumerate(read_json(path).get("results", [])):
                for record_index, record in enumerate(result.get("records", [])):
                    kind = str(record.get("indicator_type") or result.get("indicator", {}).get("type"))
                    value = str(record.get("normalized_value") or result.get("indicator", {}).get("normalized_value"))
                    ioc = iocs.get((kind, value))
                    if not ioc:
                        continue
                    provider_name = str(record["provider"])
                    provenance = f"enrichment/records.json#{result_index}:{record_index}"
                    provider = self._node(GraphNodeType.PROVIDER, provider_name, label=provider_name,
                                          source=provenance)
                    record_node = self._node(GraphNodeType.ENRICHMENT_RECORD, provenance, source=provenance,
                                             attributes={"success": record.get("success"),
                                                         "cached": record.get("cached"),
                                                         "summary": record.get("summary", {})})
                    self._edge(ioc, provider, GraphRelationship.ENRICHED_BY, 0.9, [provenance])
                    self._edge(record_node, ioc, GraphRelationship.REFERENCES, 1.0, [provenance])
                    self._edge(record_node, provider, GraphRelationship.REPORTED_BY, 1.0, [provenance])
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
            self._warn(str(path), exc)

    def _timeline(self, case_path: Path, iocs: dict[tuple[str, str], GraphNode],
                  evidence: dict[str, GraphNode], targets: dict[str, GraphNode]) -> None:
        path = case_path / "timeline" / "events.json"
        if not path.is_file():
            return
        try:
            for record in read_json(path).get("events", []):
                event_id = record["event_id"]
                provenance = f"timeline/events.json#{event_id}"
                event = self._node(GraphNodeType.TIMELINE_EVENT, event_id, label=record.get("title") or event_id,
                                   source=provenance, attributes={"event_type": record.get("event_type"),
                                                                  "timestamp": record.get("timestamp")})
                kind, value = record.get("object_type"), record.get("object_value")
                target = iocs.get((kind, value))
                if target is None and kind == "evidence":
                    target = evidence.get(value)
                if target is None and kind == "target":
                    target = targets.get(value)
                if target:
                    self._edge(event, target, GraphRelationship.REFERENCES, 1.0, [provenance])
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
            self._warn(str(path), exc)

    def _warn(self, source: str, exc: Exception) -> None:
        self.warnings.append(f"Malformed graph source skipped: {source} ({type(exc).__name__})")
        LOGGER.warning("invalid relationship skipped: source=%s", source)
