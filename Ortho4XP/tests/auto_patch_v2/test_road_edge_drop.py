"""Issues #712 / #1003 twin (owner RULINGS 2026-10-20d; spec
``docs/specs/road-edge-drop-spec.md``): where a pad fill cannot bank down,
the drop goes along a road edge — R1 a page a network road runs through is
that road, R2 the fill runs to the road, R3 the road comes down off the
fill at its design grade, R4 the road's low side is a declared wall.
Hermetic: a metre frame."""
from __future__ import annotations

import types

import pytest
from auto_patch_v2.airport import road_edge_wall as RW
from auto_patch_v2.classify import sources as S
from auto_patch_v2.classify.rules import load_rules
from auto_patch_v2.airport import fill_ramp as CF
from auto_patch_v2.planar import fill_road as PF
from shapely.geometry import LineString, Point, box

RULES = load_rules()


def _rec(poly, cls="lot", **kw):
    half = poly.length / 2.0
    base = dict(id="dsf:pol1", description="", area_m2=poly.area,
                width_m=poly.area / half, road_m=0.0, osm_road_m=0.0,
                through_m=0.0, dead_ends=0, road_pieces=0, road_reach=2,
                aisle_m=0.0, taxi_m=0.0, startups=0, parking_cover=0.0,
                apron_cover=0.0, cls=cls, reason="2 road(s) reach it")
    base.update(kw)
    return S.SourceRecord(**base)


def _tree(lines):
    from shapely.strtree import STRtree
    return STRtree(lines)


def test_r1_a_page_a_network_road_runs_through_is_that_road():
    page = box(0, 0, 1000, 18)                       # an 18 m carriageway
    road = [LineString([(-10, 9), (1010, 9)])]       # the mapped secondary
    got = S._network_strip(_rec(page), page, _tree(road), road, RULES)
    assert got.cls == "strip" and got.network_through_m == pytest.approx(1000.0)


def test_r1_a_lot_wider_than_a_road_or_with_no_road_through_stays():
    lot = box(0, 0, 200, 120)                        # 120 m: a car park
    road = [LineString([(-10, 60), (210, 60)])]
    assert S._network_strip(_rec(lot), lot, _tree(road), road, RULES).cls == "lot"
    page = box(0, 0, 1000, 18)
    stub = [LineString([(-10, 9), (100, 9)])]        # ends inside: no through road
    assert S._network_strip(_rec(page), page, _tree(stub), stub, RULES).cls == "lot"
    # taxi evidence keeps a page off the road rung
    assert S._network_strip(_rec(page, taxi_m=50.0), page, _tree(road), road,
                            RULES).cls == "lot"


class _Dem:
    def __init__(self, z):
        self.z = z


def test_r2_a_fill_that_cannot_bank_down_runs_to_the_road_kerb():
    fill = box(0, 0, 100, 60)
    road = box(-50, 120, 150, 138)                   # 60 m off, 18 m wide
    low = _Dem(lambda x, y: 88.0)
    assert PF.cannot_bank(fill, 96.6, low, 15.0, 0.33)
    assert not PF.cannot_bank(fill, 96.6, _Dem(lambda x, y: 94.0), 15.0, 0.33)
    E = PF.extend_to_roads(fill, [road], 100.0)
    assert E.contains(fill) and E.bounds[3] == pytest.approx(120.0)
    assert E.intersection(road).area < 1e-6          # the road is never taken
    assert PF.extend_to_roads(fill, [road], 40.0) is None   # beyond reach


def test_r3_the_frontage_distance_walks_the_road():
    adj = {1: [(2, 10.0)], 2: [(1, 10.0), (3, 10.0)], 3: [(2, 10.0), (4, 50.0)],
           4: [(3, 50.0)]}
    assert CF.frontage_distances(adj, {1}, 30.0) == {1: 0.0, 2: 10.0, 3: 20.0}


def test_r4_runs_are_cyclic_and_need_two_vertices():
    ring = [1, 2, 3, 4, 5, 6]
    assert RW._runs(ring, {2, 3, 5, 6, 1}.__contains__) == [[5, 6, 1, 2, 3]]
    assert RW._runs(ring, {2, 3, 5, 6}.__contains__) == [[2, 3], [5, 6]]
    assert RW._runs(ring, {4}.__contains__) == []


def test_r4_a_raised_road_declares_its_low_side_and_a_shared_kerb_does_not():
    """A road face beside a fill; its far kerb stands 6 m over the ground
    and a lot stands off it by 1 m: one wall record, upper = the far kerb,
    lower = the lot's near rim."""
    V = {}
    faces = {}

    def vx(i, x, y, dem):
        V[i] = types.SimpleNamespace(xy=(float(x), float(y)), dem_z=dem, incident_faces=[])

    # road 0..100 x 0..18; fill below it shares the south kerb (1, 2)
    for i, (x, y) in enumerate([(0, 0), (100, 0), (100, 18), (0, 18)], start=1):
        vx(i, x, y, 90.0)
    # the lot north of the road, standing 1 m off it
    for i, (x, y) in enumerate([(0, 19), (100, 19), (100, 60), (0, 60)], start=11):
        vx(i, x, y, 90.0)
    for i, (x, y) in enumerate([(0, -40), (100, -40)], start=21):
        vx(i, x, y, 90.0)
    ring = {"road": [1, 2, 3, 4], "lot": [11, 12, 13, 14], "fill": [21, 22, 2, 1]}
    roles = {"road": "service_road", "lot": "parking_lot", "fill": "building"}
    for k, (fid, name) in enumerate(((1, "road"), (2, "lot"), (3, "fill"))):
        faces[fid] = types.SimpleNamespace(id=fid, role=roles[name],
                                           ref={"fill": "b/landing0"}.get(name, name),
                                           ring=ring[name], holes=())
        for v in ring[name]:
            V[v].incident_faces.append(fid)
    reg = types.SimpleNamespace(
        landings={"b/landing0": {"block": "b", "y": 0.0, "kind": "plate"}},
        held={"b": {"datum_pred": 96.0, "samples_reach": [0.0]}})
    pm = types.SimpleNamespace(vertices=V, faces=faces, registries=reg,
                               ring_vertices=lambda c: list(c))
    from auto_patch_v2.law import Law
    law = Law.for_airport("HECA")
    targets = {1: 96.0, 2: 96.0, 3: 95.6, 4: 95.6}
    counts: dict = {}
    got = RW.road_edge_walls(pm, law, targets, 8.0, counts)
    assert len(got) == 1, counts
    rec = got[0]
    assert sorted(rec["upper"]) == [3, 4] and sorted(rec["lower"]) == [11, 12]
    assert rec["retains"] and rec["height_m"] == pytest.approx(5.6)
    assert RW.is_road_edge_wall(rec)
    line = rec["line"]
    from shapely.geometry import Polygon
    band = Polygon(line)
    assert not band.contains(Point(V[3].xy)) and band.distance(Point(V[3].xy)) < 0.1
