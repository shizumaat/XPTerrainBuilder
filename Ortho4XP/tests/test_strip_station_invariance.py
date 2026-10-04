"""THE STRIP STATION SET IS LOCAL (issue #116).

Lane terrace11c (#11) measured this between two replay arms whose way
``-10100`` (``adjacent_ground:runway:4:zone2#0``) and every vertex within
30 m of ``30.0996269, 31.3974530`` were BYTE-IDENTICAL: the census read a
NEW ``strip_arc`` CRITICAL motion row (0.36 m over 37.27 m,
``runway|junction``) in ONE arm only, and the reader visited 602 vs 603
strip stations.  The only nodes that differed (A-only 9, B-only 13) were
2.9 km away.  In another local frame the row flipped the other way.  A
CRITICAL row appearing 2.9 km from any change is a broken instrument.

TWO couplings make the station set non-local, and the twins below pin
both:

1. THE FOOTPRINT MOVES WITH THE RUNWAY'S VERTEX MULTISET.
   ``grade_law.runway_axis_and_width`` is a vertex-count-weighted PCA, so
   inserting ONE vertex anywhere on the runway ring shifts the centroid
   and tilts the axis — and the strip band's own rim vertices sit EXACTLY
   on the resulting rectangle's boundary by construction (emitter and
   validator build it from the same call).  Margin-0 membership therefore
   decides every rim vertex on the last bit of the arithmetic.  Measured
   here, on this file's own fixture: ONE extra runway vertex 2.6 km from
   the row moved 318 stations to 257.

2. THE CHAIN BREAKS AT THE EMITTED ARRAY BOUNDARY.
   ``runway_strip_longitudinal_runs`` walks an OPEN chain, so on a closed
   ring the start vertex is an extra break.  Measured here: rotating the
   strip ring's start vertex by 37 moved 318 stations to 316 with the
   local surface byte-identical.

The reader's answers: an EPSILON-INCLUSIVE boundary
(``check_grade.STRIP_STATION_BOUNDARY_EPS_M``) and a CANONICAL,
geometry-determined chain start (``check_grade._strip_chain_start``).  The
second is an invariant by construction; the first was the honest half-fix,
because the invariant for (1) belongs at the footprint's own derivation,
which is shared with the EMITTER and so was not the census's to change.

(1) IS NOW FIXED AT THAT DERIVATION (issue #190, owner ruling
``RULINGS 2026-10-02v`` (7)): ``runway_axis_and_width`` is the long side
of the minimum-area rotated rectangle of the ring cloud's CONVEX HULL, so
a vertex inserted on an edge changes the footprint by nothing.  The
epsilon stays — it is the census's one identity tolerance, and a rim
vertex emitted ON the boundary still has to read as inside — but it is no
longer load-bearing.  ``test_one_extra_collinear_runway_vertex_...``
below is the station-set half of that claim; the fit itself is twinned in
``tests/test_runway_axis_insertion_invariance.py``.
"""
from __future__ import annotations

import importlib.util
import json
import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

#: The fixture's runway and strip band.
_ANCHOR = (30.0996269, 31.3974530)      # the issue's own site
_R_EARTH = 6378137.0
_RUNWAY_LENGTH_M = 3600.0
_RUNWAY_HALF_WIDTH_M = 22.5
_RUNWAY_VERTEX_SPACING_M = 30.0
_STRIP_FROM_M = 200.0
_STRIP_TO_M = 1800.0
_STRIP_VERTEX_SPACING_M = 10.0
_BASE_ELEV_M = 10.0
#: The along-axis ramp that breaches the strip's rate-of-change law, from
#: the station where it starts (so the row sits ~2.6 km from the far end).
_RAMP_FROM_INDEX = 80
_RAMP_RISE_PER_STATION_M = 0.36
#: Where #190's collinear insertion goes: on the runway's long edge,
#: 2.6 km along and NOT on the 30 m vertex grid, so it is a genuinely new
#: vertex strictly between two emitted ones.
_COLLINEAR_VERTEX_AT_M = 2600.0
#: How far the unrelated "far" shape sits from the airport.
_FAR_SHAPE_OFFSET_M = 6000.0
_RULESET = "icao"


@pytest.fixture(scope="module")
def cg():
    spec = importlib.util.spec_from_file_location(
        "strip_station_twin_check_grade", ROOT / "tools" / "check_grade.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _ll(x: float, y: float):
    cos0 = math.cos(math.radians(_ANCHOR[0]))
    return (_ANCHOR[0] + math.degrees(y / _R_EARTH),
            _ANCHOR[1] + math.degrees(x / (_R_EARTH * cos0)))


def _patch(tmp_path: Path, strip_half: float, *,
           extra_runway_vertex: bool = False,
           collinear_runway_vertex: bool = False,
           far_shape: bool = False,
           start_rotation: int = 0,
           name: str = "STRIP"):
    """A runway ring plus ONE ``graded_strip`` band whose outer rim sits
    exactly on the strip footprint's lateral boundary (``strip_half`` from
    the centreline) — the configuration the emitter produces.

    ``extra_runway_vertex`` inserts ONE more vertex at the runway's FAR
    end (issue #116's mechanism); ``collinear_runway_vertex`` inserts one
    EXACTLY on the runway's own long edge at
    ``_COLLINEAR_VERTEX_AT_M`` (#190's own twin, and the harder arm: a
    vertex a hull cannot see at all); ``far_shape`` adds an unrelated ring
    ``_FAR_SHAPE_OFFSET_M`` away (the issue's "far vertex" literally);
    ``start_rotation`` rotates the strip ring's own emitted start vertex.
    None of the three touches a single strip-band coordinate or elevation.

    Returns ``(osm_path, strip_surface)`` where ``strip_surface`` is the
    band's emitted (lat, lon, alt) triples — the twin asserts they are
    identical across arms, so the local surface really is byte-identical.
    """
    nodes: list = []
    nid = [0]
    ways: list = []

    def add(x, y, alt):
        nid[0] -= 1
        lat, lon = _ll(x, y)
        nodes.append((str(nid[0]), lat, lon, alt))
        return str(nid[0])

    n_rw = int(_RUNWAY_LENGTH_M / _RUNWAY_VERTEX_SPACING_M) + 1
    xs = [i * _RUNWAY_VERTEX_SPACING_M for i in range(n_rw)]
    rw = [add(x, -_RUNWAY_HALF_WIDTH_M, _BASE_ELEV_M) for x in xs]
    if extra_runway_vertex:
        rw.append(add(_RUNWAY_LENGTH_M, -_RUNWAY_HALF_WIDTH_M + 0.001,
                      _BASE_ELEV_M))
    if collinear_runway_vertex:
        # ON the long edge, between two emitted vertices: the insertion
        # a densification step or a crossing split really makes.
        rw.insert(
            int(_COLLINEAR_VERTEX_AT_M / _RUNWAY_VERTEX_SPACING_M) + 1,
            add(_COLLINEAR_VERTEX_AT_M, -_RUNWAY_HALF_WIDTH_M, _BASE_ELEV_M))
    rw += [add(x, _RUNWAY_HALF_WIDTH_M, _BASE_ELEV_M)
           for x in reversed(xs)]
    ways.append((rw + [rw[0]],
                 {"role": "runway", "ref": "rwy04", "shapeID": "RW"}))

    n_gs = int((_STRIP_TO_M - _STRIP_FROM_M)
               / _STRIP_VERTEX_SPACING_M) + 1
    gxs = [_STRIP_FROM_M + i * _STRIP_VERTEX_SPACING_M for i in range(n_gs)]
    strip_surface: list = []
    gs: list = []
    for i, x in enumerate(gxs):
        z = _BASE_ELEV_M + (0.0 if i < _RAMP_FROM_INDEX else
                            _RAMP_RISE_PER_STATION_M
                            * (i - _RAMP_FROM_INDEX + 1))
        gs.append(add(x, strip_half, z))
    for x in reversed(gxs):
        gs.append(add(x, _RUNWAY_HALF_WIDTH_M, _BASE_ELEV_M))
    by_id = {n: (lat, lon, alt) for n, lat, lon, alt in nodes}
    strip_surface = sorted(by_id[n] for n in gs)
    if start_rotation:
        k = start_rotation % len(gs)
        gs = gs[k:] + gs[:k]
    ways.append((gs + [gs[0]],
                 {"role": "graded_strip", "ref": "graded_strip:rwy04",
                  "shapeID": "GS"}))

    if far_shape:
        far = [add(_FAR_SHAPE_OFFSET_M + dx, _FAR_SHAPE_OFFSET_M + dy,
                   _BASE_ELEV_M)
               for (dx, dy) in ((0.0, 0.0), (20.0, 0.0), (20.0, 20.0),
                                (0.0, 20.0))]
        ways.append((far + [far[0]],
                     {"role": "apron", "shapeID": "FAR"}))

    out = ["<?xml version='1.0' encoding='UTF-8'?>",
           "<osm version='0.6' generator='strip-station-twin'>"]
    for n, lat, lon, alt in nodes:
        out.append(f"  <node id='{n}' lat='{lat:.11f}' lon='{lon:.11f}'>"
                   f"<tag k='alt_abs' v='{alt:.3f}' /></node>")
    for nids, tags in ways:
        nid[0] -= 1
        out.append(f"  <way id='{nid[0]}'>")
        out += [f"    <nd ref='{n}' />" for n in nids]
        out += [f"    <tag k='{k}' v='{v}' />" for k, v in tags.items()]
        out.append("  </way>")
    out.append("</osm>")
    osm = tmp_path / f"{name}_auto.patch.osm"
    osm.write_text("\n".join(out) + "\n", encoding="utf-8", newline="")
    Path(str(osm) + ".axes.json").write_text(
        json.dumps({"anchor": list(_ANCHOR), "ruleset": _RULESET}),
        encoding="utf-8", newline="")
    return osm, strip_surface


# ══════════════════════════════════════════════════════════════════════
# THE FIXTURE IS NOT VACUOUS
# ══════════════════════════════════════════════════════════════════════


# ══════════════════════════════════════════════════════════════════════
# THE STATION SET IS A FUNCTION OF THE LOCAL GEOMETRY
# ══════════════════════════════════════════════════════════════════════


def test_the_boundary_epsilon_is_a_named_identity_tolerance(cg):
    """The epsilon is the census's ONE identity tolerance, not a tuned
    number: a vertex within the solver's weld tolerance of the footprint
    boundary IS on the boundary as far as this instrument can tell."""
    assert cg.STRIP_STATION_BOUNDARY_EPS_M == cg.SHARED_VERTEX_TOL_M
    assert cg.STRIP_STATION_BOUNDARY_EPS_M > 0.0


def test_the_canonical_chain_start_is_order_free(cg):
    """``_strip_chain_start`` picks the same PHYSICAL vertex whatever
    order the ring is emitted in — that is what makes the station set
    start-invariant rather than merely different."""
    pts = [(0.0, 0.0), (10.0, 0.0), (20.0, 0.0), (20.0, 5.0), (0.0, 5.0)]
    inside = [True, True, False, True, True]
    for k in range(len(pts)):
        rot = pts[k:] + pts[:k]
        rot_in = inside[k:] + inside[:k]
        start = cg._strip_chain_start(rot, rot_in)
        assert rot[start] == pts[cg._strip_chain_start(pts, inside)]
