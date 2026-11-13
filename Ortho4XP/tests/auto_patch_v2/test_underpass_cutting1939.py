"""Twins for #1939 (ESSA, roads in a surveyed cutting under taxiway U's
bridge): one wide mouth spanning every carriageway the deck crosses.

* the deck's kerbs are its PAVEMENT's, never a role seam inside it
  (``structure_underpass._PavementOf``): a seam across the axis does not
  pinch the clip ribbon, so every road under the deck is bored;
* a dual's member carriageways are its own roads however short the stub
  (``structure_mouth.member_lanes``);
* a dual's ramp is never narrowed below its carriageways by the pavement
  one of them traces (``dual_width.compose_half_fn(wide=True)``);
* a KEPT survey mouth opens into the surveyed cutting
  (``survey_cut.Cutting``): pavement on the cutting floor is no stop, a slid
  mouth where the survey still reads the cut is built, and its ramp lies on
  the survey (``lidar_road.survey_design_grade``).

Synthetic geometry only; law values read from the tables."""
from __future__ import annotations

import pytest
from shapely.geometry import LineString, Polygon

from auto_patch_v2.classify.roles import Cell
from auto_patch_v2.law import Law
from auto_patch_v2.planar import structure_underpass as _su
from auto_patch_v2.planar.dual_width import compose_half_fn
from auto_patch_v2.planar.lidar_road import KEPT, SurveyMouth, survey_design_grade
from auto_patch_v2.planar.structure_mouth import member_lanes, mouth_stops
from auto_patch_v2.planar.structure_service import airside_cut_roles
from auto_patch_v2.planar.survey_cut import Cutting, cutting_of


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


def _rect(x0, y0, x1, y1):
    return ((x0, y0), (x1, y0), (x1, y1), (x0, y1))


def _cell(i, role, ref, ring, kind="corridor", side="airside"):
    return Cell(i, role, ref, ring, (), None, "E", side, kind, {})


class _Dem:
    """A survey: ``fn(x, y)`` metres."""
    provenance = {"synthetic": "survey"}

    def __init__(self, fn):
        self._fn = fn

    def z(self, x: float, y: float) -> float:
        return self._fn(x, y)

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)


class _Airport:
    def __init__(self, fn):
        self.dem = _Dem(fn)


#: a cutting: the floor at 24 m for |x| <= 30, the ground at 31 m beyond
_CUT = _Airport(lambda x, y: 24.0 if abs(x) <= 30.0 else 31.0)


def test_a_role_seam_across_the_deck_is_no_kerb():
    """Two role pieces of ONE pavement meet on the deck's axis, their seam
    oblique to it: the kerb rays read the pavement's edges (+-12 m), never
    the seam -- the per-station offsets never pinch below the pavement."""
    a = _cell(0, "cross_connector", "pav1", ((-60, -12), (5, -12), (-5, 12), (-60, 12)))
    b = _cell(1, "primary_parallel", "pav1", ((5, -12), (60, -12), (60, 12), (-5, 12)))
    cells, polys = [a, b], [Polygon(a.ring), Polygon(b.ring)]
    ss = [float(s) for s in range(1, 100, 2)]        # (a station ON the seam reads no cell)
    offs, half, n_read, _ref = _su._deck_cell(lambda s: (s - 50.0, 0.0), ss, cells, polys,
                                              3.5, 200.0)
    assert n_read == len(ss)
    assert half == pytest.approx(12.0, abs=1e-6)
    assert min(min(hl, hr) for _s, hl, hr in offs) == pytest.approx(12.0, abs=1e-6)


def test_a_piece_the_axis_never_enters_keeps_its_seam():
    """An apron cut from the same pavement beside the taxiway: the axis
    never enters it, so its seam stays the taxiway's kerb."""
    taxi = _cell(0, "primary_parallel", "pav1", _rect(-60, -12, 60, 12))
    apron = _cell(1, "apron", "pav1", _rect(-60, 12, 60, 90))
    cells, polys = [taxi, apron], [Polygon(taxi.ring), Polygon(apron.ring)]
    ss = [float(s) for s in range(0, 101, 5)]
    _offs, half, _n, _r = _su._deck_cell(lambda s: (s - 50.0, 0.0), ss, cells, polys, 3.5,
                                         200.0)
    assert half == pytest.approx(12.0, abs=1e-6)


class _Bore:
    def __init__(self, pts):
        self.points = pts


class _Member:
    def __init__(self, x, width):
        self.bore = _Bore([(x, -40.0), (x, 0.0)])
        self.approach = [(x, 0.0), (x, 300.0)]
        self.width_m = width


class _Group:
    def __init__(self, members):
        self.members = members


def test_a_members_short_stub_is_its_own_road(law):
    """A dual of two carriageways 20 m apart; each member's road face is a
    2 m stub at the mouth (shorter than it is wide).  Neither stops the
    dual's mouth; a road CROSSING the lanes still does."""
    grid = law.tables.emit.identity.min_distinct_spacing_m
    tn = law.tables.structures.tunnel
    rim_off = tn.wall_gap_m + tn.wall_band_width_m
    lanes = member_lanes(_Group([_Member(-10.0, 7.0), _Member(10.0, 7.0)]), rim_off, grid,
                         tn.wall_gap_m)
    cells = [_cell(0, "service_road", "stubW", _rect(-13.5, 0, -6.5, 2), "road", "groundside"),
             _cell(1, "service_road", "stubE", _rect(6.5, 0, 13.5, 2), "road", "groundside"),
             _cell(2, "service_road", "cross", _rect(-80, 20, 80, 27), "road", "groundside")]
    polys = [Polygon(c.ring) for c in cells]
    axis = LineString([(0.0, 0.0), (0.0, 300.0)])
    got = mouth_stops(cells, polys, law, airside_cut_roles(law), axis, (0.0, 0.0), 13.5,
                      rim_off, (), grid, (), lanes)
    assert [r for _p, r in got] == ["cross"]
    assert member_lanes(_Group([_Member(0.0, 7.0)]), rim_off, grid) is None


def test_a_dual_trace_never_narrows_its_carriageways():
    """The pavement a dual's mean axis traces is one carriageway's ribbon:
    with ``wide`` the dual's reading stands where it is wider, the trace
    where IT is; a single bore keeps the trace (unchanged)."""
    pav = {0.0: (2.0, 9.0), 12.0: (1.5, 4.2)}

    def dual(s):
        return (24.0, 22.0)
    wide = compose_half_fn(pav, dual, 22.5, None, True)
    assert wide(0.0) == (24.0, 22.0) and wide(12.0) == (24.0, 22.0)
    assert compose_half_fn({0.0: (30.0, 1.0)}, dual, 22.5, None, True)(0.0) == (30.0, 22.0)
    single = compose_half_fn(pav, None, 3.5, None)
    assert single(12.0) == (1.5, 4.2) and single(5.0) == (3.5, 3.5)


def _kept():
    return SurveyMouth(cover=31.0, road=24.0, owed=7.5, floor=24.0, paved=True, rail=False,
                       verdict=KEPT)


def test_pavement_on_the_cutting_floor_is_no_stop(law):
    """A KEPT mouth's cutting: a lot on the floor (24 m) beside the mouth is
    the cutting's own; a lot on the ground above (31 m) still stops; a
    mouth that digs has no cutting."""
    cut = cutting_of(_CUT, law, _kept(), 10.0)
    assert isinstance(cut, Cutting) and cut.mid == pytest.approx(27.5)
    floor_lot = Polygon(_rect(12, 0, 28, 40))
    ground_lot = Polygon(_rect(34, 0, 60, 40))
    assert cut.floor_face(floor_lot, (0.0, 0.0), 40.0)
    assert not cut.floor_face(ground_lot, (0.0, 0.0), 40.0)
    assert not cut.floor_face(floor_lot, (0.0, 500.0), 40.0)          # not beside the mouth
    dug = SurveyMouth(31.0, 24.0, 7.5, 23.5, True, False, "")
    assert cutting_of(_CUT, law, dug, 10.0) is None


def test_a_slid_mouth_in_the_cut_is_built_at_the_surveyed_road(law):
    """Slid along the cutting: the survey still reads 7 m of cut there and
    the mouth stands at the surveyed road.  Out of the cutting (the ground
    flat at the road): no cut, refused as before."""
    axis = LineString([(0.0, 50.0), (0.0, 400.0)])
    assert cutting_of(_CUT, law, _kept(), 10.0).slid_floor(axis) == pytest.approx(24.0)
    flat = _Airport(lambda x, y: 24.0)
    assert cutting_of(flat, law, _kept(), 10.0).slid_floor(axis) is None


def test_a_kept_ramp_lies_on_the_survey(law):
    """A KEPT mouth on a flat cutting floor: its ramp is built at the
    survey's own grade (0), never the design grade over it; where the
    survey climbs faster than the design grade the design grade stands."""
    tn = law.tables.structures.tunnel

    def along(s):
        return (0.0, s)
    assert survey_design_grade(_CUT, law, along, _kept(), tn.ramp_grade,
                               tn.ramp_max_grade) == 0.0
    steep = _Airport(lambda x, y: 24.0 + 0.2 * max(0.0, y))
    assert survey_design_grade(steep, law, along, _kept(), tn.ramp_grade,
                               tn.ramp_max_grade) == tn.ramp_grade
