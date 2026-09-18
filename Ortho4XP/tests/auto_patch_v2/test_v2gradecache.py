"""THE AT-GRADE READ IS MEMOISED PER RESOURCE (owner RULINGS 2026-09-13bp,
lane ``v2gradecache``).

``at_grade_geometry`` / ``above_grade_footprint`` clipped and unioned the
same pack resource ONCE PER PLACEMENT: VHHH's 5,078 custom objects over
785 resources and 74 basin rings spent 2,626 s of a 3,800 s build inside
``obj8.py``'s ``unary_union`` and ``obj8_clip._clip_both``, with ~25 MB
retained per placement in the region loop's placement-keyed caches (2.2 ->
10.0 GB in 7 minutes; the app's worker 34.9 GB) — and NOTHING timed it, so
it read as a hang beside a 6.8e-06 s ``object_read_s``.

The three assertions here are the ruling's (i)-(iii): the clip + union
depends only on ``(resource, plane)`` and runs once per distinct pair with
the placement affine applied afterwards; the retention is bounded; and the
read is timed with a vertex-budget REFUSAL that names the pack.
"""
from __future__ import annotations

import math

import pytest

from auto_patch_v2.airport import obj8
from auto_patch_v2.law import Law
from auto_patch_v2.planar import basins as _basins

from test_m4b import _box_obj                                    # noqa: E402


class _FlatDem:
    """A DEM with no relief — every placement of one resource lands on the
    same plane, which is exactly VHHH's reclaimed-land case."""

    z0 = 700.0

    def z(self, x: float, y: float) -> float:
        return self.z0


#: Two placements of one resource whose CLIP PLANES differ: the plane is
#: ``DEM(component) - anchor_z - agl - band``, so an AGL of 3 m moves it 3 m
#: even on flat ground (relief under a component moves it the same way).
_AGL_APART = 3.0


@pytest.fixture(scope="module")
def bl():
    return Law.for_airport("ZZZZ").tables.structures.basin


@pytest.fixture(scope="module")
def pit(tmp_path_factory):
    return _box_obj(tmp_path_factory.mktemp("gradecache") / "pit.obj", 30.0, 20.0, 6.0)


def _placed(path: str, oid: str, xy, heading: float, dem, bl, agl=None) -> obj8.PlacedObject:
    rows = [(oid, "objects/pit.obj", xy, heading, agl,
             "OBJECT_AGL" if agl is not None else "OBJECT")]
    got, _rep = obj8.read_placed_objects(
        rows, None, {"objects/pit.obj": path}, dem.z, bl.admission_depth_m,
        bl.min_solid_thickness_m, bl.contact_band_m,
        floor_plate_normal_y_min=bl.floor_plate_normal_y_min)
    return got[0]


def test_one_clip_and_union_per_resource_and_plane(pit, bl):
    """(i) Four placements of one resource on flat ground: ONE clip+union,
    and each placement's geometry is the memoised one under its own
    affine.  This is the 2,700-unions-for-five-resources defect."""
    dem = _FlatDem()
    cache = obj8.ResourceCache(bl.min_solid_thickness_m)
    placed = [_placed(str(pit), f"o{i}", xy, hd, dem, bl) for i, (xy, hd) in enumerate(
        (((0.0, 0.0), 0.0), ((300.0, 0.0), 0.0), ((0.0, 400.0), 90.0), ((-250.0, 120.0), 33.0)))]
    reads = [obj8.at_grade_geometry(o, cache, dem.z, bl.contact_band_m) for o in placed]
    assert cache.grade.calls == 4
    assert cache.grade.unions == 1, "the clip + union is per (resource, plane), not per placement"
    assert cache.grade.vertices > 0 and cache.grade.seconds > 0.0
    # every placement still reads its OWN geometry: same rim length, its own place
    lens = [r[0].length for r in reads]
    assert all(math.isclose(v, lens[0], rel_tol=1e-9) for v in lens)
    centres = [r[0].centroid for r in reads]
    assert centres[0].distance(centres[1]) == pytest.approx(300.0, abs=1e-6)
    assert centres[0].distance(centres[2]) == pytest.approx(400.0, abs=1e-6)

    # the cover read shares the discipline and its own memo
    for o in placed:
        obj8.above_grade_footprint(o, cache, dem.z, bl.contact_band_m)
    assert cache.grade.calls == 8 and cache.grade.unions == 2


def test_a_different_plane_is_a_different_read(pit, bl):
    """The memo key is the PLANE, not the resource alone — relief must not
    be collapsed away (LEMD: 30 m of it under one authored datum)."""
    dem = _FlatDem()
    cache = obj8.ResourceCache(bl.min_solid_thickness_m)
    for i, agl in enumerate((None, _AGL_APART)):
        o = _placed(str(pit), f"o{i}", (float(i) * 500.0, 0.0), 0.0, dem, bl, agl=agl)
        obj8.at_grade_geometry(o, cache, dem.z, bl.contact_band_m)
    assert cache.grade.calls == 2 and cache.grade.unions == 2


def test_a_window_or_a_select_reads_THROUGH_the_memo(pit, bl):
    """SUPERSEDED BY RULINGS 2026-09-17k (a) (lane ``v2doorwellperf``).
    This test used to pin the opposite — a window or a ``select`` stayed
    on an unmemoised, unbudgeted path — and that path is what did not
    terminate on OTHH's 2026-09-16 pack (56:40, 25.8 GB inside
    ``read_door_wells``).  Both now read through the memo; the window is
    applied to the placed result.  The equality and the bounded call
    count live in ``test_v2doorwellperf.py``."""
    dem = _FlatDem()
    cache = obj8.ResourceCache(bl.min_solid_thickness_m)
    o = _placed(str(pit), "o0", (0.0, 0.0), 0.0, dem, bl)
    obj8.at_grade_geometry(o, cache, dem.z, bl.contact_band_m, select=lambda c: True)
    obj8.above_grade_footprint(o, cache, dem.z, bl.contact_band_m, within=o.plan_bbox)
    assert cache.grade.calls == 2 and cache.grade.unions == 2


def test_vertex_budget_refuses_and_names_the_pack(pit, bl):
    """(iii) Over budget the read REFUSES, naming the pack, its objects,
    its vertices and its seconds — instead of 44 silent minutes."""
    dem = _FlatDem()
    cache = obj8.ResourceCache(bl.min_solid_thickness_m)
    cache.grade.vertex_budget = 1                      # a synthetic over-budget pack
    first = _placed(str(pit), "o0", (0.0, 0.0), 0.0, dem, bl)
    assert obj8.at_grade_geometry(first, cache, dem.z, bl.contact_band_m)[0] is not None
    assert cache.grade.over_budget
    later = _placed(str(pit), "o1", (500.0, 0.0), 0.0, dem, bl, agl=_AGL_APART)
    assert obj8.at_grade_geometry(later, cache, dem.z, bl.contact_band_m) == (None, None)
    assert obj8.above_grade_footprint(later, cache, dem.z, bl.contact_band_m) is None
    stats = _basins.BasinStats()
    _basins._record_grade(stats, cache, bl)
    assert stats.grade_calls == 3 and stats.grade_unions == 1
    assert stats.grade_geometry_s > 0.0 and stats.grade_vertices > 0
    assert len(stats.refused) == 1
    note = stats.refused[0]
    assert "at-grade read REFUSED over the vertex budget" in note
    assert cache.grade.pack() in note and "1 resources" in note
    assert "rim_read_vertex_budget = " in note


def test_the_budget_is_law_and_off_by_default(bl):
    """The law carries the budget, and production's value does not fire on
    the packs measured 2026-09-13 (VHHH's whole read is well under it)."""
    assert bl.rim_read_vertex_budget >= 40_000_000
    cache = obj8.ResourceCache(bl.min_solid_thickness_m)
    assert cache.grade.vertex_budget == 0 and not cache.grade.over_budget


def test_the_region_loop_retains_a_bounded_window():
    """(ii) The placement-frame geometries are a bounded window, never one
    per placement to the end of the pass."""
    lru = _basins._LRU(3)
    for i in range(10):
        lru.put(f"o{i}", (i,))
    assert len(lru._d) == 3 and lru.get("o0") is None and lru.get("o9") == (9,)
    lru.get("o7")                                       # a hit renews it
    lru.put("o10", (10,))
    assert lru.get("o7") == (7,) and lru.get("o8") is None


# ── round 2: the rim diagnostic never unions, and never materialises ─────
# every member's linework at once (owner 2026-09-13; measured at VHHH:
# `unary_union` over 96 rings' member linework 979.5 s, and basin:0's
# 60,402,378 LineStrings 96.4 s and 12.4 -> 34.9 GB).

def _sq(x0, y0, s):
    from shapely.geometry import Polygon as _P
    return _P([(x0, y0), (x0 + s, y0), (x0 + s, y0 + s), (x0, y0 + s)])


def test_the_rim_reading_is_the_minimum_over_the_members_not_their_union():
    """The predicate is unchanged: a station is closed when SOME member's
    linework lies within reach.  Three members, each covering one side of
    a square ring, close the same stations their union would."""
    from shapely.geometry import LineString
    from shapely.ops import unary_union
    ring = _sq(0.0, 0.0, 100.0)
    sides = [LineString([(0, 0), (100, 0)]), LineString([(100, 0), (100, 100)]),
             LineString([(100, 100), (0, 100)])]          # the west side is OPEN
    per_member = _basins._rim_open(ring, [_basins._rim_index(s) for s in sides], 5.0, 0.5)
    unioned = _basins._rim_open(ring, [_basins._rim_index(unary_union(sides))], 5.0, 0.5)
    assert per_member == unioned
    open_n, n, first = per_member
    assert 0 < open_n < n and first is not None
    assert first[0] == pytest.approx(0.0, abs=1e-6)        # on the open west side


def test_the_rim_indexes_are_built_lazily_one_member_at_a_time():
    """A member's index is built only when the walk reaches it, and never
    at all once every station is closed — the 60 M-object peak."""
    from shapely.geometry import LineString
    ring = _sq(0.0, 0.0, 100.0)
    closed = _basins._rim_index(LineString(list(ring.exterior.coords)))
    built = []

    def trees():
        for i in range(50):
            built.append(i)
            yield closed if i == 0 else _basins._rim_index(LineString([(1e6, 1e6), (1e6, 1e6 + 1)]))

    open_n, n, _first = _basins._rim_open(ring, trees(), 5.0, 0.5)
    assert open_n == 0 and n > 0
    assert built == [0], "the walk stopped as soon as every station was closed"


def test_the_region_loop_names_the_seconds_of_each_union_site():
    """The per-site union clock (owner 2026-09-13 round 2): 634 unions in
    `build_basins` cost VHHH 1,038 s under an aggregate no report named."""
    st: dict = {}
    n: dict = {}
    uu = _basins._UnionClock(st, n)
    u = uu("cover", [_sq(0.0, 0.0, 10.0), _sq(5.0, 0.0, 10.0)])
    assert u.area == pytest.approx(150.0)
    uu("cover", [_sq(0.0, 0.0, 1.0)])
    assert n == {"cover": 2} and st["cover"] >= 0.0
