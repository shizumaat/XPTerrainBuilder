"""Owner RULINGS 2026-10-20c (39), #951 / #949 / #1060: "Roads through outer
band follow their own ground, yes. Band stops at road edge determined by
lanes or drawn edge, whichever is larger."

A mapped carriageway through a band's zone 2 is CUT out of zone 2 by its
half-width plus the groundside stand-off (``planar/zones``,
``planar/road_yield``); its ribbon vertices are the band's kerb, held under
the band's ceiling only (``constraints/zones``); the band beside it reads
the DEM past the road's cut (``planar/road_shadow``); the step across the
stand-off is a declared wall (``pipeline/band_road_wall``).

Synthetic: the #715 twin's runway 09/27 along y = 0 (edge y = -15, lip to
y = -18) and a tertiary road along y = -30 (kerbs -26 / -34) inside its
zone 2."""
from __future__ import annotations

import dataclasses as _dc

import pytest
from auto_patch_v2.law import Law
from auto_patch_v2.law.tables import snap_margin_m
from shapely.geometry import LineString
from test_roadmint100 import _way, _with
from test_roadterrace100 import _solve
from test_wall_step715 import ROAD, _road, _StepDem


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("SYNT")


def _cut(law) -> float:
    return float(law.tables.zones.adjacent_ground.groundside_cutback_m) + snap_margin_m(law)


class _HighDem(_StepDem):
    """100 m north of y = -21, 104 m south of it: the road's ground ABOVE
    the band."""

    def z(self, x: float, y: float) -> float:
        return 100.0 if y > -21.0 else 104.0


class _PostedDem(_StepDem):
    """The step DEM with a 2 m posting (the shadow's one cell)."""

    def posting_m(self) -> float:
        return 2.0


@pytest.fixture(scope="module")
def cut_arm(law):
    a = _dc.replace(_with(_way(-3, ROAD, highway="tertiary")), dem=_StepDem())
    return _solve(a, law)


@pytest.fixture(scope="module")
def high_airport():
    return _dc.replace(_with(_way(-3, ROAD, highway="tertiary")), dem=_HighDem())


@pytest.fixture(scope="module")
def high_arm(law, high_airport):
    return _solve(high_airport, law)


def _band_faces(pm):
    from auto_patch_v2.model.road_yield import is_band_zone_ref
    return [f for f in pm.faces.values()
            if f.role == "graded_strip" and is_band_zone_ref(f.ref)]


def _band_vertices(pm):
    return {v for f in _band_faces(pm) for c in (f.ring, *f.holes)
            for v in pm.ring_vertices(c)}


def test_the_snap_never_closes_the_declared_line(law):
    """The declared line runs half a stand-off off the road: the identity
    snap (``snap_margin_m``) must not carry a vertex across it."""
    assert snap_margin_m(law) < 0.5 * _cut(law)


def test_zone_two_stands_off_the_road_and_zone_one_is_untouched(cut_arm, law):
    pm, _sol, _rep = cut_arm
    road = _road(pm)
    band = _band_vertices(pm)
    assert road and not road & band, "the band still shares a vertex with the road"
    kerb_y = (-26.0, -34.0)
    near = [pm.vertices[v].xy for v in band if 620.0 <= pm.vertices[v].xy[0] <= 880.0
            and -40.0 < pm.vertices[v].xy[1] < -20.0]
    assert near
    # every band vertex beside the road stands the stand-off (less the snap)
    # or more off the kerb
    assert min(min(abs(y - k) for k in kerb_y) for _x, y in near
               if not -34.0 < y < -26.0) >= _cut(law) - snap_margin_m(law) - 1e-6
    assert all(not -34.0 < y < -26.0 for _x, y in near)
    # the road's vertices stand in a recorded cut, of the runway's band
    assert pm.road_yield and road <= set().union(*(y.kerb for y in pm.road_yield))
    assert {y.runway_ref for y in pm.road_yield} == {"09/27"}
    assert road <= pm.band_kerb_vertices()


def test_a_road_in_a_cut_follows_its_ground_and_the_wall_is_declared(cut_arm, law):
    """Twin (a): a road in a 92 m cut through a ~99 m band — the road at its
    ground, the band holding its grade at the gap, one declared wall of
    about 7 m."""
    from auto_patch_v2.pipeline.band_road_wall import LABEL, band_road_wall_joints
    pm, sol, _rep = cut_arm
    road = _road(pm)
    assert max(abs(sol.z[v] - 92.0) for v in road) <= 0.5
    band = _band_vertices(pm)
    gap = [v for v in band if 620.0 <= pm.vertices[v].xy[0] <= 880.0
           and -26.0 < pm.vertices[v].xy[1] < -20.0]
    assert gap and min(sol.z[v] for v in gap) >= 98.5
    js = band_road_wall_joints(pm, law, sol.z)
    big = [j for j in js if j["step_m"] > 5.0]
    assert big and all(j["kind"] == "wall_terrace" and j["shapes"] == [LABEL] for j in js)
    assert max(j["step_m"] for j in big) == pytest.approx(7.0, abs=1.0)
    # every chord from the road's north kerb to the band across the gap
    # crosses a declared line
    from auto_patch_v2.pipeline.ribbon_steps import _to_ll
    to_ll = _to_ll(pm)
    lines = [LineString(j["points"]) for j in big]
    north = [v for v in road if pm.vertices[v].xy[1] > -27.0]
    for a in north:
        ax, ay = pm.vertices[a].xy
        b = min(gap, key=lambda q: (pm.vertices[q].xy[0] - ax) ** 2
                + (pm.vertices[q].xy[1] - ay) ** 2)
        chord = LineString([to_ll(ax, ay), to_ll(*pm.vertices[b].xy)])
        assert any(chord.intersects(g) for g in lines)


def test_a_road_above_the_band_is_held_at_its_ceiling(high_arm, high_airport, law):
    """Twin (b): the road's ground 4 m ABOVE the band — the road stands
    under the band's ceiling (the band beside it), never at its 104 m
    ground."""
    from auto_patch_v2.constraints.zones import zone_bands
    pm, sol, _rep = high_arm
    road = _road(pm)
    rows = [r for r in zone_bands(pm, law, high_airport) if r.follows in road]
    # every road vertex carries the band's CEILING (cap-only: no floor) ...
    assert {r.follows for r in rows} == road and all(r.lo is None for r in rows)
    # ... and stands under it — to the cockpit's motion step: the kerb
    # nearer the runway has the lower ceiling, and the road's own crossfall
    # cap holds the two kerbs together (measured: the near kerb 0.049 m
    # over) — metres under its own ground
    tol = float(law.tables.emit.cockpit.motion_step_m)
    assert all(sum(c * sol.z[v] for v, c in r.terms) <= r.hi + tol for r in rows)
    assert max(sol.z[v] for v in road) < 104.0 - 3.0


def test_the_shadow_reads_the_ground_past_the_cut(law):
    """19ad: a band vertex within the probe of a zone-2 road's axis reads
    the DEM at the probe on its own side (here past the 92 m cut it stands
    in: the step DEM's 100 m north of y = -21); a vertex past the probe, or
    with another road's reach at its probe point, keeps its own."""
    import numpy as np
    from auto_patch_v2.planar.road_shadow import road_shadow
    from auto_patch_v2.planar.road_yield import BandYield
    axis = LineString([(0.0, -27.0), (100.0, -27.0)])
    y = BandYield(axis.buffer(5.0), axis, 4.0, "runway", 2, None, "09/27", True)
    probe = 4.0 + _cut(law) + 2.0 * float(law.tables.zones.adjacent_ground.road_shadow_dem_cells)
    assert -27.0 + probe > -21.0 > -27.0 + probe - 1.5
    xs = np.array([50.0, 50.0, 50.0])
    ys = np.array([-27.0 + probe - 1.5, -27.0 + probe + 0.5, -27.0 - probe + 1.5])
    zs = np.array([92.0, 92.0, 92.0])
    out, rep = road_shadow(_PostedDem(), law, [y], [0, 1, 2], xs, ys, zs)
    # vertex 0 (north, inside the probe, on the 92 m slope of the cut): its
    # probe point lands at y = -27 + probe (> -21) on the 100 m ground;
    # vertex 1 is past the probe; vertex 2 (south) reads the 92 m beyond
    assert out[0] == 100.0 and out[1] == 92.0 and out[2] == 92.0
    assert rep.vertices == 2
    other = BandYield(axis.buffer(5.0), LineString([(0.0, -27.0 + 1.5 * probe),
                                                   (100.0, -27.0 + 1.5 * probe)]),
                      4.0, "runway", 2, None, "09/27", True)
    out2, _rep2 = road_shadow(_PostedDem(), law, [y, other], [0], xs, ys, zs)
    assert out2[0] == 92.0


def test_a_road_wider_than_its_drawn_page_is_walled_at_its_lanes(law):
    """Twin (c), the #1060 geometry: a mapped road (lanes 2 x 5.25 m) over the
    narrower page drawn for it (the 1206 truck route at x = 300, 6 m wide)
    — the band stops at the LANES' edge plus the stand-off ("lanes or drawn
    edge, whichever is larger"), the gap from the page's edge is wider than
    the stand-off, and the wall across it is declared at the lanes' edge."""
    from auto_patch_v2.pipeline.band_road_wall import LABEL, band_road_wall_joints, wall_lines
    wide = _way(-7, ((300.0, -200.0), (300.0, -20.0)), highway="tertiary", width="10.5")
    a = _dc.replace(_with(wide), dem=_StepDem())
    pm, sol, _rep = _solve(a, law)
    page = [f for f in pm.faces.values() if f.role == "service_road"
            and f.ref.startswith("route") and pm.vertices[pm.ring_vertices(f.ring)[0]].xy[1] < 0.0]
    assert page
    page_x = [pm.vertices[v].xy[0] for f in page for v in pm.ring_vertices(f.ring)]
    assert min(page_x) == pytest.approx(297.0) and max(page_x) == pytest.approx(303.0)
    band = [pm.vertices[v].xy for v in _band_vertices(pm)]
    beside = [abs(x - 300.0) for x, y in band if -60.0 < y < -25.0 and abs(x - 300.0) < 10.0]
    # the band's edge by the lanes: 5.25 m + the stand-off, never the page's 3 m
    assert beside and min(beside) >= 5.25 + _cut(law) - snap_margin_m(law) - 1e-6
    assert min(beside) - 3.0 > _cut(law)
    js = [j for j in band_road_wall_joints(pm, law, sol.z) if j["shapes"] == [LABEL]]
    assert js and max(j["step_m"] for j in js) == pytest.approx(8.0, abs=0.5)
    # the declared line (plan) stands half a stand-off off the LANES' edge,
    # beyond the page's edge
    from shapely.geometry import Point
    lines = [g for g in wall_lines(pm, law) if g.distance(Point(300.0, -40.0)) < 10.0]
    assert lines
    off = 5.25 + 0.5 * _cut(law)
    assert min(g.distance(Point(300.0 + off, -40.0)) for g in lines) < 0.05
    assert min(g.distance(Point(300.0 - off, -40.0)) for g in lines) < 0.05


def test_the_seam_beside_a_road_is_where_a_runway_and_a_taxi_band_meet():
    """Owner Q53 (1), 2026-10-20: "where the runway band and a taxiway band
    meet beside a road, the taxiway band's lift yields to the road's own
    ground" (KLAX 33.945981, -118.436151: the runway 4 / taxiway F seam
    vertex 7 m along the ring from the cut edge, held 2.44 m over its DEM
    by taxiway F's floor).  The seam is the vertex on BOTH a runway band
    face and a taxi band face sharing a band ring edge with a vertex on
    the road's cut edge; a runway-only neighbour is not."""
    from types import SimpleNamespace as NS

    from shapely.geometry import box

    from auto_patch_v2.planar.road_yield import BandYield, _seam_beside
    faces = {0: NS(role="graded_strip", ref="adjacent_ground:runway:4:zone2#17"),
             1: NS(role="graded_strip", ref="adjacent_ground:taxi:F:zone2#15")}
    # v0 on the cut edge (x = 0); v1 the seam 7 m along the ring; v2 runway
    # only; v3 taxi only, beyond the seam
    xy = {0: (0.0, 0.0), 1: (7.0, 0.0), 2: (0.0, 7.0), 3: (14.0, 0.0)}
    face_vs = {0: {0, 1, 2}, 1: {1, 3}}
    edges = [NS(a=0, b=1, left_face=0, right_face=None),
             NS(a=0, b=2, left_face=0, right_face=None),
             NS(a=1, b=3, left_face=1, right_face=None)]
    cut = box(-10.0, -10.0, 0.0, 10.0)
    y = BandYield(cut, LineString([(-5.0, -10.0), (-5.0, 10.0)]), 4.0,
                  "runway", 4, None, "06L/24R", True)
    assert _seam_beside([y], faces, face_vs, edges, xy, 0.35) == {0: frozenset({1})}
    assert _seam_beside([_dc.replace(y, through=False)], faces, face_vs, edges, xy, 0.35) == {}
