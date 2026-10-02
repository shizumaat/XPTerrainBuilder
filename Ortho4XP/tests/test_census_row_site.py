"""THE ROW SITE TWINS — a census row prints WHERE IT IS (issues #106/#107).

The defect: ``_check_adjacent_ground_steps`` built its rows with correct
metre endpoints (``site_m``) and no ``lat``/``lon`` at all, so
``run_checks``'s fallback stamped each one with the CENTROID OF THE RING
it was found on.  Measured on ``nlwfroad100c_NLWF``: a 2.72 m
``adjacent_ground_step`` row printed ``-14.3115574, -178.0666656`` — the
layout origin's neighbourhood, no patch vertex within 6 m — while its
``site_m`` was ``[[645.34, 12.36], [645.33, 13.94]]`` and the true site
was ``-14.3113508, -178.0609526``, about 645 m east (spec
``docs/specs/road-exit-corridor-spec.md`` §3.4).

It is a CLASS defect, not one family's: every reader that works in the
census's metre frame and does not stamp its own site inherits the ring
centroid.  So the twin is over EVERY family ``run_checks`` emits, and the
fix is in the ONE row writer, not in the family.

THE SITE CONVENTION (``_rate_row_site``, owner RULINGS 2026-09-12aj (a);
``_check_within_shape`` R19-5): a row's printed site is the MIDPOINT of
its own two endpoints.  The midpoint of a pair spanning ``d`` metres is
therefore at most ``d/2`` from an endpoint, and every endpoint is a patch
vertex (or a vertex's projection onto an edge of the same patch).  That
is the generalisation of the issue's twin ("every census row's lat/lon
lands within 1 m of a patch vertex") to a convention that prints
midpoints — and it is what the ring centroid violates by 297 m below.
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

#: How far a printed site may sit from the row's OWN geometry (the
#: midpoint is at most half the row's span from an endpoint).  The issue's
#: own figure: a correct row lands within 1 m of a patch vertex.
ROW_SITE_LL_TOLERANCE_M = 1.0

#: NON-VACUITY FLOOR.  The twin passes trivially on a patch whose layout
#: origin (and hence whose ring centroid) happens to sit near the site, so
#: the fixture asserts the origin is at least this far from every vertex.
LAYOUT_ORIGIN_FAR_FLOOR_M = 100.0

#: The fixture's own geometry.
_ANCHOR = (-14.3113508, -178.0609526)    # NLWF-ish; any anchor works
_R_EARTH = 6378137.0
_RING_RADIUS_M = 300.0
_VERTEX_SPACING_M = 1.5
_BASE_ELEV_M = 100.0
_STEP_M = 2.72                           # the NLWF row's own step
_STEP_VERTEX = 7                         # which ring vertex carries it
_M_PER_DEG_LAT = 110540.0


@pytest.fixture(scope="module")
def cg():
    spec = importlib.util.spec_from_file_location(
        "row_site_twin_check_grade", ROOT / "tools" / "check_grade.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _cos0() -> float:
    return math.cos(math.radians(_ANCHOR[0]))


def _ll(x: float, y: float) -> "tuple[float, float]":
    return (_ANCHOR[0] + math.degrees(y / _R_EARTH),
            _ANCHOR[1] + math.degrees(x / (_R_EARTH * _cos0())))


def _ring_patch(tmp_path: Path, *, extra_far_vertex: bool = False,
                start_rotation: int = 0,
                name: str = "ROWSITE") -> "tuple[Path, list]":
    """A ring of ``adjacent_ground`` vertices on a circle of
    ``_RING_RADIUS_M`` CENTRED ON THE LAYOUT ORIGIN, with one vertex
    raised ``_STEP_M`` above its welded neighbours.

    The circle is the point: its CENTROID is the layout origin, which is
    ``_RING_RADIUS_M`` from every vertex — so a row stamped with the ring
    centroid is 300 m from its own site and the twin cannot pass
    vacuously.  Consecutive vertices are ``_VERTEX_SPACING_M`` apart, so
    the welded step the family reads spans 1.5 m.

    ``extra_far_vertex`` appends an unrelated 3-node ring several
    kilometres away (issue #116's "far vertex"); ``start_rotation``
    rotates the ring's own start vertex.  Returns ``(osm_path, vertices)``
    with ``vertices`` the (lat, lon) of every emitted node.
    """
    n_v = int(round(2.0 * math.pi * _RING_RADIUS_M / _VERTEX_SPACING_M))
    nodes: list = []
    nid = [0]
    ring: list = []
    for i in range(n_v):
        theta = 2.0 * math.pi * i / n_v
        x = _RING_RADIUS_M * math.cos(theta)
        y = _RING_RADIUS_M * math.sin(theta)
        nid[0] -= 1
        alt = _BASE_ELEV_M + (_STEP_M if i == _STEP_VERTEX else 0.0)
        lat, lon = _ll(x, y)
        nodes.append((str(nid[0]), lat, lon, alt))
        ring.append(str(nid[0]))
    if start_rotation:
        k = start_rotation % len(ring)
        ring = ring[k:] + ring[:k]
    ways = [(None, ring + [ring[0]],
             {"role": "adjacent_ground",
              "ref": "adjacent_ground:runway:4:zone2#0",
              "shapeID": "AG1"})]
    if extra_far_vertex:
        far: list = []
        for (dx, dy) in ((0.0, 0.0), (4.0, 0.0), (4.0, 4.0)):
            nid[0] -= 1
            lat, lon = _ll(4000.0 + dx, 4000.0 + dy)
            nodes.append((str(nid[0]), lat, lon, _BASE_ELEV_M))
            far.append(str(nid[0]))
        ways.append((None, far + [far[0]],
                     {"role": "adjacent_ground",
                      "ref": "adjacent_ground:runway:4:zone2#9",
                      "shapeID": "AGFAR"}))

    out = ["<?xml version='1.0' encoding='UTF-8'?>",
           "<osm version='0.6' generator='row-site-twin'>"]
    for n, lat, lon, alt in nodes:
        out.append(f"  <node id='{n}' lat='{lat:.11f}' lon='{lon:.11f}'>"
                   f"<tag k='alt_abs' v='{alt:.2f}' /></node>")
    for _wid, nids, tags in ways:
        nid[0] -= 1
        out.append(f"  <way id='{nid[0]}'>")
        out += [f"    <nd ref='{n}' />" for n in nids]
        out += [f"    <tag k='{k}' v='{v}' />" for k, v in tags.items()]
        out.append("  </way>")
    out.append("</osm>")
    osm = tmp_path / f"{name}_auto.patch.osm"
    osm.write_text("\n".join(out) + "\n", encoding="utf-8", newline="")
    Path(str(osm) + ".axes.json").write_text(
        json.dumps({"anchor": list(_ANCHOR), "ruleset": "icao"}),
        encoding="utf-8", newline="")
    return osm, [(lat, lon) for _n, lat, lon, _a in nodes]


def _ll_dist_m(a, b) -> float:
    return math.hypot((a[0] - b[0]) * _M_PER_DEG_LAT,
                      (a[1] - b[1]) * _M_PER_DEG_LAT * _cos0())


def _nearest_vertex_m(vertices, lat, lon) -> float:
    return min(_ll_dist_m((lat, lon), v) for v in vertices)


def _families(cg, osm) -> dict:
    fo: dict = {}
    cg.run_checks_law_true(osm, family_out=fo, quiet=True)
    return fo


# ══════════════════════════════════════════════════════════════════════
# THE FIXTURE IS NOT VACUOUS
# ══════════════════════════════════════════════════════════════════════

def test_the_fixture_fires_the_family_and_keeps_the_origin_far(cg, tmp_path):
    """The two halves that make the site twins mean something: the
    ``adjacent_ground_step`` family actually fires, and the layout origin
    — the point the buggy writer printed — is hundreds of metres from any
    vertex, so "the printed site is near a vertex" cannot be true by
    accident."""
    osm, vertices = _ring_patch(tmp_path)
    fo = _families(cg, osm)
    rows = fo[cg.ADJACENT_GROUND_STEP_FAMILY]
    assert len(rows) >= 1, (
        "the fixture must fire the family the issue reported; with no row "
        "the site twin passes vacuously")
    origin_gap = _nearest_vertex_m(vertices, *_ANCHOR)
    assert origin_gap > LAYOUT_ORIGIN_FAR_FLOOR_M, (
        f"the layout origin is {origin_gap:.1f} m from the nearest vertex, "
        f"inside the {LAYOUT_ORIGIN_FAR_FLOOR_M:.0f} m non-vacuity floor — "
        f"a ring-centroid site would pass this twin by coincidence")


# ══════════════════════════════════════════════════════════════════════
# EVERY ROW PRINTS ITS OWN SITE (issues #106 / #107)
# ══════════════════════════════════════════════════════════════════════

def test_every_census_row_prints_a_site_on_its_own_geometry(cg, tmp_path):
    """THE CLASS TWIN.  For every row of every family: the printed
    lat/lon lands within ``ROW_SITE_LL_TOLERANCE_M`` of a patch vertex,
    allowing for the MIDPOINT convention (half the row's own span).

    Before the fix the ``adjacent_ground_step`` rows failed this by
    ~297 m: their span is 1.5 m and they printed the ring centroid."""
    osm, vertices = _ring_patch(tmp_path)
    fo = _families(cg, osm)
    checked = 0
    for family, rows in fo.items():
        if family.startswith("_"):
            continue
        for row in rows:
            lat, lon = getattr(row, "lat", None), getattr(row, "lon", None)
            assert lat is not None and lon is not None, (
                f"{family}: a row printed no site at all")
            a, b = cg.row_points(row)
            span = (0.0 if a is None or b is None
                    else math.hypot(float(b[0]) - float(a[0]),
                                    float(b[1]) - float(a[1])))
            budget = 0.5 * span + ROW_SITE_LL_TOLERANCE_M
            gap = _nearest_vertex_m(vertices, lat, lon)
            assert gap <= budget, (
                f"{family}: printed site is {gap:.2f} m from the nearest "
                f"patch vertex but the row spans only {span:.2f} m "
                f"(budget {budget:.2f} m) — the site printer is not "
                f"carrying this row's own site_m")
            checked += 1
    assert checked >= 1, "no row was checked; the fixture priced nothing"


def test_the_adjacent_ground_step_row_lands_on_its_welded_pair(cg,
                                                               tmp_path):
    """The issue's twin, literally, on the family it was filed against: an
    ``adjacent_ground_step`` row is a WELDED pair 1.5 m apart, so its
    printed site must land within ``ROW_SITE_LL_TOLERANCE_M`` of a patch
    vertex with no midpoint allowance at all."""
    osm, vertices = _ring_patch(tmp_path)
    fo = _families(cg, osm)
    rows = fo[cg.ADJACENT_GROUND_STEP_FAMILY]
    assert rows
    for row in rows:
        gap = _nearest_vertex_m(vertices, row.lat, row.lon)
        assert gap <= ROW_SITE_LL_TOLERANCE_M, (
            f"an adjacent_ground_step row printed a site {gap:.1f} m from "
            f"the nearest patch vertex (site_m {row.pt_a} / {row.pt_b}) — "
            f"issues #106/#107")
        # ...and it is the pair the family measured, not some other pair.
        assert abs(row.de_m - _STEP_M) < 0.01
