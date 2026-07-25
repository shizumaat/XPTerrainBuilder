"""Unit tests for the CUT-LAW clamp on conformance-inserted vertices,
exercised with synthetic geometry + a stub DEM (no airport build / X-Plane
install required).

Regression pins for the SPJC clearance-envelope defect (2026-07-25): the
final epsilon-wedge weld ``enforce_conformance(tol=0.01,
include_overlay_refs=True)`` values every T-vertex it inserts by the plain
lerp of the host edge's emitted altitudes.  On the ``runway_end_resa``
outer/daylight row BOTH host vertices are ceiling-limited, so that lerp
equals the analytic ceiling ``ref + 0.05·d`` — and floats above a terrain
depression between the hosts (measured: two inserts at +2.12 / +2.22 m over
the DEM envelope, out of an emitter that was lawful at n = 24).  The fix
bounds the inserted value by the receiver's OWN cut law, ``min(lerp, DEM)``,
for CUT-ONLY receivers only.

Covered:
  * CUT-ONLY receiver, lerp ABOVE the DEM ⇒ inserted vertex clamped to the
    DEM (the shape's ``min(ceiling, DEM)`` law re-applied).
  * CUT-ONLY receiver, lerp BELOW the DEM ⇒ value untouched (a cut never
    fills UP to the terrain either).
  * FILL-only ``runway_end_skirt`` (same ROLE_RUNWAY_CLEARANCE role) and an
    ordinary junction receiver ⇒ NEVER clamped.
  * Gate ``CONFORMANCE_CUT_CLAMP_ENABLED`` off ⇒ not clamped.
  * ``dem=None`` (every non-final call site) ⇒ not clamped.
"""
from __future__ import annotations

import math

from shapely.geometry import Polygon

from auto_patch import config as cfg
from auto_patch.canonical_points import CanonicalPointRegistry
from auto_patch.conformance import enforce_conformance
from auto_patch.layout import (
    BuiltShape,
    PavementLayout,
    REF_RUNWAY_END_RESA,
    REF_RUNWAY_END_SKIRT,
    ROLE_JUNCTION,
    ROLE_OLS_CUT,
    ROLE_RUNWAY_CLEARANCE,
    SHARED_VERTEX_TOL_M,
)

# The host edge runs (0,0)→(20,0) at 10.0 → 10.4, so the insert at its
# midpoint (10, 0) lerps to exactly this.
_LERP_AT_MIDPOINT = 10.2


class _StubDEM:
    """Minimal stand-in for Ortho4XP's DEM: ``alt((dlon, dlat))`` in
    degrees relative to the tile corner, the one call
    ``elevation._sample_dem`` makes."""

    def __init__(self, value: float | None):
        self.value = value
        self.calls: list[tuple[float, float]] = []

    def alt(self, dxy) -> float:
        self.calls.append((float(dxy[0]), float(dxy[1])))
        if self.value is None:
            return float("nan")
        return float(self.value)


def _make_layout(*shapes: BuiltShape) -> PavementLayout:
    """Layout with a seeded canonical-point registry (production seeds
    every shape corner through ``get_or_add``; the tests mirror that)."""
    layout = PavementLayout(icao="TEST", anchor=(0.0, 0.0),
                            shapes=list(shapes))
    registry = CanonicalPointRegistry(tol_m=SHARED_VERTEX_TOL_M)
    for s in shapes:
        for (x, y) in list(s.polygon.exterior.coords):
            registry.get_or_add(float(x), float(y))
    layout.canonical_points = registry
    return layout


def _receiver_square(role: str, ref: str = "") -> BuiltShape:
    """Receiver: a 20×20 shape whose BOTTOM edge runs (0,0)→(20,0) with
    altitudes 10.0 → 10.4 (the host edge every test inserts into, at its
    midpoint (10, 0), t = 0.5 ⇒ lerp ``_LERP_AT_MIDPOINT``)."""
    ring = [(0.0, 0.0), (20.0, 0.0), (20.0, 20.0), (0.0, 20.0)]
    return BuiltShape(polygon=Polygon(ring), role=role, ref=ref,
                      node_altitudes=[10.0, 10.4, 10.4, 10.0])


def _donor_triangle() -> BuiltShape:
    """Donor: a triangle BELOW the receiver touching it only at its apex
    (10, 0) — the classic T-junction.  Emitted with NO altitude model, so
    it contributes geometry only and the insert takes the plain lerp."""
    ring = [(5.0, -10.0), (15.0, -10.0), (10.0, 0.0)]
    return BuiltShape(polygon=Polygon(ring), role=ROLE_JUNCTION,
                      node_altitudes=None)


def _alt_at(shape: BuiltShape, x: float, y: float) -> float:
    ring = list(shape.polygon.exterior.coords)[:-1]
    alts = list(shape.node_altitudes)
    if len(alts) == len(ring) + 1:
        alts = alts[:-1]
    assert len(alts) == len(ring)
    for (vx, vy), a in zip(ring, alts):
        if abs(vx - x) < 1e-9 and abs(vy - y) < 1e-9:
            return a
    raise AssertionError(f"no vertex at ({x}, {y}) in {ring}")


def _weld(layout: PavementLayout, dem, **kwargs) -> None:
    """The production final-weld call shape (tight tolerance, overlay refs
    included), with the tile frame the anchor sits in."""
    enforce_conformance(layout, tol=0.01, include_overlay_refs=True,
                        dem=dem, tile_lat=0, tile_lon=0, **kwargs)


# ── the clamp fires ──────────────────────────────────────────────────────
def test_cut_only_insert_clamped_down_to_the_dem():
    """RESA cut receiver, host-edge lerp ABOVE the terrain: the inserted
    vertex takes the DEM, not the lerp — ``min(ceiling, DEM)`` is the
    shape's own emitted law (``clearance._resa_cut_alt``), so a weld that
    re-derives a value above the DEM breaks it."""
    receiver = _receiver_square(ROLE_RUNWAY_CLEARANCE, REF_RUNWAY_END_RESA)
    layout = _make_layout(receiver, _donor_triangle())
    dem = _StubDEM(8.5)
    _weld(layout, dem)
    assert _alt_at(receiver, 10.0, 0.0) == 8.5
    assert dem.calls, "the clamp must sample the DEM at the insert point"


def test_ols_cut_role_is_cut_only():
    """The OLS cut carries no ref of its own — the ROLE is what makes it
    cut-only (``layout.ROLE_OLS_CUT``: 'Cut-only; an OLS has no floor')."""
    receiver = _receiver_square(ROLE_OLS_CUT, "ols_transitional")
    layout = _make_layout(receiver, _donor_triangle())
    _weld(layout, _StubDEM(8.5))
    assert _alt_at(receiver, 10.0, 0.0) == 8.5


# ── the clamp is a BOUND, never a lift ───────────────────────────────────
def test_cut_only_insert_below_the_dem_is_untouched():
    """Same receiver, terrain ABOVE the lerp: the clamp is one-sided (a
    cut never fills), so the interpolated value stands."""
    receiver = _receiver_square(ROLE_RUNWAY_CLEARANCE, REF_RUNWAY_END_RESA)
    layout = _make_layout(receiver, _donor_triangle())
    _weld(layout, _StubDEM(50.0))
    assert _alt_at(receiver, 10.0, 0.0) == _LERP_AT_MIDPOINT


def test_non_finite_dem_sample_falls_back_to_the_lerp():
    """An unavailable / NaN reading must leave the historical value."""
    receiver = _receiver_square(ROLE_RUNWAY_CLEARANCE, REF_RUNWAY_END_RESA)
    layout = _make_layout(receiver, _donor_triangle())
    dem = _StubDEM(None)                      # alt() → NaN
    _weld(layout, dem)
    assert math.isfinite(_alt_at(receiver, 10.0, 0.0))
    assert _alt_at(receiver, 10.0, 0.0) == _LERP_AT_MIDPOINT


# ── non-cut receivers are never clamped ──────────────────────────────────
def test_runway_end_skirt_is_never_clamped():
    """The skirt shares ROLE_RUNWAY_CLEARANCE with the RESA cut but is
    FILL-only by owner ruling (``clearance._skirt_lift_alt`` =
    ``max(floor, DEM)``): pulling one of its vertices DOWN to the terrain
    would cut on a fill shape.  The ref must veto the role test."""
    receiver = _receiver_square(ROLE_RUNWAY_CLEARANCE, REF_RUNWAY_END_SKIRT)
    layout = _make_layout(receiver, _donor_triangle())
    _weld(layout, _StubDEM(8.5))
    assert _alt_at(receiver, 10.0, 0.0) == _LERP_AT_MIDPOINT


def test_ordinary_pavement_receiver_is_never_clamped():
    """A plain junction is SOLVED pavement — its altitude answers to the
    grade law, not to the terrain under it."""
    receiver = _receiver_square(ROLE_JUNCTION)
    layout = _make_layout(receiver, _donor_triangle())
    _weld(layout, _StubDEM(8.5))
    assert _alt_at(receiver, 10.0, 0.0) == _LERP_AT_MIDPOINT


# ── gate / default off-switches ──────────────────────────────────────────
def test_gate_off_is_byte_identical_to_the_plain_lerp(monkeypatch):
    monkeypatch.setattr(cfg, "CONFORMANCE_CUT_CLAMP_ENABLED", False)
    receiver = _receiver_square(ROLE_RUNWAY_CLEARANCE, REF_RUNWAY_END_RESA)
    layout = _make_layout(receiver, _donor_triangle())
    dem = _StubDEM(8.5)
    _weld(layout, dem)
    assert _alt_at(receiver, 10.0, 0.0) == _LERP_AT_MIDPOINT
    assert not dem.calls, "gate off must not even sample the DEM"


def test_no_dem_keeps_todays_behaviour():
    """Every other ``enforce_conformance`` call site passes no DEM (the
    pre-solve / planarize passes), and must keep the historical value."""
    receiver = _receiver_square(ROLE_RUNWAY_CLEARANCE, REF_RUNWAY_END_RESA)
    layout = _make_layout(receiver, _donor_triangle())
    enforce_conformance(layout, tol=0.01, include_overlay_refs=True)
    assert _alt_at(receiver, 10.0, 0.0) == _LERP_AT_MIDPOINT
