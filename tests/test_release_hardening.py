import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import zipfile

import pytest
from fastapi.testclient import TestClient
from filelock import FileLock, Timeout

from dashboard.backend.app import create_app
from darkintel.cases import CaseStore
from darkintel.demo import create_demo
from darkintel.maintenance import backup_case, verify_backup, verify_case
from darkintel.release import export_release_tree, validate_release_tree
from darkintel.utils import read_json, write_json
from darkintel.version import __version__


def test_public_release_export_excludes_upstream_and_runtime_artifacts(tmp_path):
    source = Path(__file__).resolve().parents[1]
    output = tmp_path / "DarkIntel"
    report = export_release_tree(source, output)
    assert report["valid"] is True
    assert (output / "docs" / "UPSTREAM_PROVENANCE.md").is_file()
    for name in ("darkfox.sh", "onion_verifier.py", "DarkFox.desktop", "source-logo.jpg"):
        assert not list(output.rglob(name))
    for name in ("cases", "backups", "node_modules", "__pycache__", "dist"):
        assert not list(output.rglob(name))


def test_release_validator_rejects_legacy_file(tmp_path):
    (tmp_path / "darkfox.sh").write_text("legacy", encoding="utf-8")
    report = validate_release_tree(tmp_path)
    assert report["valid"] is False
    assert any("upstream source" in error for error in report["errors"])


def test_docker_context_explicitly_excludes_upstream_files():
    root = Path(__file__).resolve().parents[1]
    ignored = (root / ".dockerignore").read_text(encoding="utf-8")
    assert all(name in ignored for name in ("darkfox.sh", "onion_verifier.py", "DarkFox.desktop"))


def test_atomic_write_replaces_and_cleans_temporary_files(tmp_path):
    target = tmp_path / "canonical.json"
    write_json(target, {"old": True})
    write_json(target, {"new": True})
    assert read_json(target) == {"new": True}
    assert not list(tmp_path.glob("*.tmp"))


def test_failed_atomic_replace_preserves_canonical_file(tmp_path, monkeypatch):
    target = tmp_path / "canonical.json"
    write_json(target, {"old": True})
    monkeypatch.setattr(os, "replace", lambda *_: (_ for _ in ()).throw(OSError("replace failed")))
    with pytest.raises(OSError, match="replace failed"):
        write_json(target, {"new": True})
    assert read_json(target) == {"old": True}
    assert not list(tmp_path.glob("*.tmp"))


def test_lock_timeout_is_bounded(tmp_path):
    lock_path = tmp_path / "record.json.lock"
    with FileLock(lock_path):
        with pytest.raises(Timeout):
            FileLock(lock_path, timeout=0).acquire()


def test_concurrent_case_ids_remain_unique(tmp_path):
    store = CaseStore(tmp_path / "cases")
    with ThreadPoolExecutor(max_workers=4) as executor:
        cases = list(executor.map(lambda index: store.create_case(f"Case {index}"), range(8)))
    assert len({case.case_id for case in cases}) == 8
    assert all(case.case_id.startswith("CASE-") for case in cases)


def test_backup_manifest_verification_and_case_integrity(tmp_path):
    root = tmp_path / "cases"
    case = CaseStore(root).create_case("Backup test")
    write_json(root / case.case_id / "results" / "record.json", {"case_id": case.case_id})
    backup = backup_case(root, case.case_id, tmp_path / "backups")
    result = verify_backup(backup)
    assert result["valid"] is True and result["files_checked"] >= 2
    assert verify_case(root, case.case_id)["valid"] is True


def test_backup_detects_tampering_and_traversal(tmp_path):
    archive = tmp_path / "tampered.zip"
    manifest = {"case_id": "CASE-2026-0001", "created_at": "2026-01-01T00:00:00Z",
                "files": [{"path": "case.json", "sha256": "0" * 64}]}
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("case.json", "changed")
        output.writestr("../escape", "unsafe")
        output.writestr("backup-manifest.json", json.dumps(manifest))
    result = verify_backup(archive)
    assert result["valid"] is False
    assert any("unsafe archive path" in item for item in result["errors"])
    assert any("hash mismatch" in item for item in result["errors"])


def test_backup_skips_symlink(tmp_path):
    root = tmp_path / "cases"
    case = CaseStore(root).create_case("Symlink test")
    outside = tmp_path / "secret.txt"; outside.write_text("secret", encoding="utf-8")
    link = root / case.case_id / "evidence" / "outside.txt"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("symlinks unavailable")
    backup = backup_case(root, case.case_id, tmp_path / "backups")
    with zipfile.ZipFile(backup) as archive:
        assert "evidence/outside.txt" not in archive.namelist()


def test_production_spa_health_docs_and_headers(monkeypatch, tmp_path):
    monkeypatch.setenv("DARKINTEL_CASES_DIR", str(tmp_path / "cases"))
    (tmp_path / "cases").mkdir()
    client = TestClient(create_app())
    for route in ("/", "/cases", "/cases/demo/graph"):
        response = client.get(route)
        assert response.status_code == 200 and "id=\"root\"" in response.text
        assert response.headers["x-content-type-options"] == "nosniff"
        assert "default-src 'self'" in response.headers["content-security-policy"]
    health = client.get("/api/v1/health")
    assert health.json()["version"] == __version__ and health.json()["product"] == "DarkIntel"
    assert health.json()["owner"] == "Turki Almuraykhi"
    assert "\\" not in health.text
    assert client.get("/docs").status_code == 200
    assert client.get("/openapi.json").status_code == 200
    assert client.get("/api/v1/not-real").status_code == 404


def test_demo_is_offline_deterministic_and_dashboard_ready(tmp_path, monkeypatch):
    root = tmp_path / "cases"
    monkeypatch.setattr("requests.Session.get", lambda *args, **kwargs: pytest.fail("network called"))
    first = create_demo(root)
    assert create_demo(root) == first
    assert len(CaseStore(root).list_cases()) == 1
    assert read_json(root / first / "extracted_iocs" / "indicators.json")["total_unique"] == 3
    assert read_json(root / first / "timeline" / "events.json")["events"]
    graph = read_json(root / first / "graph" / "graph.json")
    assert graph["nodes"] and graph["edges"]
