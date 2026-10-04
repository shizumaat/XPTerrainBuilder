"""APRON SPINE STATIONS — twins for §1 and §3 of
docs/specs/heca-apron-round3-spec.md (owner sim read of 1.0.260,
RULINGS 2026-08-26b items 3/4/5).

THE DEFECT.  The owner's 84.2 m line T at HECA carried ZERO interior
emitted stations (vertices only at arc 0.00/84.22).  The taxi ROUTE was
never cut — the sidecar axes chain straight across the apron at cap
1.5 % — what was cut is the ANCHORED SURFACE, so the junction pieces the
centerline profile does anchor stood 0.7-1.2 m PROUD of the membrane
beside them, and the same membrane, coupled only to its own ring, sagged
to 70.11 at the owner's dip site.  Proud ridge and bowl are the two
sides of ONE missing coupling.

These twins pin the legs:
  * the AXIS POPULATION is ``grade_graph.centerline_specs`` — the same
    enumeration the sidecar's ``axes_exact`` publishes, never a second
    notion — and SERVICE axes are excluded;
  * the SPACING is the standing ``layout.PAVEMENT_NODE_MAX_CHORD_M``,
    reused, and a crossing at or under it gets no station;
  * a station is a CENTERLINE node: it is registered in ``G.pos`` BEFORE
    the global-spine walk, which is what makes phase A value it from the
    axis's own profile;
  * the LAW is the apron's own — station↔ring and station↔lattice pairs
    priced through ``_grade_graph_edges``/``classify_pair``, never a
    private cap, and NEVER station↔station (that pair is the spine's);
  * §3: a lattice point within 1.5x ``APRON_LATTICE_SPACING_M`` of a
    station is joined to it — one membrane, one law;
  * the FLAG defaults ON and OFF is vacuous everywhere.

No network, no DEM, no X-Plane install.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

from shapely.geometry import Polygon

_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(_ROOT / "src"), str(_ROOT), str(_ROOT / "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)


ANCHOR = (30.12, 31.40)


class _Shape:
    def __init__(self, polygon, role="apron"):
        self.polygon = polygon
        self.role = role
        self.ref = ""
        self.fan_ramp_zone = False
        self.lateral_cap = None
        # the altitude model ``conformance._vertex_alts`` reads (the §A
        # weld goes through that one implementation)
        self.node_altitudes = None
        self.altitude = None
        self.altitude_high = None
        self.altitude_low = None


class _CPS:
    """The canonical registry's contract, at its own 0.5 m tolerance."""

    def __init__(self):
        self._k = {}

    def get_or_add(self, x, y):
        k = (int(round(x / 0.5)), int(round(y / 0.5)))
        self._k.setdefault(k, k)
        return k


class _Layout:
    def __init__(self, shapes):
        self.shapes = list(shapes)
        self.anchor = ANCHOR
        self.canonical_points = _CPS()

    def m_to_ll(self, x, y):
        return (ANCHOR[0] + y / 111_320.0, ANCHOR[1] + x / 96_000.0)


def _square(side):
    h = side / 2.0
    return Polygon([(-h, -h), (h, -h), (h, h), (-h, h), (-h, -h)])


# ═════════════════════════════════════════════════════════════════════
# SPACING — the standing pavement-node rule, reused
# ═════════════════════════════════════════════════════════════════════


# ═════════════════════════════════════════════════════════════════════
# THE AXIS POPULATION — one enumeration, aircraft only
# ═════════════════════════════════════════════════════════════════════


# ═════════════════════════════════════════════════════════════════════
# A STATION IS A CENTERLINE NODE (§1.2)
# ═════════════════════════════════════════════════════════════════════

class _G:
    """The one graph, reduced to what the interpolation reads."""

    def __init__(self):
        self.pos = {}
        self.node_stage = {}
        self.centerline_chains = {}


class _CL:
    """``grade_graph._project``'s contract: ``.pts`` + ``.arc()``."""

    def __init__(self, pts):
        self.pts = [(float(x), float(y)) for (x, y) in pts]

    def arc(self):
        out = [0.0]
        for a, b in zip(self.pts, self.pts[1:]):
            out.append(out[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
        return out


# ═════════════════════════════════════════════════════════════════════
# THE LAW IS THE APRON'S OWN (§1.3) AND THE LATTICE JOINS IT (§3.1)
# ═════════════════════════════════════════════════════════════════════


# ═════════════════════════════════════════════════════════════════════
# THE FLAG
# ═════════════════════════════════════════════════════════════════════


# ═════════════════════════════════════════════════════════════════════
# EMISSION + CENSUS
# ═════════════════════════════════════════════════════════════════════

def _parse_with_features(path):
    import check_grade as CG
    feats: dict = {}
    nodes, ways = CG._parse_osm(Path(path), feature_out=feats)
    return nodes, ways, feats


def test_the_station_class_is_registered_and_not_a_host_cap_class():
    """Without the registration the emitted polylines are dropped by the
    ring filter and every station edge becomes a LOST MEASUREMENT."""
    import check_grade as CG
    assert "apron_spine_station" in CG.ROLE_LESS_FEATURE_CLASSES
    assert "apron_spine_station" not in CG.HOST_CAP_FEATURE_CLASSES


def test_the_membrane_family_joins_station_ways_too(tmp_path):
    """The sidecar's ``apron_lattice_edges`` now carries station pairs;
    a lattice-only join population would report every one of them
    unmatched — a LOST measurement reported as a pass."""
    import check_grade as CG
    lat0, lon0 = ANCHOR
    dlon = 50.0 / (111320.0 * math.cos(math.radians(lat0)))
    txt = ["<?xml version='1.0' encoding='UTF-8'?>\n<osm version='0.6'>\n"]
    for i, (dl, alt) in enumerate(((0.0, 74.00), (dlon, 74.20),
                                   (2 * dlon, 74.40))):
        txt.append(f"  <node id='-{i + 1}' lat='{lat0:.9f}' "
                   f"lon='{lon0 + dl:.9f}'>\n"
                   f"    <tag k='alt_abs' v='{alt}'/>\n  </node>\n")
    txt.append("  <way id='-900'>\n    <nd ref='-1'/>\n    <nd ref='-2'/>\n"
               "    <nd ref='-3'/>\n"
               "    <tag k='o4_feature' v='apron_spine_station'/>\n"
               "  </way>\n</osm>\n")
    p = tmp_path / "st.osm"
    p.write_text("".join(txt), encoding="utf-8", newline="")
    edges = [{"a": [lat0, lon0], "b": [lat0, lon0 + dlon],
              "budget_m": 0.10, "shapeID": 3,
              "provenance": "apron_spine_station"}]
    (tmp_path / "st.osm.axes.json").write_text(json.dumps(
        {"anchor": list(ANCHOR), "ruleset": "icao",
         "apron_lattice_edges": edges}), encoding="utf-8", newline="")
    nodes, ways, feats = _parse_with_features(p)
    to_m = CG._ll_to_m_factory(nodes, ANCHOR)
    join = (list(feats.get("apron_lattice", []))
            + list(feats.get("apron_spine_station", [])))
    rows, n_checked, n_unmatched = CG._check_apron_lattice_membrane(
        edges, join, ways, nodes, to_m)
    assert (n_checked, n_unmatched) == (1, 0)
    assert len(rows) == 1 and abs(rows[0].de_m - 0.20) < 1e-6
    # and the lattice-only population would have LOST it
    _r2, _c2, u2 = CG._check_apron_lattice_membrane(
        edges, list(feats.get("apron_lattice", [])), [], nodes, to_m)
    assert u2 == 1


# ═════════════════════════════════════════════════════════════════════
# THE §2 DISCIPLINE APPLIED TO THE SPINE'S OWN RUN
# ═════════════════════════════════════════════════════════════════════


# ═════════════════════════════════════════════════════════════════════
# AMENDMENT 1 RULING 1 — A STATION IS A CONSTANT IN THE MEMBRANE SOLVE
#
# The station's value is PHASE-A OUTPUT (the route profile's own solve,
# where it is a legitimate collinear interior chain point — not a
# mid-taxiway external pin).  In the membrane/POCS solve it must not be
# a free variable: a station-touching law edge is then satisfiable ONLY
# by moving the ring/lattice side.  Measured on the arm that did not do
# this: the projection lowered the ANCHORED side instead — line-T ring
# 74.02 → 73.43, dip-site junctions down 0.22 m, lattice unmoved.
# ═════════════════════════════════════════════════════════════════════


# ═════════════════════════════════════════════════════════════════════
# §A — STATIONS WELD INTO THE MEMBRANE, STAND DOWN ON SENIORS
# (docs/specs/lemd-rim-and-stations-spec.md §A; owner RULINGS 2026-08-28
# item 1 at LEMD 40.4968469,-3.5645062 and RULINGS 2026-08-28b item 4 at
# HECA 30.109477,31.4036224)
#
# THE DEFECT.  ``_free`` guards candidates against plan VERTICES only —
# a 0.5 m STRtree, no EDGE test — and an aircraft axis is routinely
# COLLINEAR with the apron slice boundaries it crosses.  Measured at
# 1.0.263: 144 station nodes across LEMD (76) / HECA (29) / SPJC (33) /
# CYXY (6) sat ON a ring edge as unwelded T-vertices, EVERY one on a
# boundary shared by two rings, worst value tear 0.907 m.  Two
# near-collinear constrained segments ~2 cm apart are also the
# documented mm-jitter segment-recovery killer, so a value-only patch
# cannot fix the tear: the GEOMETRY has to become one.
# ═════════════════════════════════════════════════════════════════════

def _band(y0, y1, x0=-200.0, x1=200.0, role="apron"):
    """A rectangle whose y0 edge can HOST a station: two shapes sharing
    one long boundary is the measured population (every one of the 144
    was on a two-host shared boundary)."""
    return _Shape(Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1),
                           (x0, y0)]), role=role)


def test_the_flag_is_default_ON():
    from auto_patch import config as CFG
    assert CFG.STATION_EDGE_WELD is True


# ═════════════════════════════════════════════════════════════════════
# §A THROUGH ``to_osm`` — ONE NODE, AND THE STATION VALUE WINS
#
# The presolve weld puts the station INTO the host ring; two more things
# had to be true before the emitted patch showed it, and both were
# measured false at CYXY on the first arm:
#
#   * BOTH DECIMATORS must exempt it (``emit_decimate.decimate_emit_
#     nodes`` and ``to_osm``'s own sweep).  A welded station is
#     3D-redundant against its host edge by construction and each vote
#     is taken over SHAPES, while the thing that needs the vertex is an
#     emitted FEATURE way — the crown-spine ``_crown_spine_weld_xy``
#     class exactly (SPLP -13/-77).  Arm 1: the insert landed, both
#     decimators dropped it, the sweep still read 6 of 6 unwelded.
#   * ``to_osm`` must REUSE the ring's interned node.  Arm 2: the vertex
#     survived and the emitter minted a fresh nid anyway — a COORDINATE
#     TWIN, ring 695.02 against station 695.73, a 0.71 m tear at zero
#     horizontal distance.
#
# The value ruling is the OPPOSITE of the crown spine's: there the ring
# is the authority; here round-3 Amendment 1 makes station values
# phase-A constants and the membrane the side that yields.
# ═════════════════════════════════════════════════════════════════════

_ST_RING_V, _ST_STATION_V = 92.0, 99.0


def _emit_and_parse(layout):
    import re
    import tempfile
    with tempfile.NamedTemporaryFile(
            mode="r", suffix=".osm", delete=False) as f:
        path = f.name
    try:
        layout.to_osm(path)
        text = Path(path).read_text(encoding="utf-8")
    finally:
        for p in (Path(path), Path(path + ".axes.json")):
            if p.exists():
                p.unlink()
    nodes = {int(m.group(1)): (float(m.group(2)), float(m.group(3)))
             for m in re.finditer(
                 r"""<node id='(-?\d+)'[^>]*lat='([^']+)' lon='([^']+)'""",
                 text)}
    node_alts = {int(m.group(1)): float(m.group(2))
                 for m in re.finditer(
                     r"""<node id='(-?\d+)'[^>]*?>\s*"""
                     r"""<tag k='alt_abs' v='([^']+)'""", text, re.DOTALL)}
    ways = []
    for m in re.finditer(r"<way id='(-?\d+)'[^>]*>(.*?)</way>",
                         text, re.DOTALL):
        body = m.group(2)
        ways.append((int(m.group(1)),
                     [int(x) for x in re.findall(r"""<nd ref='(-?\d+)'""",
                                                 body)],
                     dict(re.findall(r"""<tag k='([^']+)' v='([^']+)'""",
                                     body))))
    return nodes, ways, node_alts


# ═════════════════════════════════════════════════════════════════════
# AMENDMENT 1 §1 — A PAD RING IS A STAND-DOWN HOST FOR EVERY WELD
#
# A building pad is ONE FLAT VALUE by definition (the pads-as-band-
# variables §1.1 invariant), and the ruling enforces that at the
# GEOMETRY layer: no weld inserts a foreign-valued node into a pad ring.
# Measured at LEMD: the §B rim/pan rings ran along `building8`'s ring and
# the nid-level final weld took it from 19 nodes at 600.50 to 71 nodes at
# three values (600.50 / 596.30 / 587.75) — a 12.75 m step inside a pad
# and 1,421 `building|building` census rows.
#
# Rim/pan geometry may still ABUT the pad ring: §B ownership is
# unchanged, and only the node INSERTION stands down.
# ═════════════════════════════════════════════════════════════════════


# ── the GENERIC final weld (to_osm's nid-level splice) ───────────────


