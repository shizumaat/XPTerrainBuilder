"""#2283 (owner RULINGS 2026-11-25e, EKVG): a groundside parking lot with no
level target follows its ground within its grade cap, and a road leaving a
lot at a neck climbs with its ground under the road law.

Synthetic readings of the three derivations: which vertices are the lot's
own (``model/lot_ground``), where a lot narrows into a road
(``classify/neck.road_necks``, ``geom/centreline.medial_directions``) and
how the road's rows are priced (``constraints/lot_neck``).  The airport
read is the EKVG replay in the lane report."""
from __future__ import annotations

import types

import pytest
from shapely.geometry import LineString, Polygon, box
from shapely.ops import unary_union
from shapely.strtree import STRtree

from auto_patch_v2.classify.neck import road_necks
from auto_patch_v2.classify.rules import load_rules
from auto_patch_v2.constraints import lot_neck, roads
from auto_patch_v2.geom.centreline import medial_directions
from auto_patch_v2.law import load_default
from auto_patch_v2.model.constraints import Diff, Source
from auto_patch_v2.model.lot_ground import lot_datum_vertices

LAW = load_default()
RULES = load_rules()


# --- the lot's own vertices -------------------------------------------------

def _face(fid, role, ring, holes=()):
    return types.SimpleNamespace(id=fid, role=role, ring=tuple(ring), holes=tuple(holes),
                                 ref=f"f{fid}")


def _map(faces, dem, **kw):
    """A duck-typed map whose rings are their vertex ids."""
    vertices = [types.SimpleNamespace(xy=(float(i), 0.0), dem_z=z) for i, z in enumerate(dem)]
    return types.SimpleNamespace(faces={f.id: f for f in faces}, vertices=vertices,
                                 ring_vertices=lambda ring: tuple(ring),
                                 road_terrace=kw.get("road_terrace", {}),
                                 preferred_z=kw.get("preferred_z", {}))


def test_lot_vertices_are_the_lots_own():
    pm = _map([_face(1, "parking_lot", [0, 1, 2, 3]), _face(2, "apron", [3, 4, 5])],
              [10.0, 11.0, None, 12.0, 13.0, 14.0])
    # 3 is the apron's too (airside is king), 2 has no DEM sample
    assert lot_datum_vertices(pm) == {0, 1}


def test_a_car_lot_is_its_own_stage():
    """A last-stage car lot already takes its ground in its own stage
    (``constraints/car_lot_follow``): it carries no datum here."""
    car = types.SimpleNamespace(id=1, role="parking_lot", ring=(0, 1, 2), holes=(),
                                ref="carlot:7")
    assert lot_datum_vertices(_map([car], [1.0, 2.0, 3.0])) == frozenset()


def test_a_lot_with_a_level_target_keeps_it():
    faces = [_face(1, "parking_lot", [0, 1, 2]), _face(2, "parking_lot", [3, 4, 5])]
    dem = [1.0] * 6
    levelled = _map(faces, dem, road_terrace={"lot_level": {"lots": [1]}})
    assert lot_datum_vertices(levelled) == {3, 4, 5}
    profiled = _map(faces, dem, preferred_z={4: 1.0})
    assert lot_datum_vertices(profiled) == {0, 1, 2, 3, 5}


def test_other_groundside_bodies_are_not_lots():
    pm = _map([_face(1, "groundside_pavement", [0, 1, 2]), _face(2, "service_road", [3, 4, 5])],
              [1.0] * 6)
    assert lot_datum_vertices(pm) == frozenset()


# --- the neck ---------------------------------------------------------------

#: a 120 x 80 m lot with an 8 m wide road leaving its north side for 90 m
LOT = box(0.0, 0.0, 120.0, 80.0)
ARM = box(56.0, 79.0, 64.0, 170.0)


def test_a_lot_narrowing_to_a_road_is_a_neck():
    necks = road_necks(unary_union([LOT, ARM]), RULES)
    assert len(necks) == 1
    n = necks[0]
    assert n.kind == "arm"
    assert n.width_m == pytest.approx(8.0, abs=1.0)
    assert n.polygon.contains(box(57.0, 100.0, 63.0, 160.0))
    assert not n.polygon.intersects(box(10.0, 10.0, 110.0, 60.0))


def test_a_lot_alone_has_no_neck():
    assert road_necks(LOT, RULES) == []


def test_a_stall_wide_strip_is_lot_not_road():
    # wider than anything a vehicle parks across: the lot, not its road
    wide = box(50.0, 79.0, 68.0, 170.0)
    assert road_necks(unary_union([LOT, wide]), RULES) == []


def test_a_short_driveway_is_a_notch():
    stub = box(56.0, 79.0, 64.0, 110.0)
    assert road_necks(unary_union([LOT, stub]), RULES) == []


def test_medial_directions_follow_the_ribbon():
    axes = medial_directions(Polygon([(0, 0), (100, 0), (100, 8), (0, 8)]))
    assert axes
    along = [abs(u[0]) for a, b, u in axes if 10.0 < 0.5 * (a[0] + b[0]) < 90.0]
    assert along and min(along) > 0.99


# --- the road law from the neck on -----------------------------------------

def _rows_map():
    """Lot vertices 0, 1 in the lot body, 2-5 up the road (climbing 9 %
    north), 6 airside."""
    xy = [(40.0, 40.0), (80.0, 40.0),            # the lot
          (57.0, 100.0), (63.0, 100.0),          # the road, one section
          (57.0, 150.0), (63.0, 150.0),          # 50 m on
          (60.0, -10.0)]                         # airside
    dem = [80.0, 80.0, 82.0, 82.12, 86.5, 86.62, 79.0]
    vertices = [types.SimpleNamespace(xy=p, dem_z=z, key=(62.0 + 1e-5 * p[1], -7.0 + 1e-5 * p[0]))
                for p, z in zip(xy, dem, strict=True)]
    lot = types.SimpleNamespace(id=1, role="parking_lot", ring=(0, 1, 2, 3, 4, 5), holes=(),
                                ref="dsf:pol1")
    return types.SimpleNamespace(vertices=vertices, faces={1: lot},
                                 ring_vertices=lambda ring: tuple(ring))


def _road():
    axes = tuple(medial_directions(ARM))
    return lot_neck._LotRoad(ARM, frozenset({2, 3, 4, 5}), axes,
                            STRtree([LineString([a, b]) for a, b, _u in axes]))


def _diff(pm, a, b, gen=roads.GEN):
    (ax, ay), (bx, by) = pm.vertices[a].xy, pm.vertices[b].xy
    d = ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5
    return Diff(a, b, 0.05, d, Source(gen, "common.roles longitudinal (2026-08-03)"))


@pytest.fixture
def pm(monkeypatch):
    monkeypatch.setattr(lot_neck, "_lot_roads", lambda planar, law: [_road()])
    monkeypatch.setattr(lot_neck, "stage_one_vertices", lambda planar, law: frozenset({6}))
    return _rows_map()


def test_the_road_climbs_with_its_ground(pm):
    (out,), n = lot_neck.neck_release([_diff(pm, 2, 4)], pm, LAW)
    assert n == 1
    assert out.cap * out.d >= 4.5               # the ground's own climb fits
    assert out.cap <= 0.20 + 1e-9               # never past the steep cap


def test_the_road_holds_two_percent_laterally(pm):
    (out,), _n = lot_neck.neck_release([_diff(pm, 2, 3)], pm, LAW)
    assert out.cap == pytest.approx(0.02, abs=1e-3)
    twin = _diff(pm, 2, 3, gen="pavement_ceiling")
    (kept,), _n = lot_neck.neck_release([twin], pm, LAW)
    assert kept is twin                         # a hard twin only ever widens


def test_a_gentle_road_takes_the_road_cap(pm):
    pm.vertices[4].dem_z = 82.5                 # 1 % over 50 m
    (out,), _n = lot_neck.neck_release([_diff(pm, 2, 4)], pm, LAW)
    assert out.cap == pytest.approx(0.10, rel=1e-3)


def test_the_lot_lets_its_road_go(pm):
    (out,), n = lot_neck.neck_release([_diff(pm, 0, 4)], pm, LAW)
    assert n == 1 and out.cap > 0.05
    lot_row = _diff(pm, 0, 1)                   # inside the lot: its own law
    (same,), n = lot_neck.neck_release([lot_row], pm, LAW)
    assert same is lot_row and n == 0


def test_airside_is_never_touched(pm):
    row = _diff(pm, 6, 4)
    (out,), n = lot_neck.neck_release([row], pm, LAW)
    assert out is row and n == 0


def test_the_published_pairs_are_the_releases_own(pm):
    """The verify / census read (``lot_neck_pairs``) prices each pair at
    the bound the release gave its row: one reading, two consumers."""
    pub = {(tuple(a), tuple(b)): bound for a, b, bound in lot_neck.neck_pair_bounds(pm, LAW)}
    key = {v: tuple(pm.vertices[v].key) for v in range(len(pm.vertices))}
    for a, b in ((2, 4), (2, 3), (0, 4)):
        (out,), _n = lot_neck.neck_release([_diff(pm, a, b)], pm, LAW)
        got = pub.get((key[a], key[b]), pub.get((key[b], key[a])))
        assert got == pytest.approx(out.cap * out.d, abs=1e-3), (a, b)
    assert (key[0], key[1]) not in pub          # inside the lot: its own law
    assert all(key[6] not in k for k in pub)    # airside is never published


def test_the_lot_follows_after_stage_two_alone(pm):
    """THE FOLLOWER PASS (airside is king): the lot's own vertices are the
    only unknowns, every other vertex a constant at its stage-2 level, and
    the neck rows are priced in this pass only."""
    from auto_patch_v2.model.constraints import ConstraintSet
    from auto_patch_v2.pipeline.lot_follow import lot_follow_rewrite
    pm.road_terrace, pm.preferred_z = {}, {}
    cs = ConstraintSet.from_rows([_diff(pm, 2, 4), _diff(pm, 0, 1), _diff(pm, 6, 0)])
    z = [80.0] * len(pm.vertices)
    cs_f, fixed, rep = lot_follow_rewrite(pm, cs, z, LAW)
    assert set(fixed) == {6}
    assert rep["ground_followers"] == 6 and rep["neck_rows"] == 1
    road = [d for d in cs_f.diffs if {d.a, d.b} == {2, 4}]
    assert road and road[0].cap > 0.05
