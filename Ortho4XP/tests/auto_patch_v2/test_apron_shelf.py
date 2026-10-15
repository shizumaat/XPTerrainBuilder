"""THE APRON-EDGE SHELF — the twins (owner RULINGS 2026-10-14n D2, #709;
``planar/apron_shelf``).

A walled cluster under ``[placement] cluster_pad_min_m2`` that stands on an
apron (at least ``apron_shelf_min_share`` of its closed outline on it) and
reaches past the apron's edge gets a flat ``shelf<k>`` face on the ground
under the overhang — never on airside, standing off it — and a ``#collar``
bank around it.  The object stage reads the shelf as ground.

The fixture, in metres (the frame's ``entry`` is the identity, rings are
``(lat, lon) = (y, x)``, part boxes ``(y0, x0, y1, x1)``): an apron (x 0..100,
y 0..50); a 30 x 26 m building at x 40..70, y 30..56 — 77 % on the apron,
its north 6 m past the edge — and, for the chain twin, a canopy roof east of
it with a post under it, and a free-standing post 40 m away.
"""
from __future__ import annotations

import dataclasses as _dc
import json

import pytest
from shapely.geometry import Polygon, box

from auto_patch_v2.airport.placement_read import pads_rims_from_graded_doc
from auto_patch_v2.law import Law
from auto_patch_v2.model.planar import COLLAR_SUFFIX, is_shelf_ref
from auto_patch_v2.planar import apron_shelf as sh
from auto_patch_v2.planar.overlay import Region


def _ring(x0, y0, x1, y1):
    return ((y0, x0), (y0, x1), (y1, x1), (y1, x0))


@_dc.dataclass
class _Cluster:
    id: str
    rings: tuple
    area_m2: float
    unit: str = "unit:1"
    members: tuple = ("objects/fbo.obj",)
    walled: int = 1
    floors: tuple = (0.0,)
    bridges: tuple = ()
    evidence: object = None


@_dc.dataclass
class _Part:
    box: tuple
    rings: tuple = ()
    feet: tuple = ((0.0, 0.0, 0.0),)


@_dc.dataclass
class _Member:
    resource: str
    parts: tuple
    deck_shade_ring: tuple = ()


@_dc.dataclass
class _Unit:
    id: str
    members: tuple


class _Partition:
    def __init__(self, units):
        self.units = units


class _Frame:
    @staticmethod
    def entry():
        return lambda lo, la: (float(lo), float(la))

    @staticmethod
    def transformers():
        f = lambda a, b: (float(a), float(b))  # noqa: E731
        return f, f


class _Airport:
    def __init__(self, clusters, parts=()):
        self.clusters = clusters
        self.frame = _Frame()
        self.buildings = ()
        self.sunken_ramps = None
        self.partition = _Partition([_Unit("unit:1", (_Member("objects/fbo.obj", tuple(parts)),))])


APRON = box(0.0, 0.0, 100.0, 50.0)
BUILDING = _ring(40.0, 30.0, 70.0, 56.0)


def _regions():
    return [Region("apron", "pavA", APRON, None, None, "airside", "cell")]


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


def _run(law, clusters, parts=(), pads=()):
    counts: dict = {}
    out = sh.shelf_regions(_regions(), list(pads), _Airport(clusters, parts),
                           law, 0.5, counts)
    return out, counts


def test_building_on_the_apron_edge_gets_a_shelf_off_the_airside(law):
    c = _Cluster("unit:1#0", (BUILDING,), 600.0)
    out, counts = _run(law, [c])
    flat = [r for r in out if not str(r.ref).endswith(COLLAR_SUFFIX)]
    bank = [r for r in out if str(r.ref).endswith(COLLAR_SUFFIX)]
    assert counts["shelves"] == 1 and flat and bank
    assert all(is_shelf_ref(r.ref) and r.role == "building" for r in out)
    for r in out:
        # never airside, never touching it: the stand-off
        assert r.polygon.distance(APRON) >= 1.0
    keep = float(law.tables.emit.design.bank_min_width_m)
    for r in bank:
        assert r.polygon.distance(APRON) >= keep - 1e-6
    # the shelf is the building's off-apron ground (y 50..56), not more
    S = flat[0].polygon
    assert S.bounds[1] >= 50.0 and S.bounds[3] <= 56.0 + 1e-6
    assert 40.0 - 1e-6 <= S.bounds[0] and S.bounds[2] <= 70.0 + 1e-6


def test_a_post_that_chains_widens_the_ground_a_free_post_does_not(law):
    c = _Cluster("unit:1#0", (BUILDING,), 600.0)
    roof = _Part(box=(40.0, 70.3, 60.0, 82.0), feet=())      # canopy, chained
    post = _Part(box=(58.0, 80.0, 59.0, 81.0))               # under the canopy
    far = _Part(box=(90.0, 110.0, 91.0, 111.0))              # free-standing
    out0, _ = _run(law, [c])
    out1, _ = _run(law, [c], parts=(roof, post, far))
    a0 = max(r.polygon.bounds[2] for r in out0 if not str(r.ref).endswith(COLLAR_SUFFIX))
    a1 = max(r.polygon.bounds[2] for r in out1 if not str(r.ref).endswith(COLLAR_SUFFIX))
    assert a1 > a0 + 4.0                                     # the canopy's ground
    assert all(r.polygon.bounds[2] < 100.0 and r.polygon.bounds[3] < 80.0
               for r in out1)                                # never the far post


def test_no_shelf_under_the_share_or_over_the_bar_or_disarmed(law):
    off = _Cluster("unit:1#0", (_ring(40.0, 47.0, 70.0, 67.0),), 600.0)  # 15 % on
    assert _run(law, [off])[1]["shelves"] == 0
    big = _Cluster("unit:1#0", (BUILDING,), 6000.0)          # a cluster pad's
    assert _run(law, [big])[0] == []
    leaf = _Cluster("unit:1#0", (BUILDING,), 600.0, walled=0)
    assert _run(law, [leaf])[0] == []
    st = _dc.replace(law.tables.structures.placement, apron_shelf_min_share=0.0)
    off_law = _dc.replace(law, tables=_dc.replace(
        law.tables, structures=_dc.replace(law.tables.structures, placement=st)))
    assert _run(off_law, [_Cluster("unit:1#0", (BUILDING,), 600.0)])[0] == []


def test_a_held_region_keeps_its_ground(law):
    c = _Cluster("unit:1#0", (BUILDING,), 600.0)
    road = Region("service_road", "road1", box(30.0, 50.0, 80.0, 60.0), None,
                  None, "groundside", "cell")
    counts: dict = {}
    out = sh.shelf_regions(_regions() + [road], [], _Airport([c]), law, 0.5, counts)
    assert out == [] and counts["shelf_none_free"] == 1


def test_the_object_stage_reads_a_shelf_as_ground():
    doc = {"vertices": [[0, 0.0, 0.0, 1.0], [1, 0.0, 1.0, 1.0], [2, 1.0, 1.0, 1.0],
                        [3, 2.0, 0.0, 1.0], [4, 2.0, 1.0, 1.0], [5, 3.0, 1.0, 1.0]],
           "faces": [{"role": "building", "ref": "shelf1", "ring": [0, 1, 2]},
                     {"role": "building", "ref": "shelf1#collar", "ring": [0, 2, 3]},
                     {"role": "building", "ref": "building1", "ring": [3, 4, 5]}],
           "breaklines": []}
    pads, _rims = pads_rims_from_graded_doc(json.loads(json.dumps(doc)))
    assert [p.ref for p in pads] == ["building1"]
    assert is_shelf_ref("shelf12") and is_shelf_ref("shelf3#collar")
    assert not is_shelf_ref("shelfX") and not is_shelf_ref("building1")


# ---------------------------------------------------------------- stage 2
from auto_patch_v2.constraints.apron_shelf import shelf_release  # noqa: E402
from auto_patch_v2.model.constraints import ConstraintSet, Linear, Source  # noqa: E402


@_dc.dataclass
class _F:
    ref: str
    ring: tuple
    holes: tuple = ()


@_dc.dataclass
class _V:
    dem_z: float


class _Map:
    def __init__(self, dem):
        self.faces = {0: _F("shelf1", (0, 1, 2)), 1: _F("shelf1#collar", (2, 3, 4)),
                      2: _F("pavA", (5, 6, 7))}
        self.vertices = {v: _V(dem) for v in range(8)}

    @staticmethod
    def ring_vertices(ring):
        return list(ring)


def _level_row():
    # the §20 frontage level: the shelf's mean against the apron's leaders
    terms = tuple((v, 1.0 / 3.0) for v in (0, 1, 2)) + ((5, -0.5), (6, -0.5))
    return Linear(terms, 0.0, 0.0, Source(
        "pads", "structures.building_pad frontage_level (test)", ("face:0", "shelf1")))


@pytest.mark.parametrize("dem, kept", [(99.0, True), (100.2, False), (107.0, False)])
def test_a_shelf_fills_it_never_cuts(law, dem, kept):
    """Stage 1 put the apron at 100 m: a shelf over ground 1 m below keeps
    its level row (it fills); one within ``split_tol_m`` or above it (a cut)
    is released and keeps its own ground."""
    cs = ConstraintSet(linears=(_level_row(),))
    out, recs = shelf_release(_Map(dem), law, cs, {5: 100.0, 6: 100.0, 7: 100.0})
    assert [r["kept"] for r in recs] == [kept]
    assert len(out.linears) == (1 if kept else 0)
