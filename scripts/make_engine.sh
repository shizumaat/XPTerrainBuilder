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
# A venv whose pyvenv.cfg is gone is not a venv: macOS purges old files under
# ${TMPDIR} at reboot but leaves the bin/ symlinks, and the bare interpreter they
# point at is Homebrew's externally-managed python (PEP 668) — the freeze then
# fails at the first pip call and make_app.sh bundles the PREVIOUS engine under
# a new version label (2026-09-16, "1.0.342" shipped 1.0.341's engine).
if [[ ! -x "$VENV/bin/python" || ! -f "$VENV/pyvenv.cfg" ]]; then
  rm -rf "$VENV"
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

# THE LERC SMOKE TEST (owner RULINGS 2026-09-12as (3) / 2026-09-13a (1)):
# ONE implementation, run against whichever binary this freeze produced —
# the same script the Windows and Linux release jobs run against theirs.
# The Qt freeze emits `Ortho4XP_Qt/Ortho4XP_Qt`, the engine freeze
# `Ortho4XP/Ortho4XP`; on macOS the Qt freeze ALSO emits an .app, whose
# executable is the same file inside the bundle, so the onedir binary is
# the one tested.
if (( NEED_QT )); then
  LERC_BIN="dist/Ortho4XP_Qt/Ortho4XP_Qt"
else
  LERC_BIN="dist/Ortho4XP/Ortho4XP"
fi
"$ROOT/scripts/check_frozen_lerc.sh" "$ENGINE/$LERC_BIN" "$PY"

# THE GDAL BUNDLE CHECK (2026-10-26, app 1.0.429): a Homebrew GDAL upgrade
# left the freeze venv's bindings linked to a libgdal that no longer
# existed; PyInstaller only WARNED "Library not found" and the frozen engine
# shipped with no GDAL at all, so every lidar airport refused to patch
# ("the GDAL python bindings (osgeo) are unavailable").  The bindings are
# bundled, so the libgdal they link must be bundled too, or the freeze fails.
BUNDLE_DIR="$(dirname "$ENGINE/$LERC_BIN")/_internal"
if [[ -d "$BUNDLE_DIR/osgeo" ]]; then
  GDAL_LINK="$(otool -L "$BUNDLE_DIR"/osgeo/_gdal*.so 2>/dev/null | awk '/libgdal/ {print $1; exit}')"
  GDAL_LIB="$(basename "${GDAL_LINK:-missing}")"
  if [[ ! -f "$BUNDLE_DIR/$GDAL_LIB" ]]; then
    echo "ERROR: the frozen engine's GDAL bindings link $GDAL_LINK, which is not in the bundle." >&2
    echo "       Match requirements.txt's Darwin gdal pin to Homebrew's GDAL (gdal-config --version)." >&2
    exit 1
  fi
  # ONE COPY OF EACH SHARED LIBRARY (2026-10-26, app 1.0.430): Pillow ships
  # its own libharfbuzz.0.dylib under PIL/.dylibs (harfbuzz 13 at Pillow
  # 12.2) while Homebrew's GDAL 3.13 pulls harfbuzz 15 (libharfbuzz-subset).
  # dyld resolves both to ONE image by install name, the older one won, and
  # libgdal failed to load ("Symbol not found:
  # _hb_draw_funcs_set_get_budget_remaining_func") — so the frozen engine
  # had no GDAL although every file was bundled.  The newer copy replaces
  # the older (harfbuzz keeps ABI backward-compatible), and the check
  # below proves libgdal actually LOADS, not just that it is present.
  # PyInstaller dedupes by name: the bundle-root libharfbuzz.0.dylib is a
  # SYMLINK to Pillow's copy, so Homebrew's newer one is never collected.
  # Put Homebrew's harfbuzz in Pillow's slot, made relocatable: its own id
  # and its Homebrew deps rewritten to @rpath, plus an rpath to the bundle
  # root where PyInstaller collected those deps (freetype, glib, graphite2).
  HB_PIL="$BUNDLE_DIR/PIL/.dylibs/libharfbuzz.0.dylib"
  HB_BREW="$(brew --prefix harfbuzz 2>/dev/null)/lib/libharfbuzz.0.dylib"
  if [[ -f "$BUNDLE_DIR/libharfbuzz-subset.0.dylib" && -f "$HB_PIL" && -f "$HB_BREW" ]]; then
    rm -f "$HB_PIL"
    cp "$HB_BREW" "$HB_PIL"
    chmod u+w "$HB_PIL"
    install_name_tool -id "@rpath/libharfbuzz.0.dylib" "$HB_PIL"
    for DEP in $(otool -L "$HB_PIL" | awk 'NR>2 && /\/opt\/homebrew\// {print $1}'); do
      install_name_tool -change "$DEP" "@rpath/$(basename "$DEP")" "$HB_PIL"
    done
    install_name_tool -add_rpath "@loader_path/../.." "$HB_PIL" 2>/dev/null || true
    codesign --force --sign - "$HB_PIL" >/dev/null 2>&1 || true
    echo "   unified libharfbuzz.0.dylib (Homebrew's, relocatable, in PIL/.dylibs)"
  fi
  # The signed app's hardened runtime refuses a library whose install-name
  # leaf differs from the requested one (liblz4.1.dylib -> 1.10.0); this
  # unsigned check cannot see that, make_app's signed-engine gate does.
  "$ROOT/scripts/fix_bundle_install_names.sh" "$BUNDLE_DIR"
  "$PY" -I -c "import ctypes, sys; ctypes.CDLL(sys.argv[1])" "$BUNDLE_DIR/$GDAL_LIB" || {
    echo "ERROR: the bundled $GDAL_LIB does not load (see the dyld error above)." >&2
    exit 1
  }
  echo "   frozen GDAL OK ($GDAL_LIB bundled and loads)"
fi

echo "Frozen engine: $ENGINE/$OUT (version ${VERSION:-unknown})"
