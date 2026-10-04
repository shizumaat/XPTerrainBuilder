"""Unit tests for auto_patch.layout — data model + OSM emission.

Covers:
* PavementLayout.m_to_ll / ll_to_m round-trip.
* _projection / _airport_anchor helpers.
* PavementLayout.to_osm: shape emission, shared-vertex IDs, tag
  handling per role and per elevation form.
"""
import math
import re
import tempfile
from pathlib import Path

from shapely.geometry import Polygon

from auto_patch.build_support import _airport_anchor, _projection


def _square(cx=0.0, cy=0.0, side=10.0):
    """Axis-aligned square in meter space."""
    h = side / 2.0
    return Polygon([
        (cx - h, cy - h),
        (cx + h, cy - h),
        (cx + h, cy + h),
        (cx - h, cy + h),
    ])


def _emit_and_parse(layout):
    """Call to_osm then parse the resulting XML.

    Returns (nodes, ways, node_alts) where:
      nodes:     {nid: (lat, lon)}
      ways:      [(wid, [nid_refs], {tag: val})]
      node_alts: {nid: alt_abs}  — per-node ``alt_abs`` tags (the
                 backward-compatible per-vertex altitude form)
    """
    with tempfile.NamedTemporaryFile(
            mode="r", suffix=".osm", delete=False) as f:
        path = f.name
    try:
        layout.to_osm(path)
        text = Path(path).read_text(encoding="utf-8")
    finally:
        Path(path).unlink()

    # Match the OPENING <node ...> tag for BOTH the self-closing form
    # (`... />`) and the form that carries a per-node <tag> child
    # (`...>`).  lat/lon always live in the opening tag.
    node_re = re.compile(
        r"""<node id='(-?\d+)'[^>]*lat='([^']+)' lon='([^']+)'""")
    node_alt_re = re.compile(
        r"""<node id='(-?\d+)'[^>]*?>\s*<tag k='alt_abs' v='([^']+)'""",
        re.DOTALL)
    way_open_re = re.compile(r"""<way id='(-?\d+)'""")
    nd_re = re.compile(r"""<nd ref='(-?\d+)'""")
    tag_re = re.compile(r"""<tag k='([^']+)' v='([^']+)'""")

    nodes = {}
    for m in node_re.finditer(text):
        nodes[int(m.group(1))] = (float(m.group(2)), float(m.group(3)))

    node_alts = {}
    for m in node_alt_re.finditer(text):
        node_alts[int(m.group(1))] = float(m.group(2))

    ways = []
    way_blocks = re.findall(
        r"<way id='-?\d+'[^>]*>(.*?)</way>", text, flags=re.DOTALL)
    for i, m_open in enumerate(way_open_re.finditer(text)):
        wid = int(m_open.group(1))
        body = way_blocks[i]
        nds = [int(x) for x in nd_re.findall(body)]
        tags = {k: v for k, v in tag_re.findall(body)}
        ways.append((wid, nds, tags))

    return nodes, ways, node_alts


# ──────────────────────────────────────────────────────────────────────
# _projection helper
# ──────────────────────────────────────────────────────────────────────
def test_projection_returns_callable_to_m():
    """_projection(anchor) returns a (lon, lat[, z]) → (x, y[, z])
    function whose origin is the anchor."""
    to_m = _projection((40.0, -100.0))
    assert callable(to_m)
    x, y = to_m(-100.0, 40.0)
    assert abs(x) < 1e-9
    assert abs(y) < 1e-9


def test_projection_with_z_passes_through():
    """The optional z argument is preserved in the output tuple."""
    to_m = _projection((40.0, -100.0))
    x, y, z = to_m(-100.0, 40.0, 123.4)
    assert z == 123.4


# ──────────────────────────────────────────────────────────────────────
# _airport_anchor
# ──────────────────────────────────────────────────────────────────────
class _StubRunway:
    def __init__(self, lat_a, lon_a, lat_b, lon_b):
        self.lat_a, self.lon_a = lat_a, lon_a
        self.lat_b, self.lon_b = lat_b, lon_b


class _StubAirport:
    def __init__(self, runways=(), boundary=None):
        self.runways = list(runways)
        self.boundary = boundary


def test_airport_anchor_uses_first_runway_midpoint():
    """When runways are present, anchor = midpoint of first runway."""
    apt = _StubAirport(runways=[
        _StubRunway(40.0, -100.0, 40.02, -100.0),
    ])
    lat, lon = _airport_anchor(apt)
    assert abs(lat - 40.01) < 1e-9
    assert abs(lon - (-100.0)) < 1e-9


def test_airport_anchor_falls_back_to_boundary_centroid():
    """No runways → use boundary centroid (note shapely centroid is
    .y=lat, .x=lon)."""
    boundary = Polygon([
        (-100.0, 40.0),
        (-99.99, 40.0),
        (-99.99, 40.02),
        (-100.0, 40.02),
    ])
    apt = _StubAirport(boundary=boundary)
    lat, lon = _airport_anchor(apt)
    assert abs(lat - 40.01) < 1e-9
    assert abs(lon - (-99.995)) < 1e-9


def test_airport_anchor_default_zero():
    """No runways AND no boundary → (0, 0)."""
    apt = _StubAirport()
    assert _airport_anchor(apt) == (0.0, 0.0)


# ── THE AXES SIDECAR IS THE LAW CONTRACT ─────────────────────────────
# ``<patch>.axes.json`` is what makes a standalone census law-true: the
# exact centrelines, caps, anchor, seam pins, pair caps, terrace joints
# and RULESET the build actually ran under.  Without it every reader
# silently falls back to the CONTEXT-FREE check, which over-flags by
# multiples (measured 2026-08-05: SPJC 4,010 rows against a law-true
# 810; HEAZ 959 vs 144; HECA 12,932 vs 8,099) and says nothing.
#
# Two guards used to make that silence possible and both are gone:
# a ``config.LOG_VERBOSITY > 0`` gate, and a bare
# ``except Exception: pass`` around the whole write.


