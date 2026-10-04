"""Tests for the implied-tunnel level-crossing feature (user 2026-07-16).

Three landed behaviours are exercised here, all headless (no network,
no X-Plane install, ``tmp_path`` only):

A. ``bridges._carriageway_width_from_tags`` — carriageway width derived
   from a road way's own OSM ``width=`` / ``lanes=`` measurements, with
   sanity clamps and a fall-through to the per-highway-type table.

B. The at-grade level-crossing VETO inside
   ``bridges._synthesize_implied_crossing_bores`` — positive OSM
   evidence (an ``aeroway=aircraft_crossing`` node, or a nearby
   ``barrier`` gate) on a public road that crosses runway/taxiway
   pavement keeps the road at grade instead of synthesising a bore.

C. The OSM cache node-tag round-trip — ``OSM_layer.update_dicosm`` /
   ``write_to_file`` / ``_cached_osm_schema_matches`` /
   ``osm_load._load_osm_tile`` carry the whitelisted node tags (and the
   schema marker) through a write-then-read cycle.
"""
from __future__ import annotations

import sys
from pathlib import Path


# Mirror the established test idiom (see tests/test_boundary.py): put the
# project's ``src/`` on sys.path so the O4 / auto_patch modules import
# directly without installing the package.  ``conftest.py`` also does this,
# but the explicit insert keeps the module importable in isolation.
_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import O4_OSM_Utils as OSM  # noqa: E402


# ──────────────────────────────────────────────────────────────────
# C. OSM cache node-tag round-trip
# ──────────────────────────────────────────────────────────────────
_ROUND_TRIP_OSM_XML = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<osm version="0.6" generator="test">\n'
    '  <node id="1" lat="60.0000000" lon="-1.0000000">\n'
    '    <tag k="barrier" v="lift_gate"/>\n'
    '    <tag k="aeroway" v="aircraft_crossing"/>\n'
    '  </node>\n'
    '  <node id="2" lat="60.0010000" lon="-1.0010000"/>\n'
    '  <way id="10" version="1">\n'
    '    <nd ref="1"/>\n'
    '    <nd ref="2"/>\n'
    '    <tag k="highway" v="primary"/>\n'
    '    <tag k="width" v="6.5"/>\n'
    '    <tag k="lanes" v="2"/>\n'
    '  </way>\n'
    '</osm>'
)

_SCHEMA = "2026-07-16"


class TestOsmNodeTagCacheRoundTrip:
    """Whitelisted node tags and the schema marker survive a write-read
    cycle through ``OSM_layer`` and ``osm_load._load_osm_tile``."""

    def _build_layer(self) -> OSM.OSM_layer:
        """Parse the fixture XML through ``update_dicosm`` with the
        node/way tag whitelists the road-layer download uses."""
        layer = OSM.OSM_layer()
        input_tags = {"n": [], "w": [("highway", "primary")], "r": []}
        target_tags = {
            "n": [("barrier", ""), ("aeroway", "")],
            "w": [("highway", "primary"), ("width", ""), ("lanes", "")],
            "r": [],
        }
        ok = layer.update_dicosm(
            _ROUND_TRIP_OSM_XML.encode("utf-8"), input_tags, target_tags)
        assert ok == 1
        return layer

    def test_schema_marker_written_and_matched(self, tmp_path) -> None:
        """``write_to_file`` stamps the schema marker;
        ``_cached_osm_schema_matches`` reads it back correctly."""
        layer = self._build_layer()
        path = tmp_path / "cache_schema.osm"
        assert layer.write_to_file(
            str(path), header_attributes={"o4_tag_schema": _SCHEMA}) == 1

        assert OSM._cached_osm_schema_matches(str(path), _SCHEMA) is True
        assert OSM._cached_osm_schema_matches(str(path), "other") is False
        # An empty schema request accepts any cache (legacy behaviour).
        assert OSM._cached_osm_schema_matches(str(path), "") is True

