"""Twins for issue #1629 — A DUAL CARRIAGEWAY THAT SPLITS INTO TWO BORES
(``planar/structure_approach._parallel``, ``planar/structure_mouth``).

Measured at a field where one road splits 31 m before two portals 10 m
apart: 31h's test refused the pair as a dual (the carriageways CLOSE their
separation on the approach), one bore was built alone, its mouth slid out
of its sibling's carriageway and was held at bore depth beneath it, and the
two carriageways stood at grade on the roof up to the portal — a 7.2 m
step and two stray road pieces.  Three rules, one twin each:

* converging approaches are a dual (only PARTING ones are two roads);
* a mouth slides out of the runway strip keep-out as out of pavement;
* a slid mouth's covered stretch cuts the ramp's own road there;
* a road crossing over the bore at its mouth is the mouth's deck (owner
  Q286): the mouth stops just short of it, and the strip keep-out neither
  pushes it back nor refuses it.

Law values are read from the tables, never retyped."""
from __future__ import annotations

import pytest
from shapely.geometry import LineString, Polygon

from auto_patch_v2.classify.roles import Cell, Classification
from auto_patch_v2.law import Law
from auto_patch_v2.law.tables import zone2_half_width_m
from auto_patch_v2.model.airport import Airport, OsmWay, Runway, RunwayEnd, SceneryPack
from auto_patch_v2.model.frame import Frame
from auto_patch_v2.planar.structure_approach import Mouth, merge_duals
from auto_patch_v2.planar.structure_mouth import (covered_stretch, own_road_blade,
                                                   road_over_mouth)
from auto_patch_v2.planar.structures import build_structures


class _FlatDem:
    provenance = {"synthetic": "flat 700 m"}

    def z(self, x: float, y: float) -> float:
        return 700.0

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)


class _Stats:
    duals_merged = 0


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


def _mouth(y: float, approach, bore=None) -> Mouth:
    return Mouth(bore if bore is not None else object(), (0.0, y), (1.0, 0.0), 7.0,
                 list(approach), (int(y),))


def test_converging_carriageways_are_one_dual(law):
    """Two portals 10 m apart whose carriageways rejoin one road 30 m out
    merge; two whose roads PART (40 m apart 50 m out) stay two."""
    conv = [_mouth(-5.0, [(0.0, -5.0), (-30.0, 0.0), (-300.0, 0.0)]),
            _mouth(5.0, [(0.0, 5.0), (-30.0, 0.0), (-300.0, 0.0)])]
    got = merge_duals(conv, law, _Stats())
    assert len(got) == 1 and len(got[0][0]) == 2
    part = [_mouth(-5.0, [(0.0, -5.0), (-50.0, -25.0), (-300.0, -25.0)]),
            _mouth(5.0, [(0.0, 5.0), (-50.0, 25.0), (-300.0, 25.0)])]
    assert len(merge_duals(part, law, _Stats())) == 2


def test_covered_stretch_cuts_only_the_ramps_own_road(law):
    """The stretch between the mapped portal (x = 0) and the slid mouth
    (x = -20) cuts the carriageway the route runs along, never a road the
    route crosses nor an airside face."""
    grid = law.tables.emit.identity.min_distinct_spacing_m
    portal = LineString([(0.0, 0.0), (-300.0, 0.0)])
    slid = LineString([(-20.0, 0.0), (-300.0, 0.0)])
    stretch = covered_stretch(portal, slid, [portal], 6.0, grid)
    assert stretch is not None and stretch[0].area == pytest.approx(20.0 * 12.0, rel=1e-6)
    assert covered_stretch(portal, portal, [portal], 6.0, grid) is None
    own = Cell(0, "service_road", "own", ((-60, -4), (5, -4), (5, 4), (-60, 4)), (), None,
               None, "groundside", "road", {})
    across = Cell(1, "service_road", "x", ((-12, -40), (-8, -40), (-8, 40), (-12, 40)), (),
                  None, None, "groundside", "road", {})
    apron = Cell(2, "apron", "ap", ((-60, -4), (5, -4), (5, 4), (-60, 4)), (), None, None,
                 "airside", "apron", {})
    for c, want in ((own, True), (across, False), (apron, False)):
        blade = own_road_blade(c, Polygon(c.ring), law, [stretch], grid)
        assert (blade is not None) is want, c.ref


def _airport(law, hw: float):
    """A dual bore x in [0, 400] at y = +-5 under a runway whose strip
    reaches 10 m west of the west portals; the carriageways rejoin one
    road 30 m west of them."""
    t = {"highway": "primary", "tunnel": "yes", "lanes": "2", "layer": "-1"}
    r = {"highway": "primary", "lanes": "2"}
    ways = (OsmWay(-101, "big_roads", ((0.0, -5.0), (400.0, -5.0)), False, t),
            OsmWay(-102, "big_roads", ((400.0, 5.0), (0.0, 5.0)), False, t),
            OsmWay(-201, "big_roads", ((-30.0, 0.0), (0.0, -5.0)), False, r),
            OsmWay(-202, "big_roads", ((0.0, 5.0), (-30.0, 0.0)), False, r),
            OsmWay(-203, "big_roads", ((-900.0, 0.0), (-30.0, 0.0)), False, r))
    x0 = -10.0 + hw
    frame = Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11)
    ends = (RunwayEnd("09", (x0, 0.0), (60.5, -135.5), 0.0, 0.0, 700.0, "fixture"),
            RunwayEnd("27", (x0 + 1800.0, 0.0), (60.5, -135.5), 0.0, 0.0, 700.0, "fixture"))
    rw = Runway("09/27", 45.0, 1, ends, 3, "D")
    pack = SceneryPack("fixture", "apt.dat", "0", (), ())
    return Airport("ZZZZ", "Synthetic", frame, 700.0, (rw,), (), (), {}, (),
                   (), (), (), ways, (), (), pack, _FlatDem(), law.ruleset_key), x0


def test_the_mouth_slides_out_of_the_strip_and_its_roof_carries_no_road(law):
    """The west portals stand inside the runway strip keep-out: the dual is
    built (once refused outright), its mouth slid west clear of the strip,
    and the carriageway pieces between the slid mouth and the portals are
    cut — no road stands at grade on the bore's roof."""
    hw = max(zone2_half_width_m(law, "runway", 3, "D", s) for s in (0, 1))
    assert hw
    airport, x0 = _airport(law, hw)
    cells = [Cell(0, "runway", "09/27", ((x0, -22.5), (x0 + 1800, -22.5), (x0 + 1800, 22.5),
                                         (x0, 22.5)), (), 3, "D", "airside", "runway", {}),
             Cell(1, "service_road", "big_roads:-201",
                  ((-30, -3.5), (0, -8.5), (0, -1.5), (-30, 3.5)), (), None, None,
                  "groundside", "road", {}),
             Cell(2, "service_road", "big_roads:-202",
                  ((-30, -3.5), (0, 1.5), (0, 8.5), (-30, 3.5)), (), None, None,
                  "groundside", "road", {})]
    cl = Classification(tuple(cells), (), {}, ())
    cl2, tunnels, st = build_structures(airport, cl, law)
    west = [t for t in tunnels if t.axis[0][0] < 100.0]
    assert len(west) == 1, st.refused
    t = west[0]
    assert set(t.ways) == {-101, -102}                       # one dual ramp
    assert t.axis[0][0] < -10.0                              # clear of the strip
    roof = Polygon([(t.axis[0][0] + 1.0, -9), (0, -9), (0, 9), (t.axis[0][0] + 1.0, 9)])
    on_roof = sum(Polygon(c.ring, c.holes).intersection(roof).area for c in cl2.cells
                  if c.ref.split("#")[0] in ("big_roads:-201", "big_roads:-202"))
    assert on_roof < 1.0


def test_a_road_over_the_mouth_is_found_the_approach_road_is_not():
    """``road_over_mouth``: a road the bore passes under and out beyond, at
    the mouth, decks it; the approach road that holds the mouth does not,
    nor a road the bore ends inside."""
    bore = LineString([(0.0, 0.0), (400.0, 0.0)])
    over = Cell(0, "service_road", "over", ((2, -60), (7, -60), (7, 60), (2, 60)), (), None,
                None, "groundside", "road", {})
    own = Cell(1, "service_road", "own", ((-60, -4), (1, -4), (1, 4), (-60, 4)), (), None,
               None, "groundside", "road", {})
    far = Cell(2, "service_road", "far", ((60, -60), (65, -60), (65, 60), (60, 60)), (), None,
               None, "groundside", "road", {})
    cells = [own, far, over]
    polys = [Polygon(c.ring) for c in cells]
    assert road_over_mouth([bore], (0.0, 0.0), cells, polys, 12.0) == "over"
    assert road_over_mouth([bore], (0.0, 0.0), cells[:2], polys[:2], 12.0) == ""


def test_a_road_over_the_mouth_holds_it_inside_the_strip(law):
    """Owner Q286: a service road crossing over the bores 2 m inside the
    portals, within the strip keep-out.  The dual's mouth stops just short
    of the road (never pushed out of the strip), and is built there."""
    hw = max(zone2_half_width_m(law, "runway", 3, "D", s) for s in (0, 1))
    airport, x0 = _airport(law, hw)
    tn = law.tables.structures.tunnel
    cells = [Cell(0, "runway", "09/27", ((x0, -22.5), (x0 + 1800, -22.5), (x0 + 1800, 22.5),
                                         (x0, 22.5)), (), 3, "D", "airside", "runway", {}),
             Cell(1, "service_road", "deck", ((2, -80), (8, -80), (8, 80), (2, 80)), (), None,
                  None, "groundside", "road", {})]
    cl = Classification(tuple(cells), (), {}, ())
    _cl2, tunnels, st = build_structures(airport, cl, law)
    west = [t for t in tunnels if t.axis[0][0] < 100.0]
    assert len(west) == 1, st.refused
    reach = 2.0 * (tn.wall_gap_m + tn.wall_band_width_m) + tn.wall_gap_m
    assert -reach - 1.0 <= west[0].axis[0][0] <= 0.0          # just short of the road
    assert any("deck" in n for n in st.portals_in_strip), st.portals_in_strip
