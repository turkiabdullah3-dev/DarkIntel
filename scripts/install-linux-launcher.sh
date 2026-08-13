#!/usr/bin/env bash
set -euo pipefail

SCRIPT_PATH="${BASH_SOURCE[0]}"
if command -v readlink >/dev/null 2>&1; then
  SCRIPT_PATH="$(readlink -f "$SCRIPT_PATH" 2>/dev/null || printf '%s' "$SCRIPT_PATH")"
fi
ROOT_DIR="$(cd -- "$(dirname -- "$SCRIPT_PATH")/.." && pwd -P)"
BIN_DIR="${HOME}/.local/bin"
APP_DIR="${XDG_DATA_HOME:-${HOME}/.local/share}/applications"
ICON_DIR="${XDG_DATA_HOME:-${HOME}/.local/share}/icons/hicolor/256x256/apps"
STATE_DIR="${XDG_STATE_HOME:-${HOME}/.local/state}/darkintel"
LAUNCHER_LINK="$BIN_DIR/darkintel"
DESKTOP_FILE="$APP_DIR/DarkIntel.desktop"
ICON_FILE="$ICON_DIR/darkintel.png"
MANIFEST="$STATE_DIR/launcher-installation"

mkdir -p -- "$BIN_DIR" "$APP_DIR" "$ICON_DIR" "$STATE_DIR"
if [[ -e "$LAUNCHER_LINK" && ! -L "$LAUNCHER_LINK" ]]; then
  printf 'Refusing to overwrite unrelated file: %s\n' "$LAUNCHER_LINK" >&2
  exit 1
fi
if [[ -L "$LAUNCHER_LINK" && "$(readlink -f "$LAUNCHER_LINK")" != "$ROOT_DIR/scripts/darkintel-launcher.sh" ]]; then
  printf 'Refusing to overwrite unrelated symlink: %s\n' "$LAUNCHER_LINK" >&2
  exit 1
fi
if [[ -e "$DESKTOP_FILE" ]] && ! grep -q '^X-DarkIntel-Managed=true$' "$DESKTOP_FILE"; then
  printf 'Refusing to overwrite unrelated desktop entry: %s\n' "$DESKTOP_FILE" >&2
  exit 1
fi
if [[ -e "$ICON_FILE" && ! -f "$DESKTOP_FILE" ]]; then
  printf 'Refusing to overwrite unrelated icon: %s\n' "$ICON_FILE" >&2
  exit 1
fi

chmod u+x -- "$ROOT_DIR/scripts/darkintel-launcher.sh"
ln -sfn -- "$ROOT_DIR/scripts/darkintel-launcher.sh" "$LAUNCHER_LINK"
while IFS= read -r desktop_line; do
  if [[ "$desktop_line" == "Exec=@DARKINTEL_EXEC@" ]]; then
    printf 'Exec=%s\n' "$LAUNCHER_LINK"
  else
    printf '%s\n' "$desktop_line"
  fi
done <"$ROOT_DIR/packaging/linux/DarkIntel.desktop" >"$DESKTOP_FILE"
install -m 0644 -- "$ROOT_DIR/packaging/linux/darkintel.png" "$ICON_FILE"
printf '%s\n%s\n%s\n' "$LAUNCHER_LINK" "$DESKTOP_FILE" "$ICON_FILE" >"$MANIFEST"

if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "$APP_DIR" >/dev/null 2>&1 || true
fi
printf 'DarkIntel launcher installed. Open DarkIntel from your applications menu.\n'
