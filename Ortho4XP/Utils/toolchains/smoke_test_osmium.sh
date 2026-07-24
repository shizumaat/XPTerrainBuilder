#!/bin/sh
# Smoke-test an osmium-tool binary before bundling it as
# Utils/<platform>/osmium.  Usage:
#
#   sh smoke_test_osmium.sh <path-to-osmium>
#
# Checks, in order:
#   1. the binary runs and reports exactly the pinned osmium-tool and
#      libosmium versions from build_osmium_tool.sh;
#   2. an `osmium extract` with the engine's exact flags (the command
#      O4_OSM_Extract_Filter._run_osmium_extract builds) cuts a tiny
#      synthetic extract correctly: the in-box way survives, the
#      out-of-box way is dropped.
#
# POSIX sh only — must run under macOS /bin/sh, Alpine busybox ash,
# and Windows git-bash alike.
set -eu

OSMIUM="$1"

# Pins — keep in lockstep with build_osmium_tool.sh.
OSMIUM_TOOL_VERSION=1.19.1
LIBOSMIUM_VERSION=2.23.1

echo "== version check: $OSMIUM"
"$OSMIUM" --version
"$OSMIUM" --version | grep -F "osmium version $OSMIUM_TOOL_VERSION" \
  > /dev/null || {
    echo "FAIL: expected osmium-tool $OSMIUM_TOOL_VERSION" >&2; exit 1; }
"$OSMIUM" --version | grep -F "libosmium version $LIBOSMIUM_VERSION" \
  > /dev/null || {
    echo "FAIL: expected libosmium $LIBOSMIUM_VERSION" >&2; exit 1; }

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

# Same fixture shape as tests/test_osm_extracts_store.py: way 10 sits
# inside the clip box, way 20 far outside it.
cat > "$WORK/extract.osm" <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6" generator="smoke-test-fixture">
  <node id="1" lat="38.5" lon="-9.2" version="1"/>
  <node id="2" lat="38.6" lon="-9.1" version="1"/>
  <node id="3" lat="20.0" lon="20.0" version="1"/>
  <node id="4" lat="20.1" lon="20.1" version="1"/>
  <way id="10" version="1">
    <nd ref="1"/>
    <nd ref="2"/>
    <tag k="natural" v="water"/>
  </way>
  <way id="20" version="1">
    <nd ref="3"/>
    <nd ref="4"/>
    <tag k="natural" v="water"/>
  </way>
</osm>
EOF

echo "== extract smoke test (engine flags)"
"$OSMIUM" extract \
  --strategy smart --option types=any \
  --bbox "-9.5000000,38.0000000,-8.5000000,39.0000000" \
  --no-progress --overwrite \
  --output "$WORK/clip.osm.pbf" \
  "$WORK/extract.osm"
"$OSMIUM" fileinfo -e "$WORK/clip.osm.pbf"
"$OSMIUM" cat -f osm "$WORK/clip.osm.pbf" > "$WORK/clip.osm"
grep -F '<way id="10"' "$WORK/clip.osm" > /dev/null || {
    echo "FAIL: in-box way 10 missing from the clip" >&2; exit 1; }
if grep -F '<way id="20"' "$WORK/clip.osm" > /dev/null; then
    echo "FAIL: out-of-box way 20 survived the clip" >&2; exit 1
fi

echo "OK: $OSMIUM"
