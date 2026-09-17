#!/usr/bin/env bash
# THE FROZEN TILE-BUILD SMOKE TEST — one implementation, every frozen
# artifact (beta plan docs/BETA-PLAN-20260916.md §1 B4, round 2).
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
#                    (--deadline, --logs, --lat/--lon, --keep).
#
# The fixture is generated into a temp dir and thrown away: a synthetic
# data root, one synthetic elevation source, pre-seeded empty OSM caches,
# imagery off, auto_patch off, no X-Plane install, no shared corpus, no
# provider key, no network.  The whole check runs under a deadline
# enforced inside the helper — coreutils `timeout` exists on neither the
# mac runner nor the maintainer's mac.
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

echo "Checking the frozen bundle can BUILD A TILE ($BIN) …"
"$PY" "$HERE/check_frozen_tile.py" "$BIN" "$@"
