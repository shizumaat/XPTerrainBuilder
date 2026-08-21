#!/bin/zsh
# Freeze the vendored Ortho4XP engine into a fully self-contained folder:
# its own Python runtime plus every required package, so users never install
# or configure Python. Uses the engine's own PyInstaller specs.
#
# Usage: scripts/make_engine.sh [--qt]
#   default : Ortho4XP.spec     (engine + jsonl protocol; what the mac app embeds)
#   --qt    : Ortho4XP_Qt.spec  (standalone Qt GUI; the Windows/Linux release app)
#
# Output: Ortho4XP/dist/Ortho4XP/ (onedir: executable + _internal/)
set -euo pipefail

SPEC="Ortho4XP.spec"
NEED_QT=0
if [[ "${1:-}" == "--qt" ]]; then
  SPEC="Ortho4XP_Qt.spec"
  NEED_QT=1
fi

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENGINE="$ROOT/Ortho4XP"
source "$ROOT/scripts/version.sh"
cd "$ENGINE"

# iCloud Drive conflict copies ("Foo 2.lay") poison the freeze — they get
# baked into the runtime and show up as duplicate providers in the UIs.
# Refuse to freeze from a dirty checkout.
# Airport_mod_cache holds downloaded airport packs whose legitimate names
# can match the conflict pattern ("… 3.0 Nueva Terminal …"); it is runtime
# data the spec never embeds, so it is exempt — as are the dev venv (the
# freeze uses its own venv; iCloud mints thousands of dupes in
# site-packages), dist/build, and .claude (session worktrees carry full
# checkout copies — including nested Airport_mod_cache dirs whose pack
# names re-trip the pattern, 2026-07-27 — and are never embedded), and
# tmp/ (the lane-local engine cache root, tmp/engine_caches/Airport_mod_cache,
# seeds the same pack names from the shared corpus, 2026-08-21).
# No `| head` inside the substitution: with pipefail, head closing the
# pipe early SIGPIPEs find and the whole script died with exit 141 —
# silently, under callers that piped our output (2026-07-23).
CONFLICTS="$(find . -path ./dist -prune -o -path ./build -prune \
  -o -path ./Airport_mod_cache -prune -o -path ./venv -prune \
  -o -path ./.claude -prune -o -path ./tmp -prune \
  -o -name '* [2-9].*' -print)"
if [[ -n "$CONFLICTS" ]]; then
  echo "ERROR: iCloud conflict copies in the engine checkout — clean first:" >&2
  echo "$CONFLICTS" | head -5 >&2
  exit 1
fi

# Dedicated freeze venv, separate from any dev venv. ${TMPDIR} keeps the
# heavyweight site-packages out of synced folders (iCloud Documents).
VENV="${ENGINE_FREEZE_VENV:-${TMPDIR:-/tmp}/xptb-freeze-venv}"
PYTHON_BOOT="${PYTHON:-python3}"
if [[ ! -x "$VENV/bin/python" ]]; then
  "$PYTHON_BOOT" -m venv "$VENV"
fi
PY="$VENV/bin/python"
"$PY" -m pip install --upgrade pip >/dev/null

# Requirements, filtered: the dev/test section stays out; PySide6 only for
# the Qt build; gdal is optional at runtime (the engine degrades gracefully),
# so its install failure must not sink the freeze.
CORE_REQS="$(mktemp)"
GDAL_REQ="$(awk '/^gdal==/' requirements.txt || true)"
awk '
  /^# Dev \/ test/ { exit }
  /^gdal==/ { next }
  NEED_QT == 0 && /^PySide6==/ { next }
  NF { print }
' NEED_QT="$NEED_QT" requirements.txt > "$CORE_REQS"

echo "Installing engine packages into $VENV …"
"$PY" -m pip install -r "$CORE_REQS"
rm -f "$CORE_REQS"
if [[ -n "$GDAL_REQ" ]]; then
  echo "Installing optional GDAL bindings…"
  "$PY" -m pip install $(echo "$GDAL_REQ" | head -1 | cut -d';' -f1) \
    || echo "WARNING: GDAL install failed — airport elevation insets will be disabled (engine handles this gracefully)."
fi
"$PY" -m pip install pyinstaller

# Every freeze is a new engine build: bump 1.50.<build> before PyInstaller
# runs, so the version baked into the frozen tree is the one this build
# ships. Late enough that a failed pip install doesn't burn a number.
NEW_VERSION="$(xptb_version_bump "$ENGINE/src/O4_Version.py")"
echo "Engine build $NEW_VERSION"

echo "Freezing with $SPEC …"
rm -rf build dist
"$PY" -m PyInstaller "$SPEC" --noconfirm

# Version stamp: frozen engines have no src/O4_Version.py on disk; the app
# reads VERSION.txt instead.
# Belt to the pre-freeze check's suspenders: purge any conflict copies the
# file provider slipped in DURING the freeze.
find dist -name '* [2-9].*' -delete 2>/dev/null || true

VERSION="$(grep -m1 '^version' src/O4_Version.py | cut -d= -f2 | tr -d " '\"" )"
OUT="dist/Ortho4XP"
if [[ -d "dist/Ortho4XP.app" && ! -d "$OUT" ]]; then
  # The Qt spec on macOS may emit an .app; the raw onedir also exists for it.
  OUT="$(ls -d dist/*/ | head -1)"
fi
echo "${VERSION:-unknown}" > "$OUT/VERSION.txt"

echo "Frozen engine: $ENGINE/$OUT (version ${VERSION:-unknown})"
