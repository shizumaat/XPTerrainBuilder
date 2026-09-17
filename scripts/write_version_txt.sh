#!/usr/bin/env bash
# THE VERSION TRIPLE — one implementation, every artifact root
# (docs/BETA-PLAN-20260916.md §1 B3(2)).
#
# A beta tester's report is only actionable if it says WHICH build broke, and
# "1.0.347" alone does not: the app version, the engine version and the commit
# are three independent numbers.  So every artifact root carries VERSION.txt:
#
#   app=1.0.347
#   engine=1.50.1793
#   sha=5883949fd1c2...
#
# Both UIs read this file for their About box (Ortho4XP/src/O4_Build_Info.py,
# Sources/XPTerrainBuilder — via Info.plist keys stamped from here), so the
# key=value shape is a contract, pinned by tests/test_version_scheme.py.
#
# Usage: scripts/write_version_txt.sh <out-file>
#
# bash, not zsh: this runs on the Windows and Linux release runners too.
set -euo pipefail

OUT="${1:?usage: write_version_txt.sh <out-file>}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

read_triple() {  # <file>
  grep -o -E -m1 '[0-9]+\.[0-9]+\.[0-9]+' "$1" 2>/dev/null || true
}

APP="$(read_triple "$ROOT/Sources/XPTerrainBuilder/Resources/VERSION")"
ENGINE="$(read_triple "$ROOT/Ortho4XP/src/O4_Version.py")"
[ -n "$APP" ] || APP="dev"
[ -n "$ENGINE" ] || ENGINE="dev"

# CI hands us the exact commit; a local package asks git.  A tree that is not
# a checkout at all (a source tarball) says "dev" rather than lying.
SHA="${GITHUB_SHA:-}"
if [ -z "$SHA" ]; then
  SHA="$(git -C "$ROOT" rev-parse HEAD 2>/dev/null || true)"
  if [ -n "$SHA" ] && ! git -C "$ROOT" diff --quiet HEAD 2>/dev/null; then
    SHA="$SHA-dirty"
  fi
fi
[ -n "$SHA" ] || SHA="dev"

printf 'app=%s\nengine=%s\nsha=%s\n' "$APP" "$ENGINE" "$SHA" > "$OUT"
cat "$OUT"
