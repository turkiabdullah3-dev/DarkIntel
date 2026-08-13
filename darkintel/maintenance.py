"""Local backup and integrity operations for investigation cases."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import zipfile

from .utils import read_json, validate_case_id


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def backup_case(root: Path, case_id: str, output: Path) -> Path:
    validate_case_id(case_id)
    case_dir = root / case_id
    if not (case_dir / "case.json").is_file():
        raise FileNotFoundError(f"case not found: {case_id}")
    output.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    destination = output / f"{case_id}_{stamp}.zip"
    entries: list[tuple[str, bytes]] = []
    for path in sorted(case_dir.rglob("*")):
        if not path.is_file() or path.is_symlink() or path.name.endswith(".lock") or ".tmp" in path.name:
            continue
        resolved = path.resolve()
        if not resolved.is_relative_to(case_dir.resolve()):
            continue
        relative = path.relative_to(case_dir).as_posix()
        entries.append((relative, path.read_bytes()))
    manifest = {"case_id": case_id, "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "files": [{"path": name, "sha256": _digest(data)} for name, data in entries]}
    with zipfile.ZipFile(destination, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in entries:
            archive.writestr(name, data)
        archive.writestr("backup-manifest.json", json.dumps(manifest, indent=2) + "\n")
    return destination


def verify_backup(path: Path) -> dict[str, object]:
    if not path.is_file():
        raise FileNotFoundError(f"backup not found: {path}")
    errors: list[str] = []
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        for name in names:
            item = PurePosixPath(name)
            if item.is_absolute() or ".." in item.parts or "\\" in name:
                errors.append(f"unsafe archive path: {name}")
        if "backup-manifest.json" not in names:
            return {"valid": False, "case_id": None, "files_checked": 0,
                    "errors": errors + ["backup manifest missing"]}
        manifest = json.loads(archive.read("backup-manifest.json"))
        case_id = validate_case_id(manifest.get("case_id", ""))
        checked = 0
        for item in manifest.get("files", []):
            name = item.get("path", "")
            if name not in names:
                errors.append(f"manifest file missing: {name}")
                continue
            if _digest(archive.read(name)) != item.get("sha256"):
                errors.append(f"hash mismatch: {name}")
            checked += 1
    return {"valid": not errors, "case_id": case_id, "files_checked": checked, "errors": errors}


def verify_case(root: Path, case_id: str) -> dict[str, object]:
    validate_case_id(case_id)
    case_dir = root / case_id
    if not case_dir.is_dir():
        raise FileNotFoundError(f"case not found: {case_id}")
    errors: list[str] = []
    checked: list[str] = []
    for relative in ("case.json", "extracted_iocs/indicators.json", "enrichment/records.json",
                     "timeline/events.json", "graph/graph.json"):
        path = case_dir / relative
        if not path.exists():
            continue
        try:
            data = read_json(path)
            checked.append(relative)
            embedded = data.get("case_id") if isinstance(data, dict) else None
            if embedded and embedded != case_id:
                errors.append(f"case ID mismatch: {relative}")
        except (OSError, ValueError, TypeError):
            errors.append(f"invalid JSON: {relative}")
    graph_path = case_dir / "graph" / "graph.json"
    if graph_path.is_file():
        graph = read_json(graph_path)
        node_ids = {node.get("node_id") for node in graph.get("nodes", [])}
        for edge in graph.get("edges", []):
            if edge.get("source_node_id") not in node_ids or edge.get("target_node_id") not in node_ids:
                errors.append(f"dangling graph edge: {edge.get('edge_id', 'unknown')}")
    for metadata_path in (case_dir / "results").glob("*.json"):
        try:
            metadata = read_json(metadata_path)
            checked.append(f"results/{metadata_path.name}")
            evidence_file = metadata.get("evidence_file")
            expected = metadata.get("sha256")
            if evidence_file and expected:
                candidate = (case_dir / evidence_file).resolve()
                if candidate.is_relative_to(case_dir.resolve()) and candidate.is_file():
                    if _digest(candidate.read_bytes()) != expected:
                        errors.append(f"evidence hash mismatch: {metadata_path.name}")
        except (OSError, ValueError, TypeError):
            errors.append(f"invalid evidence metadata: {metadata_path.name}")
    return {"valid": not errors, "case_id": case_id, "files_checked": len(checked), "errors": errors}
