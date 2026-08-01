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

SPJC is clean (0) and gates hard — a regression guard.  CYXY (aprons seated
above their reach ceiling — the A2-end apron / building over-pinning issue) and
HECA (multi-runway empty bands) still carry violations; their zero-outcome is
xfail-tracked (the check still RUNS and the count is surfaced — not ignored), and
flips to XPASS the moment the solver/rule places every vertex in its band.
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
_KNOWN_RED = {"CYXY", "HECA"}
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
def test_route_band_flags_cyxy_apron_ceiling():
    """ANTI-GAMING: the checker MUST flag CYXY's aprons seated above their reach
    ceiling, so the zero-gate cannot be faked by a no-op / over-weakened check."""
    from auto_patch.grade_graph_validate import route_band_violations
    v = route_band_violations(cached_airport_layout("CYXY"))
    assert v, "route_band_violations found nothing at CYXY — the checker is a no-op"
    assert any(t[1] == "ceil" for t in v), (
        "expected ceil (above-reach) violations at CYXY's hillside aprons; got "
        f"{[t[1] for t in v[:6]]}")


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
    runway-reach band on the ONE graph G.  SPJC GREEN (hard regression guard); the
    others are xfail-tracked infeasibilities (the check runs, the count is
    surfaced — NOT ignored).

    BAND GRID RESIDUAL: under the grid lookup the band uses, junction ``route_band`` violations up to the
    documented grid-discretization bound (``RASTER_REACH_BAND_GRID_RESIDUAL_M``,
    cited in config.py — SPJC's one dense multi-anchor junction complex, worst
    0.228 m, EMITTED SURFACE unchanged) are the discretization residual, not a
    regression.  Anything larger, off a junction, or any emitted-surface defect
    still gates hard.  The anti-gaming injectors above (+50 m) exceed the bound
    by two orders of magnitude, so the gate cannot be faked."""
    from collections import Counter
    from auto_patch.grade_graph_validate import route_band_violations
    from auto_patch.config import RASTER_REACH_BAND_GRID_RESIDUAL_M
    layout = cached_airport_layout(icao)
    if not layout.shapes:
        pytest.skip(f"{icao}: no shapes built")
    v = route_band_violations(layout)
    # ``t = (excess_m, side, role, x, y, elev, lo, hi)``.  Unconditional
    # since 2026-07-29: there is ONE band engine (the grid lookup), so its
    # documented discretization residual always applies.
    v = [t for t in v
         if not (t[2] == "junction"
                 and t[0] <= RASTER_REACH_BAND_GRID_RESIDUAL_M)]
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


def test_seam_allowance_is_measured_not_the_grid_residual(monkeypatch):
    """ANTI-GAMING.  The bound is the pin's OWN deficit, never a constant: a
    0.20 m excess beside a pin that is only 0.05 m out of band still flags —
    even though 0.20 m would fit inside ``RASTER_REACH_BAND_GRID_RESIDUAL_M``.
    That 0.25 m budget stays reserved for grid-vs-continuous discretization; the
    seam contract must not be charged to it (or vice versa)."""
    from auto_patch.config import RASTER_REACH_BAND_GRID_RESIDUAL_M as _GRID
    layout, band = _seam_layout(
        [(0.0, 0.0, 100.00, 100.05, 130.0),    # pin: 0.05 m deficit
         (50.0, 0.0, 99.80, 100.00, 130.0)],   # 0.20 m — past 0.05, under 0.25
        pins=[(0.0, 0.0)])
    assert 0.20 < _GRID, "fixture must sit INSIDE the discretization budget"
    t = _at(_run(monkeypatch, layout, band), 50.0, 0.0)
    assert t is not None and t[1] == "floor", (
        "a 0.20 m deficit was excused by a 0.05 m seam pin — the allowance has "
        "become a constant (the grid residual?) instead of a measurement")


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
    """CORRIDOR SCOPE: the yield only reaches ``_SEAM_ZONE_M`` (400 m, the
    owner-ruled seam terrain-matching zone — the same scope
    ``tools/check_grade`` and ``tools/grade_feasibility_audit`` use).  A vertex
    beyond it flags even when its excess is under the line's bound."""
    from auto_patch.grade_graph_validate import _SEAM_ZONE_M
    assert _SEAM_ZONE_M == 400.0
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
        f"{_SEAM_ZONE_M:.0f} m")


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
