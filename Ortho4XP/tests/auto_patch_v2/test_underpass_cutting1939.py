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
  mouth where the survey still reads the cut is built (round 2 R0: its ramp
  keeps the design grade, ``lidar_road.survey_design_grade``);
* round 2 R1: a class-K mouth stands on the deck's line through the
  outermost member end, its ring sheared onto it
  (``underpass_mouth.place_mouth`` / ``sheared_ring``).

Synthetic geometry only; law values read from the tables."""
from __future__ import annotations

import dataclasses
import math

import pytest
from auto_patch_v2.classify.roles import Cell
from auto_patch_v2.law import Law
from auto_patch_v2.planar import structure_underpass as _su
from auto_patch_v2.planar.dual_width import compose_half_fn
from auto_patch_v2.planar.lidar_road import (
    KEPT,
    SurveyMouth,
    mouth_verdict,
    survey_design_grade,
    surveyed_road,
)
from auto_patch_v2.planar.structure_mouth import member_lanes, mouth_stops
from auto_patch_v2.planar.structure_service import airside_cut_roles
from auto_patch_v2.planar.survey_cut import Cutting, cutting_of
from auto_patch_v2.planar.underpass_mouth import member_roads, place_mouth, sheared_ring
from shapely.geometry import LineString, Polygon


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


def test_a_kept_ramp_keeps_the_design_grade(law):
    """Round 2 R0 (the round-1 KEPT clause reverted): a KEPT mouth's ramp
    is planned at the design grade, flat survey or not -- a surveyed
    underpass mouth is class K (``underpass_mouth``), never a flatter ramp."""
    tn = law.tables.structures.tunnel

    def along(s):
        return (0.0, s)
    assert survey_design_grade(_CUT, law, along, _kept(), tn.ramp_grade,
                               tn.ramp_max_grade) == tn.ramp_grade
    steep = _Airport(lambda x, y: 24.0 + 0.2 * max(0.0, y))
    assert survey_design_grade(steep, law, along, _kept(), tn.ramp_grade,
                               tn.ramp_max_grade) == tn.ramp_grade


def _deck_group(angle_deg: float, xs=(-15.0, -5.0, 5.0, 15.0)):
    """Parallel carriageways (at ``xs``) running north, their south ends on
    a deck line at ``angle_deg`` off east-west through the origin; the mouth
    is the north side (outward +y)."""
    t = math.tan(math.radians(angle_deg))
    ms = []
    for x in xs:
        m = _Member(x, 7.0)
        y0 = 10.0 + t * x                  # the covered edge, parallel to the deck
        m.xy, m.inward = (x, y0), (0.0, -1.0)
        m.bore = _Bore([(x, y0 - 30.0), (x, y0)])
        m.approach = [(x, y0), (x, y0 + 300.0)]
        ms.append(m)
    deck = [(-60.0, -60.0 * t), (60.0, 60.0 * t)]
    y_out = max(m.xy[1] for m in ms)
    axis = LineString([(0.0, y_out), (0.0, y_out + 300.0)])
    return ms, deck, axis


def test_a_skewed_deck_shears_the_mouth_onto_its_line(law):
    """The deck crosses the roads at 59 deg (31 deg off square): the mouth
    edge runs parallel to the deck within 1 deg through the outermost
    member end, and the ring stands clear of the deck's pavement."""
    tn = law.tables.structures.tunnel
    grid = law.tables.emit.identity.min_distinct_spacing_m
    rim_off = tn.wall_gap_m + tn.wall_band_width_m
    ms, deck, axis = _deck_group(31.0)
    sk, ax, _note = place_mouth(deck, "-74", ms, axis, (0.0, -1.0), 19.0, rim_off, law)
    assert sk is not None and sk.sigma != 0.0
    end = max(ms, key=lambda m: m.xy[0] * -sk.e[1] + m.xy[1] * sk.e[0]).xy
    # the mouth on the axis lies on the deck's line through that end
    assert abs((ax.coords[0][0] - end[0]) * sk.e[1] - (ax.coords[0][1] - end[1]) * sk.e[0]) < 1e-6

    def fn(s, _ln=ax):
        q = _ln.interpolate(min(s, _ln.length))
        return (q.x, q.y)
    @dataclasses.dataclass
    class G:
        inward: tuple
        capped: bool = True
        far_capped: bool = False
        rim_fn: object = None
        cap_off: object = None
        far_off: object = None
    ring = sheared_ring(sk, None, fn, [0.0, 12.0], 19.0, rim_off, (0.0, -1.0), grid,
                        G((0.0, -1.0)))
    assert ring is not None
    (x0, y0), (x1, y1) = ring.right[0], ring.left[0]
    edge = math.degrees(math.atan2(y1 - y0, x1 - x0)) % 180.0
    assert abs(edge - 31.0) < 1.0 or abs(edge - 211.0) < 1.0
    deck_pav = LineString(deck).buffer(5.0)          # the deck's pavement up to the edge
    assert ring.ramp.distance(deck_pav) > 0.0


def test_a_square_crossing_keeps_the_square_ring(law):
    """Identity where the shear moves the ring's corner no more than
    ``wall_gap_m``: the square mouth stands."""
    tn = law.tables.structures.tunnel
    rim_off = tn.wall_gap_m + tn.wall_band_width_m
    ms, deck, axis = _deck_group(0.2)
    sk, ax, note = place_mouth(deck, "-74", ms, axis, (0.0, -1.0), 19.0, rim_off, law)
    assert sk is not None and sk.sigma == 0.0 and ax is axis and "square" in note


def _cross_fall(cover: float):
    """A cutting beyond the deck's covered edge (y = 10 + tan 31 . x): its
    floor 24.5 m west of x = 21 and 23.5 m east (a lower carriageway), the
    deck and its faces at ``cover`` inside the edge."""
    t = math.tan(math.radians(31.0))

    def z(x, y):
        if y < 10.0 + t * x - 1e-6 or abs(x) > 40.0:
            return cover
        return 23.5 if x >= 21.0 else 24.5
    return _Airport(z)


def test_the_aligned_read_finds_the_floor_the_square_window_misses(law):
    """#1939 R1 (spec author's ruling on the R1 gate): under a deck at a 59
    deg crossing the square window from the axis point never reaches the
    low east carriageway beyond the skewed edge within 12 m -- it reads 24.5
    and the mouth digs; the members' own reads outward from L find 23.5 and
    the one verdict (``lidar_road.mouth_verdict``) keeps it.  A truly shallow
    cutting is not KEPT under either read."""
    tn = law.tables.structures.tunnel
    rim_off = tn.wall_gap_m + tn.wall_band_width_m
    ms, deck, axis = _deck_group(31.0, (-15.0, -5.0, 8.0, 23.0))
    sk, ax, _n = place_mouth(deck, "-74", ms, axis, (0.0, -1.0), 25.0, rim_off, law)
    assert sk is not None and sk.sigma != 0.0

    def fn(s, _ln=ax):
        q = _ln.interpolate(min(s, _ln.length))
        return (q.x, q.y)
    deep = _cross_fall(31.0)
    square = surveyed_road(deep, fn, 50.0)
    assert square == pytest.approx(24.5)
    assert mouth_verdict(law, 31.0, square, True, False).verdict != KEPT
    reads = member_roads(deep, sk, ms)
    assert len(reads) == 4 and min(z for _t, z in reads) == pytest.approx(23.5)
    assert mouth_verdict(law, 31.0, min(z for _t, z in reads), True, False).verdict == KEPT
    shallow = _cross_fall(30.0)
    low = min(z for _t, z in member_roads(shallow, sk, ms))
    assert mouth_verdict(law, 30.0, low, True, False).verdict != KEPT


class _V:
    def __init__(self, xy, dem_z=None):
        self.xy, self.dem_z = xy, dem_z


class _F:
    def __init__(self, ring):
        self.ring = ring


class _Map:
    """A planar map's vertex / ring surface, enough for the pin writers."""

    def __init__(self, pts):
        self.vertices = {i: _V(p) for i, p in enumerate(pts)}

    def ring_vertices(self, ring):
        return tuple(ring)


class _Tn:
    def __init__(self, sf, axis, cap=None, cover=31.0, notes=()):
        self.survey_floor, self.axis = sf, axis
        self.cap_corners = None if cap is None else (cap[0], cap[-1])
        self.cap_centre = None if cap is None else cap[1]
        self.mouth_dem_z, self.notes = cover, notes


class _Face:
    def __init__(self, role):
        self.role = role


class _Vw:
    """The precedence view's surface ``_ground_carries`` reads."""

    def __init__(self, vertex_faces, roles):
        self.vertex_faces, self.caps = vertex_faces, {f: (0.02, 0.02) for f in roles}

    def side(self, role):
        return "airside" if role in ("apron", "primary_parallel") else "groundside"


def _k_ramp(top_roles, **targets):
    """A K ramp 0-1 (mouth edge) / 2-3 (top), the top vertices shared with
    faces 10 / 11 of ``top_roles``; ``targets`` are the map's channels."""
    pm = _Map([(-10.0, 0.0), (10.0, 0.0), (10.0, 12.0), (-10.0, 12.0)])
    pm.faces = {10: _Face(top_roles[0]), 11: _Face(top_roles[1])}
    for ch, d in targets.items():
        setattr(pm, ch, d)
    vw = _Vw({0: (1,), 1: (1,), 2: (1, 10), 3: (1, 11)},
             {10: top_roles[0], 11: top_roles[1]})
    return pm, vw


def _pin_k(pm, vw, shared):
    from auto_patch_v2.constraints.survey_floor import survey_floor_pins
    tn = _Tn((24.0, 0.05, (-10.0, 0.0), (10.0, 0.0)), ((0.0, 0.0), (0.0, 12.0)))
    pins = {}
    survey_floor_pins(pm, _Airport(lambda x, y: 30.0 + 0.0 * x), tn, [_F((0, 1, 2, 3))],
                      lambda v: v in shared, lambda v, z, src, senior=False: pins.__setitem__(v, z),
                      ("t",), 0.5, "structures", vw)
    return pins


def test_a_survey_floor_ramp_is_pinned_not_planned():
    """#1939 R2 / A1: the mouth-edge vertices at z0 + k.tau, a bare top
    vertex at the DEM, a top vertex an APRON shares left to the ground (A1
    (b): stage 1 owns it) -- and no other row kind is written."""
    pm, vw = _k_ramp(("apron", "service_road"))
    pins = _pin_k(pm, vw, {2})
    assert pins[0] == pytest.approx(24.0 - 0.5) and pins[1] == pytest.approx(24.5)
    assert pins[3] == pytest.approx(30.0) and 2 not in pins


def test_a_k_top_on_a_road_with_no_target_is_pinned_at_the_dem():
    """A1 (c): a top vertex only a groundside road shares, publishing no
    target there, is pinned at the DEM -- never left to the objective."""
    pm, vw = _k_ramp(("service_road", "parking_lot"))
    pins = _pin_k(pm, vw, {2, 3})
    assert pins[2] == pytest.approx(30.0) and pins[3] == pytest.approx(30.0)


def test_a_k_top_with_a_published_target_keeps_the_ground():
    """A1 (b): a road top with ``road_ramp_z`` (or ``preferred_z``) gets no
    row; one touching a taxiway gets none either."""
    pm, vw = _k_ramp(("service_road", "service_road"), road_ramp_z={2: 29.0},
                     preferred_z={3: 29.5})
    pins = _pin_k(pm, vw, {2, 3})
    assert 2 not in pins and 3 not in pins
    pm, vw = _k_ramp(("primary_parallel", "service_road"))
    pins = _pin_k(pm, vw, {2, 3})
    assert 2 not in pins and pins[3] == pytest.approx(30.0)


def test_no_k_ramp_vertex_is_ungoverned():
    """A1 coverage: after ``survey_floor_pins`` every K ramp vertex is
    pinned or carried by a target / an airside face."""
    from auto_patch_v2.constraints.survey_floor import _ground_carries
    for roles, tg in ((("service_road", "parking_lot"), {}),
                      (("apron", "service_road"), {"taxi_trend_z": {3: 28.0}})):
        pm, vw = _k_ramp(roles, **tg)
        pins = _pin_k(pm, vw, {2, 3})
        assert all(v in pins or _ground_carries(pm, vw, v) for v in range(4))


def test_a_k_cap_stands_at_the_cover():
    """#1939 R3: a bare rim vertex on the cap line is pinned at the cover;
    one off it at the DEM; one the ground shares keeps the ground's value."""
    from auto_patch_v2.constraints.structures import _rim_rows
    from auto_patch_v2.constraints.survey_floor import cap_line
    pm = _Map([(-12.0, -2.0), (0.0, -2.0), (12.0, -2.0), (-12.0, 10.0)])
    tn = _Tn((24.0, 0.0, (-10.0, 0.0), (10.0, 0.0)), ((0.0, 0.0), (0.0, 12.0)),
             cap=[(-12.0, -2.0), (0.0, -2.0), (12.0, -2.0)], cover=31.3)
    pins = {}
    path = LineString([(-12.0, 10.0), (-12.0, -2.0), (0.0, -2.0), (12.0, -2.0), (12.0, 10.0)])
    _rim_rows(pm, _Airport(lambda x, y: 27.0), path, [0, 1, 2, 3], lambda v: v == 2,
              lambda v, z, src, senior=False: pins.__setitem__(v, z), None,
              cap=cap_line(tn), grid=0.5)
    assert pins[0] == pins[1] == pytest.approx(31.3)
    assert pins[3] == pytest.approx(27.0) and 2 not in pins


def test_the_under_deck_band_cuts_the_roads_through_the_mouth(law):
    """#1939 R4: a groundside road through the mouth (meeting the band and
    the ramp) is cut by the band; a road along the deck (in the band, never
    meeting the ramp) and the airside deck are kept."""
    from auto_patch_v2.planar.underpass_mouth import under_deck_band, under_deck_blade

    class M:
        bore = _Bore([(0.0, 0.0), (0.0, -40.0)])
    band = under_deck_band([(-20.0, -2.0), (0.0, -2.0), (20.0, -2.0)], (0.0, -1.0), [M()])
    ramp = Polygon(_rect(-15, 0, 15, 12))
    through = _cell(0, "service_road", "r1", _rect(-3, -30, 3, 40), "road", "groundside")
    along = _cell(1, "service_road", "r2", _rect(-18, -15, 18, -10), "road", "groundside")
    deck = _cell(2, "primary_parallel", "pav24", _rect(-30, -18, 30, -6))
    blade = under_deck_blade(through, Polygon(through.ring), law, [(band, ramp)])
    assert blade is not None and blade.equals(band)
    assert under_deck_blade(along, Polygon(along.ring), law, [(band, ramp)]) is None
    assert under_deck_blade(deck, Polygon(deck.ring), law, [(band, ramp)]) is None


def test_bore_ground_reads_the_floor_between_two_k_mouths(law):
    """#1939 R5: between the two K mouths of one deck a road sample reads
    the floor interpolated across (lower only); outside the span and with
    no K tunnel the sampler is the identity."""
    import numpy as np
    from auto_patch_v2.airport.bore_ground import bore_sampler, bore_spans
    from auto_patch_v2.model.structures import UNDERPASS_NOTE
    north = _Tn((24.0, 0.0, (10.0, 20.0), (-10.0, 20.0)), ((0.0, 20.0), (0.0, 32.0)),
                notes=(UNDERPASS_NOTE + "-74",))
    south = _Tn((25.0, 0.0, (-10.0, -20.0), (10.0, -20.0)), ((0.0, -20.0), (0.0, -32.0)),
                notes=(UNDERPASS_NOTE + "-74",))
    spans = bore_spans([north, south], law)
    assert len(spans) == 1

    def deck(xs, ys):
        return np.full(len(np.atleast_1d(xs)), 31.0)
    f = bore_sampler(deck, spans)
    got = f(np.array([0.0, 0.0, 0.0, 100.0]), np.array([0.0, 10.0, 20.0, 0.0]))
    assert got[0] == pytest.approx(24.5) and got[1] == pytest.approx(24.25)
    assert got[2] == pytest.approx(24.0) and got[3] == pytest.approx(31.0)
    low = bore_sampler(lambda xs, ys: np.full(len(np.atleast_1d(xs)), 20.0), spans)
    assert low(np.array([0.0]), np.array([0.0]))[0] == pytest.approx(20.0)
    assert bore_sampler(deck, bore_spans([], law)) is deck
