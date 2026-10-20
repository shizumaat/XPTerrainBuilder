"""ONE READER FRAME FOR EVERY CENSUS FAMILY: THE ENGINE'S METRIC (#772).

The engine states its bounds in its own transverse-Mercator frame on the
ellipsoid (``auto_patch_v2.verify.frame.metric_frame``).  The census
frame is a spherical equirectangular, 0.1-0.7 % off it, so a row the
engine held EXACTLY at a bound priced by plan distance read as a breach.
Lane rwyzone15c moved the runway-end profile alone (RULINGS 2026-10-15h);
``run_checks`` now reads every family in the metric and maps every row's
points back to the census frame, so joins and ``site_m`` do not move.

The scene: a laterally flat service road running EAST-WEST at 60.7 N,
where the sphere reads E-W distance about 0.25 % short of the ellipsoid.
Its rise along the axis is the road's chord cap times the ENGINE's
length.  Hand answers:

* held exactly at the bound: no ``within_shape`` row;
* the same road read in the old frame would be over its budget by more
  than the emit noise (the defect's size, asserted, so the twin cannot
  pass vacuously);
* a road 2 % over the bound still reads, and its row's points are the
  census-frame projections of its nodes.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pytest
from shapely.geometry import Point, Polygon

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))

cg = pytest.importorskip("check_grade")
from auto_patch_v2.verify.frame import metric_frame  # noqa: E402

ANCHOR = (60.7, -135.1)     # never an integer degree (seam-anchored)
LENGTH_M, WIDTH_M = 300.0, 6.0


def _road(tmp_path: Path, rise_m: float) -> tuple[Path, dict]:
    """A service-road ring laid out in the ENGINE's metric; returns the
    patch and its nodes' lat/lon by id."""
    _fwd, to_ll = metric_frame(*ANCHOR)
    corners = [(0.0, 0.0, 10.0), (LENGTH_M, 0.0, 10.0 + rise_m),
               (LENGTH_M, WIDTH_M, 10.0 + rise_m), (0.0, WIDTH_M, 10.0)]
    out = ["<?xml version='1.0' encoding='UTF-8'?>",
           "<osm version='0.6' generator='metric-twin'>"]
    ll = {}
    for k, (x, y, z) in enumerate(corners):
        nid = str(-1 - k)
        lat, lon = to_ll(x - LENGTH_M / 2, y)
        ll[nid] = (float(f"{lat:.11f}"), float(f"{lon:.11f}"))
        out.append(f"  <node id='{nid}' lat='{lat:.11f}' lon='{lon:.11f}'>"
                   f"<tag k='alt_abs' v='{z:.2f}' /></node>")
    out.append("  <way id='-10'>")
    out += [f"    <nd ref='{n}' />" for n in ("-1", "-2", "-3", "-4", "-1")]
    out += ["    <tag k='role' v='service_road' />",
            "    <tag k='shapeID' v='R1' />", "  </way>", "</osm>"]
    osm = tmp_path / "METRIC_auto.patch.osm"
    osm.write_text("\n".join(out) + "\n", encoding="utf-8", newline="")
    Path(str(osm) + ".axes.json").write_text(json.dumps(
        {"anchor": list(ANCHOR), "ruleset": "icao"}), encoding="utf-8",
        newline="")
    return osm, ll


def _engine_length(ll) -> float:
    fwd, _ = metric_frame(*ANCHOR)
    return math.dist(fwd(*ll["-1"]), fwd(*ll["-2"]))


def _within(osm) -> list:
    fam: dict = {}
    cg.run_checks(osm, top_n=0, quiet=True, family_out=fam)
    return fam["within_shape"]


def test_a_row_held_exactly_at_its_bound_reads_zero(tmp_path):
    cap = cg.SERVICE_ROAD_MAX_GRADE
    # one emit quantum (0.01 m) under the bound: the nodes' 11-dp lat/lon
    # put the engine length a hair under 300 m
    rise = round(cap * LENGTH_M - 0.01, 2)
    osm, ll = _road(tmp_path, rise)
    d_engine = _engine_length(ll)
    census = cg._ll_to_m_factory({}, anchor=ANCHOR)
    d_census = math.dist(census(*ll["-1"]), census(*ll["-2"]))
    # the defect's size: the old frame priced this pair over its budget
    # by more than any emit-noise allowance (0.01 m)
    assert rise <= cap * d_engine + 1e-9
    assert rise - cap * d_census > 0.02
    assert _within(osm) == []


def test_an_over_cap_row_still_reads_with_census_frame_points(tmp_path):
    cap = cg.SERVICE_ROAD_MAX_GRADE
    osm, ll = _road(tmp_path, round(cap * 1.02 * LENGTH_M, 2))
    rows = _within(osm)
    assert rows, "a road 2 % over its chord cap read nothing"
    # the frames differ by ~0.4 m across this road: a point on the
    # census-frame ring (1 mm) is in the census frame.  A bare
    # ``run_checks`` centres it on the nodes' mean (no sidecar anchor).
    census = cg._ll_to_m_factory(ll)
    ring = Polygon([census(*ll[n]) for n in ("-1", "-2", "-3", "-4")])
    for r in rows:
        for pt in (r.pt_a, r.pt_b):
            assert ring.exterior.distance(Point(pt)) < 1e-3 or \
                ring.contains(Point(pt)), "a row's point left the census frame"
            assert r.lat is not None


def test_the_engine_metric_is_not_wrapped_twice():
    census = cg._ll_to_m_factory({}, anchor=ANCHOR)
    to_m, _back = cg._engine_metric(census)
    again, back2 = cg._engine_metric(to_m)
    assert again is to_m and back2((1.0, 2.0)) == (1.0, 2.0)
    # the frame's origin maps to the origin: the site-less families
    _m, to_census = cg._engine_metric(census)
    assert to_census((0.0, 0.0)) == (0.0, 0.0)
