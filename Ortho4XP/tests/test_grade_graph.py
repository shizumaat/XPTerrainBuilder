"""Hermetic unit tests for the clean-room single grade graph
(``auto_patch.grade_graph``).  No build/fixtures — pure geometry."""
import math
import pytest

from auto_patch import grade_graph as GG
from auto_patch import grade_law as GL
from auto_patch.config import (
    APRON_MAX_GRADE, TAXI_MAX_GRADE, TAXI_MAX_GRADE_NARROW,
    SERVICE_ROAD_MAX_GRADE, TAXI_GRADE_BY_WIDTH,
)


def _square(side=20.0):
    """4-corner square apron/junction ring + keys."""
    ring = [(0.0, 0.0), (side, 0.0), (side, side), (0.0, side)]
    keys = [0, 1, 2, 3]
    return ring, keys


def _cap_of(sc, a, b):
    for (x, y, cap) in sc.edges:
        if {x, y} == {a, b}:
            return cap.flat_cap()
    return None


def test_apron_body_is_one_percent_no_spine():
    """RE-AMENDED by RULINGS 2026-08-24: a bare square apron with no spine,
    no frontage AND NO BACK-EDGE ZONE is strict throughout — every pair
    inside the 60 m body gate reads ``APRON_MAX_GRADE``.

    The history this twin has tracked: pre-2026-08-21c every pair was 1 %;
    A1c/A2 raised the whole interior to ``APRON_INTERIOR_CAP`` (5 %); the
    2026-08-24 back-edge rescope returns everything OUTSIDE a fan-ramp
    back-edge zone to the strict cap, and this fixture declares no zone.
    The 5 % half now lives in ``test_backedge_rescope``, on a fixture that
    actually has a zone."""
    ring, keys = _square()
    s = GG.GradeShape(role="apron", ring=ring, keys=keys)
    ctx = GG.GradeContext(centerlines=[])
    sc = GG.shape_constraints(s, ctx)
    assert sc.edges, "apron must produce body edges"
    caps = {round(cap.flat_cap(), 9) for (_a, _b, cap) in sc.edges}
    assert caps == {round(APRON_MAX_GRADE, 9)}, (
        "with no back-edge zone declared the apron body is STRICT "
        "(RULINGS 2026-08-24)")
    # with the rule OFF the pre-ruling all-strict reading is restored.
    saved = GL.APRON_INTERIOR_RAMP_CAP
    try:
        GL.APRON_INTERIOR_RAMP_CAP = False
        off = GG.shape_constraints(
            GG.GradeShape(role="apron", ring=ring, keys=keys), ctx)
    finally:
        GL.APRON_INTERIOR_RAMP_CAP = saved
    assert all(abs(cap.flat_cap() - APRON_MAX_GRADE) < 1e-9
               for (_a, _b, cap) in off.edges)


def test_junction_no_spine_inherits_cap():
    ring, keys = _square()
    s = GG.GradeShape(role="junction", ring=ring, keys=keys)
    # nearest connected taxiway is narrow (A/B) → 3%
    ctx = GG.GradeContext(
        centerlines=[], inherited_junction_cap=lambda sh: TAXI_MAX_GRADE_NARROW)
    sc = GG.shape_constraints(s, ctx)
    assert sc.edges
    assert all(abs(cap.flat_cap() - TAXI_MAX_GRADE_NARROW) < 1e-9
               for (_a, _b, cap) in sc.edges)


def test_junction_with_spine_uniform_taxiway_cap():
    # a centerline running through the middle of the square along x
    ring = [(0.0, 0.0), (20.0, 0.0), (20.0, 20.0), (0.0, 20.0),
            (0.0, 10.0), (20.0, 10.0)]   # last two ON the centerline y=10
    keys = list(range(len(ring)))
    cl = GG.Centerline(pts=[(0.0, 10.0), (20.0, 10.0)],
                       seg_caps=[TAXI_MAX_GRADE_NARROW])
    s = GG.GradeShape(role="junction", ring=ring, keys=keys)
    ctx = GG.GradeContext(centerlines=[cl])
    sc = GG.shape_constraints(s, ctx)
    # the two spine nodes (idx 4,5) share a centerline → spine cap (3%)
    assert _cap_of(sc, 4, 5) == pytest.approx(TAXI_MAX_GRADE_NARROW)
    # junction body is ALSO the taxiway cap → uniform
    assert all(abs(cap.flat_cap() - TAXI_MAX_GRADE_NARROW) < 1e-9
               for (_a, _b, cap) in sc.edges)
    # spine chain recorded, ordered along arc
    assert sc.spine_chains == [[4, 5]] or sc.spine_chains == [[5, 4]]


def test_apron_with_spine_taxi_on_spine_one_percent_body():
    # Same topology as the junction spine test, scaled 4× in y so the bottom
    # body edge (corners 0→1) sits 40 m from the mid-height spine — beyond
    # APRON_TAXI_TRANSITION_M (30 m).  With O4_APRON_TAXI_BLEND on, a body edge
    # that is BOTH near AND along a running taxiway earns a blended cap (see
    # _apron_edge_cap); placing this edge past the transition lets it decay back
    # to the flat apron 1 % so the body-vs-spine distinction is what's tested.
    ring = [(0.0, 0.0), (20.0, 0.0), (20.0, 80.0), (0.0, 80.0),
            (0.0, 40.0), (20.0, 40.0)]
    keys = list(range(len(ring)))
    cl = GG.Centerline(pts=[(0.0, 40.0), (20.0, 40.0)], seg_caps=[TAXI_MAX_GRADE])
    s = GG.GradeShape(role="apron", ring=ring, keys=keys)
    ctx = GG.GradeContext(centerlines=[cl])
    sc = GG.shape_constraints(s, ctx)
    # spine pair (4,5) at taxiway cap.  A CORRIDOR pair is never interior
    # (spec AMENDMENT A2): raising it to the 5 % interior cap would legalise
    # a 5 % grade along a running taxiway, and this assertion is what caught
    # that when A2 first landed.
    assert _cap_of(sc, 4, 5) == pytest.approx(TAXI_MAX_GRADE)
    # A body RING EDGE (corner 0 to corner 1), 40 m from the spine, fronting
    # nothing and outside any back-edge zone.  THIS APRON CARRIES A SPINE,
    # so it is CORRIDOR-CONNECTED and the edge inherits the corridor's own
    # cap (RULINGS 2026-08-24b, "no plateaus": an apron spanning between
    # two lawful 1.5 % taxiways lawfully runs ~1.5 % itself).  The history:
    # pre-A2 this read the flat apron 1 %, A2 raised it to the 5 % interior
    # cap, 2026-08-24 cut that back to 1 %, and 24b settled it at the
    # corridor cap.
    assert _cap_of(sc, 0, 1) == pytest.approx(TAXI_MAX_GRADE)
    # ...and with the rule off it still reads the pre-ruling 1 %.
    saved = GL.APRON_INTERIOR_RAMP_CAP
    try:
        GL.APRON_INTERIOR_RAMP_CAP = False
        off = GG.shape_constraints(
            GG.GradeShape(role="apron", ring=ring, keys=keys), ctx)
    finally:
        GL.APRON_INTERIOR_RAMP_CAP = saved
    assert _cap_of(off, 0, 1) == pytest.approx(APRON_MAX_GRADE)
    assert _cap_of(off, 4, 5) == pytest.approx(TAXI_MAX_GRADE)


def test_seam_endpoint_drops_pair():
    """Seam-pin law (2026-07-03/04 seam architecture — ``grade_law.classify_pair``
    lines ~242-246 / ~314-315):

    * a pair with BOTH endpoints seam-pinned (an along-seam pair) is
      terrain-controlled → dropped from the law;
    * a pair with ONE seam endpoint STAYS in the law but never earns
      spine/blend credit — the seam pin is a graded-TO hard anchor, so the
      approach is clamped to the shape's own BODY cap;
    * RUNWAY-family shapes keep the full one-seam exemption (the FAA profile
      is solved separately; a mid-runway seam pin can contradict it locally).
    """
    # (1) BOTH-seam pair dropped; the one-seam pairs of the same shape stay.
    ring, keys = _square()
    s = GG.GradeShape(role="apron", ring=ring, keys=keys)
    ctx = GG.GradeContext(centerlines=[], seam_keys=frozenset({0, 1}))
    sc = GG.shape_constraints(s, ctx)
    assert _cap_of(sc, 0, 1) is None          # seam↔seam: terrain-controlled
    assert _cap_of(sc, 0, 3) is not None      # seam↔free: kept in the law

    # (2) ONE-seam pair clamped to the body cap: seam node 4 lies ON the taxi
    # centerline, so without the clamp the (4,5) spine pair would earn
    # TAXI_MAX_GRADE — the seam-pin approach grades at the apron body cap.
    ring2 = [(0.0, 0.0), (20.0, 0.0), (20.0, 80.0), (0.0, 80.0),
             (0.0, 40.0), (20.0, 40.0)]      # 4,5 ON the centerline y=40
    keys2 = list(range(len(ring2)))
    cl = GG.Centerline(pts=[(0.0, 40.0), (20.0, 40.0)],
                       seg_caps=[TAXI_MAX_GRADE])
    s2 = GG.GradeShape(role="apron", ring=ring2, keys=keys2)
    sc2 = GG.shape_constraints(
        s2, GG.GradeContext(centerlines=[cl], seam_keys=frozenset({4})))
    assert _cap_of(sc2, 4, 5) == pytest.approx(APRON_MAX_GRADE)

    # (3) runway-role one-seam exemption: every pair touching the seam pin
    # leaves the law entirely; the rest of the shape is still graded.
    s3 = GG.GradeShape(role="runway", ring=ring, keys=keys)
    sc3 = GG.plane_constraints(
        s3, GG.GradeContext(centerlines=[], seam_keys=frozenset({0})),
        cap=TAXI_MAX_GRADE)
    assert sc3.edges, "runway plane must still grade its seam-free pairs"
    assert all(0 not in (a, b) for (a, b, _c) in sc3.edges)


def test_service_junction_four_percent():
    """The road family's LONGITUDINAL cap is the service-road limit.

    AMENDED BY RULINGS 2026-08-25g ("ROADS ARE LATERALLY FLAT"): a road
    ring's pairs partition by angle to the ring's own long axis — the
    ACROSS ones are the road's CROSS-SECTION and price at
    ``SERVICE_ROAD_MAX_TRANSVERSE``.  So the assertion is per CLASS, and
    the class is the law's own verdict (``edge_transverse_road``,
    recorded at mint) rather than a guess from the cap value.  The
    pre-ruling reading — every pair at the longitudinal cap — is what
    ``O4_ROAD_CROSS_SECTION_LAW=0`` restores, twinned in
    ``tests/test_road_cross_section.py``.
    """
    from auto_patch.config import SERVICE_ROAD_MAX_TRANSVERSE
    ring, keys = _square()
    s = GG.GradeShape(role="service_junction", ring=ring, keys=keys)
    ctx = GG.GradeContext(centerlines=[])
    sc = GG.shape_constraints(s, ctx)
    assert sc.edges and len(sc.edge_transverse_road) == len(sc.edges)
    for (_a, _b, cap), across in zip(sc.edges, sc.edge_transverse_road):
        want = (SERVICE_ROAD_MAX_TRANSVERSE if across
                else SERVICE_ROAD_MAX_GRADE)
        assert abs(cap.flat_cap() - want) < 1e-9


def _deseg_runway_ring(length=800.0, width=40.0, stations=5):
    """A de-segmented single-poly runway ring (length ≫ width): profile
    stations as interior LONG-EDGE vertices, going up one edge and back the
    other.  Keys are ring indices; vertex ``k`` and ``2*stations-1-k`` share a
    station.  ``width²/length`` stays < the 5 m cluster tolerance so same-station
    cross-edge vertices cluster (as they do on a real runway)."""
    step = length / (stations - 1)
    left = [(i * step, 0.0) for i in range(stations)]
    right = [((stations - 1 - i) * step, width) for i in range(stations)]
    ring = left + right
    return ring, list(range(len(ring)))


def test_runway_station_clustering_and_predicate():
    """The station clusterer projects a de-seg ring's vertices onto the ref
    axis and groups them at 5 m; same-cross-end vertices share a station, and
    the domain predicate keeps only |Δstation| ≤ 1."""
    from auto_patch import grade_law as GL
    ring, _keys = _deseg_runway_ring(length=800.0, width=40.0, stations=5)
    stations = GL.runway_axis_station_indices(ring)
    # 5 stations, and the two long-edge vertices at each station share an index.
    assert stations == [0, 1, 2, 3, 4, 4, 3, 2, 1, 0]
    assert len(set(stations)) == 5
    # A LEGACY 4-corner square is NOT length ≫ width, so its longest pair is a
    # DIAGONAL that over-segments it — which is exactly why plane_constraints
    # gates the scoping on ``single_poly`` (this ring is never scoped).
    assert GL.runway_axis_station_indices(
        [(0.0, 0.0), (45.0, 0.0), (45.0, 45.0), (0.0, 45.0)]) == [0, 1, 2, 1]
    # Predicate: same / adjacent in domain, 2+ intervals out.
    assert GL.runway_within_pair_in_domain(2, 2)
    assert GL.runway_within_pair_in_domain(2, 3)
    assert not GL.runway_within_pair_in_domain(2, 4)


def test_plane_constraints_runway_single_poly_scopes_multistation():
    """USER RULING 2026-07-08 — a de-segmented runway RING's within-shape pair
    domain is scoped to LATERAL + same/adjacent-station; a pair spanning 2+
    station intervals leaves it (the FAA profile law owns the longitudinal
    grade).  The scoping is gated on ``single_poly`` so a LEGACY segmented rect
    is a byte-identical no-op."""
    ring, keys = _deseg_runway_ring(length=800.0, width=40.0, stations=5)
    ctx = GG.GradeContext(centerlines=[])
    n = len(ring)  # 10; vertex k and n-1-k share a station

    def _has(sc, a, b):
        return any({x, y} == {a, b} for (x, y, _c) in sc.edges)

    # single_poly=True → scoped.
    scoped = GG.plane_constraints(
        GG.GradeShape(role="runway", ring=ring, keys=keys, single_poly=True),
        ctx, cap=TAXI_MAX_GRADE)
    assert _has(scoped, 0, 9)      # same station (0,0) ↔ station 0 — LATERAL
    assert _has(scoped, 0, 1)      # adjacent station 0↔1
    assert _has(scoped, 1, 8)      # same station 1
    assert not _has(scoped, 0, 2)  # 2 intervals — longitudinal, dropped
    assert not _has(scoped, 0, 4)  # far — dropped
    assert not _has(scoped, 0, 5)  # opposite corner (station 0↔4) — dropped

    # single_poly=False (legacy segmented rect) → NO scoping, full all-pair.
    legacy = GG.plane_constraints(
        GG.GradeShape(role="runway", ring=ring, keys=keys, single_poly=False),
        ctx, cap=TAXI_MAX_GRADE)
    assert _has(legacy, 0, 2) and _has(legacy, 0, 4) and _has(legacy, 0, 5)
    assert len(legacy.edges) > len(scoped.edges)
    # Every legacy edge sits at the plane cap (the scoping only DROPS pairs,
    # never changes a surviving pair's budget).
    assert all(abs(cap.flat_cap() - TAXI_MAX_GRADE) < 1e-9
               for (_a, _b, cap) in scoped.edges)


def test_nonconvex_visibility_drops_chord_across_notch():
    # an L-shaped apron; the chord between the two far tips leaves the pavement
    ring = [(0, 0), (30, 0), (30, 10), (10, 10), (10, 30), (0, 30)]
    keys = list(range(len(ring)))
    s = GG.GradeShape(role="apron", ring=ring, keys=keys)
    ctx = GG.GradeContext(centerlines=[])
    sc = GG.shape_constraints(s, ctx)
    # (30,0) idx1 to (0,30) idx5: chord cuts across the missing quadrant
    assert _cap_of(sc, 1, 5) is None


# ── ds_decompose: the anisotropic (Δs∥, Δs⊥) primitive (Phase 1) ──────────────

def test_ds_decompose_straight_route_is_isotropic():
    """A STRAIGHT route → (Δs∥, Δs⊥) == (sep, 0): straight taxiways/aprons see
    the legacy ``cap·dist`` budget, so wiring anisotropy can't change them."""
    route = GG.RouteChain(pts=[(0.0, 0.0), (100.0, 0.0)])
    # a pair strung ALONG the line
    dpar, dperp = GG.ds_decompose((10.0, 0.0), (40.0, 0.0), route)
    assert dpar == pytest.approx(30.0, abs=1e-6)
    assert dperp == pytest.approx(0.0, abs=1e-6)
    # a pair offset to the SAME side (parallel) — still zero transverse SEPARATION
    dpar2, dperp2 = GG.ds_decompose((10.0, 5.0), (40.0, 5.0), route)
    assert dpar2 == pytest.approx(30.0, abs=1e-6)
    assert dperp2 == pytest.approx(0.0, abs=1e-6)
    # a pure PERPENDICULAR pair → (0, perp)
    dpar3, dperp3 = GG.ds_decompose((20.0, 0.0), (20.0, 12.0), route)
    assert dpar3 == pytest.approx(0.0, abs=1e-6)
    assert dperp3 == pytest.approx(12.0, abs=1e-6)


def test_ds_decompose_never_inflates():
    """The decomposition is a ROTATION of the direct separation, never an
    inflation: ``Δs∥² + Δs⊥² == sep²`` exactly, including on a CURVED route.

    (The original arc-credit form — Δs∥ = along-route arc between the
    projections — was measured WRONG 2026-07-03: near curves two
    physically-close points earned budgets far beyond any surface cap, so
    12 %+ surface cliffs perpendicular to the spine were ruled legal.  The
    pavement between two nearby points is continuous; the standards regulate
    the SURFACE gradient, so the budget derives from the direct separation,
    only rotated into (∥, ⊥) for the cL/cT anisotropy.)"""
    # up 100 m then right 100 m: arc 200, chord (0,0)->(100,100) = 141.42
    route = GG.RouteChain(pts=[(0.0, 0.0), (0.0, 100.0), (100.0, 100.0)])
    sep = math.hypot(100.0, 100.0)
    dpar, dperp = GG.ds_decompose((0.0, 0.0), (100.0, 100.0), route)
    assert math.hypot(dpar, dperp) == pytest.approx(sep, abs=1e-6)
    assert dpar <= sep + 1e-9                           # never > direct
    # mid-leg pair: (0,40)->(0,90) is 50 m of pure along-route separation
    dpar2, dperp2 = GG.ds_decompose((0.0, 40.0), (0.0, 90.0), route)
    assert dpar2 == pytest.approx(50.0, abs=1e-6)
    assert dperp2 == pytest.approx(0.0, abs=1e-6)


def test_ds_decompose_matches_centerline_and_routechain():
    """``ds_decompose`` is geometry-only and duck-typed: a single-segment route
    gives identical results whether passed a ``Centerline`` or a ``RouteChain``."""
    pts = [(0.0, 0.0), (50.0, 0.0)]
    rc = GG.RouteChain(pts=pts)
    cl = GG.Centerline(pts=pts, seg_caps=[TAXI_MAX_GRADE])
    a = GG.ds_decompose((5.0, 2.0), (35.0, 3.0), rc)
    b = GG.ds_decompose((5.0, 2.0), (35.0, 3.0), cl)
    assert a == pytest.approx(b, abs=1e-9)


# ── cT transverse-cap table (Phase 2) ────────────────────────────────────────

def test_taxi_transverse_cap_per_letter():
    """ICAO Annex 14 §3.9.11 transverse caps: A/B → 2 %, C–F → = longitudinal
    (isotropic).  When width-grading is off, cT collapses to cL everywhere."""
    from auto_patch.config import (
        taxi_transverse_cap_for_letter as cT,
        taxi_grade_cap_for_letter as cL,
        TAXI_MAX_TRANSVERSE_NARROW)
    # C–F (and unknown) are isotropic: cT == cL
    for L in ("C", "D", "E", "F", None, ""):
        assert cT(L, enabled=True) == cL(L, enabled=True)
    # A/B earn the 2 % transverse cap when width-grading is on
    assert cT("A", enabled=True) == pytest.approx(0.02)
    assert cT("B", enabled=True) == pytest.approx(TAXI_MAX_TRANSVERSE_NARROW)
    # cT (2 %) is BELOW cL (3 %) for A/B — anisotropic, not looser
    assert cT("A", enabled=True) < cL("A", enabled=True)
    # gate OFF → cT collapses to cL (isotropic) for every letter
    for L in ("A", "B", "C", "F"):
        assert cT(L, enabled=False) == cL(L, enabled=False)


# ── spine-drop census (hygiene 2026-07-31) ───────────────────────────────────

def test_global_spine_counts_centerlines_that_contribute_no_string(capsys):
    """A centerline with < 2 on-line geometry nodes weaves NO spine string.
    That used to be a silent ``continue``; it is now counted (zero-node and
    one-node apart — absent geometry vs a THINNED region are different
    findings) and summarised in one build-log line."""
    G = GG.UnifiedGraph()
    G.pos = {0: (0.0, 0.0), 1: (10.0, 0.0), 2: (20.0, 0.0)}
    cap = [TAXI_MAX_GRADE]
    strung = GG.Centerline(pts=[(0.0, 0.0), (20.0, 0.0)], seg_caps=cap)
    one_node = GG.Centerline(pts=[(20.0, 0.0), (60.0, 0.0)], seg_caps=cap)
    no_node = GG.Centerline(pts=[(0.0, 500.0), (20.0, 500.0)], seg_caps=cap)
    ctx = GG.GradeContext(centerlines=[strung, one_node, no_node])

    GG._build_global_spine(G, ctx, icao="TEST")

    assert G.spine_centerlines == 3
    assert G.spine_no_string == 2            # one_node + no_node
    assert G.spine_no_string_zero == 1       # ... of which no_node
    # the strung centerline still wove its chain
    assert G.spine_adj.get(0) and G.spine_adj.get(2)
    assert G.centerline_chains[0] == [0, 1, 2]
    out = capsys.readouterr().out
    assert "contributed no string" in out
    assert "2 of 3 centerline(s)" in out


def test_global_spine_census_is_zero_when_every_centerline_strings(capsys):
    """No false positives: a fully covered centerline set reports 0 drops."""
    G = GG.UnifiedGraph()
    G.pos = {0: (0.0, 0.0), 1: (10.0, 0.0)}
    ctx = GG.GradeContext(centerlines=[
        GG.Centerline(pts=[(0.0, 0.0), (10.0, 0.0)], seg_caps=[TAXI_MAX_GRADE])])
    GG._build_global_spine(G, ctx, icao="TEST")
    assert (G.spine_centerlines, G.spine_no_string, G.spine_no_string_zero) \
        == (1, 0, 0)
    assert "0 of 1 centerline(s) contributed no string" in capsys.readouterr().out


# ── perf P3 lane D: the batched / prefiltered paths are TWINS of the
# per-item paths they stand in for.  Each optimisation below replaces a
# per-item shapely call with a vectorised one, or skips a call whose
# answer is already known; none of them may change a verdict, and none of
# them may be trusted on the comment alone.  Each test runs BOTH paths on
# the same input and asserts equality.

def _notched_ring(side=60.0):
    """A NON-CONVEX ring, so the visibility predicate actually says False
    for some chords (a convex ring would twin trivially)."""
    h = side / 2.0
    return [(0.0, 0.0), (side, 0.0), (side, side), (h + 5.0, side),
            (h + 5.0, h), (h - 5.0, h), (h - 5.0, side), (0.0, side)]


def _all_chords(ring):
    """Every (i, j) chord of the ring, in ``shape_constraints`` order."""
    import numpy as np
    import shapely
    n = len(ring)
    xy = np.asarray(ring, dtype=float)
    iu, ju = np.triu_indices(n, 1)
    pts = np.empty((2 * len(iu), 2), dtype=float)
    pts[0::2] = xy[iu]
    pts[1::2] = xy[ju]
    chords = shapely.linestrings(
        pts, indices=np.repeat(np.arange(len(iu)), 2))
    return xy, iu, ju, chords


def test_visibility_batch_twins_the_per_chord_predicate():
    ring = _notched_ring()
    vis = GG._visibility_predicate(ring)
    assert vis is not None
    xy, iu, ju, chords = _all_chords(ring)
    batched = list(vis.batch(chords))
    one_at_a_time = [vis(xy[a, 0], xy[a, 1], xy[b, 0], xy[b, 1])
                     for a, b in zip(iu, ju)]
    assert batched == one_at_a_time
    # and the fixture is discriminating, not all-True
    assert not all(one_at_a_time)


def _crossing_ctx_and_shape():
    """An apron with two taxi centerlines through it, so chords cross a
    spine, touch one at an endpoint, and miss entirely."""
    ring = [(0.0, 0.0), (60.0, 0.0), (60.0, 60.0), (0.0, 60.0),
            (0.0, 30.0), (60.0, 30.0)]
    cls = [GG.Centerline(pts=[(0.0, 30.0), (60.0, 30.0)],
                         seg_caps=[TAXI_MAX_GRADE]),
           GG.Centerline(pts=[(30.0, 0.0), (30.0, 60.0)],
                         seg_caps=[TAXI_MAX_GRADE])]
    ctx = GG.GradeContext(centerlines=cls)
    shape = GG.GradeShape(role="apron", ring=ring,
                          keys=list(range(len(ring))))
    return ctx, shape, ring


def test_crossing_tree_predicate_twins_the_linear_scan():
    """The crossing predicate now pushes ``intersects`` INTO the tree query
    instead of filtering bbox candidates in Python.  Its own fallback — the
    linear scan over every spine, reached when there is no tree — is the
    reference: both must give the same verdict for every chord."""
    ctx, shape, ring = _crossing_ctx_and_shape()
    mem = GG._spine_membership(shape, ctx)
    with_tree = GG._spine_crossing_predicate(shape, ctx, mem)
    assert with_tree is not None
    attr = ("_crossing_tree" if GG._reads_service_spines(shape)
            else "_crossing_tree_nosvc")
    geoms, tree = getattr(ctx, attr)
    assert tree is not None, "fixture did not build a tree at all"
    setattr(ctx, attr, (geoms, None))              # force the linear scan
    linear = GG._spine_crossing_predicate(shape, ctx, mem)

    xy, iu, ju, _chords = _all_chords(ring)
    a = [with_tree(xy[p, 0], xy[p, 1], xy[q, 0], xy[q, 1])
         for p, q in zip(iu, ju)]
    b = [linear(xy[p, 0], xy[p, 1], xy[q, 0], xy[q, 1])
         for p, q in zip(iu, ju)]
    assert a == b
    # discriminating both ways
    assert any(a) and not all(a)


def test_spine_membership_box_query_twins_the_buffer_query():
    """The candidate query dropped a per-vertex ``Point(...).buffer(TOL)``
    for a box.  This is the retired spelling, run side by side."""
    from shapely.geometry import Point
    ctx, shape, _ring = _crossing_ctx_and_shape()

    def _reference(shape, ctx):
        out = {}
        tree, idxs, _g = GG._polyline_tree(ctx, "cl")
        assert tree is not None
        svc_ok = GG._reads_service_spines(shape)
        for ri, (x, y) in enumerate(shape.ring):
            hits = []
            for k in tree.query(Point(x, y).buffer(GG.SPINE_PERP_TOL_M)):
                ci = idxs[int(k)]
                if not svc_ok and ctx.centerlines[ci].is_service:
                    continue
                a, d, _f = GG._project(ctx.centerlines[ci], x, y)
                if d <= GG.SPINE_PERP_TOL_M:
                    hits.append((ci, a))
            if hits:
                hits.sort()
                out[ri] = hits
        return out

    got = GG._spine_membership(shape, ctx)
    ref = _reference(shape, ctx)
    assert got == ref
    # key ORDER travels too: _build_spine_chains iterates this mapping
    assert list(got) == list(ref)
    assert got, "fixture produced no membership at all"


def test_shape_constraints_batched_and_unbatched_agree():
    """The whole function, both ways: with the vectorised predicate table
    and with it forced off (the per-pair thunks that are still there)."""
    ctx, shape, _ring = _crossing_ctx_and_shape()
    batched = GG.shape_constraints(shape, ctx)

    class _NoBatch:
        """The predicate factory's product minus its ``batch`` attribute,
        so ``shape_constraints`` takes the per-pair path."""
        def __init__(self, fn):
            self._fn = fn

        def __call__(self, *a):
            return self._fn(*a)

    real_vis, real_cross = (GG._visibility_predicate,
                            GG._spine_crossing_predicate)
    try:
        GG._visibility_predicate = lambda ring: (
            _NoBatch(real_vis(ring)) if real_vis(ring) is not None else None)
        GG._spine_crossing_predicate = lambda sh, c, m: (
            _NoBatch(real_cross(sh, c, m))
            if real_cross(sh, c, m) is not None else None)
        plain = GG.shape_constraints(shape, ctx)
    finally:
        GG._visibility_predicate = real_vis
        GG._spine_crossing_predicate = real_cross

    assert [(a, b, cap.flat_cap()) for (a, b, cap) in batched.edges] == \
           [(a, b, cap.flat_cap()) for (a, b, cap) in plain.edges]
    assert batched.spine_chains == plain.spine_chains
    assert batched.edges, "fixture produced no edges at all"


def test_overlap_clip_bbox_prefilter_twins_the_unfiltered_pass():
    """``_drop_overlap_against_fixed_shapes`` gained a bounding-box
    prefilter in front of its pairwise ``intersects``.  With the filter
    disabled the pass must reach the SAME shapes."""
    from shapely.geometry import box
    from auto_patch import elevation as EL
    from auto_patch.layout import BuiltShape, ROLE_APRON, ROLE_JUNCTION

    def _layout():
        class _L:
            pass
        lay = _L()
        lay.shapes = [
            BuiltShape(polygon=box(0, 0, 100, 100), role=ROLE_APRON),
            BuiltShape(polygon=box(90, 0, 200, 100), role=ROLE_APRON),
            BuiltShape(polygon=box(300, 300, 400, 400), role=ROLE_APRON),
            BuiltShape(polygon=box(95, 50, 120, 150), role=ROLE_JUNCTION),
            BuiltShape(polygon=box(1000, 0, 1100, 100), role=ROLE_JUNCTION),
        ]
        return lay

    filtered = _layout()
    EL._drop_overlap_against_fixed_shapes(filtered, include_aprons=True)

    unfiltered = _layout()
    real = EL._envelopes_disjoint
    try:
        EL._envelopes_disjoint = lambda a, b: False      # never prefilter
        EL._drop_overlap_against_fixed_shapes(unfiltered, include_aprons=True)
    finally:
        EL._envelopes_disjoint = real

    def _sig(lay):
        return [(s.role, s.polygon.wkt) for s in lay.shapes]

    assert _sig(filtered) == _sig(unfiltered)
    assert len(filtered.shapes) >= 3


# ── the RUN-SCOPED law memo (perf P3 lane perfgraph) ─────────────────────

class _RunLayout:
    """The minimum a run memo needs: something to hang it off."""


def _two_builds_ctx(layout, *, buildings=frozenset()):
    """A GradeContext as a second graph build would construct it — same
    law inputs, a fresh object, sharing ``layout``'s run memo."""
    cls = [GG.Centerline(pts=[(0.0, 30.0), (60.0, 30.0)],
                         seg_caps=[TAXI_MAX_GRADE])]
    ctx = GG.GradeContext(centerlines=cls, building_keys=frozenset(buildings))
    ctx._sc_run_memo = layout._sc_run_memo
    return ctx


def _run_shape():
    ring = [(0.0, 0.0), (60.0, 0.0), (60.0, 60.0), (0.0, 60.0),
            (0.0, 30.0), (60.0, 30.0)]
    return GG.GradeShape(role="apron", ring=ring, keys=list(range(len(ring))))


def _sig(sc):
    return ([(a, b, cap.cL, cap.cT, cap.budget) for (a, b, cap) in sc.edges],
            sc.spine_chains)


def test_run_memo_off_and_on_agree_across_two_graph_builds():
    """THE TWIN: two graph builds of the same shape, run memo ON (the
    second is served from the first) and OFF (both computed).  The
    constraint sets must be identical — the memo is a saving, never a
    different answer."""
    lay = _RunLayout()
    lay._sc_run_memo = {}
    shape = _run_shape()

    real = GG.SC_RUN_MEMO
    try:
        GG.SC_RUN_MEMO = False
        a1 = GG.shape_constraints_cached(1, shape, _two_builds_ctx(lay))
        a2 = GG.shape_constraints_cached(1, shape, _two_builds_ctx(lay))
        assert not lay._sc_run_memo, "kill switch still populated the memo"

        GG.SC_RUN_MEMO = True
        b1 = GG.shape_constraints_cached(1, shape, _two_builds_ctx(lay))
        b2 = GG.shape_constraints_cached(1, shape, _two_builds_ctx(lay))
    finally:
        GG.SC_RUN_MEMO = real

    assert _sig(a1) == _sig(a2) == _sig(b1) == _sig(b2)
    assert a1.edges, "fixture produced no edges at all"
    # and the memo really served the second build rather than recomputing
    assert b2 is b1
    assert a2 is not a1


def test_run_memo_key_is_sensitive_to_every_input_it_covers():
    """THE SENSITIVITY ARM: poison ONE key component at a time and the
    second build must MISS.  A key that cannot see an input is a
    wrong-answer machine, so each of these is a rail, not a nicety."""
    lay = _RunLayout()
    lay._sc_run_memo = {}
    shape = _run_shape()
    base = GG.shape_constraints_cached(1, shape, _two_builds_ctx(lay))

    def _misses(ctx=None, sh=None, ring_only=False):
        before = len(lay._sc_run_memo)
        got = GG.shape_constraints_cached(
            2, sh or shape, ctx or _two_builds_ctx(lay), ring_only=ring_only)
        return got is not base and len(lay._sc_run_memo) == before + 1

    # 1. building_keys — the mover that makes the whole tier worth having
    assert _misses(ctx=_two_builds_ctx(lay, buildings={0, 1}))
    # 2. seam_keys
    ctx = _two_builds_ctx(lay)
    ctx.seam_keys = frozenset({0})
    assert _misses(ctx=ctx)
    # 3. inherited_junction_cap's VALUE for this shape
    ctx = _two_builds_ctx(lay)
    ctx.centerlines = []
    ctx.inherited_junction_cap = lambda s: 0.0123
    assert _misses(ctx=ctx, sh=GG.GradeShape(
        role="junction", ring=shape.ring, keys=list(shape.keys)))
    # 4. centerlines (inside the ctx law digest)
    ctx = _two_builds_ctx(lay)
    ctx.centerlines = [GG.Centerline(pts=[(0.0, 10.0), (60.0, 10.0)],
                                     seg_caps=[TAXI_MAX_GRADE])]
    assert _misses(ctx=ctx)
    # 5. road_zone (also inside the digest, via its prepared geometry's wkb)
    from shapely.geometry import box as _box
    from shapely.prepared import prep as _prep
    ctx = _two_builds_ctx(lay)
    ctx.road_zone = _prep(_box(-5.0, -5.0, 65.0, 5.0))
    assert _misses(ctx=ctx)
    # 6. the ring itself
    moved = GG.GradeShape(role=shape.role, keys=list(shape.keys),
                          ring=[(x, y + 0.5) for (x, y) in shape.ring])
    assert _misses(sh=moved)
    # 7. the node keys
    rekeyed = GG.GradeShape(role=shape.role, ring=list(shape.ring),
                            keys=[k + 100 for k in shape.keys])
    assert _misses(sh=rekeyed)
    # 8. ring_only
    assert _misses(ring_only=True)


def test_run_memo_refuses_a_ctx_it_cannot_digest():
    """``mesh_edges_exact`` is the validator's structure and is not
    digestible here — the memo must switch ITSELF off rather than key an
    input it cannot see."""
    lay = _RunLayout()
    lay._sc_run_memo = {}
    shape = _run_shape()
    ctx = _two_builds_ctx(lay)
    ctx.mesh_edges_exact = GG.MeshEdgesExact([])
    assert GG._sc_run_key(shape, ctx, False) is None
    GG.shape_constraints_cached(1, shape, ctx)
    assert not lay._sc_run_memo


def test_run_memo_is_scoped_to_one_layout_and_to_the_solver_key_space():
    """``build_context`` hangs the memo off the LAYOUT, so a process that
    builds two airports never serves one's answers to the other — and it
    attaches ONLY in the solver key space, because the validator's
    ring-index keys are collidable with small solver node indices."""
    class _L:
        anchor = (0.0, 0.0)
        shapes = []
        canonical_points = None

    a, b = _L(), _L()
    ctx_a = GG.build_context(a, {})
    ctx_b = GG.build_context(b, {})
    assert ctx_a._sc_run_memo is a._sc_run_memo
    assert ctx_b._sc_run_memo is b._sc_run_memo
    assert ctx_a._sc_run_memo is not ctx_b._sc_run_memo
    # a second ctx on the SAME layout shares the one store
    assert GG.build_context(a, {})._sc_run_memo is ctx_a._sc_run_memo
    # the VALIDATOR space (bucket_to_idx None) never joins the memo
    validator = GG.build_context(a, None)
    assert getattr(validator, "_sc_run_memo", None) is None


# ── centerline_specs: the input-keyed memo (perf P3 lane perfcenter) ────
#
# THE SINK.  ``centerline_specs`` is THE law's centerline enumeration and it
# had no memo: ``build_context`` walks it twice per graph build and
# ``verification``'s two sidecar exports walk it again, so a build reached it
# 9-11 times and the dupcensus measured ONE distinct input fingerprint behind
# all of them (HECA replay 11/1, full build 9/1).  The memo below serves the
# answer for exactly as long as its INPUTS are unchanged; these twins are the
# proof that "unchanged" means every input, not the ones that happened to
# move at HECA.

class _CLine:
    """The ``apt_dat_reader.TaxiCenterline`` surface the law reads."""

    def __init__(self, pts, is_service=False, seg_sizes=None, route_line=None):
        from shapely.geometry import LineString
        self.line = LineString(pts)
        self.route_line = route_line
        self.is_service = is_service
        self.name = "svc" if is_service else "T"
        self.seg_sizes = (list(seg_sizes) if seg_sizes is not None
                          else [""] * (len(pts) - 1))


def _cls_layout(*, sliced=None, corridors=None, shared_route=True):
    """A layout carrying every branch of the enumeration: two bend-split taxi
    pieces (sharing one ``route_line`` object, or not), an apt.dat service
    route, and optionally a sliced road set and corridor courses."""
    from shapely.geometry import LineString
    route_pts = [(0.0, -100.0), (0.0, 260.0)]
    r1 = LineString(route_pts)
    r2 = r1 if shared_route else LineString(route_pts)

    class _L:
        pass

    lay = _L()
    lay.icao = "TEST"
    lay.apt_taxi_centerlines = [
        _CLine([(0.0, -100.0), (0.0, 100.0)], seg_sizes=["C"], route_line=r1),
        _CLine([(0.0, 100.0), (0.0, 260.0)], seg_sizes=["A"], route_line=r2),
        _CLine([(0.0, 0.0), (50.0, 0.0)], is_service=True),
    ]
    if sliced is not None:
        lay._slice_service_subsegments = [LineString(p) for p in sliced]
    if corridors is not None:
        lay._service_corridor_lines = [LineString(p) for p in corridors]
    return lay


_SLICED = [[(12.0, 0.0), (50.0, 0.0)], [(50.0, 0.0), (110.0, 0.0)]]
_CORRIDORS = [[(12.0, 0.0), (110.0, 0.0)]]


def _computation_counter(monkeypatch):
    """Count how many times the UNCACHED computation actually runs."""
    calls = []
    real = GG._centerline_specs_uncached

    def _counted(layout):
        calls.append(1)
        return real(layout)

    monkeypatch.setattr(GG, "_centerline_specs_uncached", _counted)
    return calls


def test_specs_memo_serves_exactly_what_it_would_have_computed(monkeypatch):
    """Memo ON vs OFF on the same layout: equal answers, and the ON arm
    proves it SERVED rather than recomputed."""
    lay_off = _cls_layout(sliced=_SLICED, corridors=_CORRIDORS)
    monkeypatch.setattr(GG, "CENTERLINE_SPECS_MEMO", False)
    calls = _computation_counter(monkeypatch)
    off = [GG.centerline_specs(lay_off) for _ in range(3)]
    assert len(calls) == 3, "with the memo off every call must recompute"
    assert off[0] == off[1] == off[2]

    monkeypatch.setattr(GG, "CENTERLINE_SPECS_MEMO", True)
    lay_on = _cls_layout(sliced=_SLICED, corridors=_CORRIDORS)
    calls.clear()
    on = [GG.centerline_specs(lay_on) for _ in range(3)]
    assert len(calls) == 1, "the memo must SERVE calls 2 and 3, not recompute"
    assert on[0] == on[1] == on[2]
    # Route keys carry object ids, so compare everything else verbatim and
    # the route GROUPING (which is all a route key ever means) structurally.
    assert ([(p, c, s, r) for (p, c, s, _k, r) in on[0]]
            == [(p, c, s, r) for (p, c, s, _k, r) in off[0]])
    assert (_route_grouping(on[0]) == _route_grouping(off[0]))


def _route_grouping(specs):
    """Route keys as ORDINALS of first appearance — the only thing a caller
    (``build_context``, ``taxi_axes_exact_ll``) ever does with them."""
    seen: dict = {}
    return [seen.setdefault(rkey, len(seen)) for (_p, _c, _s, rkey, _r) in specs]


def test_specs_memo_hands_every_caller_its_own_lists(monkeypatch):
    """``build_context`` stores ``pts``/``seg_caps`` straight onto its
    ``Centerline``/``RouteChain`` objects, so a shared list would put one
    graph build's answer inside another's.  The ``rpts is pts`` ALIASING the
    uncached path produces is preserved exactly."""
    monkeypatch.setattr(GG, "CENTERLINE_SPECS_MEMO", True)
    lay = _cls_layout(sliced=_SLICED)
    a = GG.centerline_specs(lay)
    b = GG.centerline_specs(lay)
    assert a is not b
    for (sa, sb) in zip(a, b):
        assert sa[0] is not sb[0] and sa[1] is not sb[1]
        assert sa[0] == sb[0] and sa[1] == sb[1]
        # a sliced/corridor piece IS its own route: the alias must survive
        assert (sa[4] is sa[0]) == (sb[4] is sb[0])
    svc = [s for s in a if s[2]]
    assert svc and all(s[4] is s[0] for s in svc)
    a[0][0].append((999.0, 999.0))          # poison the caller's copy
    assert GG.centerline_specs(lay)[0][0] == b[0][0]


def test_specs_memo_sensitivity_every_read_set_component_misses(monkeypatch):
    """THE SENSITIVITY ARM.  Poison each member of the read set one at a
    time; each must change the key, i.e. MISS.  A key that cannot see an
    input is a wrong-answer machine, and the census's identity duplicates
    are evidence that HECA does not move these — never proof that no airport
    does."""
    from shapely.geometry import LineString
    from auto_patch import config as CFG

    def _key(lay):
        return GG._cls_specs_key(lay)

    base = _cls_layout(sliced=_SLICED, corridors=_CORRIDORS)
    k0 = _key(base)
    assert k0 is not None and _key(_cls_layout(
        sliced=_SLICED, corridors=_CORRIDORS)) == k0, (
        "an equal layout must key EQUAL, or the memo never hits")

    # 1. a centerline's own geometry
    lay = _cls_layout(sliced=_SLICED, corridors=_CORRIDORS)
    lay.apt_taxi_centerlines[0].line = LineString([(0.0, -100.0), (1.0, 100.0)])
    assert _key(lay) != k0
    # 2. the is_service flag (it selects the whole service branch)
    lay = _cls_layout(sliced=_SLICED, corridors=_CORRIDORS)
    lay.apt_taxi_centerlines[0].is_service = True
    assert _key(lay) != k0
    # 3. seg_sizes (the per-letter cap table)
    lay = _cls_layout(sliced=_SLICED, corridors=_CORRIDORS)
    lay.apt_taxi_centerlines[0].seg_sizes = ["A"]
    assert _key(lay) != k0
    # 4. the route-line SHARING pattern — same coordinates, two objects, so
    #    two routes instead of one.  A pure value digest cannot see this.
    split = _cls_layout(sliced=_SLICED, corridors=_CORRIDORS,
                        shared_route=False)
    assert _key(split) != k0
    assert (_route_grouping(GG._centerline_specs_uncached(split))
            != _route_grouping(GG._centerline_specs_uncached(base))), (
        "the split must really change the answer, or this arm proves nothing")
    # 5. the sliced road set's content
    lay = _cls_layout(sliced=[_SLICED[0]], corridors=_CORRIDORS)
    assert _key(lay) != k0
    # 6. PRESENCE, not truthiness: absent vs present-and-empty are different
    #    service SOURCES ("presence of the attribute is the switch").
    absent = _cls_layout(corridors=_CORRIDORS)
    empty = _cls_layout(sliced=[], corridors=_CORRIDORS)
    assert _key(absent) != _key(empty) != k0
    # 7. the corridor courses
    lay = _cls_layout(sliced=_SLICED, corridors=[[(12.0, 1.0), (110.0, 1.0)]])
    assert _key(lay) != k0
    # 8-13. the config / module values the computation reads
    for (mod, name, value) in (
            (CFG, "SERVICE_CORRIDOR_CHAINS", False),
            (CFG, "SERVICE_ROAD_MAX_GRADE", 0.07),
            (CFG, "SERVICE_ROAD_WIDTH_M", 9.0),
            (CFG, "TAXI_GRADE_BY_WIDTH", not TAXI_GRADE_BY_WIDTH),
            (CFG, "TAXI_MAX_GRADE", 0.02),
            (CFG, "TAXI_MAX_GRADE_NARROW", 0.04),
            (CFG, "NARROW_TAXI_CODE_LETTERS", frozenset({"A"})),
            (GG, "_CORRIDOR_COVER_FRAC", 0.9)):
        monkeypatch.setattr(mod, name, value)
        assert _key(base) != k0, f"{name} is in the read set and must key"
        monkeypatch.undo()


def test_specs_memo_recomputes_when_the_layout_moves(monkeypatch):
    """End to end: a write to the read set after a warm memo recomputes."""
    from shapely.geometry import LineString
    monkeypatch.setattr(GG, "CENTERLINE_SPECS_MEMO", True)
    calls = _computation_counter(monkeypatch)
    lay = _cls_layout()
    first = GG.centerline_specs(lay)
    GG.centerline_specs(lay)
    assert len(calls) == 1
    lay._slice_service_subsegments = [LineString(p) for p in _SLICED]
    second = GG.centerline_specs(lay)
    assert len(calls) == 2, "the slice's write must MISS the warm memo"
    assert second != first
    assert second == GG._centerline_specs_uncached(lay)


def test_specs_memo_declines_an_input_it_cannot_digest(monkeypatch):
    """A geometry with no ``wkb`` is an input the key cannot see — the memo
    must switch ITSELF off rather than key on what it can read."""
    monkeypatch.setattr(GG, "CENTERLINE_SPECS_MEMO", True)

    class _Opaque:
        is_empty = False
        coords = [(0.0, 0.0), (10.0, 0.0)]

    lay = _cls_layout()
    lay.apt_taxi_centerlines[0].line = _Opaque()
    assert GG._cls_specs_key(lay) is None
    calls = _computation_counter(monkeypatch)
    GG.centerline_specs(lay)
    GG.centerline_specs(lay)
    assert len(calls) == 2, "an undigestible layout must never be memoed"
    assert getattr(lay, "_cls_specs_memo", None) is None


def test_specs_memo_is_scoped_to_one_layout(monkeypatch):
    """The store hangs off the LAYOUT, so a process that builds two airports
    (a tile) never serves one's centerlines to the other."""
    monkeypatch.setattr(GG, "CENTERLINE_SPECS_MEMO", True)
    calls = _computation_counter(monkeypatch)
    a = _cls_layout(sliced=_SLICED)
    b = _cls_layout(sliced=[_SLICED[0]])
    GG.centerline_specs(a)
    GG.centerline_specs(b)
    GG.centerline_specs(a)
    GG.centerline_specs(b)
    assert len(calls) == 2
    assert a._cls_specs_memo[0] != b._cls_specs_memo[0]


# ── the per-ctx CONTENT key (finalarch item 2, RULINGS 2026-08-14) ───

def test_per_ctx_memo_cannot_collide_on_a_recycled_polygon_id():
    """THE DEFECT CLASS, as a twin.  The historical per-ctx key was
    ``(id(s.polygon), role, ring_only)``; a ctx carried across the
    freeze→solve gap let a RECYCLED id serve one shape another shape's
    pairs (measured at HECA: within_shape 3,764 → 5,629, worst 431 %).
    Same ``polygon_key``, different ring ⇒ two distinct answers."""
    lay = _RunLayout()
    lay._sc_run_memo = {}
    ctx = _two_builds_ctx(lay)
    a = GG.shape_constraints_cached(123, _run_shape(), ctx)
    base = _run_shape()
    moved = GG.GradeShape(role=base.role, keys=list(base.keys),
                          ring=[(x, y + 7.0) for (x, y) in base.ring])
    b = GG.shape_constraints_cached(123, moved, ctx)
    assert b is not a, (
        "a recycled polygon id served one shape another shape's "
        "constraint pairs — the per-ctx memo is keyed by identity again")


def test_per_ctx_memo_hits_by_content_never_by_object_identity():
    """The freeze→solve collapse's enabling property: the SAME shape
    presented under two different polygon ids (two graph builds of one
    frozen layout) is ONE computation."""
    lay = _RunLayout()
    lay._sc_run_memo = {}
    ctx = _two_builds_ctx(lay)
    a = GG.shape_constraints_cached(111, _run_shape(), ctx)
    b = GG.shape_constraints_cached(222, _run_shape(), ctx)
    assert b is a, (
        "two spellings of one shape recomputed — the published frozen "
        "ctx cannot be build-once-read-many under this key")


def test_per_ctx_memo_key_is_sensitive_to_the_gradeshape_flags():
    """The gate-off ``adopts_*`` flags are IN the key: two GradeShapes
    that differ only there must not share an answer (the old id key let
    whichever consumer ran first fix the answer for both)."""
    lay = _RunLayout()
    lay._sc_run_memo = {}
    ctx = _two_builds_ctx(lay)
    base = _run_shape()
    a = GG.shape_constraints_cached(1, base, ctx)
    flagged = GG.GradeShape(role=base.role, ring=list(base.ring),
                            keys=list(base.keys), adopts_apron_grade=True)
    b = GG.shape_constraints_cached(1, flagged, ctx)
    assert b is not a


# ═══════════════════════════════════════════════════════════════════════
# R3 — TRANSVERSE CAP WITHOUT A SHARED ROUTE (service-road law spec
# 2026-08-15).  A service-family pair whose endpoints find no SHARED
# nearest route bakes against the nearest route of EITHER endpoint
# (tightest budget wins) instead of staying isotropic at the 8 % road
# cap; a pair genuinely off-network stays isotropic as before.
# ═══════════════════════════════════════════════════════════════════════

def _two_parallel_service_routes():
    r0 = GG.RouteChain(pts=[(0.0, -50.0), (0.0, 50.0)])
    r1 = GG.RouteChain(pts=[(6.0, -50.0), (6.0, 50.0)])
    cl0 = GG.Centerline(pts=list(r0.pts), seg_caps=[SERVICE_ROAD_MAX_GRADE],
                        route_idx=0, is_service=True)
    cl1 = GG.Centerline(pts=list(r1.pts), seg_caps=[SERVICE_ROAD_MAX_GRADE],
                        route_idx=1, is_service=True)
    return GG.GradeContext(centerlines=[cl0, cl1], routes=[r0, r1])


def test_unshared_route_service_pair_takes_the_nearest_route_transverse_cap():
    from auto_patch import grade_law as GL
    ctx = _two_parallel_service_routes()
    allow = GL.Allowance(SERVICE_ROAD_MAX_GRADE, SERVICE_ROAD_MAX_GRADE)
    pa, pb = (0.0, 0.0), (6.0, 0.0)
    # endpoints sit ON different routes → _edge_route is None (unshared)
    out = GG._bake_edge(allow, "service_road", pa, pb, set(), ctx,
                        (0, 0.0), (1, 0.0))
    cT = GG._transverse_cap_for_longitudinal_cap(SERVICE_ROAD_MAX_GRADE)
    assert cT < SERVICE_ROAD_MAX_GRADE, "service pairs owe a tighter cT"
    assert out.budget is not None, "the pair must be BAKED, not isotropic"
    assert out.budget == pytest.approx(cT * 6.0), (
        f"budget {out.budget}: a pure cross-road pair owes cT×width")
    assert out.budget < SERVICE_ROAD_MAX_GRADE * 6.0
    assert getattr(ctx, "_svc_pair_route_migrated", 0) == 1


def test_genuinely_off_network_service_pair_stays_isotropic():
    from auto_patch import grade_law as GL
    ctx = _two_parallel_service_routes()
    allow = GL.Allowance(SERVICE_ROAD_MAX_GRADE, SERVICE_ROAD_MAX_GRADE)
    inf = float("inf")
    out = GG._bake_edge(allow, "service_road", (200.0, 0.0), (206.0, 0.0),
                        set(), ctx, (-1, inf), (-1, inf))
    assert out is allow, "no route at all → isotropic, as today"
    # within reach of a route index but OUTSIDE the perp tolerance:
    far = GG.SERVICE_SPINE_PERP_TOL_M + 1.0
    out2 = GG._bake_edge(allow, "service_road", (200.0, 0.0), (206.0, 0.0),
                         set(), ctx, (0, far), (1, far))
    assert out2 is allow, (
        "beyond the service perp tolerance the pair is off-network")
    assert getattr(ctx, "_svc_pair_route_migrated", 0) == 0


def test_non_service_unshared_route_pair_is_untouched_by_r3():
    from auto_patch import grade_law as GL
    ctx = _two_parallel_service_routes()
    allow = GL.Allowance(APRON_MAX_GRADE, APRON_MAX_GRADE)
    out = GG._bake_edge(allow, "apron", (0.0, 0.0), (6.0, 0.0), set(), ctx,
                        (0, 0.0), (1, 0.0))
    assert out is allow, (
        "R3 migrates the SERVICE family only; an apron pair spanning two "
        "routes' Voronoi cells stays isotropic exactly as before")


# ══════════════════════════════════════════════════════════════════════
# AN UNDECLARED CROWN ENDPOINT IS UNKNOWN, NOT ON THE RIDGE
# (wave-3 residual sweep; the R8 docket's two "diagonal" ws::runway rows).
#
# The crown field is exported per SOLVE-TIME node.  A ring vertex minted
# after the solve that ``crown.extend_field_to_new_ring_nodes`` did not
# reach is ABSENT from it — and ``crown_by_nid.get(nid, 0.0)`` used to
# read that absence as "sits on the crown ridge", manufacturing an
# expected step equal to its neighbour's whole drop.  Nothing in the
# SOLVER makes that claim: ``build_unified_graph`` constrains only
# SOFT_VISIBILITY_ROLES and ``plane_constraints`` — the runway ring's
# pair set — has no caller outside tools/check_grade.py.
# ══════════════════════════════════════════════════════════════════════

def test_a_declared_pair_keeps_its_crown_target():
    from auto_patch.grade_law import (crown_pair_offset,
                                      crown_pair_offset_interval as ITV,
                                      crown_pair_offset_clamped as CLAMP)
    assert ITV(0.3, 0.0) == (crown_pair_offset(0.3, 0.0),) * 2
    off, unk = CLAMP(0.3, 0.0, 0.65)
    assert off == crown_pair_offset(0.3, 0.0) and unk is False


def test_an_uncrowned_pair_is_byte_identical():
    """Neither endpoint declared — an uncrowned patch, or an uncrowned
    region of a crowned one — reads exactly as before."""
    from auto_patch.grade_law import (crown_pair_offset_interval as ITV,
                                      crown_pair_offset_clamped as CLAMP)
    assert ITV(None, None) == (0.0, 0.0)
    assert CLAMP(None, None, 4.2) == (0.0, False)
    # a DECLARED ridge node beside an undeclared one implies no step either
    assert ITV(0.0, None) == (0.0, 0.0)
    assert CLAMP(None, 0.0, 4.2) == (0.0, False)


def test_an_undeclared_endpoint_is_not_placed_on_the_ridge():
    """HECA way -12222, nodes -17936 -> -17914: a declared 0.30 m drop
    against an undeclared neighbour.  The measured step is +0.65 m over
    59.04 m — 1.10 %, under the 1.5 % cap — and the ridge default turned it
    into a 0.95 m excess."""
    from auto_patch.grade_law import crown_pair_offset_clamped as CLAMP
    off, unk = CLAMP(0.3, None, 0.65)
    assert off == pytest.approx(0.0)        # the nearest compatible target
    assert abs(0.65 - off) == pytest.approx(0.65)   # NOT 0.95
    assert unk is False                     # outside the interval: priced


def test_a_step_inside_the_compatible_interval_is_unpriceable_and_counted():
    """HECA way -12220, nodes -33497 -> -33498: measured -0.06 m against a
    declared 0.30 m neighbour.  Every compatible declaration explains it,
    so it carries no excess — and the reader must be able to COUNT it."""
    from auto_patch.grade_law import crown_pair_offset_clamped as CLAMP
    off, unk = CLAMP(0.3, None, -0.06)
    assert off == pytest.approx(-0.06) and unk is True


def test_the_interval_never_blinds_a_genuinely_over_cap_pair():
    """A pair over cap under EVERY compatible declaration keeps its FULL
    excess — the clamp may only remove a fabricated one.  Measured: 3 of
    the 6 HECA pairs a plain skip would have dropped are over cap on their
    raw grade too."""
    from auto_patch.grade_law import crown_pair_offset_clamped as CLAMP
    # interval spans [-0.3, 0]; a 5 m step is outside it on the high side
    off, unk = CLAMP(0.3, None, 5.0)
    assert off == pytest.approx(0.0) and unk is False
    assert abs(5.0 - off) == pytest.approx(5.0)
    # …and on the low side
    off, unk = CLAMP(0.3, None, -9.0)
    assert off == pytest.approx(-0.3) and unk is False
    assert abs(-9.0 - off) == pytest.approx(8.7)


def test_the_runway_pair_set_is_the_validators_alone():
    """The premise of the whole fix: the SOLVER never priced these pairs,
    so the expected step was minted by the reader.  ``plane_constraints``
    is the runway ring's pair set and the solver's constraint graph does
    not scope runways into its within-shape domain."""
    import auto_patch.grade_graph as GG
    assert "runway" not in GG.SOFT_VISIBILITY_ROLES
    assert "runway_crossing" not in GG.SOFT_VISIBILITY_ROLES
