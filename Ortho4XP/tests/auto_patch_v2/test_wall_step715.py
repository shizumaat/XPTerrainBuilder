"""Owner RULINGS 2026-10-15a (2) (#715, KATL 33.6412038, -84.4211416): "Yes,
the wall is the step" — a pack wall that RETAINS ITS OWN HEIGHT (slender
for its height, the ground stepping 0.75-1.25 x its height across it) is a
declared terrace: the airside above holds its level, the ROAD below sits
at the lower ground, released from the upper level, and the step across
the wall line is declared.  The same step at a covered-ground deck's edge
where a pack portal bounds it (#714, ``planar/covered_ground``).

Synthetic: the runway 09/27 along y = 0 (edge y = -15) on ground at
100 m; a tertiary road at y = -30 inside the runway's strip; the ground
south of y = -21 at 92 m (an 8 m step) and an 8 m wall along y = -21,
5 m off the runway's edge and 4 m off the road's kerb."""
from __future__ import annotations

import dataclasses as _dc
from types import SimpleNamespace as NS

import pytest
from shapely.geometry import LineString, Polygon, box

from auto_patch_v2.law import Law

from test_roadmint100 import _way, _with
from test_roadterrace100 import _solve

WALL = box(560.0, -22.0, 940.0, -20.0)
#: a tertiary road along y = -30 (kerbs -26 / -34), 4 m off the wall
ROAD = ((600.0, -30.0), (900.0, -30.0))


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("SYNT")


class _StepDem:
    """100 m north of y = -21, 92 m south of it."""
    provenance = {"base": "synthetic"}

    def z(self, x: float, y: float) -> float:
        return 100.0 if y > -21.0 else 92.0

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)


@pytest.fixture(scope="module")
def arms(law):
    """(no wall, a thin wall that does not retain, a retaining wall)."""
    from auto_patch_v2.airport import road_ramp as rr
    from auto_patch_v2.airport.road_ramp import WallPiece
    a = _dc.replace(_with(_way(-3, ROAD, highway="tertiary")), dem=_StepDem())
    out = [_solve(a, law)]
    for retains in (False, True):
        mp = pytest.MonkeyPatch()
        try:
            mp.setattr(rr, "wall_pieces", lambda _ap, _cfg=None, r=retains: (
                WallPiece(WALL, 8.0, "wall.obj#comp0", r),))
            out.append(_solve(a, law))
        finally:
            mp.undo()
    return out


def _road(pm):
    from auto_patch_v2.model.planar import is_osm_ribbon_ref
    return {v for f in pm.faces.values() if is_osm_ribbon_ref(f.ref)
            for v in pm.ring_vertices(f.ring)
            if 620.0 <= pm.vertices[v].xy[0] <= 880.0}


def test_without_a_retaining_wall_the_road_in_the_strip_holds_the_runway_level(arms):
    for pm, sol, _rep in arms[:2]:
        road = _road(pm)
        assert road and set(pm.road_terrace["foot"]) & road
        assert min(sol.z[v] for v in road) > 97.0


def test_below_a_retaining_wall_the_road_sits_at_the_lower_ground(arms):
    pm, sol, _rep = arms[2]
    road = _road(pm)
    assert road and not set(pm.road_terrace["foot"]) & road
    # at its ground within a metre (the road here is the zone band's kerb on
    # both sides and carries no target of its own: the strip's fit leads)
    assert max(abs(sol.z[v] - 92.0) for v in road) <= 1.0
    rec = next(iter(pm.road_terrace["wall"].values()))
    assert set(rec["lower"]) & road and rec["upper"]


def test_the_step_is_declared_at_the_wall_and_the_airside_is_untouched(arms):
    from auto_patch_v2.pipeline.publication import wall_terrace_joints
    from auto_patch_v2.solve.design_roles import airside_stage_vertices
    (pm0, sol0, _r0), _thin, (pm2, sol2, _r2) = arms
    law = Law.for_airport("SYNT")
    j = wall_terrace_joints(pm2, law, sol2.z)
    assert len(j) == 1 and 7.0 <= j[0]["emitted_step_m"] <= 8.0 + 0.6
    z0 = {pm0.vertices[v].xy: sol0.z[v] for v in airside_stage_vertices(pm0, law)}
    at2 = {pm2.vertices[v].xy: v for v in pm2.vertices}
    assert z0 and all(abs(sol2.z[at2[xy]] - zz) <= 1e-6 for xy, zz in z0.items()
                      if xy in at2)


def test_a_mouth_wall_is_the_deck_edge_under_a_deep_pack_object():
    """``planar/covered_ground._mouth_walls``: the deck's edge at the
    pavement's end, under a pack object reaching the mouth depth below its
    zero — and nothing under a shallow one."""
    from auto_patch_v2.planar.covered_ground import _mouth_walls
    # the airside over the bore, grown by the identity tolerance (as the
    # caller hands it) and the cut's ribbon clipped to it
    pav = box(0.0, 0.0, 100.0, 50.0).buffer(0.5)
    rib = box(40.0, -5.0, 60.0, 55.0).intersection(pav)
    from auto_patch_v2.planar.covered_ground import _Section
    secs = [_Section(0.0, (50.0, 0.0), (1.0, 0.0), 10.0, 10.0, 100.0, 100.0)]
    cuts = [(None, secs, rib, None)]

    def obj(depth):
        return NS(plan_bbox=box(35.0, -10.0, 65.0, 5.0), anchor_z=100.0,
                  agl_m=0.0, solid_min_z=100.0 - depth, path="portal.obj")
    got = _mouth_walls(cuts, pav, [obj(23.7)], 7.5)
    assert got and all(d == 23.7 for _r, d, _p in got)
    # the open cut beyond the edge, off the pavement, is in the piece
    from shapely.geometry import Point
    assert any(Polygon(r).contains(Point(50.0, -6.0)) for r, _d, _p in got)
    edge = LineString([(40.0, 0.0), (60.0, 0.0)])
    assert any(Polygon(r).intersects(edge) for r, _d, _p in got)
    assert not any(Polygon(r).intersects(LineString([(40.0, 50.0), (60.0, 50.0)]))
                   for r, _d, _p in got)
    assert _mouth_walls(cuts, pav, [obj(3.0)], 7.5) == []
