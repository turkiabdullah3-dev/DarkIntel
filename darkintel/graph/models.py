"""Bounded, controlled relationship graph models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
import uuid
from typing import Any

from ..timeline.models import bound_metadata
from ..utils import validate_case_id

MAX_LABEL_CHARS = 500
MAX_VALUE_CHARS = 4_000
MAX_TAGS = 100
MAX_SOURCE_IDS = 1_000
MAX_PROVENANCE = 1_000


class GraphNodeType(StrEnum):
    CASE = "case"
    TARGET = "target"
    ONION = "onion"
    EVIDENCE = "evidence"
    IPV4 = "ipv4"
    IPV6 = "ipv6"
    DOMAIN = "domain"
    URL = "url"
    EMAIL = "email"
    MD5 = "md5"
    SHA1 = "sha1"
    SHA256 = "sha256"
    SHA512 = "sha512"
    BITCOIN = "bitcoin"
    MONERO = "monero"
    CVE = "cve"
    TELEGRAM = "telegram"
    PROVIDER = "provider"
    ENRICHMENT_RECORD = "enrichment_record"
    TIMELINE_EVENT = "timeline_event"
    ANALYST_ENTITY = "analyst_entity"
    THREAT_ACTOR = "threat_actor"
    ORGANIZATION = "organization"


class GraphRelationship(StrEnum):
    CONTAINS = "contains"
    OBSERVED_IN = "observed_in"
    EXTRACTED_FROM = "extracted_from"
    DERIVED_FROM = "derived_from"
    VERIFIED_AS = "verified_as"
    HASHED_AS = "hashed_as"
    ENRICHED_BY = "enriched_by"
    REPORTED_BY = "reported_by"
    RELATED_TO = "related_to"
    REFERENCES = "references"
    BELONGS_TO_CASE = "belongs_to_case"
    CORRELATED_WITH = "correlated_with"
    MENTIONS = "mentions"
    ASSOCIATED_WITH = "associated_with"


def stable_node_id(case_id: str, node_type: str, value: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"darkintel:graph:node:{case_id}\0{node_type}\0{value}"))


def stable_edge_id(case_id: str, source: str, relationship: str, target: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL,
                          f"darkintel:graph:edge:{case_id}\0{source}\0{relationship}\0{target}"))


@dataclass(slots=True)
class GraphNode:
    node_id: str
    node_type: GraphNodeType
    value: str
    label: str
    case_id: str
    attributes: dict[str, object] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    source_ids: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        validate_case_id(self.case_id)
        if not isinstance(self.node_type, GraphNodeType):
            self.node_type = GraphNodeType(self.node_type)
        uuid.UUID(self.node_id)
        if not self.value or len(self.value) > MAX_VALUE_CHARS:
            raise ValueError("node value is empty or exceeds limit")
        if not self.label:
            raise ValueError("node label cannot be empty")
        self.label = self.label[:MAX_LABEL_CHARS]
        self.tags = sorted(set(self.tags))[:MAX_TAGS]
        self.source_ids = sorted(set(self.source_ids))[:MAX_SOURCE_IDS]
        self.attributes, truncated = bound_metadata(self.attributes)
        if truncated:
            self.attributes["bounded"] = True

    @classmethod
    def generated(cls, case_id: str, node_type: GraphNodeType, value: str, label: str | None = None,
                  *, attributes: dict[str, object] | None = None, tags: list[str] | None = None,
                  source_ids: list[str] | None = None) -> "GraphNode":
        node_type = GraphNodeType(node_type)
        details = {"origin": "system", **(attributes or {})}
        return cls(stable_node_id(case_id, node_type.value, value), node_type, value, label or value,
                   case_id, details, list(tags or []), list(source_ids or []))

    @classmethod
    def analyst(cls, case_id: str, node_type: GraphNodeType, value: str, label: str) -> "GraphNode":
        if node_type not in {GraphNodeType.ANALYST_ENTITY, GraphNodeType.THREAT_ACTOR, GraphNodeType.ORGANIZATION}:
            raise ValueError("manual nodes require an analyst entity type")
        return cls(str(uuid.uuid4()), node_type, value, label, case_id, {"origin": "analyst"})

    def to_dict(self) -> dict[str, Any]:
        return {"node_id": self.node_id, "node_type": self.node_type.value, "value": self.value,
                "label": self.label, "case_id": self.case_id, "attributes": self.attributes,
                "tags": self.tags, "source_ids": self.source_ids}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GraphNode":
        return cls(**dict(data))


@dataclass(slots=True)
class GraphEdge:
    edge_id: str
    case_id: str
    source_node_id: str
    target_node_id: str
    relationship: GraphRelationship
    confidence: float
    provenance: list[str] = field(default_factory=list)
    attributes: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_case_id(self.case_id)
        if not isinstance(self.relationship, GraphRelationship):
            self.relationship = GraphRelationship(self.relationship)
        uuid.UUID(self.edge_id)
        uuid.UUID(self.source_node_id)
        uuid.UUID(self.target_node_id)
        if self.source_node_id == self.target_node_id:
            raise ValueError("self-loop relationships are not allowed")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("relationship confidence must be between 0 and 1")
        self.provenance = sorted(set(self.provenance))[:MAX_PROVENANCE]
        self.attributes, truncated = bound_metadata(self.attributes)
        if truncated:
            self.attributes["bounded"] = True

    @classmethod
    def generated(cls, case_id: str, source: str, target: str, relationship: GraphRelationship,
                  confidence: float, provenance: list[str],
                  attributes: dict[str, object] | None = None) -> "GraphEdge":
        relationship = GraphRelationship(relationship)
        return cls(stable_edge_id(case_id, source, relationship.value, target), case_id, source, target,
                   relationship, confidence, provenance, {"origin": "system", **(attributes or {})})

    @classmethod
    def analyst(cls, case_id: str, source: str, target: str, relationship: GraphRelationship,
                confidence: float = 0.75) -> "GraphEdge":
        return cls(str(uuid.uuid4()), case_id, source, target, relationship, confidence, ["analyst"],
                   {"origin": "analyst", "created_by": "analyst"})

    def to_dict(self) -> dict[str, Any]:
        return {"edge_id": self.edge_id, "case_id": self.case_id, "source_node_id": self.source_node_id,
                "target_node_id": self.target_node_id, "relationship": self.relationship.value,
                "confidence": self.confidence, "provenance": self.provenance, "attributes": self.attributes}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GraphEdge":
        return cls(**dict(data))


@dataclass(slots=True)
class GraphResult:
    case_id: str
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {"case_id": self.case_id, "nodes": [node.to_dict() for node in self.nodes],
                "edges": [edge.to_dict() for edge in self.edges], "warnings": self.warnings}
