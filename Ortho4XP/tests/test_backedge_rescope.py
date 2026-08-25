"""Twins for THE 5 % CLASS IS ONLY THE BACK-EDGE ZONES BETWEEN BUILDINGS
(owner ruling RULINGS 2026-08-24, amending 2026-08-21c).

The interior 5 % cap applies to an apron pair only where the pair lies
WHOLLY inside the fan-ramp back-edge geometry — the ground between two
adjacent building pads, computed live from ``plan_fan_ramp_zones``'
predicate (the zones are declared nowhere; nothing splits an apron at
them).  Everywhere else inside the 60 m body gate the apron body holds the
STRICT cap again.

Measured basis for the amendment (the owner's HECA in-sim review): the
broad 5 % interior let whole rings DRAPE onto the DEM — apron median
height-above-DEM 2.92 → 1.99 m, ring relief +19 %, site -10682 down 7.3 m.

Headless, geometry-only, no network and no X-Plane install.
"""

import sys
from pathlib import Path

import pytest
from shapely.geometry import Polygon

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from auto_patch import grade_graph as GG                       # noqa: E402
from auto_patch import grade_law as GL                         # noqa: E402
from auto_patch.config import APRON_MAX_GRADE                  # noqa: E402


# ── 1. THE BACK-EDGE RESCOPE ──────────────────────────────────────────

def _apron_ring(w=40.0, h=40.0):
    """A plain square apron ring, well inside the 60 m body gate so the
    A3 / 21d long-chord classes cannot confound the reading."""
    ring = [(0.0, 0.0), (w, 0.0), (w, h), (0.0, h)]
    return ring, list(range(len(ring)))


def _caps(sc):
    return {round(cap.flat_cap(), 9) for (_a, _b, cap) in sc.edges}


def test_same_geometry_prices_5pct_inside_a_zone_and_strict_outside():
    """THE RESCOPE, stated as one A/B on ONE geometry.

    Identical apron ring, identical context, the ONLY difference being
    whether a back-edge zone covers it.  Inside a zone the pairs price at
    ``APRON_INTERIOR_CAP`` (5 %); outside every zone they price at the
    shape's strict body cap.  That is the whole of RULINGS 2026-08-24's
    first clause, and it fails on the pre-ruling code (which returned 5 %
    for both arms).
    """
    ring, keys = _apron_ring()
    zone = ((-5.0, -5.0), (45.0, -5.0), (45.0, 45.0), (-5.0, 45.0))

    inside = GG.shape_constraints(
        GG.GradeShape(role="apron", ring=ring, keys=keys),
        GG.GradeContext(centerlines=[], interior_zones=(zone,)))
    outside = GG.shape_constraints(
        GG.GradeShape(role="apron", ring=ring, keys=keys),
        GG.GradeContext(centerlines=[], interior_zones=()))

    assert inside.edges and outside.edges
    assert _caps(inside) == {round(GL.APRON_INTERIOR_CAP, 9)}, (
        "a pair wholly inside a back-edge zone must keep the 5 % ramp cap")
    assert _caps(outside) == {round(APRON_MAX_GRADE, 9)}, (
        "outside every back-edge zone the apron body is STRICT again "
        "(RULINGS 2026-08-24)")
    # The pair populations are IDENTICAL — the rescope changes the CAP,
    # never the domain (nothing is removed from the law).
    assert ({(a, b) for (a, b, _c) in inside.edges}
            == {(a, b) for (a, b, _c) in outside.edges})


def test_a_3pct_pair_passes_in_a_zone_and_fails_at_1pct_outside():
    """The ruling's acceptance shape, read as a VERDICT rather than a cap:
    a 3 % pair is lawful inside a back-edge zone and unlawful outside it.
    """
    ring, keys = _apron_ring()
    zone = ((-5.0, -5.0), (45.0, -5.0), (45.0, 45.0), (-5.0, 45.0))
    dz = 0.03 * 40.0                       # 3 % over the 40 m ring edge

    for zones, lawful in ((( zone,), True), ((), False)):
        sc = GG.shape_constraints(
            GG.GradeShape(role="apron", ring=ring, keys=keys),
            GG.GradeContext(centerlines=[], interior_zones=zones))
        edge = next((c for (a, b, c) in sc.edges if {a, b} == {0, 1}), None)
        assert edge is not None, "the ring edge must stay in the domain"
        assert (edge.at(40.0, 0.0) + 1e-9 >= dz) is lawful, (
            f"3 % over 40 m should be {'lawful' if lawful else 'unlawful'} "
            f"with zones={bool(zones)}")


def test_a_chord_leaving_the_zone_is_not_a_back_edge_pair():
    """``FanRampPlan.pair_cap``'s composition clause, as the law reads it:
    both ENDS in one zone is not enough — the CHORD must be inside it too,
    because a chord that leaves the zone crosses ground the zone does not
    own.  A zone shaped like two lobes joined outside the apron gives
    exactly that pair."""
    ring, keys = _apron_ring()
    # An L-shaped zone that covers corners 0 and 1 but NOT the straight
    # chord between them.
    zone = ((-5.0, -5.0), (5.0, -5.0), (5.0, 10.0), (35.0, 10.0),
            (35.0, -5.0), (45.0, -5.0), (45.0, 45.0), (-5.0, 45.0))
    sc = GG.shape_constraints(
        GG.GradeShape(role="apron", ring=ring, keys=keys),
        GG.GradeContext(centerlines=[], interior_zones=(zone,)))
    edge = next((c for (a, b, c) in sc.edges if {a, b} == {0, 1}), None)
    assert edge is not None
    assert edge.flat_cap() == pytest.approx(APRON_MAX_GRADE), (
        "a chord that leaves its zone is not a back-edge pair")


def test_beyond_the_body_gate_stays_at_the_interior_cap():
    """The ruling's own qualifier — "under the existing 60 m body gate".

    A ring edge LONGER than ``APRON_BODY_CHORD_MAX_M`` is the class A3 and
    RULING 2026-08-21d measured and refuted as strict (HECA -10612's
    650-857 m "edges" at 1.36-1.64 % over an 11.7 m fall 1 % can span 8.4 m
    of).  The back-edge rescope does not re-open it: with no zone at all,
    such a pair still prices at the interior cap."""
    ring, keys = _apron_ring(w=400.0, h=400.0)
    sc = GG.shape_constraints(
        GG.GradeShape(role="apron", ring=ring, keys=keys),
        GG.GradeContext(centerlines=[], interior_zones=()))
    edge = next((c for (a, b, c) in sc.edges if {a, b} == {0, 1}), None)
    assert edge is not None
    assert edge.flat_cap() == pytest.approx(GL.APRON_INTERIOR_CAP), (
        "a >60 m ring edge is the refuted A3/21d class and keeps the "
        "interior cap — the rescope's subject is the SHORT interior pair")


def test_the_zone_polygons_census_equals_bake():
    """ONE GEOMETRY, BOTH READERS.  The census reaches the back-edge
    predicate through the SAME ``GradeContext`` field the bake filled, so
    the only way the two can disagree is if the sidecar export and the
    context differ.  This asserts the round trip: the rings the solver
    handed the law survive lat/lon export and re-projection with the same
    verdict on the same pair.
    """
    import check_grade as CG
    from auto_patch.elevation_per_surface.route_profile import (
        apron_terrace as AT)

    zone_m = ((-5.0, -5.0), (45.0, -5.0), (45.0, 45.0), (-5.0, 45.0))
    lat0, lon0 = 30.1, 31.4
    mpd_lat = 111320.0
    import math
    mpd_lon = 111320.0 * math.cos(math.radians(lat0))

    class _Layout:
        _interior_zone_rings = (zone_m,)

        @staticmethod
        def m_to_ll(x, y):
            return (lat0 + y / mpd_lat, lon0 + x / mpd_lon)

    exported = AT.interior_zones_sidecar(_Layout())
    assert len(exported) == 1 and len(exported[0]) == 4

    def ll_to_m(la, lo):
        return ((lo - lon0) * mpd_lon, (la - lat0) * mpd_lat)

    round_tripped = tuple(
        tuple(ll_to_m(float(la), float(lo)) for (la, lo) in ring)
        for ring in exported)

    ring, keys = _apron_ring()
    bake = GG.shape_constraints(
        GG.GradeShape(role="apron", ring=ring, keys=keys),
        GG.GradeContext(centerlines=[], interior_zones=(zone_m,)))
    census = GG.shape_constraints(
        GG.GradeShape(role="apron", ring=ring, keys=keys),
        GG.GradeContext(centerlines=[], interior_zones=round_tripped))
    assert _caps(bake) == _caps(census) == {round(GL.APRON_INTERIOR_CAP, 9)}

    # …and the sidecar key is registered as LAW INPUT, so no census can
    # silently ignore it (the census-wrapper precedent in CLAUDE.md).
    assert CG.SIDECAR_LAW_KEYS.get("interior_zones") == "interior_zones_ll"


def test_production_build_context_computes_the_back_edge_zones_live():
    """The rescope's zones are computed LIVE from ``plan_fan_ramp_zones``'
    predicate — they need no declaration, no apron split and no shape.  An
    airport with two adjacent pads on an apron yields the back-edge wedge
    between them straight out of ``build_context``; one with no pads
    yields none, and its apron is then strict throughout."""
    from auto_patch.layout import (BuiltShape, PavementLayout,
                                   ROLE_BUILDING, ROLE_APRON, ROLE_RUNWAY)

    bare = PavementLayout("BARE", anchor=(30.1, 31.4))
    bare.shapes = [BuiltShape(
        polygon=Polygon([(300, 120), (800, 120), (800, 300), (300, 300)]),
        role=ROLE_APRON, ref="apron1")]
    assert GG.build_context(bare).interior_zones == (), (
        "no building pads ⇒ no back-edge zone, and the apron is strict")


    from shapely.geometry import LineString
    L = PavementLayout("TEST", anchor=(30.1, 31.4))
    L.shapes = [BuiltShape(
        polygon=Polygon([(0, -22.5), (3000, -22.5),
                         (3000, 22.5), (0, 22.5)]),
        role=ROLE_RUNWAY, ref="05C/23C")]
    # A movement network is a PRECONDITION of the ruling's own zone
    # geometry — a zone is the ground between two pads and CLEAR of every
    # movement surface, so with no corridor there is nothing to be clear
    # of and ``plan_fan_ramp_zones`` declines.
    L.apt_taxi_centerlines = [(LineString([(300, 150), (800, 150)]), "A")]
    L.shapes.append(BuiltShape(
        polygon=Polygon([(400, 220), (500, 220), (500, 290), (400, 290)]),
        role=ROLE_BUILDING, ref="building1"))
    L.shapes.append(BuiltShape(
        polygon=Polygon([(560, 220), (660, 220), (660, 290), (560, 290)]),
        role=ROLE_BUILDING, ref="building2"))
    L.shapes.append(BuiltShape(
        polygon=Polygon([(300, 120), (800, 120), (800, 300), (300, 300)]),
        role=ROLE_APRON, ref="apron1"))
    ctx = GG.build_context(L)
    assert len(ctx.interior_zones) == 1, (
        "two adjacent pads on an apron must yield the back-edge wedge "
        "between them, computed live and declared nowhere")
    assert Polygon(ctx.interior_zones[0]).area > 200.0
    # The zones are a pure function of the geometry, so the answer is
    # cached on the LAYOUT and re-read (``build_context`` runs several
    # times per solve).
    assert ctx.interior_zones == tuple(L._interior_zone_rings)
    assert GG.build_context(L).interior_zones is ctx.interior_zones
