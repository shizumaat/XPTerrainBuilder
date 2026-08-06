"""ROUTE-BAND confirmation on THE unified grade graph G (handover item 1).

The solver bounds every airside node by the runway-reach band
(``building_feasibility.reach_band_unified``: a cap-Dijkstra over ``G.spine_adj``
from the runway anchors).  ``grade_graph_validate.route_band_violations`` is the
AS-BUILT confirmation of that bound on the SAME graph G — one graph, no separate
route-field.  A vertex outside its band is an infeasibility to ROOT-CAUSE (a
solver bug, a missing rule, or a rule needing adjustment), NEVER ignored:

  * ``ceil``  — above the reachable ceiling (steeper than cap from every runway);
  * ``floor`` — below the reachable floor;
  * ``pinned`` — the band is EMPTY (``floor > ceiling``): no compliant elevation
    exists at the vertex (mutually-unreachable runway anchors); fix is upstream.

TILE-SEAM TERRAIN CONTRACT (owner rulings 2026-06-20 / 2026-07-24).  Where
pavement crosses a tile boundary the surface must MATCH the neighbour tile's
terrain mesh, so an airside seam pin is anchored to the raw DEM and can sit
BELOW the runway-anchored band; the solver then correctly grades the pin's
neighbours down to it.  ``route_band_violations`` therefore YIELDS inside the
seam terrain-matching corridor by exactly the MEASURED amount that line's own
pins sit out of band — per crossed seam line, per side.  The band is a derived
solver self-consistency device (docs/route_field_model.md), not a citable
aerodrome standard; the citable per-edge taxi cap is unaffected and still binds
the seam approach.  The hermetic tests at the bottom of this file hold that
yield to its bound: no pins ⇒ no allowance, a feasible pin ⇒ no allowance, and a
vertex deeper out of band than the pins explain STILL flags.

CYXY's apron-ceiling defect (the A2-end apron / building over-pinning issue) is
GONE — measured at HEAD, its raw population is empty (cycle-5 instrument-fix
spec item 3; before item 1 it was 2 junction rows 17-26 m from a runway ring,
grading to that runway's own value inside the taxi cap, which the runway-datum
exemption now covers).  HECA (multi-runway empty bands) still carries
violations; its zero-outcome is xfail-tracked (the check still RUNS and the
count is surfaced — not ignored), and flips to XPASS the moment the solver/rule
places every vertex in its band.

NO DISCRETIZATION EXCUSE (cycle-5 item 2).  ``test_route_band_zero`` used to
filter junction rows under ``RASTER_REACH_BAND_GRID_RESIDUAL_M`` (0.25 m) as
grid-vs-continuous noise.  That constant is DELETED: the rows are invariant
under a 3.0 → 1.5 m cell sweep, so they are not discretization.  Every row
reports.  SPJC's ceil cluster (the ~0.3 m junction quartet, author
``final_grade_projection``) is therefore RED here on purpose until the
solve/projection round lands it — the instrument's job is to show it.
"""
from __future__ import annotations

import pytest

from conftest import cached_airport_layout

# Airports whose route-band outcome is currently RED — tracked, not ignored.
# Each is an infeasibility under root-cause (handover items 1–3); the xfail flips
# to XPASS the moment the solver/rule lands every airside vertex in its band.
# SPJC green since 2026-07-05 (and carries NO seam pins, so the seam yield is
# identically zero there — full gate sensitivity).  SPLP flipped to XPASS
# 2026-07-17 (the runway-datum reach exemption — vertices grading at cap from a
# local runway contact are the runway's own datum) and gates hard.  SPLP is the
# only fixture that CROSSES a tile line, so it is the only one where the
# measured tile-seam yield can be active at all: any sub-metre floor deficit its
# raw-DEM seam pins (2026-07-24 ruling) impose on the neighbouring junctions is
# covered by that yield — never by a widened constant — and the yield goes inert
# the moment the runway profile lands those pins back inside the band.
# DRAIN LEDGER ITEM CLOSED 2026-08-04 (test-maintenance lane) — CYXY
# REMOVED from this set, so its zero-outcome is now a LIVE GUARD.
#
# The marker's own contract was "flips to XPASS the moment the
# solver/rule lands every airside vertex in its band".  That happened
# and has held: ``test_route_band_zero[CYXY]`` is recorded as XPASS in
# 17 separate ledgered full-suite runs spanning 15 distinct code trees
# (``constants_absorb`` 2026-08-03 through ``seedfix-suite-lane``
# 2026-08-04), plus the 2026-08-04 baseline run at e07a3f6 — 18 in a
# row, never once xfailing.  It was ``strict=False``, so it could and
# did start passing silently; leaving it would have kept a solved
# infeasibility indefinitely invisible, which is the exact hole the
# drain ledger exists to close.  Same disposition as c48ce36's two.
#
# What actually closed it: CYXY's remaining raw route-band violations
# were all junction-role rows 17-26 m from a runway ring, each grading to
# that runway's own value INSIDE the taxi cap — the runway-datum class.
# They were excused first by a filter (the deleted grid-residual constant)
# and are now covered by the runway-datum exemption itself, scoped to the
# join/contact law's reach (cycle-5 items 1 and 2).  CYXY's raw
# population is EMPTY, which is why the ex-anti-gaming fixture below
# asserts that emptiness plus an injected overshoot rather than a defect
# that no longer exists.
#
# HECA stays: it xfailed in the same runs, still a real infeasibility.
_KNOWN_RED = {"HECA"}
_FIXTURES = ["SPJC", "CYXY", "SPLP", "HECA"]


def _param(icao):
    if icao in _KNOWN_RED:
        return pytest.param(icao, marks=pytest.mark.xfail(
            reason="route-band infeasibility under root-cause (handover items "
                   "1–3) — the check runs and surfaces the count; flips to "
                   "XPASS when every airside vertex lands in its reach band",
            strict=False))
    return icao


@pytest.mark.xdist_group("CYXY")   # reuse CYXY's already-built layout
def test_route_band_cyxy_is_empty_and_the_checker_still_bites():
    """THE CURRENT POPULATION'S INVARIANT (cycle-5 instrument-fix spec item 3).

    This test used to assert that CYXY still had APRON vertices above their
    reach ceiling — the A2-end apron / building over-pinning defect.  That
    defect is gone: measured at HEAD the raw population was 2 rows, both
    ``floor``, both ``junction``-role, both 17-26 m from a 14R/32L ring vertex
    and grading to that runway's own value at 1.11-1.15 % (inside
    ``TAXI_MAX_GRADE``) — the runway-datum class, not an apron ceiling; and
    with the exemption scoped to the join/contact law's reach (item 1) the
    population is EMPTY.  Asserting a defect that no longer exists makes the
    suite red for good news, which is a broken instrument, not a finding.

    What replaces it is the invariant that actually needs guarding once a
    population goes to zero: that the zero is REAL.  ``test_route_band_zero``
    covers CYXY as a live gate, so the anti-gaming duty here is to prove the
    checker is not a no-op ON THIS LAYOUT — the same +50 m injector duty
    ``test_route_band_detects_injected_overshoot`` carries at SPJC, run here
    on the layout whose zero it protects (same cached build, no extra cost).
    """
    import copy
    from auto_patch.grade_graph_validate import route_band_violations
    from auto_patch.layout import ROLE_JUNCTION
    layout = cached_airport_layout("CYXY")
    v = route_band_violations(layout)
    assert not v, (
        "CYXY's route-band population is no longer empty: "
        + "; ".join(f"{t[1]} {t[0]:.3f}m {t[2]}@({t[3]:.0f},{t[4]:.0f})"
                    for t in v[:6])
        + " — re-read the population before adjusting this test; the previous "
          "occupants were the runway-datum class (cycle-5 spec items 1/3)")
    bumped_layout = copy.copy(layout)
    bumped_layout.shapes = [copy.copy(s) for s in layout.shapes]
    bumped = 0
    for s in bumped_layout.shapes:
        if (s.role == ROLE_JUNCTION and s.node_altitudes
                and s.polygon is not None and not s.polygon.is_empty):
            s.node_altitudes = [
                float(a) + 50.0 if a is not None else a
                for a in s.node_altitudes]
            bumped += 1
    assert bumped, "no junction with node_altitudes to perturb"
    injected = route_band_violations(bumped_layout)
    assert any(t[1] == "ceil" for t in injected), (
        "a +50 m junction overshoot at CYXY was not flagged ceil — the empty "
        "population above is a no-op checker, not a lawful surface")


@pytest.mark.xdist_group("SPJC")   # reuse SPJC's already-built layout
def test_route_band_detects_injected_overshoot():
    """ANTI-GAMING: a vertex shoved well above its band MUST be flagged ``ceil``,
    so the gate cannot be quietly weakened (looser band, dropped vertices).  Uses
    SPJC (otherwise clean) so the flag can only come from the injected step.  The
    band is positional (runway anchors + spine geometry), so bumping junction
    elevations does not move the band — it only pushes the vertex out of it."""
    import copy
    from auto_patch.grade_graph_validate import route_band_violations
    from auto_patch.layout import ROLE_JUNCTION
    layout = copy.copy(cached_airport_layout("SPJC"))
    layout.shapes = [copy.copy(s) for s in layout.shapes]
    bumped = 0
    for s in layout.shapes:
        if (s.role == ROLE_JUNCTION and s.node_altitudes
                and s.polygon is not None and not s.polygon.is_empty):
            s.node_altitudes = [
                float(a) + 50.0 if a is not None else a for a in s.node_altitudes]
            bumped += 1
    assert bumped, "no junction with node_altitudes to perturb"
    v = route_band_violations(layout)
    assert any(t[1] == "ceil" for t in v), (
        "a +50 m junction overshoot was not flagged ceil — the band check is "
        "too weak; do not relax it to fake route-band=0")


@pytest.mark.parametrize("icao", [_param(a) for a in _FIXTURES])
def test_route_band_zero(icao):
    """OUTCOME: zero route-band violations — every airside vertex sits inside the
    runway-reach band on the ONE graph G.  SPJC and CYXY are live gates; HECA is
    an xfail-tracked infeasibility (the check runs, the count is surfaced — NOT
    ignored).

    NO EXCUSE FILTER (cycle-5 instrument-fix spec item 2).  This test used to
    drop every junction row at or under ``RASTER_REACH_BAND_GRID_RESIDUAL_M``
    (0.25 m) as grid-vs-continuous discretization noise.  The constant is
    DELETED and the filter with it: rebuilding the band at 3.0 / 2.0 / 1.5 m
    cells leaves the rows invariant (55 raw rows at every cell size, the
    ceiling at the worst vertex moving 0.023 m while the excess stays
    ~0.31 m), which falsifies the discretization mechanism outright.  The
    rows are surface, and the surface reports.  SPJC's ~0.3 m junction ceil
    cluster — measured author ``final_grade_projection`` — is consequently
    RED here until the solve/projection round lands it; that is the
    instrument working, not a regression to chase in a test."""
    from collections import Counter
    from auto_patch.grade_graph_validate import route_band_violations
    layout = cached_airport_layout(icao)
    if not layout.shapes:
        pytest.skip(f"{icao}: no shapes built")
    # ``t = (excess_m, side, role, x, y, elev, lo, hi)``
    v = route_band_violations(layout)
    cls = Counter(t[1] for t in v)
    assert not v, (
        f"{icao}: {len(v)} route-band violation(s) "
        f"(ceil={cls['ceil']}, floor={cls['floor']}, pinned={cls['pinned']}).  "
        f"worst: " + "; ".join(
            f"{t[1]} {t[0]:.1f}m {t[2]}@({t[3]:.0f},{t[4]:.0f})"
            for t in v[:4]))


# ══════════════════════════════════════════════════════════════════════════
# TILE-SEAM TERRAIN-CONTRACT YIELD (owner rulings 2026-06-20 / 2026-07-24)
#
# Hermetic unit tests for the measured seam yield inside
# ``grade_graph_validate.route_band_violations`` — no X-Plane install, no
# network, no airport build.  A synthetic layout plus an INJECTED band closure
# give exact control over every quantity the rule reads, so each property of
# the rule (bounded by the measured pin deficit, side-specific, corridor-scoped,
# zero without pins) is asserted in isolation.
# ══════════════════════════════════════════════════════════════════════════

_ANCHOR = (-12.5, -77.0)     # lon0 ON the integer line ⇒ the seam line is x = 0


def _sq(x, y, alt, size=1.0):
    """Unit-square ``junction`` whose FIRST ring vertex is exactly ``(x, y)``"""
    from shapely.geometry import Polygon
    from auto_patch.layout import BuiltShape, ROLE_JUNCTION
    return BuiltShape(
        polygon=Polygon([(x, y), (x + size, y),
                         (x + size, y + size), (x, y + size)]),
        role=ROLE_JUNCTION, node_altitudes=[float(alt)] * 5)


def _seam_layout(verts, pins=()):
    """``(layout, band)`` for a synthetic airport, one junction square per
    vertex under test.

    ``verts`` is ``[(x, y, elev, lo, hi), ...]``; the injected band constrains
    ONLY each square's first corner and returns ``None`` everywhere else — the
    same "off the spine network" answer a real coverage hole gives, so no other
    ring vertex can add noise.  ``pins`` lists the ``(x, y)`` positions
    published as solver tile-seam pins (``layout._seam_pin_ll``)."""
    from auto_patch.layout import PavementLayout
    layout = PavementLayout(icao="TEST", anchor=_ANCHOR)
    bands = {}
    for (x, y, e, lo, hi) in verts:
        layout.shapes.append(_sq(x, y, e))
        bands[(round(x, 2), round(y, 2))] = (float(lo), float(hi))
    if pins:
        layout._seam_pin_ll = [layout.m_to_ll(px, py) for (px, py) in pins]

    def band(px, py):
        return bands.get((round(px, 2), round(py, 2)))
    return layout, band


def _run(monkeypatch, layout, band, yield_on=True):
    """``route_band_violations`` on a synthetic layout with the band injected.

    Passing a non-``None`` ``G`` skips the node-list / unified-graph build, so
    the only collaborator left is ``reach_band_unified`` — replaced here by the
    caller's exact band."""
    from auto_patch.elevation_per_surface import building_feasibility as BF
    from auto_patch import grade_graph_validate as GGV
    monkeypatch.setattr(BF, "reach_band_unified", lambda _l, _g: band)
    if not yield_on:
        monkeypatch.setattr(GGV, "_seam_contract_yield",
                            lambda _l, viol, _b, _n, _c: viol)
    return GGV.route_band_violations(layout, G=object())


def _at(viol, x, y):
    """The violation reported at ``(x, y)``, or ``None``."""
    for t in viol:
        if abs(t[3] - x) < 0.01 and abs(t[4] - y) < 0.01:
            return t
    return None


def test_seam_yield_still_flags_a_vertex_deeper_than_the_contract(monkeypatch):
    """ANTI-GAMING (the load-bearing test).  The seam allowance is bounded by
    the MEASURED pin deficit, so a vertex that sits deeper out of band than the
    seam contract can explain MUST still flag.  Same seam line, same corridor,
    same side — only the depth differs."""
    layout, band = _seam_layout(
        [(0.0, 0.0, 100.00, 100.20, 130.0),    # the seam pin: 0.20 m deficit
         (50.0, 0.0, 99.95, 100.05, 130.0),    # 0.10 m — inside the bound
         (100.0, 0.0, 99.00, 100.00, 130.0)],  # 1.00 m — far past it
        pins=[(0.0, 0.0)])
    v = _run(monkeypatch, layout, band)
    deep = _at(v, 100.0, 0.0)
    assert deep is not None, (
        "a 1.00 m floor deficit beside a 0.20 m seam pin was swallowed — the "
        "seam yield is unbounded; it must never exceed the measured deficit")
    assert deep[1] == "floor" and abs(deep[0] - 1.0) < 1e-6
    # …and the yield is not a no-op: the two within-bound vertices are gone.
    assert _at(v, 50.0, 0.0) is None
    assert _at(v, 0.0, 0.0) is None


def test_seam_allowance_is_measured_never_a_constant(monkeypatch):
    """ANTI-GAMING.  The bound is the pin's OWN deficit, never a constant: a
    0.20 m excess beside a pin that is only 0.05 m out of band still flags.

    Renamed from ``…_not_the_grid_residual`` with cycle-5 item 2: the constant
    it named (``RASTER_REACH_BAND_GRID_RESIDUAL_M``, 0.25 m) is deleted, and
    0.20 m is exactly the size of row that used to be swallowed by it.  The
    property under test is unchanged and is now the ONLY allowance this check
    grants — a measured, per-seam-line, side-specific quantity."""
    layout, band = _seam_layout(
        [(0.0, 0.0, 100.00, 100.05, 130.0),    # pin: 0.05 m deficit
         (50.0, 0.0, 99.80, 100.00, 130.0)],   # 0.20 m — well past the pin's
        pins=[(0.0, 0.0)])
    t = _at(_run(monkeypatch, layout, band), 50.0, 0.0)
    assert t is not None and t[1] == "floor", (
        "a 0.20 m deficit was excused by a 0.05 m seam pin — the allowance has "
        "become a constant instead of a measurement")


def test_seam_floor_deficit_does_not_excuse_a_ceiling(monkeypatch):
    """SIDE-SPECIFIC: pins that are below their floor buy floor slack only."""
    layout, band = _seam_layout(
        [(0.0, 0.0, 100.00, 100.20, 130.0),    # pin: FLOOR deficit 0.20
         (50.0, 0.0, 100.10, 90.0, 100.00),    # 0.10 m above the CEILING
         (100.0, 0.0, 99.90, 100.00, 130.0)],  # 0.10 m below the FLOOR
        pins=[(0.0, 0.0)])
    v = _run(monkeypatch, layout, band)
    ceil = _at(v, 50.0, 0.0)
    assert ceil is not None and ceil[1] == "ceil", (
        "a floor deficit at the seam pins excused a CEILING violation — the "
        "two sides must carry separate bounds")
    assert _at(v, 100.0, 0.0) is None, "the floor side should have yielded"


def test_seam_ceiling_excess_does_not_excuse_a_floor(monkeypatch):
    """SIDE-SPECIFIC, mirrored: pins above their ceiling buy ceiling slack
    only."""
    layout, band = _seam_layout(
        [(0.0, 0.0, 100.00, 90.0, 99.80),      # pin: CEILING excess 0.20
         (50.0, 0.0, 100.10, 90.0, 100.00),    # 0.10 m above the CEILING
         (100.0, 0.0, 99.90, 100.00, 130.0)],  # 0.10 m below the FLOOR
        pins=[(0.0, 0.0)])
    v = _run(monkeypatch, layout, band)
    flo = _at(v, 100.0, 0.0)
    assert flo is not None and flo[1] == "floor", (
        "a ceiling excess at the seam pins excused a FLOOR violation")
    assert _at(v, 50.0, 0.0) is None, "the ceiling side should have yielded"


def test_seam_yield_stops_at_the_terrain_matching_corridor(monkeypatch):
    """CORRIDOR SCOPE: the yield only reaches ``TILE_SEAM_ZONE_M`` (400 m, the
    owner-ruled TILE-seam terrain-matching zone — the same scope
    ``tools/check_grade`` and ``tools/grade_feasibility_audit`` use).  A vertex
    beyond it flags even when its excess is under the line's bound.

    Renamed from the bare ``_SEAM_ZONE_M`` by the seam-continuity-v2 §1
    vocabulary split: this is the GRATICULE corridor, unrelated to the
    graded-strip seam law in ``auto_patch.strip_seam_law``."""
    from auto_patch.grade_graph_validate import TILE_SEAM_ZONE_M
    assert TILE_SEAM_ZONE_M == 400.0
    layout, band = _seam_layout(
        [(0.0, 0.0, 100.00, 100.20, 130.0),     # pin: 0.20 m deficit
         (300.0, 0.0, 99.90, 100.00, 130.0),    # 300 m out — inside the zone
         (600.0, 0.0, 99.90, 100.00, 130.0)],   # 600 m out — beyond it
        pins=[(0.0, 0.0)])
    v = _run(monkeypatch, layout, band)
    assert _at(v, 300.0, 0.0) is None, "inside the corridor should yield"
    far = _at(v, 600.0, 0.0)
    assert far is not None and far[1] == "floor", (
        "a violation 600 m from the seam was excused — the yield must stop at "
        f"{TILE_SEAM_ZONE_M:.0f} m")


def test_no_seam_pins_leaves_every_verdict_untouched(monkeypatch):
    """ZERO BOUND: an airport with no seam pins (every single-tile airport, and
    SPJC among the fixtures) gets NO allowance — the verdicts are bit-for-bit
    what they were before the yield existed."""
    verts = [(0.0, 0.0, 100.00, 100.20, 130.0),
             (50.0, 0.0, 99.95, 100.05, 130.0),
             (100.0, 0.0, 99.00, 100.00, 130.0)]
    layout, band = _seam_layout(verts)               # ← no pins published
    before = _run(monkeypatch, layout, band, yield_on=False)
    monkeypatch.undo()
    after = _run(monkeypatch, layout, band)
    assert after == before, "the yield changed a no-seam-pin airport's verdicts"
    assert len(after) == 3, "all three out-of-band vertices must be reported"


def test_feasible_seam_pins_grant_no_allowance(monkeypatch):
    """D_line → 0.  Once the pins themselves sit inside the band (e.g. after the
    runway profile is reconciled toward the seam DEM), the measured allowance is
    zero and the yield stops exempting anything — no residual special case."""
    layout, band = _seam_layout(
        [(0.0, 0.0, 100.00, 99.00, 130.0),     # pin comfortably IN band
         (50.0, 0.0, 99.90, 100.00, 130.0)],   # 0.10 m floor deficit
        pins=[(0.0, 0.0)])
    t = _at(_run(monkeypatch, layout, band), 50.0, 0.0)
    assert t is not None and t[1] == "floor", (
        "a feasible seam pin still granted an allowance — with the pins in "
        "band the yield must be inert")


def test_seam_yield_never_excuses_an_empty_band(monkeypatch):
    """``pinned`` (floor > ceiling) is a mutually-unreachable-anchor
    infeasibility the seam contract does not explain, so it is never yielded —
    even when the band deficit is under the line's floor bound."""
    layout, band = _seam_layout(
        [(0.0, 0.0, 100.00, 100.50, 130.0),      # pin: 0.50 m floor deficit
         (50.0, 0.0, 100.70, 101.00, 100.50)],   # EMPTY band, 0.50 m deficit
        pins=[(0.0, 0.0)])
    t = _at(_run(monkeypatch, layout, band), 50.0, 0.0)
    assert t is not None and t[1] == "pinned", (
        "an EMPTY band was excused by the seam yield; only floor/ceil yield")


def test_an_empty_band_pin_grants_no_allowance(monkeypatch):
    """A pin whose own band is EMPTY contributes nothing to either bound —
    counting it on both sides at once would break side-specificity."""
    layout, band = _seam_layout(
        [(0.0, 0.0, 100.00, 101.00, 100.50),   # pin with an EMPTY band
         (50.0, 0.0, 99.90, 100.00, 130.0)],   # 0.10 m floor deficit
        pins=[(0.0, 0.0)])
    t = _at(_run(monkeypatch, layout, band), 50.0, 0.0)
    assert t is not None and t[1] == "floor"


def test_a_pin_the_airside_network_does_not_carry_is_ignored(monkeypatch):
    """The bound is measured from AIRSIDE pins the band actually governs.  A
    published pin with no emitted airside vertex at it (runway-only, service
    network, or dropped by a late geometry pass) grants nothing."""
    layout, band = _seam_layout(
        [(0.0, 0.0, 100.00, 100.20, 130.0),
         (50.0, 0.0, 99.90, 100.00, 130.0)],
        pins=[(5.0, 200.0)])                   # on the seam line, on no shape
    v = _run(monkeypatch, layout, band)
    assert _at(v, 50.0, 0.0) is not None
    assert _at(v, 0.0, 0.0) is not None


# ══════════════════════════════════════════════════════════════════════════
# THE BUILD-TIME BAND-EXCESS REPORT (cycle-5 instrument-fix spec item 7)
#
# The build's post-solve band law is INVERSION-ONLY
# (``assert_no_final_band_inversion``: it fails on floor > ceiling and is
# silent about a value merely OUTSIDE its band).  SPJC shipped 0.3 m of
# ceiling excess under a "2 sub-materiality inversion(s), PASS-with-residual"
# line, invisible until pytest ran.  ``final_band_excess_report`` closes that:
# it measures MEMBERSHIP with this same checker, logs it, and lands in the
# patch sidecar as evidence — and it is a REPORT, so it must never raise and
# never change a verdict.
# ══════════════════════════════════════════════════════════════════════════

def _excess_layout():
    """One material row (0.50 m), one vertex whose 0.02 m excess is inside
    the CHECKER's own rounding noise, one vertex comfortably in band."""
    return _seam_layout(
        [(0.0, 0.0, 100.50, 90.0, 100.00),      # ceil excess 0.500
         (50.0, 0.0, 100.02, 90.0, 100.00),     # 0.020 — under the noise floor
         (100.0, 0.0, 95.00, 90.0, 100.00)])    # in band


def test_the_band_excess_report_counts_what_the_checker_returns(monkeypatch):
    from auto_patch.config import ELEV_ROUNDING_NOISE_M
    from auto_patch.elevation_per_surface import building_feasibility as BF
    from auto_patch import grade_graph_validate as GGV
    layout, band = _excess_layout()
    monkeypatch.setattr(BF, "reach_band_unified", lambda _l, _g: band)
    rep = GGV.final_band_excess_report(layout, "TEST", G=object())
    assert rep["rows"] == 1 and rep["material"] == 1, (
        "the report must count exactly the checker's rows — no second "
        "opinion about which vertices are out of band")
    assert rep["by_side"]["ceil"] == 1
    assert rep["worst_m"] == pytest.approx(0.50, abs=1e-6)
    assert rep["worst"][0]["role"] == "junction"
    # THE FLOOR IS INERT BY CONSTRUCTION, and that is worth pinning: the
    # checker's own rounding noise (0.03 m) is ALREADY coarser than the
    # convergence guards' 0.01 m materiality floor, so no row it returns can
    # land under the floor.  The split stays in the report because the floor
    # is the contract the log line quotes — but nobody should read
    # "sub_materiality: 0" as evidence about the surface.
    assert ELEV_ROUNDING_NOISE_M > GGV.FINAL_BAND_EXCESS_MATERIALITY_M
    assert rep["sub_materiality"] == 0
    # …and the split mechanism itself works when the floor is raised above
    # the rows (which is how a caller asks "anything worse than X?").
    coarse = GGV.final_band_excess_report(layout, "TEST", tol=0.6, G=object())
    assert coarse["material"] == 0 and coarse["sub_materiality"] == 1


def test_the_band_excess_report_lands_on_the_layout_for_the_sidecar(
        monkeypatch):
    """The sidecar reads ``layout._final_band_excess``.  Without the stash
    the evidence never reaches the artifact and the question is only
    answerable by re-running pytest — which is the hole item 7 closes."""
    from auto_patch.elevation_per_surface import building_feasibility as BF
    from auto_patch import grade_graph_validate as GGV
    layout, band = _excess_layout()
    monkeypatch.setattr(BF, "reach_band_unified", lambda _l, _g: band)
    rep = GGV.final_band_excess_report(layout, "TEST", G=object())
    assert layout._final_band_excess is rep
    import json
    json.dumps(rep)          # the sidecar is JSON — no numpy/shapely leakage


def test_the_band_excess_report_is_never_a_gate(monkeypatch):
    """A REPORT that can fail a build is a gate.  Even a checker that raises
    must come back as a summary naming the failure, never as an exception —
    the pipeline calls this after the loud inversion error, and a patch must
    not be lost to a diagnostic."""
    from auto_patch import grade_graph_validate as GGV

    def _boom(_layout, **_kw):
        raise RuntimeError("the checker exploded")
    monkeypatch.setattr(GGV, "route_band_violations", _boom)

    class _L:
        pass
    layout = _L()
    rep = GGV.final_band_excess_report(layout, "TEST")
    assert "exploded" in rep["error"]
    assert layout._final_band_excess is rep
    assert "NOT measured" in GGV.format_final_band_excess(rep, "TEST")


def test_the_band_excess_log_line_names_itself_a_report(monkeypatch):
    from auto_patch.elevation_per_surface import building_feasibility as BF
    from auto_patch import grade_graph_validate as GGV
    layout, band = _excess_layout()
    monkeypatch.setattr(BF, "reach_band_unified", lambda _l, _g: band)
    line = GGV.format_final_band_excess(
        GGV.final_band_excess_report(layout, "TEST", G=object()), "TEST")
    assert "OUTSIDE their band" in line and "0.5000 m" in line
    assert "REPORT, not a gate" in line, (
        "the build log must say what this line is; a bare violation count "
        "reads as a failed gate and will be chased as one")
    # a clean airport says so positively — an ABSENT line is indistinguishable
    # from a report that never ran, which is the failure mode being repaired
    clean, cband = _seam_layout([(0.0, 0.0, 95.0, 90.0, 100.0)])
    monkeypatch.setattr(BF, "reach_band_unified", lambda _l, _g: cband)
    assert "INSIDE its band" in GGV.format_final_band_excess(
        GGV.final_band_excess_report(clean, "TEST", G=object()), "TEST")
