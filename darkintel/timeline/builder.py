"""Offline construction of timeline events from authoritative case artifacts."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from .correlation import correlate_events
from .models import TimelineEvent, TimelineEventType, sort_events
from .store import MAX_TIMELINE_EVENTS, TimelineStore
from ..utils import read_json, validate_case_id

LOGGER = logging.getLogger(__name__)


class TimelineBuilder:
    def __init__(self, root: str | Path = "cases", *, max_events: int = MAX_TIMELINE_EVENTS) -> None:
        if max_events < 1 or max_events > MAX_TIMELINE_EVENTS:
            raise ValueError(f"max_events must be between 1 and {MAX_TIMELINE_EVENTS}")
        self.root = Path(root)
        self.max_events = max_events
        self.warnings: list[str] = []

    def build_case_timeline(self, case_id: str) -> list[TimelineEvent]:
        validate_case_id(case_id)
        case_path = self.root / case_id
        if not (case_path / "case.json").is_file():
            raise FileNotFoundError(f"case not found: {case_id}")
        LOGGER.info("timeline build started: case=%s", case_id)
        self.warnings = []
        events: list[TimelineEvent] = []
        self._case_events(case_id, case_path, events)
        self._verification_events(case_id, case_path, events)
        self._ioc_events(case_id, case_path, events)
        self._enrichment_events(case_id, case_path, events)
        deduplicated = {event.event_id: event for event in events}
        duplicate_count = len(events) - len(deduplicated)
        events = sort_events(list(deduplicated.values()))
        if len(events) > self.max_events:
            self.warnings.append(f"Timeline event limit reached at {self.max_events}")
            events = events[:self.max_events]
        correlate_events(events)
        stored = TimelineStore(self.root).save(case_id, events, self.warnings)
        LOGGER.info("events generated: %d; events deduplicated: %d", len(events), duplicate_count)
        LOGGER.info("timeline build completed: case=%s events=%d", case_id, len(stored))
        return stored

    def _case_events(self, case_id: str, case_path: Path, events: list[TimelineEvent]) -> None:
        try:
            case = read_json(case_path / "case.json")
            events.append(TimelineEvent.generated(case_id=case_id, event_type=TimelineEventType.CASE_CREATED,
                                                   timestamp=case["created_at"], title=f"Case {case_id} created",
                                                   description=case.get("name"), source="case.json",
                                                   object_type="case", object_value=case_id,
                                                   metadata={"source_record_id": case_id, "status": case.get("status")}))
            if case.get("updated_at") and case["updated_at"] != case["created_at"]:
                event_type = (TimelineEventType.CASE_CLOSED if case.get("status") == "closed"
                              else TimelineEventType.CASE_UPDATED)
                events.append(TimelineEvent.generated(case_id=case_id, event_type=event_type,
                                                       timestamp=case["updated_at"],
                                                       title=f"Case {case_id} {event_type.value.split('_')[-1]}",
                                                       source="case.json", object_type="case", object_value=case_id,
                                                       metadata={"source_record_id": case_id,
                                                                 "status": case.get("status")}))
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            self._warn("case.json", exc)

    def _verification_events(self, case_id: str, case_path: Path, events: list[TimelineEvent]) -> None:
        for path in sorted((case_path / "results").glob("*.json")):
            try:
                record = read_json(path)
                timestamp = record.get("observed_at")
                if not timestamp:
                    self._missing_timestamp(path)
                    continue
                url = record.get("url")
                source = str(path.relative_to(case_path))
                metadata = {"source_record_id": path.name, "status_code": record.get("status_code"),
                            "response_time_ms": record.get("response_time_ms"), "sha256": record.get("sha256"),
                            "final_url": record.get("final_url"), "error": record.get("error")}
                events.append(TimelineEvent.generated(case_id=case_id,
                                                       event_type=TimelineEventType.TARGET_DISCOVERED,
                                                       timestamp=timestamp, title="Onion target discovered", source=source,
                                                       object_type="target", object_value=url, metadata=metadata))
                reachable = bool(record.get("is_live"))
                event_type = TimelineEventType.TARGET_VERIFIED if reachable else TimelineEventType.TARGET_UNREACHABLE
                description = (f"HTTP {record.get('status_code')} — {record.get('response_time_ms')} ms"
                               if reachable else str(record.get("error") or "Target unreachable"))
                events.append(TimelineEvent.generated(case_id=case_id, event_type=event_type, timestamp=timestamp,
                                                       title="Target verified" if reachable else "Target unreachable",
                                                       description=description, source=source, object_type="target",
                                                       object_value=url, metadata=metadata))
                if record.get("evidence_file"):
                    events.append(TimelineEvent.generated(case_id=case_id,
                                                           event_type=TimelineEventType.EVIDENCE_COLLECTED,
                                                           timestamp=timestamp, title="Evidence collected", source=source,
                                                           object_type="evidence", object_value=record["evidence_file"],
                                                           metadata={"source_record_id": path.name,
                                                                     "evidence_id": record["evidence_file"],
                                                                     "sha256": record.get("sha256")}))
                if record.get("sha256"):
                    events.append(TimelineEvent.generated(case_id=case_id,
                                                           event_type=TimelineEventType.EVIDENCE_HASHED,
                                                           timestamp=timestamp, title="Evidence SHA-256 recorded", source=source,
                                                           object_type="sha256", object_value=record["sha256"],
                                                           metadata={"source_record_id": path.name,
                                                                     "evidence_id": record.get("evidence_file"),
                                                                     "sha256": record["sha256"]}))
            except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
                self._warn(str(path), exc)

    def _ioc_events(self, case_id: str, case_path: Path, events: list[TimelineEvent]) -> None:
        path = case_path / "extracted_iocs" / "indicators.json"
        if not path.is_file():
            return
        try:
            payload = read_json(path)
            for index, record in enumerate(payload.get("indicators", [])):
                timestamp = record.get("first_seen")
                if not timestamp:
                    self._missing_timestamp(path, index)
                    continue
                indicator_type = record["type"]
                value = record["normalized_value"]
                source = record.get("source") or "extracted_iocs/indicators.json"
                metadata = {"source_record_id": f"indicator:{indicator_type}:{value}",
                            "indicator_type": indicator_type, "indicator_value": value,
                            "observation_count": record.get("observation_count", 1),
                            "sources": record.get("sources", [])[:50]}
                events.append(TimelineEvent.generated(case_id=case_id, event_type=TimelineEventType.IOC_EXTRACTED,
                                                       timestamp=timestamp, title=f"{indicator_type.upper()} indicator extracted",
                                                       source=source, object_type=indicator_type, object_value=value,
                                                       metadata=metadata))
                events.append(TimelineEvent.generated(case_id=case_id, event_type=TimelineEventType.IOC_OBSERVED,
                                                       timestamp=timestamp, title="IOC observed", source=source,
                                                       object_type=indicator_type, object_value=value, metadata=metadata))
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
            self._warn(str(path), exc)

    def _enrichment_events(self, case_id: str, case_path: Path, events: list[TimelineEvent]) -> None:
        path = case_path / "enrichment" / "records.json"
        if not path.is_file():
            return
        try:
            payload = read_json(path)
            for result_index, result in enumerate(payload.get("results", [])):
                indicator = result.get("indicator", {})
                for record_index, record in enumerate(result.get("records", [])):
                    timestamp = record.get("queried_at")
                    if not timestamp:
                        self._missing_timestamp(path, result_index)
                        continue
                    provider = record.get("provider")
                    kind = record.get("indicator_type") or indicator.get("type")
                    value = record.get("normalized_value") or indicator.get("normalized_value")
                    source = "enrichment/records.json"
                    record_id = f"result:{result_index}:record:{record_index}"
                    metadata = {"source_record_id": record_id, "provider": provider,
                                "indicator_type": kind, "indicator_value": value,
                                "cached": bool(record.get("cached")), "success": bool(record.get("success")),
                                "provider_summary": record.get("summary", {}),
                                "error_category": record.get("error_category")}
                    events.append(TimelineEvent.generated(case_id=case_id,
                                                           event_type=TimelineEventType.ENRICHMENT_REQUESTED,
                                                           timestamp=timestamp, title=f"{provider} enrichment requested",
                                                           source=source, object_type=kind, object_value=value,
                                                           metadata=metadata))
                    if record.get("cached"):
                        event_type = TimelineEventType.ENRICHMENT_CACHE_HIT
                    elif record.get("success"):
                        event_type = TimelineEventType.ENRICHMENT_COMPLETED
                    else:
                        event_type = TimelineEventType.ENRICHMENT_FAILED
                    description = self._provider_description(provider, record)
                    events.append(TimelineEvent.generated(case_id=case_id, event_type=event_type,
                                                           timestamp=timestamp,
                                                           title=f"{provider} enrichment {event_type.value.split('_')[-1]}",
                                                           description=description, source=source,
                                                           object_type=kind, object_value=value, metadata=metadata))
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
            self._warn(str(path), exc)

    @staticmethod
    def _provider_description(provider: object, record: dict[str, object]) -> str | None:
        summary = record.get("summary")
        if isinstance(summary, dict):
            if isinstance(summary.get("malicious"), int):
                return f"{provider} provider claim: {summary['malicious']} malicious detections"
            if isinstance(summary.get("abuse_confidence_score"), (int, float)):
                return f"{provider} provider claim: abuse confidence score {summary['abuse_confidence_score']}"
        return str(record.get("error")) if record.get("error") else None

    def _warn(self, source: str, exc: Exception) -> None:
        warning = f"Malformed record skipped: {source} ({type(exc).__name__})"
        self.warnings.append(warning)
        LOGGER.warning("malformed record skipped: %s", source)

    def _missing_timestamp(self, path: Path, index: int | None = None) -> None:
        suffix = f"[{index}]" if index is not None else ""
        self.warnings.append(f"Missing timestamp skipped: {path.name}{suffix}")
