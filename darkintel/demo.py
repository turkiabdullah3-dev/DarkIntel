"""Deterministic, offline synthetic investigation generator."""

from datetime import datetime, timezone
import hashlib
from pathlib import Path

from .cases import CaseStore
from .evidence import EvidenceStore, IOCStore
from .graph import RelationshipGraphBuilder
from .models import ExtractionResult, IOC, IOCType, OnionResult
from .timeline import TimelineBuilder, TimelineStore
from .utils import write_json

DEMO_NAME = "DarkIntel Synthetic Demo"
DEMO_TIME = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)


def create_demo(root: Path) -> str:
    store = CaseStore(root)
    existing = next((case for case in store.list_cases() if case.name == DEMO_NAME), None)
    if existing:
        return existing.case_id
    case = store.create_case(DEMO_NAME, "DarkIntel synthetic offline CTI workflow using reserved examples.",
                             ["demo", "synthetic", "offline"])
    body = b"Synthetic report: example.com resolved to 192.0.2.10 and references CVE-2024-0001."
    result = OnionResult("https://example.com/report", True, 200, "Synthetic Example Report", 12.0,
                         "text/plain", "https://example.com/report", hashlib.sha256(body).hexdigest(),
                         observed_at=DEMO_TIME)
    EvidenceStore(root).save_result(case.case_id, result, body)
    indicators = [IOC(IOCType.DOMAIN, "example.com", "example.com", "synthetic-evidence", DEMO_TIME, .95),
                  IOC(IOCType.IPV4, "192.0.2.10", "192.0.2.10", "synthetic-evidence", DEMO_TIME, 1.0),
                  IOC(IOCType.CVE, "CVE-2024-0001", "CVE-2024-0001", "synthetic-evidence", DEMO_TIME, 1.0)]
    IOCStore(root).merge(case.case_id, ExtractionResult("synthetic-evidence", indicators,
                                                        extracted_at=DEMO_TIME))
    write_json(root / case.case_id / "enrichment" / "records.json", {"case_id": case.case_id, "results": [{
        "indicator": indicators[0].to_dict(), "records": [{"provider": "local", "indicator_type": "domain",
        "indicator_value": "example.com", "normalized_value": "example.com", "queried_at": "2026-01-15T12:05:00Z",
        "success": True, "confidence": None, "summary": {"classification": "reserved example domain"},
        "raw_reference": None, "error": None, "error_category": None, "expires_at": None, "cached": False}],
        "enriched_at": "2026-01-15T12:05:00Z", "warnings": []}]})
    TimelineBuilder(root).build_case_timeline(case.case_id)
    TimelineStore(root).add_note(case.case_id, "Synthetic analyst finding",
                                 "Reserved example indicators are linked for dashboard review.",
                                 "2026-01-15T12:10:00Z", ["demo"])
    RelationshipGraphBuilder(root).build_case_graph(case.case_id)
    return case.case_id
