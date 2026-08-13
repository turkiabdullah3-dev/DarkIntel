#!/usr/bin/env bash
set -euo pipefail

STATE_DIR="${XDG_STATE_HOME:-${HOME}/.local/state}/darkintel"
MANIFEST="$STATE_DIR/launcher-installation"
APP_DIR="${XDG_DATA_HOME:-${HOME}/.local/share}/applications"

if [[ -f "$MANIFEST" ]]; then
  while IFS= read -r installed_path; do
    [[ -n "$installed_path" ]] || continue
    case "$installed_path" in
      "${HOME}/.local/bin/darkintel"|"${XDG_DATA_HOME:-${HOME}/.local/share}/applications/DarkIntel.desktop"|"${XDG_DATA_HOME:-${HOME}/.local/share}/icons/hicolor/256x256/apps/darkintel.png")
        rm -f -- "$installed_path"
        ;;
      *)
        printf 'Skipping unexpected manifest path: %s\n' "$installed_path" >&2
        ;;
    esac
  done <"$MANIFEST"
  rm -f -- "$MANIFEST"
fi
if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "$APP_DIR" >/dev/null 2>&1 || true
fi
printf 'DarkIntel launcher integration removed. Investigation data was not changed.\n'
