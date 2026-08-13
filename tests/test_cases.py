from datetime import datetime, timezone
import json

import pytest

from darkintel.cases import CaseStore
from darkintel.evidence import EvidenceStore
from darkintel.models import OnionResult


def test_case_creation_loading_and_layout(tmp_path, monkeypatch):
    store = CaseStore(tmp_path / "cases")
    case = store.create_case("Ransomware Investigation", tags=["ransomware"])
    assert case.case_id.startswith(f"CASE-{datetime.now(timezone.utc).year}-")
    assert store.load_case(case.case_id) == case
    assert (tmp_path / "cases" / case.case_id / "case.json").is_file()
    for directory in ("results", "evidence", "screenshots", "extracted_iocs", "logs", "reports"):
        assert (tmp_path / "cases" / case.case_id / directory).is_dir()


def test_case_ids_increment(tmp_path):
    store = CaseStore(tmp_path)
    first = store.create_case("One")
    second = store.create_case("Two")
    assert int(second.case_id[-4:]) == int(first.case_id[-4:]) + 1


@pytest.mark.parametrize("case_id", ["../escape", "CASE-2026-1", "CASE-2026-0001/../../x", ""])
def test_case_path_validation(tmp_path, case_id):
    with pytest.raises(ValueError):
        CaseStore(tmp_path).load_case(case_id)


def test_update_and_close_case(tmp_path):
    store = CaseStore(tmp_path)
    case = store.create_case("One")
    updated = store.update_case(case.case_id, description="new", tags=["cti"])
    assert updated.description == "new"
    assert store.close_case(case.case_id).status == "closed"


def test_evidence_metadata_and_body_hash(tmp_path):
    store = CaseStore(tmp_path)
    case = store.create_case("Evidence")
    body = b"collected body"
    import hashlib
    result = OnionResult("http://" + "a" * 56 + ".onion/", True, status_code=200,
                         content_type="text/html", sha256=hashlib.sha256(body).hexdigest())
    result_path = EvidenceStore(tmp_path).save_result(case.case_id, result, body)
    metadata = json.loads(result_path.read_text(encoding="utf-8"))
    assert metadata["sha256"] == hashlib.sha256(body).hexdigest()
    assert (tmp_path / case.case_id / metadata["evidence_file"]).read_bytes() == body
