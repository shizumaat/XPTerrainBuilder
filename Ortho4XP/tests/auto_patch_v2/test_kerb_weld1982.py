"""A SERVICE ROAD AT A TAXIWAY WELDS TO IT AND FOLLOWS ITS LEVEL (#1982 /
#1983; owner RULINGS 2026-10-28p (1) read for every band, 2026-10-03b).

Found at KEGE (``small_roads:-895``, a ``highway=service`` road from taxi
E's edge across its zone 2): cut out of the zone like a public road
(20c (39)), its kerb carried the band's ceiling and no level of its own,
while the run linked beyond it took the taxiway's — it stepped 2.8 m under
the taxiway at its weld and sank 6 m under the band beside it (a trench).

* ``planar/zones``: a taxiway's zone 2, like a runway's, yields only the
  roads that do not sit at grade (``rsa_carriageways``) — an airport
  service road through it is not cut.
* ``constraints/road_ramp.terrace_rewrite``: an at-grade road's band kerb
  bordered by a taxiway or an apron takes its terrace level as its design
  target; a runway-bordered kerb still takes none (#951)."""
from __future__ import annotations

import types

import pytest
from auto_patch_v2.classify.roles import Cell
from auto_patch_v2.law import Law
from auto_patch_v2.law.tables import zone_edge_offset_m
from auto_patch_v2.model.airport import OsmWay
from auto_patch_v2.planar.road_yield import road_carriageways, rsa_carriageways
from auto_patch_v2.planar.zones import zone_regions

#: a taxiway 30 m wide along y, its east edge at x = 0
PAV = ((-30.0, -400.0), (0.0, -400.0), (0.0, 400.0), (-30.0, 400.0))


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


def _through(law, highway: str) -> list:
    """The zone-2 cuts a road along the middle of a taxiway's zone 2 makes."""
    # zone 2's outer edge off the pavement (5 m for code C; the lip is 3 m):
    # the centreline outside the lip, inside zone 2
    x = 0.8 * zone_edge_offset_m(law, "junction", None, "C")
    ways = (OsmWay(1, "small_roads", ((x, -300.0), (x, 300.0)), False,
                   {"highway": highway}),)
    cells = (Cell(0, "junction", "T", PAV, (), None, "C", "airside", "junction", {}),)
    ys: list = []
    zone_regions(cells, law, carriageways=road_carriageways(ways, law), yields=ys,
                 rsa_carriageways=rsa_carriageways(ways, law))
    return [y for y in ys if y.through]


def test_a_service_road_through_a_taxiway_zone_two_is_not_cut(law):
    assert "service" in law.tables.zones.adjacent_ground.rsa_at_grade_highways
    assert _through(law, "service") == []
    # a public road through the same band keeps 20c (39): it is cut
    assert [y.family for y in _through(law, "tertiary")] == ["taxi"]


def _route(n: int) -> dict:
    return {v: (0, float(5 * v)) for v in range(n)}


def test_a_taxi_bordered_kerb_takes_the_taxiway_level(law):
    """Stations 0-1 are band KERBS bordered by a taxiway at 110 m (no §37
    (6) row); 2-5 are road vertices whose own target is 100 m.  The kerb
    gets the taxiway's level as its design target and the run beyond it
    climbs from there — no dip between the weld and the linked run."""
    from auto_patch_v2.constraints import road_ramp as rr
    from auto_patch_v2.model.constraints import ConstraintSet, Linear, Source

    st = _route(6)
    foot = {v: (100 + v, 200 + v, 0.0, "pol93") for v in (0, 1)}
    lv = {100: 110.0, 101: 110.0, 200: 110.0, 201: 110.0}
    road = [2, 3, 4, 5]
    face = types.SimpleNamespace(ref="small_roads:-1", role="service_road")
    planar = types.SimpleNamespace(
        road_terrace={"foot": foot, "pad": {}, "station": st, "kerb": {0: True, 1: True},
                      "runway": {}},
        vertices={v: types.SimpleNamespace(dem_z=100.0, incident_faces=(0,)) for v in st},
        faces={0: face})
    cs = ConstraintSet(linears=tuple(
        Linear(((v, 1.0),), 100.0, 100.0, Source(rr.GEN, rr.RULING, (f"vertex:{v}", "r")))
        for v in road))
    out, rep = rr.terrace_rewrite(planar, law, cs, lv)
    got = {int(r.source.inputs[0][7:]): r.hi for r in out.linears}
    assert got[0] == pytest.approx(110.0) and got[1] == pytest.approx(110.0)
    assert rep["kerb"] == 2
    # the run beyond the kerb leaves the taxiway's level, never under it
    # first: the profile is monotone from the weld
    zs = [got[v] for v in range(6)]
    assert all(a >= b - 1e-9 for a, b in zip(zs[:-1], zs[1:], strict=True))

    # the same kerb bordered by a RUNWAY gets no target (#951)
    planar.road_terrace["runway"] = {0: True, 1: True}
    out, rep = rr.terrace_rewrite(planar, law, cs, lv)
    got = {int(r.source.inputs[0][7:]) for r in out.linears}
    assert not got & {0, 1} and rep["kerb"] == 0
