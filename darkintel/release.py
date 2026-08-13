"""Allowlisted export of the independent DarkIntel public release tree."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

PUBLIC_DIRECTORIES = (".github", "darkintel", "dashboard", "docs", "tests")
PUBLIC_FILES = (".dockerignore", ".env.example", ".gitignore", "CHANGELOG.md", "CONTRIBUTING.md",
                "Dockerfile", "README.md", "SECURITY.md", "config.example.toml", "docker-compose.yml",
                "main.py", "requirements-dev.txt", "requirements.txt", "THIRD_PARTY_NOTICES.md")
EXCLUDED_NAMES = {"darkfox.sh", "onion_verifier.py", "DarkFox.desktop", ".env", "cases", "backups",
                  "node_modules", "__pycache__", ".pytest_cache", "dist", "source-logo.jpg"}
EXCLUDED_SUFFIXES = (".pyc", ".pyo", ".tsbuildinfo", ".lock")
UPSTREAM_REFERENCES_ALLOWED_IN = {"README.md", "SECURITY.md", "CHANGELOG.md", "RELEASE_CHECKLIST.md",
                                  "PUBLIC_RELEASE_TREE.md", "UPSTREAM_PROVENANCE.md", ".dockerignore",
                                  "release.py", "test_release_hardening.py"}
DEVELOPER_PATH = re.compile(r"(?:[A-Za-z]:\\Users\\|OneDrive[/\\]|/home/kali|/root(?:/|\\)|/opt/darkfox)")
SECRET_PATTERN = re.compile(r"(?:BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY|authorization:\s*bearer\s+\S+)", re.I)


def _excluded(path: Path) -> bool:
    return any(part in EXCLUDED_NAMES for part in path.parts) or path.name.endswith(EXCLUDED_SUFFIXES)


def export_release_tree(source: Path, output: Path) -> dict[str, object]:
    source, output = source.resolve(), output.resolve()
    if output == source or source in output.parents:
        raise ValueError("release output must be outside the source repository")
    if output.exists() and any(output.iterdir()):
        raise ValueError("release output directory must be empty")
    output.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    for filename in PUBLIC_FILES:
        candidate = source / filename
        if not candidate.is_file():
            raise FileNotFoundError(f"required release file missing: {filename}")
        shutil.copy2(candidate, output / filename)
        copied.append(filename)
    for dirname in PUBLIC_DIRECTORIES:
        root = source / dirname
        if not root.is_dir():
            raise FileNotFoundError(f"required release directory missing: {dirname}")
        for candidate in sorted(root.rglob("*")):
            relative = candidate.relative_to(source)
            if candidate.is_symlink() or _excluded(relative) or not candidate.is_file():
                continue
            destination = output / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(candidate, destination)
            copied.append(relative.as_posix())
    report = validate_release_tree(output)
    if not report["valid"]:
        shutil.rmtree(output)
        raise ValueError("release tree validation failed: " + "; ".join(report["errors"]))
    return {"output": str(output), "files": len(copied), **report}


def validate_release_tree(root: Path) -> dict[str, object]:
    root = root.resolve()
    errors: list[str] = []
    checked = 0
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if _excluded(relative):
            errors.append(f"excluded path present: {relative.as_posix()}")
        if path.is_symlink():
            errors.append(f"symlink present: {relative.as_posix()}")
        if not path.is_file():
            continue
        checked += 1
        if path.name in {"darkfox.sh", "onion_verifier.py", "DarkFox.desktop"}:
            errors.append(f"upstream source present: {relative.as_posix()}")
        if path.suffix.lower() in {".jpg", ".png", ".webp", ".ico"}:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if path.name != "release.py" and DEVELOPER_PATH.search(text):
            errors.append(f"developer-specific path present: {relative.as_posix()}")
        if SECRET_PATTERN.search(text):
            errors.append(f"probable secret present: {relative.as_posix()}")
        if any(name in text for name in ("darkfox.sh", "onion_verifier.py", "DarkFox.desktop")):
            if path.name not in UPSTREAM_REFERENCES_ALLOWED_IN:
                errors.append(f"unexpected upstream filename reference: {relative.as_posix()}")
    return {"valid": not errors, "files_checked": checked, "errors": errors}
