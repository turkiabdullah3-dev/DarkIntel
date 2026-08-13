import os
from pathlib import Path
import shutil
import socket
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "scripts" / "darkintel-launcher.sh"
INSTALLER = ROOT / "scripts" / "install-linux-launcher.sh"
UNINSTALLER = ROOT / "scripts" / "uninstall-linux-launcher.sh"
DESKTOP = ROOT / "packaging" / "linux" / "DarkIntel.desktop"


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_launcher_is_relocatable_and_unprivileged():
    source = text(LAUNCHER)
    assert 'dirname -- "$SCRIPT_PATH"' in source
    assert "/home/kali" not in source and "/opt/darkfox" not in source
    assert "sudo" not in source and "chmod 777" not in source
    assert "pkill" not in source and "killall" not in source
    assert "127.0.0.1:8000/api/v1/health" in source
    assert '${XDG_STATE_HOME:-${HOME}/.local/state}/darkintel' in source


def test_desktop_entry_metadata_and_installer_paths():
    desktop = text(DESKTOP)
    assert "Name=DarkIntel" in desktop
    assert "Comment=CTI & OSINT Investigation Platform" in desktop
    assert "Categories=Utility;Security;Development;" in desktop
    assert "Exec=@DARKINTEL_EXEC@" in desktop and "Icon=darkintel" in desktop
    installer = text(INSTALLER)
    assert ".local/share}/applications" in installer
    assert ".local/share}/icons/hicolor/256x256/apps" in installer
    assert "sudo" not in installer
    uninstaller = text(UNINSTALLER)
    assert "cases" not in uninstaller and "evidence" not in uninstaller
    assert "pkill" not in uninstaller and "killall" not in uninstaller


pytestmark = pytest.mark.skipif(os.name == "nt" or not shutil.which("bash"),
                                reason="Linux launcher behavior")


def make_repo(tmp_path: Path) -> Path:
    root = tmp_path / "relocated" / "DarkIntel"
    (root / "scripts").mkdir(parents=True)
    shutil.copy2(LAUNCHER, root / "scripts" / LAUNCHER.name)
    (root / "dashboard" / "frontend" / "src").mkdir(parents=True)
    (root / "dashboard" / "frontend" / "package.json").write_text("{}", encoding="utf-8")
    (root / "dashboard" / "frontend" / "package-lock.json").write_text("{}", encoding="utf-8")
    (root / "dashboard" / "frontend" / "index.html").write_text("", encoding="utf-8")
    return root


def fake_command(directory: Path, name: str, body: str) -> None:
    path = directory / name
    path.write_text("#!/usr/bin/env bash\n" + body, encoding="utf-8")
    path.chmod(0o755)


def run_launcher(root: Path, tmp_path: Path, fake_bin: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update({"HOME": str(tmp_path / "home"), "XDG_STATE_HOME": str(tmp_path / "state"),
                "PATH": f"{fake_bin}{os.pathsep}{env['PATH']}"})
    return subprocess.run(["bash", str(root / "scripts" / LAUNCHER.name)], env=env,
                          text=True, capture_output=True, timeout=10, check=False)


def test_missing_venv_reports_setup_required(tmp_path):
    root, fake_bin = make_repo(tmp_path), tmp_path / "bin"
    fake_bin.mkdir()
    fake_command(fake_bin, "curl", "exit 1\n")
    result = run_launcher(root, tmp_path, fake_bin)
    assert result.returncode == 1
    assert "Setup is required" in result.stderr
    assert str(root) in result.stderr


def test_existing_healthy_darkintel_only_opens_browser(tmp_path):
    root, fake_bin = make_repo(tmp_path), tmp_path / "bin"
    fake_bin.mkdir()
    opened = tmp_path / "opened"
    fake_command(fake_bin, "curl", "printf '%s' '{\"product\":\"DarkIntel\"}'\n")
    fake_command(fake_bin, "xdg-open", f"printf '%s' \"$1\" > {opened!s}\n")
    result = run_launcher(root, tmp_path, fake_bin)
    assert result.returncode == 0
    for _ in range(20):
        if opened.exists():
            break
        import time
        time.sleep(0.05)
    assert opened.read_text(encoding="utf-8") == "http://127.0.0.1:8000"
    assert not (tmp_path / "state" / "darkintel" / "server.pid").exists()


def test_port_conflict_does_not_kill_listener(tmp_path):
    root, fake_bin = make_repo(tmp_path), tmp_path / "bin"
    fake_bin.mkdir()
    fake_command(fake_bin, "curl", "exit 1\n")
    listener = socket.socket()
    try:
        listener.bind(("127.0.0.1", 8000))
    except OSError:
        pytest.skip("port 8000 unavailable")
    listener.listen()
    result = run_launcher(root, tmp_path, fake_bin)
    assert result.returncode == 1 and "Port 8000 is in use" in result.stderr
    assert listener.fileno() >= 0
    listener.close()


def test_missing_npm_when_frontend_build_required(tmp_path):
    root, fake_bin = make_repo(tmp_path), tmp_path / "isolated-bin"
    fake_bin.mkdir()
    for command in ("dirname", "readlink", "mkdir", "rmdir", "grep", "find"):
        target = shutil.which(command)
        assert target
        (fake_bin / command).symlink_to(target)
    fake_command(fake_bin, "curl", "exit 1\n")
    python = root / ".venv" / "bin" / "python"
    python.parent.mkdir(parents=True)
    python.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    python.chmod(0o755)
    result = run_launcher(root, tmp_path, fake_bin)
    assert result.returncode == 1
    assert "npm is unavailable" in result.stderr


def test_user_local_install_and_uninstall_preserve_repository(tmp_path):
    root = tmp_path / "moved project" / "DarkIntel"
    (root / "scripts").mkdir(parents=True)
    (root / "packaging" / "linux").mkdir(parents=True)
    for source in (LAUNCHER, INSTALLER, UNINSTALLER):
        shutil.copy2(source, root / "scripts" / source.name)
    shutil.copy2(DESKTOP, root / "packaging" / "linux" / DESKTOP.name)
    shutil.copy2(ROOT / "packaging" / "linux" / "darkintel.png",
                 root / "packaging" / "linux" / "darkintel.png")
    home, data, state = tmp_path / "home", tmp_path / "data", tmp_path / "state"
    env = os.environ.copy()
    env.update({"HOME": str(home), "XDG_DATA_HOME": str(data), "XDG_STATE_HOME": str(state)})
    install = subprocess.run(["bash", str(root / "scripts" / INSTALLER.name)], env=env,
                             text=True, capture_output=True, check=False)
    assert install.returncode == 0, install.stderr
    link = home / ".local" / "bin" / "darkintel"
    desktop = data / "applications" / "DarkIntel.desktop"
    icon = data / "icons" / "hicolor" / "256x256" / "apps" / "darkintel.png"
    assert link.is_symlink() and link.resolve() == root / "scripts" / LAUNCHER.name
    assert f"Exec={link}" in desktop.read_text(encoding="utf-8")
    assert icon.is_file()
    uninstall = subprocess.run(["bash", str(root / "scripts" / UNINSTALLER.name)], env=env,
                               text=True, capture_output=True, check=False)
    assert uninstall.returncode == 0, uninstall.stderr
    assert not link.exists() and not desktop.exists() and not icon.exists()
    assert root.is_dir()
