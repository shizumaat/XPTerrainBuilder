"""Free-road scoping of the service slice set — owner ruling 2026-07-27,
with the R7a LANDSIDE TERM (owner ruling 2026-08-15, Fable amendment A1).

"Any road inside, or sharing an edge with an apron must be graded the
same as the apron, so essentially just becomes part of the apron and
never needs to be carved in the first place.  We only want completely
free roads, with no pavement on either side of road-width pavement, to
be graded as roads."

``groundside.free_road_subsegments`` implements the slice-side half of
the ruling; ``carve_narrow_service_strips`` keys the strip carve on the
SAME per-station measurement (``_svc_contiguous_width``), so the two
cannot drift.

R7a: the ruling says APRON.  Wide pavement carrying POSITIVE LANDSIDE
EVIDENCE is a lot, not an apron, and the road keeps its knife there.
Amendment A1 is why the term is positive: the first arm read the ABSENCE
of airside evidence as landside, and at a DSF-pack airport genuine apron
routinely carries no OSM aeroway and no apt.dat name at all.

Hermetic: hand-built geometry, no fixtures, no DEM, no network.
"""
from shapely.geometry import LineString, Polygon

from auto_patch.groundside import (
    _svc_contiguous_cross_section, _svc_contiguous_width,
    free_road_subsegments)
from auto_patch.pavement_classification import CoverIndex


# A 400 m x 200 m apron and, east of it, a free-standing 10 m road
# ribbon crossing open terrain.
_APRON = Polygon([(0, -100), (400, -100), (400, 100), (0, 100)])
_RIBBON = Polygon([(500, -5), (900, -5), (900, 5), (500, 5)])
_PAV = _APRON.union(_RIBBON)
# The LANDSIDE evidence layer.  In production: the parking-aisle
# corridor layer, and pavement outside the runway-touch chain.  EMPTY is
# the normal reading of aircraft pavement — including DSF apron that
# carries no OSM/apt evidence of its own.
_NO_LANDSIDE = CoverIndex([])
_LANDSIDE = CoverIndex([_APRON])


def test_a_road_through_the_apron_is_not_free():
    """The through-apron span (cross-section 200 m) never reaches the
    slice — it IS the apron."""
    road = LineString([(50, 0), (350, 0)])
    assert free_road_subsegments(
        [road], _PAV, landside_evidence=_NO_LANDSIDE) == []


def test_a_road_hugging_the_apron_edge_is_not_free():
    """Edge-sharing: a road just inside the apron's south edge still
    measures the apron's full cross-section — part of the apron."""
    road = LineString([(50, -95), (350, -95)])
    assert free_road_subsegments(
        [road], _PAV, landside_evidence=_NO_LANDSIDE) == []


def test_a_road_width_ribbon_is_free():
    """Pavement that is nothing but the road grades as a road."""
    road = LineString([(510, 0), (890, 0)])
    segs = free_road_subsegments([road], _PAV,
                                 landside_evidence=_NO_LANDSIDE)
    assert len(segs) == 1
    assert segs[0].length > 350.0


def test_a_mixed_route_keeps_only_its_free_span():
    """One 1206 route running apron → open ribbon: only the ribbon span
    survives; the apron span is dropped whole."""
    road = LineString([(50, 0), (890, 0)])
    segs = free_road_subsegments([road], _PAV,
                                 landside_evidence=_NO_LANDSIDE)
    assert len(segs) == 1
    (x0, _y0) = segs[0].coords[0]
    (x1, _y1) = segs[0].coords[-1]
    assert min(x0, x1) >= 395.0, "the apron span must not be carved"
    assert max(x0, x1) > 850.0


def test_off_pavement_roads_pass_through_unfiltered():
    road = LineString([(0, 500), (400, 500)])
    segs = free_road_subsegments([road], _PAV,
                                 landside_evidence=_NO_LANDSIDE)
    assert len(segs) == 1


def test_the_carve_and_the_filter_share_one_measurement():
    """Lockstep: the width the filter keys on IS the carve's width."""
    road = LineString([(510, 0), (890, 0)])
    w = _svc_contiguous_width(road, road.length / 2.0, _PAV)
    assert w is not None and 8.0 <= w <= 12.0
    w_apron = _svc_contiguous_width(
        LineString([(50, 0), (350, 0)]), 150.0, _PAV)
    assert w_apron is not None and w_apron > 100.0


def test_the_width_is_the_length_of_the_one_cross_section():
    """The width is derived FROM the chord, not measured beside it —
    the landside term reads the same geometry the width came from."""
    road = LineString([(50, 0), (350, 0)])
    part = _svc_contiguous_cross_section(road, 150.0, _PAV)
    w = _svc_contiguous_width(road, 150.0, _PAV)
    assert part is not None and not part.is_empty
    assert w == part.length
    # off pavement: an EMPTY chord, width 0.0 (the pre-R7a sentinel).
    off = _svc_contiguous_cross_section(
        LineString([(0, 500), (400, 500)]), 200.0, _PAV)
    assert off is not None and off.is_empty
    assert _svc_contiguous_width(
        LineString([(0, 500), (400, 500)]), 200.0, _PAV) == 0.0


# ── R7a / A1: THE POSITIVE LANDSIDE TERM ─────────────────────────────

def test_a_road_through_a_LANDSIDE_lot_keeps_its_knife():
    """THE R7a CLAUSE.  Same 200 m-wide pavement, same road — but the
    pavement carries landside evidence (a parking aisle, or no
    touch-chain to a runway).  It is a car park, not an apron: the road
    cuts its own face straight through it (CYXY lot 377)."""
    road = LineString([(50, 0), (350, 0)])
    segs = free_road_subsegments([road], _PAV, landside_evidence=_LANDSIDE)
    assert len(segs) == 1, "a landside lot may not swallow a public road"
    assert segs[0].length > 250.0


def test_the_landside_term_is_evidence_not_geometry():
    """The ONLY difference between the two verdicts is the evidence
    layer — the guard against 'it happened to be the width after all'."""
    road = LineString([(50, 0), (350, 0)])
    assert free_road_subsegments(
        [road], _PAV, landside_evidence=_NO_LANDSIDE) == []
    assert free_road_subsegments(
        [road], _PAV, landside_evidence=_LANDSIDE) != []


def test_ABSENCE_of_evidence_leaves_wide_pavement_APRON():
    """AMENDMENT A1, stated as a test.  An empty evidence layer is the
    DSF-pack airport whose genuine apron carries no OSM aeroway and no
    apt.dat name: it must read APRON, not landside.  The refuted arm
    inverted exactly this and cut the airport's real apron."""
    road = LineString([(50, 0), (350, 0)])
    assert free_road_subsegments(
        [road], _PAV, landside_evidence=CoverIndex([])) == []


def test_evidence_ANYWHERE_on_the_cross_section_is_read():
    """The evidence is asked about the cross-section the station stands
    in, not about the station point: a lot's parking aisle 60 m inboard
    still releases a road hugging the lot's south edge."""
    road = LineString([(50, -95), (350, -95)])
    # Evidence that does NOT contain the station (y = -95) but does
    # touch the chord it stands in (the probe reaches y = -35).
    inboard = CoverIndex([
        Polygon([(0, -60), (400, -60), (400, -40), (0, -40)])])
    assert not inboard.intersects(LineString([(200, -96), (200, -94)]))
    assert free_road_subsegments(
        [road], _PAV, landside_evidence=inboard) != []


def test_a_landside_lot_ABUTTING_an_apron_still_yields_the_apron_span():
    """A road running apron → landside lot: the apron span is dropped
    and the lot span keeps its knife.  One route, both laws."""
    lot = Polygon([(400, -100), (800, -100), (800, 100), (400, 100)])
    pav = _APRON.union(lot)
    road = LineString([(50, 0), (750, 0)])
    segs = free_road_subsegments([road], pav,
                                 landside_evidence=CoverIndex([lot]))
    assert len(segs) == 1
    xs = [c[0] for c in segs[0].coords]
    assert min(xs) >= 395.0, "the apron span must not be carved"
    assert max(xs) > 700.0, "the lot span must keep its knife"


def test_no_evidence_layer_at_all_is_the_pre_R7a_law():
    """``landside_evidence=None`` — synthetic callers and the width-only
    fallback: every wide station is apron, exactly as before R7a."""
    road = LineString([(50, 0), (350, 0)])
    assert free_road_subsegments([road], _PAV) == []


def test_the_cover_index_answers_a_LINE_not_only_an_area():
    """``CoverIndex.intersects`` is the membership question the area
    fractions cannot answer for a zero-area chord."""
    chord = LineString([(200, -100), (200, 100)])
    assert _LANDSIDE.cover_fraction(chord) == 0.0    # no area, no fraction
    assert _LANDSIDE.intersects(chord) is True
    assert _NO_LANDSIDE.intersects(chord) is False
    assert _LANDSIDE.intersects(LineString()) is False
    assert _LANDSIDE.intersects(None) is False


# ── the layer itself ─────────────────────────────────────────────────

class _FakeShape:
    def __init__(self, role, polygon):
        self.role = role
        self.polygon = polygon


class _FakeLayout:
    """The two attributes ``runway_disconnected_pavement`` reads."""

    def __init__(self, runway_union, shapes):
        self.runway_union = runway_union
        self.shapes = shapes


def test_pavement_off_the_runway_touch_chain_IS_landside_evidence():
    """The standing 2026-06-09 law, stated over the pavement union: a
    component that cannot reach a runway is landside (FBO ramps,
    curbside, parking) — CYXY's west-side 'aprons', 6-153 m from the
    airside network."""
    from auto_patch.pavement_classification import (
        runway_disconnected_pavement)
    runway = Polygon([(0, -10), (400, -10), (400, 10), (0, 10)])
    lot = Polygon([(600, -100), (800, -100), (800, 100), (600, 100)])
    pav = _APRON.union(lot)          # _APRON overlaps the runway strip
    lay = _FakeLayout(runway, [_FakeShape("building", _APRON)])
    out = runway_disconnected_pavement(lay, pav)
    assert len(out) == 1 and out[0].equals(lot)


def test_the_connectivity_term_is_inert_with_no_buildings():
    """"Airports with NO terminal have no landside" (user 2026-06-11) —
    the precondition travels with the law it comes from."""
    from auto_patch.pavement_classification import (
        runway_disconnected_pavement)
    runway = Polygon([(0, -10), (400, -10), (400, 10), (0, 10)])
    lot = Polygon([(600, -100), (800, -100), (800, 100), (600, 100)])
    lay = _FakeLayout(runway, [])
    assert runway_disconnected_pavement(lay, _APRON.union(lot)) == []


def test_the_connectivity_term_is_inert_with_no_runway_union():
    """Absence of the SOURCE is never evidence."""
    from auto_patch.pavement_classification import (
        runway_disconnected_pavement)
    lot = Polygon([(600, -100), (800, -100), (800, 100), (600, 100)])
    lay = _FakeLayout(None, [_FakeShape("building", _APRON)])
    assert runway_disconnected_pavement(lay, _APRON.union(lot)) == []
