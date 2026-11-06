#!/usr/bin/env bash
# The frozen engine's provenance stamp (2026-11-06, app 1.0.471): that app
# was packaged at 81a3d0649 without re-running make_engine.sh, embedded the
# engine frozen for 1.0.470 (82ea809e3), and its log quoted the SOURCE
# tree's commit — the owner tested an app with none of the new code.
#
#   engine_stamp.sh write FROZEN_DIR [ROOT]   make_engine.sh, after the freeze
#   engine_stamp.sh check FROZEN_DIR [ROOT]   make_app.sh, before embedding;
#                                             prints the embedded commit, or
#                                             REFUSING (exit 1)
#
# The stamp (FROZEN_DIR/ENGINE_STAMP.txt) names the commit frozen from, a
# dirty flag, and — when dirty — a digest of the uncommitted engine code, so
# a dirty tree only matches the exact edits it was frozen with.  The version
# files are excluded exactly as scripts/tree_dirty.sh excludes them.
set -uo pipefail
MODE="${1:?write|check}"; FROZEN="${2:?frozen dir}"
ROOT="${3:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
STAMP="$FROZEN/ENGINE_STAMP.txt"

source_state() {
  local sha dirty=0 digest=-
  sha="$(git -C "$ROOT" rev-parse HEAD 2>/dev/null)" || sha=unknown
  if bash "$ROOT/scripts/tree_dirty.sh" "$ROOT"; then
    dirty=1
    digest="$(git -C "$ROOT" diff HEAD -- . ':!Sources/XPTerrainBuilder/Resources/VERSION' \
      ':!Ortho4XP/src/O4_Version.py' | shasum -a 256 | cut -d' ' -f1)"
  fi
  printf 'commit=%s\ndirty=%s\ndigest=%s\n' "$sha" "$dirty" "$digest"
}

case "$MODE" in
  write) source_state > "$STAMP" ;;
  check)
    WANT="$(source_state)"
    if [[ ! -f "$STAMP" ]]; then
      echo "REFUSING: embedded engine has no provenance stamp, source is $(sed -n 's/^commit=//p' <<< "$WANT"); run scripts/make_engine.sh" >&2
      exit 1
    fi
    HAVE="$(cat "$STAMP")"
    if [[ "$HAVE" != "$WANT" ]]; then
      fmt() { awk -F= '/^commit=/{c=$2}/^dirty=/{d=$2}/^digest=/{g=$2}END{printf "%s%s", c, (d=="1" ? "-dirty(" substr(g,1,12) ")" : "")}'; }
      echo "REFUSING: embedded engine was frozen at $(fmt <<< "$HAVE"), source is $(fmt <<< "$WANT"); run scripts/make_engine.sh" >&2
      exit 1
    fi
    sed -n 's/^commit=//p' "$STAMP"
    ;;
  *) echo "usage: engine_stamp.sh write|check FROZEN_DIR [ROOT]" >&2; exit 2 ;;
esac
