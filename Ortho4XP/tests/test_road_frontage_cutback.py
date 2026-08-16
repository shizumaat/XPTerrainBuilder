"""R7b CLAUSE 3 — PARALLEL FRONTAGE CUTS BACK TO DEM.

Owner ruling 2026-08-15 late (the sink ruling, docs/RULINGS.md):

    "A road running PARALLEL to an apron for more than 1.5x the road's
    width takes the STANDARD GROUNDSIDE CUTBACK and stays AT DEM —
    roads commonly run up to and along terminals at DIFFERENT LEVELS
    (at CYXY the landside frontage road is a second-story level several
    metres above the airside apron; that separation is real and must be
    preserved, not welded away)."

Fable amendment A2 rules the mechanism GEOMETRIC and names the machinery:
``groundside._separate_groundside_from_airside``'s clearance buffer, its
mouth windows and its DEM re-follow, applied to the ROAD face.  A road
that no longer shares a node with the apron cannot be welded to it — so
clause 1 ("welds at MOUTHS only") and clause 3 are one geometry read from
two sides, which is why the mouth windows are the exemption here too.

Hermetic: hand-built geometry, a constant DEM callable, no fixtures.
"""
import pytest
from shapely.geometry import Polygon

from auto_patch.groundside import (
    GROUNDSIDE_CLEARANCE_M, ROAD_FRONTAGE_SPAN_WIDTH_FACTOR,
    _cut_back_road_frontage, _face_carriageway_width,
    _longest_contact_run_m, _separate_groundside_from_airside)
from auto_patch.layout import (
    BuiltShape, PavementLayout, ROLE_APRON, ROLE_JUNCTION,
    ROLE_SERVICE_JUNCTION, ROLE_SERVICE_ROAD)


# A 200 m x 100 m apron, and a 200 m x 8 m road running flush along its
# north edge — the CYXY landside frontage geometry, reduced.
_APRON = Polygon([(0, 0), (200, 0), (200, 100), (0, 100)])
_ROAD = Polygon([(0, 100), (200, 100), (200, 108), (0, 108)])
# A short road STUB meeting the apron end-on: a mouth, not a frontage.
_STUB = Polygon([(90, 100), (110, 100), (110, 140), (90, 140)])


def _layout(*shapes):
    lay = PavementLayout(icao="T", anchor=(0.0, 0.0))
    lay.shapes.extend(shapes)
    return lay


def _shape(role, polygon):
    return BuiltShape(polygon=polygon, role=role, ref="")


def _flat_dem(_x, _y):
    return 700.0


def _clip_of(polygon, clearance=GROUNDSIDE_CLEARANCE_M):
    """The clearance buffer the separation pass builds (mitre join)."""
    return polygon.buffer(clearance, join_style=2)


# ── the two measurements the clause is stated in ─────────────────────

def test_the_width_is_the_faces_OWN_carriageway_width():
    """``2·area/perimeter`` is W for an L x W strip — no axis, no
    centerline, no second measurement free to drift."""
    assert _face_carriageway_width(_ROAD) == pytest.approx(
        8.0 * 200.0 / 208.0, abs=1e-9)
    assert 7.5 < _face_carriageway_width(_ROAD) < 8.0


def test_the_span_is_the_LONGEST_CONTIGUOUS_run_not_the_total():
    """PARALLEL is the ruling's word: a road touching an apron at two
    separate mouths is not a road running along it, and summing the two
    runs would say it was."""
    apron = Polygon([(0, 0), (200, 0), (200, 100), (0, 100)])
    # A road bar that dips down to the apron's north edge at two ends.
    two_mouths = Polygon([(0, 100), (20, 100), (20, 120), (180, 120),
                          (180, 100), (200, 100), (200, 128), (0, 128)])
    clip = _clip_of(apron)
    run = _longest_contact_run_m(two_mouths.exterior, clip)
    total = two_mouths.exterior.intersection(clip).length
    assert run < 30.0 < total
    assert total > 1.8 * run, "the two mouths must not compose"


# ── the clause ───────────────────────────────────────────────────────

def test_a_road_FRONTING_an_apron_is_cut_back():
    """THE CLAUSE.  200 m of flush contact against an 8 m road: far past
    1.5x, so the road separates and stops sharing the apron's nodes."""
    road = _shape(ROLE_SERVICE_ROAD, _ROAD)
    lay = _layout(_shape(ROLE_APRON, _APRON), road)
    n = _cut_back_road_frontage(lay, [_clip_of(_APRON)], _flat_dem)
    assert n == 1
    assert road.polygon.distance(_APRON) >= GROUNDSIDE_CLEARANCE_M - 1e-6, (
        "the frontage road still shares the apron's edge")
    assert road.polygon.area > 0.5 * _ROAD.area, "the road was eaten"


def test_the_cut_back_road_DEM_REFOLLOWS():
    """"stays AT DEM": the separated face carries DEM altitudes of its
    own, not the apron's level."""
    road = _shape(ROLE_SERVICE_ROAD, _ROAD)
    lay = _layout(_shape(ROLE_APRON, _APRON), road)
    assert _cut_back_road_frontage(lay, [_clip_of(_APRON)], _flat_dem) == 1
    alts = [a for a in (road.node_altitudes or []) if a is not None]
    assert alts and all(abs(a - 700.0) < 0.5 for a in alts)


def test_a_MOUTH_WINDOW_is_carved_out_of_the_clip_the_clause_reads():
    """The window is subtracted from the clearance buffer BEFORE this
    clause sees it, so inside a mouth the road is neither counted nor
    cut and keeps its shared edge — R7b clause 1's weld."""
    from shapely.geometry import box
    windowed = _clip_of(_APRON).difference(box(85, 85, 115, 115))
    stub = _shape(ROLE_SERVICE_ROAD, _STUB)
    lay = _layout(_shape(ROLE_APRON, _APRON), stub)
    assert _cut_back_road_frontage(lay, [windowed], _flat_dem) == 0
    assert stub.polygon.equals(_STUB), "a mouth was cut back"


def test_a_SHORT_contact_is_not_frontage():
    """Under 1.5x the road's own width the clause does not fire — the
    threshold is the ruling's, not a tuning knob.  A 20 m-wide road
    running AWAY from the apron touches it over its own end only."""
    end_on = Polygon([(90, 100), (110, 100), (110, 300), (90, 300)])
    need = ROAD_FRONTAGE_SPAN_WIDTH_FACTOR * _face_carriageway_width(end_on)
    assert _longest_contact_run_m(end_on.exterior, _clip_of(_APRON)) < need
    s = _shape(ROLE_SERVICE_ROAD, end_on)
    lay = _layout(_shape(ROLE_APRON, _APRON), s)
    assert _cut_back_road_frontage(lay, [_clip_of(_APRON)], _flat_dem) == 0


def test_a_cut_that_would_FRAGMENT_the_road_is_refused():
    """A cutback opens a gap along a FLANK.  Anything that severs the
    road into pieces is a severance this clause never authorised."""
    # An apron that would slice the road's middle out entirely.
    apron = Polygon([(80, 96), (120, 96), (120, 112), (80, 112)])
    road = _shape(ROLE_SERVICE_ROAD, _ROAD)
    lay = _layout(_shape(ROLE_APRON, apron), road)
    assert _cut_back_road_frontage(lay, [_clip_of(apron)], _flat_dem) == 0
    assert road.polygon.equals(_ROAD)


def test_a_JUNCTION_face_fronts_too():
    """``service_junction`` is road family: the ruling names the road,
    not one of its two roles."""
    road = _shape(ROLE_SERVICE_JUNCTION, _ROAD)
    lay = _layout(_shape(ROLE_JUNCTION, _APRON), road)
    assert _cut_back_road_frontage(lay, [_clip_of(_APRON)], _flat_dem) == 1


def test_a_face_that_is_NOT_a_road_is_never_touched():
    """Scoped to the road family — an apron beside an apron is a
    different law entirely."""
    other = _shape(ROLE_APRON, _ROAD)
    lay = _layout(_shape(ROLE_APRON, _APRON), other)
    assert _cut_back_road_frontage(lay, [_clip_of(_APRON)], _flat_dem) == 0
    assert other.polygon.equals(_ROAD)


# ── the wiring ───────────────────────────────────────────────────────

def _const_dem():
    from auto_patch.constant_dem import ConstantDEM
    return ConstantDEM(700.0)


def test_the_clause_is_OFF_by_default_in_the_separation_pass():
    """Every pre-existing call site must be byte-identical: the clause
    is reached only through the ONE explicit pre-solve call."""
    road = _shape(ROLE_SERVICE_ROAD, _ROAD)
    lay = _layout(_shape(ROLE_APRON, _APRON), road)
    _separate_groundside_from_airside(lay, _const_dem(), 0, 0)
    assert road.polygon.equals(_ROAD)


def test_groundside_clip_False_runs_ONLY_the_road_clause():
    """The explicit pre-solve call must not also re-clip groundside —
    that pass re-derives lot altitudes and has its own ordering law."""
    from auto_patch.layout import ROLE_GROUNDSIDE_PAVEMENT
    lot = Polygon([(0, 108), (200, 108), (200, 200), (0, 200)])
    lot_shape = _shape(ROLE_GROUNDSIDE_PAVEMENT, lot)
    road = _shape(ROLE_SERVICE_ROAD, _ROAD)
    lay = _layout(_shape(ROLE_APRON, _APRON), road, lot_shape)
    n = _separate_groundside_from_airside(
        lay, _const_dem(), 0, 0,
        road_frontage_cutback=True, groundside_clip=False)
    assert n == 1
    assert not road.polygon.equals(_ROAD), "the road clause did not run"
    assert lot_shape.polygon.equals(lot), "groundside was clipped anyway"


def test_a_cut_that_would_PUNCH_A_HOLE_is_refused():
    """An apron poking into a road's bay makes the difference an
    ANNULUS, and ``_dem_follow_polygon`` opens the hole with a corridor —
    rewriting the road's footprint instead of trimming its flank."""
    bay = Polygon([(0, 100), (200, 100), (200, 160), (0, 160)])
    intruder = Polygon([(60, 115), (140, 115), (140, 145), (60, 145)])
    road = _shape(ROLE_SERVICE_ROAD, bay)
    lay = _layout(_shape(ROLE_APRON, intruder), road)
    clip = _clip_of(intruder)
    assert bay.difference(clip).interiors, "the fixture must make an annulus"
    assert _cut_back_road_frontage(lay, [clip], _flat_dem) == 0
    assert road.polygon.equals(bay)
