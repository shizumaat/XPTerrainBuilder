"""#1638: A DUAL ROADWAY THROUGH THE AIRPORT IS ONE TRENCH AT ONE DEPTH
(``planar/dual_trench``; owner 2026-10-29, found at LFPG's Terminal 2 road
and KPHX's terminal road — the twins hold the general rule on a synthetic
field, never an airport).

Two carriageways of one road, 30 m apart, cross a field inside the
aerodrome boundary; each is mapped in short ways, some ``tunnel=yes``, some
on a viaduct, some at ``layer=-1``.  Between the first and the last
below-grade station the pair is ONE trench spanning both carriageways at ONE
floor (the cover beside it less the mouth depth), and every bore mouth inside it is
the trench's.  A single carriageway, a short run, a pair too far apart, a
run under a runway's strip or outside the boundary builds nothing of it."""
from __future__ import annotations

import pytest
from auto_patch_v2.classify.roles import Cell
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import Boundary, OsmWay
from auto_patch_v2.model.structures import profile_z
from auto_patch_v2.planar.dual_trench import (ID_PREFIX, _below_grade, absorb_mouths,
                                              dual_trench_groups, yield_groups)
from shapely.geometry import Point, Polygon

GROUND = 100.0
BOX = ((-3000.0, -3000.0), (3000.0, -3000.0), (3000.0, 3000.0), (-3000.0, 3000.0))


class _Dem:
    def z(self, x: float, y: float) -> float:
        return GROUND


class _Field:
    def __init__(self, ways, boundary=BOX):
        self.osm_ways = tuple(ways)
        self.dem = _Dem()
        self.boundaries = (Boundary("b", boundary, ()),) if boundary else ()
        self.icao = "ZZZZ"


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


#: one carriageway's pieces: (x0, x1, tags) — a tunnel, a viaduct, an open cut
PIECES = ((-2500.0, -800.0, {}), (-800.0, -600.0, {"tunnel": "yes", "layer": "-1"}),
          (-600.0, 0.0, {"bridge": "yes", "layer": "2"}),
          (0.0, 600.0, {"layer": "-1"}), (600.0, 700.0, {"tunnel": "yes", "layer": "-1"}),
          (700.0, 2500.0, {}))


def _carriageway(y: float, first_id: int, pieces=PIECES, cls="secondary"):
    return [OsmWay(first_id + k, "big_roads", ((x0, y), ((x0 + x1) / 2.0, y), (x1, y)), False,
                   {"highway": cls, **t}) for k, (x0, x1, t) in enumerate(pieces)]


def _dual(sep: float = 30.0, pieces=PIECES):
    return _carriageway(0.0, 100, pieces) + _carriageway(sep, 200, pieces)


def test_below_grade_reads_every_passage_under_something():
    def w(t):
        return OsmWay(1, "big_roads", ((0.0, 0.0), (1.0, 0.0)), False, {"highway": "primary", **t})
    assert _below_grade(w({"tunnel": "yes"})) and _below_grade(w({"tunnel": "building_passage"}))
    assert _below_grade(w({"covered": "yes"})) and _below_grade(w({"layer": "-1"}))
    assert not _below_grade(w({})) and not _below_grade(w({"tunnel": "no"}))
    assert not _below_grade(w({"bridge": "yes", "layer": "2"}))


def test_a_dual_roadway_is_one_trench_spanning_both_at_one_floor(law):
    d = dual_trench_groups(_Field(_dual()), law)
    assert not d.refused and len(d.notes) == 1 and "#1638" in d.notes[0]
    assert len(d.groups) == 2
    a, b = d.groups
    assert a.tid.startswith(ID_PREFIX) and a.sibling == b.tid and b.sibling == a.tid
    assert a.kind == "sunken_road" and not a.capped and not a.mouth_strip
    tn = law.tables.structures.tunnel
    floor = GROUND - tn.mouth_depth_m
    # ONE floor from the first below-grade station (x -800) to the last (x 700)
    for g in d.groups:
        flat = g.profile[1][0]
        assert profile_z(g.profile, 0.0) == pytest.approx(floor)
        assert profile_z(g.profile, flat) == pytest.approx(floor)
        assert flat >= 700.0                          # each half reaches its end of the run
        s_top, z_top = g.profile[-1]
        assert (z_top - floor) / (s_top - flat) <= tn.ramp_grade + 1e-9
    # the trench spans both carriageways and everything between them
    for x in (-700.0, -300.0, 300.0):
        for y in (0.0, 15.0, 30.0):
            assert d.footprint.contains(Point(x, y))
    half = a.half_fn(100.0)
    assert half[0] >= 15.0 + 3.0 and half[1] >= 15.0 + 3.0


def test_the_mouths_and_the_levels_inside_it_are_the_trenches(law):
    d = dual_trench_groups(_Field(_dual()), law)

    class _M:
        def __init__(self, xy, ways):
            self.xy, self.ways = xy, ways
    inside, outside = _M((-800.0, 0.0), (101,)), _M((-800.0, 400.0), (9,))
    kept, notes = absorb_mouths([inside, outside], d.footprint)
    assert kept == [outside] and len(notes) == 1 and "101" in notes[0]

    class _G:
        def __init__(self, axis, tid):
            self.axis, self.tid = axis, tid
    lvl, far = _G(((-500.0, 15.0), (-100.0, 15.0)), "viaduct-road:0"), \
        _G(((-500.0, 900.0), (-100.0, 900.0)), "viaduct-road:1")
    kept, out = yield_groups([lvl, far], d.footprint)
    assert kept == [far] and len(out) == 1 and "viaduct-road:0" in out[0]
    assert absorb_mouths([inside], None) == ([inside], [])       # no trench, nothing taken


def test_a_runway_strip_over_the_run_refuses_it_by_name(law):
    rw = Cell(1, "runway", "09/27", ((-200.0, -40.0), (200.0, -40.0), (200.0, 70.0),
                                     (-200.0, 70.0)), (), 4, "E", "airside", "runway", {})
    from auto_patch_v2.planar.structure_mouth import runway_strip
    strip = runway_strip((rw,), (Polygon(rw.ring),), law, ())
    d = dual_trench_groups(_Field(_dual()), law, strip)
    assert d.groups == () and d.footprint is None
    assert len(d.refused) == 1 and "runway strip" in d.refused[0]


@pytest.mark.parametrize("ways,boundary", [
    (_carriageway(0.0, 100), BOX),                                   # one carriageway
    (_dual(sep=400.0), BOX),                                         # two roads, not a pair
    (_dual(pieces=((-2500.0, -100.0, {}), (-100.0, 100.0, {"tunnel": "yes"}),
                   (100.0, 2500.0, {}))), BOX),                      # one short tunnel
    (_dual(), ((2800.0, 2800.0), (2900.0, 2800.0), (2900.0, 2900.0))),  # outside the field
    (_dual(), None),                                                 # no boundary at all
])
def test_no_witness_builds_nothing(law, ways, boundary):
    d = dual_trench_groups(_Field(ways, boundary), law)
    assert d.groups == () and d.notes == () and d.refused == ()


def test_each_trench_keeps_its_own_span(law):
    """Two dual roadways on one field: each trench's width is its own pair's
    (a late-bound width read the last pair's)."""
    narrow = _carriageway(0.0, 100) + _carriageway(20.0, 200)
    wide = _carriageway(1500.0, 300) + _carriageway(1620.0, 400)
    d = dual_trench_groups(_Field(narrow + wide), law)
    assert len(d.groups) == 4 and not d.refused
    spans = sorted(sum(g.half_fn(50.0)) for g in d.groups)
    assert spans[0] == pytest.approx(spans[1]) and spans[2] == pytest.approx(spans[3])
    assert 20.0 < spans[0] < 40.0 and 120.0 < spans[2] < 140.0
