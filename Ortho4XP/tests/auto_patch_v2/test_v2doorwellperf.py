"""A WINDOWED OBJ8 READ IS THE MEMOISED WHOLE-OBJECT READ, INTERSECTED
(owner RULINGS 2026-09-17k (a), lane ``v2doorwellperf``).

``above_grade_footprint(within=...)`` and ``at_grade_geometry(within=...)``
had their OWN branch: per call, per component, ``v[comp.tris]``
materialised twice, ``_clip_component``, NO memo and NO
``rim_read_vertex_budget``.  On OTHH's 2026-09-16 pack (14,218 placements
over 1,247 resources) ``read_door_wells`` asks that branch once per
(well, placement within ``[cutout.door] max_length_m``): 56:40 and 25.8 GB
RSS without reaching a structure stage — the production tile build pays
the same reader (``planar/build.py``).

The clip plane of a component does not depend on the window, so the
windowed read IS the whole-object read intersected with the window.  The
three assertions are the ruling's: geometry equality, a bounded number of
clips however many windows ask, and the budget refusal reaching the
windowed caller too.
"""
from __future__ import annotations

import pytest
from shapely.geometry import box

from auto_patch_v2.airport import obj8
from auto_patch_v2.law import Law

from test_m4b import _two_box_obj                                # noqa: E402


class _FlatDem:
    z0 = 700.0

    def z(self, x: float, y: float) -> float:
        return self.z0


#: the frame window: it CUTS box A (authored x -20..-10) at x = -12 and
#: misses box B entirely — the case the old branch got wrong, because
#: ``_windowed`` kept whole triangles whose plan bbox overlapped and never
#: intersected the result with the window itself
_WINDOW = box(-20.0, -5.0, -12.0, 5.0)


@pytest.fixture(scope="module")
def bl():
    return Law.for_airport("ZZZZ").tables.structures.basin


@pytest.fixture(scope="module")
def pair(tmp_path_factory):
    """One OBJ8, TWO components: 10 x 10 m lidded boxes 3 m proud of the
    authored datum, centred at authored x = -15 and x = +15."""
    d = tmp_path_factory.mktemp("doorwellperf")
    common = dict(hx=5.0, hz=5.0, depth=6.0, top=3.0, lid=True)
    return _two_box_obj(d / "pair.obj", dict(cx=-15.0, **common), dict(cx=15.0, **common))


def _placed(path, oid, xy, dem, bl, agl=None) -> obj8.PlacedObject:
    rows = [(oid, "objects/pair.obj", xy, 0.0, agl,
             "OBJECT_AGL" if agl is not None else "OBJECT")]
    got, _rep = obj8.read_placed_objects(
        rows, None, {"objects/pair.obj": str(path)}, dem.z, bl.admission_depth_m,
        bl.min_solid_thickness_m, bl.contact_band_m,
        floor_plate_normal_y_min=bl.floor_plate_normal_y_min)
    return got[0]


def _same(a, b) -> bool:
    if a is None or b is None:
        return a is None and b is None
    return a.symmetric_difference(b).area < 1e-9


def test_the_windowed_cover_read_is_the_whole_read_intersected(pair, bl):
    """The geometry bar: ``above_grade_footprint(within=w)`` == the whole
    read ∩ w, exactly — including where the window cuts a triangle."""
    dem = _FlatDem()
    cache = obj8.ResourceCache(bl.min_solid_thickness_m)
    o = _placed(pair, "o0", (0.0, 0.0), dem, bl)
    whole = obj8.above_grade_footprint(o, cache, dem.z, bl.contact_band_m)
    assert whole is not None and whole.area == pytest.approx(200.0, abs=1e-6), \
        "two 10 x 10 m boxes stand above the contact band"
    got = obj8.above_grade_footprint(o, cache, dem.z, bl.contact_band_m, within=_WINDOW)
    assert got is not None
    assert _same(got, whole.intersection(_WINDOW))
    assert got.area == pytest.approx(80.0, abs=1e-6), \
        "the window keeps 8 of box A's 10 m and none of box B"


def test_the_windowed_at_grade_read_is_the_whole_read_intersected(pair, bl):
    """The same for ``at_grade_geometry`` — linework and polygons."""
    dem = _FlatDem()
    cache = obj8.ResourceCache(bl.min_solid_thickness_m)
    o = _placed(pair, "o0", (0.0, 0.0), dem, bl)
    wl, wp = obj8.at_grade_geometry(o, cache, dem.z, bl.contact_band_m)
    gl, gp = obj8.at_grade_geometry(o, cache, dem.z, bl.contact_band_m, within=_WINDOW)
    assert wp is not None and gp is not None
    assert _same(gp, wp.intersection(_WINDOW))
    assert wl is not None and gl is not None
    assert gl.difference(_WINDOW).length < 1e-9
    assert gl.length == pytest.approx(wl.intersection(_WINDOW).length, abs=1e-9)


def test_many_windows_clip_the_resource_once(pair, bl):
    """The cost bar: N placements × their own windows pay ONE clip+union
    per (resource, planes) — the memo the unwindowed branch always had.
    On the defect this reads ``unions == 0`` (the windowed branch was not
    even counted) and clips 2 components per placement."""
    dem = _FlatDem()
    cache = obj8.ResourceCache(bl.min_solid_thickness_m)
    placed = [_placed(pair, f"o{i}", (300.0 * i, 0.0), dem, bl) for i in range(6)]
    for i, o in enumerate(placed):
        w = box(300.0 * i - 20.0, -5.0, 300.0 * i - 12.0, 5.0)
        got = obj8.above_grade_footprint(o, cache, dem.z, bl.contact_band_m, within=w)
        assert got is not None and got.area == pytest.approx(80.0, abs=1e-6)
    assert cache.grade.calls == 6
    assert cache.grade.unions == 1, "one clip + union for the whole resource, not one per window"
    # the window is applied at COMPONENT granularity: box B never overlaps
    # any of the six windows, so it is never clipped at all, and box A is
    # clipped ONCE for all six (the per-component memo is window-free)
    assert len(cache.clip_memo) == 1, "one entry per component reached, not per placement"


def test_the_vertex_budget_reaches_the_windowed_caller(pair, bl):
    """The refusal bar (RULINGS 2026-09-13bp (iii)): past the budget the
    windowed read stops too, instead of 56 silent minutes."""
    dem = _FlatDem()
    cache = obj8.ResourceCache(bl.min_solid_thickness_m)
    cache.grade.vertex_budget = 1
    first = _placed(pair, "o0", (0.0, 0.0), dem, bl)
    assert obj8.above_grade_footprint(first, cache, dem.z, bl.contact_band_m,
                                      within=_WINDOW) is not None
    assert cache.grade.over_budget
    # a different AGL is a different clip plane, so a different memo key:
    # the REFUSAL is what must reach the windowed caller, not a memo hit
    later = _placed(pair, "o1", (0.0, 400.0), dem, bl, agl=3.0)
    assert obj8.above_grade_footprint(later, cache, dem.z, bl.contact_band_m,
                                      within=box(-20.0, 395.0, -12.0, 405.0)) is None
    assert obj8.at_grade_geometry(later, cache, dem.z, bl.contact_band_m,
                                  within=box(-20.0, 395.0, -12.0, 405.0)) == (None, None)


def test_a_select_still_reads_only_its_components_and_is_memoised(pair, bl):
    """``door_wells.shell`` / ``building`` pass a ``select``: it keeps the
    components it accepts (the result is the resource's, so it keys the
    same memo) — one union per distinct selected set."""
    dem = _FlatDem()
    cache = obj8.ResourceCache(bl.min_solid_thickness_m)
    placed = [_placed(pair, f"o{i}", (300.0 * i, 0.0), dem, bl) for i in range(4)]
    west = [obj8.at_grade_geometry(o, cache, dem.z, bl.contact_band_m,
                                   select=lambda c: c.cx < 0.0)[1] for o in placed]
    assert all(p is not None and p.area == pytest.approx(100.0, abs=1e-6) for p in west)
    assert cache.grade.unions == 1
    both = obj8.at_grade_geometry(placed[0], cache, dem.z, bl.contact_band_m)[1]
    assert both.area == pytest.approx(200.0, abs=1e-6)
    assert cache.grade.unions == 2, "a different component set is a different key"
