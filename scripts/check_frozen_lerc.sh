#!/usr/bin/env bash
# THE LERC SMOKE TEST — one implementation, every frozen artifact
# (owner RULINGS 2026-09-12as (3), extended to Windows/Linux by 2026-09-13a (1)).
#
# A frozen binary decodes LERC elevation assets by re-exec'ing ITSELF as
# `<binary> --lerc-decode IN OUT` (src/O4_LERC_Decode.py); tifffile hands the
# decode to imagecodecs' compiled _lerc extension.  A bundle missing either
# does not crash — it SKIPS the source and silently degrades New Zealand's
# 1 m lidar to the base tier, which is how 1.0.324 shipped.  So a missing
# codec fails THE BUILD, never a tile build.
#
# Usage: scripts/check_frozen_lerc.sh <frozen-binary> [python]
#   <frozen-binary>  the frozen executable (mac engine `Ortho4XP`, or the
#                    Windows/Linux Qt app `Ortho4XP_Qt[.exe]`)
#   [python]         a Python with numpy + tifffile + imagecodecs, used to
#                    WRITE the fixture and CHECK the result (default: python3;
#                    the freeze venv under make_engine.sh, the job interpreter
#                    in CI).  It is never the thing under test.
#
# bash, not zsh: this script runs on the Windows and Linux release runners
# as well as on the maintainer's mac.
set -euo pipefail

BIN="${1:?usage: check_frozen_lerc.sh <frozen-binary> [python]}"
PY="${2:-python3}"

if [[ ! -x "$BIN" && ! -f "$BIN" ]]; then
  echo "ERROR: no frozen binary at $BIN" >&2
  exit 1
fi

echo "Checking the frozen binary decodes LERC ($BIN) …"
LERC_DIR="$(mktemp -d)"
trap 'rm -rf "$LERC_DIR"' EXIT

"$PY" - "$LERC_DIR" <<'PYEOF'
import sys
import numpy
import tifffile
directory = sys.argv[1]
values = (numpy.arange(64 * 64, dtype=numpy.float32).reshape(64, 64) / 7.0)
tifffile.imwrite(
    directory + "/fixture.tif", values, compression="lerc",
    extratags=[(33550, "d", 3, (1.0, 1.0, 0.0)),
               (33922, "d", 6, (0.0, 0.0, 0.0, 170.0, -45.0, 0.0))])
PYEOF

"$BIN" --lerc-decode "$LERC_DIR/fixture.tif" "$LERC_DIR/out.npy" \
  > "$LERC_DIR/stdout.json" || {
  echo "ERROR: the frozen binary cannot decode LERC (--lerc-decode failed) —" >&2
  echo "       tifffile / imagecodecs / imagecodecs._lerc are missing from the" >&2
  echo "       bundle, or the entry point does not dispatch --lerc-decode." >&2
  exit 1
}

"$PY" - "$LERC_DIR" <<'PYEOF' || exit 1
import json
import os
import sys
import numpy
directory = sys.argv[1]
values = numpy.load(directory + "/out.npy")
# The tags come back on stdout AND in the sidecar beside the array: a
# console-less (windowed) frozen binary can run with sys.stdout None, so
# the sidecar is the channel that cannot go missing.  Both are checked —
# a build whose sidecar is absent would break the Qt app's own caller.
text = open(directory + "/stdout.json").read().strip()
sidecar = directory + "/out.npy.tags.json"
if not os.path.isfile(sidecar):
    raise SystemExit("ERROR: the frozen LERC decode wrote no OUT.tags.json")
if not text:
    text = open(sidecar).read()
tags = json.loads(text)
expected = (numpy.arange(64 * 64, dtype=numpy.float32).reshape(64, 64) / 7.0)
if values.shape != (64, 64) or not numpy.allclose(values, expected, atol=1e-3):
    raise SystemExit("ERROR: the frozen LERC decode returned the wrong array")
if tags["tiepoint"][3:5] != [170.0, -45.0]:
    raise SystemExit("ERROR: the frozen LERC decode lost the georeferencing tags")
print("   frozen LERC decode OK (64x64 float32, tags carried)")
PYEOF
