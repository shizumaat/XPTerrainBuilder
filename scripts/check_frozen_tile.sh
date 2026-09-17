#!/usr/bin/env bash
# THE FROZEN BUILD SMOKE TEST — one implementation, every frozen
# artifact (beta plan docs/BETA-PLAN-20260916.md §1 B4, rounds 2-3).
#
# TWO PASSES, run by this one call (release.yml is untouched):
#   1. a synthetic TILE with auto_patch OFF — vector + mesh + imagery,
#      a real .dsf on disk;
#   2. ONE REAL AIRPORT SOLVED with auto_patch ON — the vector step over
#      the checked-in CYXY fixture, arranged into an X-Plane-shaped root,
#      asserting the emitted <ICAO>_auto.patch.osm + .axes.json sidecar
#      and no AutoPatchFailed.  Pass 2 is the only one that walks
#      auto_patch_v2's linear programme, i.e. the lazy `highspy` import
#      that actually shipped broken.  Restrict with `--pass tile|airport`.
#
# The release jobs' PROJ and LERC self-checks prove the frozen bundle
# IMPORTS.  What has actually shipped broken is narrower and invisible to
# both: a function-level third-party import PyInstaller never sees and the
# test suite never exercises (highspy, 2026-09-10), a data file missing
# from the .spec, or a wrong data-root / cwd resolution inside the bundle.
# Those only surface on a code path a real build walks.  So every release
# job BUILDS A TILE with the frozen bundle, through the shipped interface
# — the engine's JSON-lines protocol (`<binary> --engine-jsonl`), never an
# import — before the artifact is signed (mac) or zipped (Windows/Linux).
#
# Usage: scripts/check_frozen_tile.sh <frozen-binary> [python] [extra args]
#   <frozen-binary>  the frozen executable (mac engine `Ortho4XP`, or the
#                    Windows/Linux Qt app `Ortho4XP_Qt[.exe]` — that
#                    binary dispatches --engine-jsonl before any Qt
#                    import, so it is a headless engine too)
#   [python]         the helper interpreter that generates the fixture and
#                    checks the result (default: python3).  It needs
#                    NOTHING but the standard library — the mac release
#                    job's bare python3 has no numpy, which is what killed
#                    a redundant LERC step (removed 2026-09-17).  It is
#                    never the thing under test.
#   [extra args]     passed through to scripts/check_frozen_tile.py
#                    (--pass, --deadline, --airport-deadline, --logs,
#                    --lat/--lon, --keep, --xplat-dump, --xplat-quantise).
#
# --xplat-dump additionally runs a SECOND, NON-GATING airport solve with the
# load stage's projection snapped (--xplat-quantise, default 1 mm) — the
# interventional arm of the cross-platform measurement (lane `xplatspread`).
# Its outcome is printed and discarded: a release never goes red over an
# instrument.  Pass `--xplat-quantise 0` to skip it.
#
# Both fixtures are generated into temp dirs and thrown away: a private
# data root, imagery off, no shared corpus, no provider key, no network
# (every OSM layer is pre-seeded as an empty, schema-stamped cache; the
# airport pass additionally has elevation insets off, the one auto-patch
# input that would fetch from national elevation servers).  Each pass
# runs under its own deadline enforced inside the helper — coreutils
# `timeout` exists on neither the mac runner nor the maintainer's mac.
#
# bash, not zsh: this runs on the Windows and Linux release runners as
# well as on the maintainer's mac.
set -euo pipefail

BIN="${1:?usage: check_frozen_tile.sh <frozen-binary> [python] [extra args]}"
PY="${2:-python3}"
shift || true
shift || true

if [[ ! -x "$BIN" && ! -f "$BIN" ]]; then
  echo "ERROR: no frozen binary at $BIN" >&2
  exit 1
fi

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Checking the frozen bundle can BUILD A TILE and SOLVE AN AIRPORT ($BIN) …"
"$PY" "$HERE/check_frozen_tile.py" "$BIN" "$@"
