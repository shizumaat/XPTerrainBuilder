#!/usr/bin/env bash
# Is the working tree dirty in a way that makes the commit sha a LIE?
#
# Exit 0 = dirty (the stamped sha does not describe what was built).
# Exit 1 = clean enough to stamp the sha bare.
#
# The two tracked version files are EXCLUDED. A local `make_app.sh` /
# `make_engine.sh` bumps its own version file as its first act
# (scripts/version.sh), so by the time anything stamps a sha the tree always
# differs from HEAD by exactly that line — a plain `git diff --quiet HEAD`
# would mark every single local build "-dirty" and the marker would carry no
# information at all. Any OTHER modification still marks it, which is the
# case the marker exists for.
#
# Untracked files are not dirt: build outputs and caches are untracked by
# design, and none of them is in the binary.
#
# bash, not zsh: called from the zsh build scripts AND from bash
# scripts/write_version_txt.sh — one implementation, either shell.
#
# Usage: scripts/tree_dirty.sh [repo-root]
set -uo pipefail

ROOT="${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"

CHANGED="$(git -C "$ROOT" diff --name-only HEAD 2>/dev/null)" || exit 1

while IFS= read -r path; do
  [ -n "$path" ] || continue
  case "$path" in
    Sources/XPTerrainBuilder/Resources/VERSION|Ortho4XP/src/O4_Version.py) ;;
    *) exit 0 ;;
  esac
done <<< "$CHANGED"

exit 1
