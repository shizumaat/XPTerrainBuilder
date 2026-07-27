"""Torn datum-pin release in ``final_grade_projection`` (2026-07-26).

The KCLT 18L/36R junction micro-step class: a runway-end-skirt ring vertex
is HARD-pinned at its birth value (Slice B stage B1) and welded into a
junction ring ~1 m from a runway-hard corner whose profile value disagrees
by decimetres.  The violated law pair IS in the projection graph, but both
endpoints are frozen, so the ring step ships to the mesh (measured KCLT:
227.54 skirt pin 0.99 m from the 227.24 runway corner = a 30 % step).

The repair RE-SEATS the NON-datum side of every violated both-hard law
pair whose other side is runway datum (the runway is the datum, 2026-07-16
ruling; a disagreeing weld is torn, not authoritative — the 2026-07-06
agreement gate): the pin's value moves inside the interval its datum-side
edges admit while the pin STAYS HARD, so neither the sweep worklist nor
the envelope pass can drag it back onto the contradiction.  Tile-seam
pins are the owner's seam law and must never move.

Hermetic unit tests on a tiny hand-built layout (the ``_FakeShape`` /
``_FakeLayout`` pattern of ``test_final_projection_snapshot_recapture``
— no fixtures, no DEM, no network).  Coordinates are non-integral so the
identity ``m_to_ll`` never triggers the tile-seam terrain pins, except
where a test places one there deliberately.
"""
import pytest

import auto_patch.config as config  # noqa: F401  (config import side effects)
from auto_patch.canonical_points import CanonicalPointRegistry
from auto_patch.elevation_per_surface import solver_primitives as SP
from auto_patch.elevation_per_surface.route_profile import solve as RP
from auto_patch.layout import (
    REF_RUNWAY_END_SKIRT, ROLE_JUNCTION, ROLE_RUNWAY, ROLE_RUNWAY_CLEARANCE)

from shapely.geometry import Polygon


class _FakeShape:
    def __init__(self, role, polygon, *, ref=None, altitude=None,
                 altitude_high=None, altitude_low=None, node_altitudes=None):
        self.role = role
        self.polygon = polygon
        self.ref = ref
        self.altitude = altitude
        self.altitude_high = altitude_high
        self.altitude_low = altitude_low
        self.node_altitudes = node_altitudes
        self.is_bridge = False


class _FakeLayout:
    def __init__(self, shapes, icao="TEST"):
        self.shapes = shapes
        self.icao = icao
        self.canonical_points = CanonicalPointRegistry()

    def m_to_ll(self, x, y):
        return (x, y)


_RWY_ALT = 100.0
_PIN_ALT = 100.4        # skirt birth pin, 0.4 m off the runway datum


def _torn_pin_layout(pin_xy=(51.3, 20.3)):
    """Runway rect at ``_RWY_ALT`` + junction ring containing the runway
    corner (50.3, 20.3) and, ``~1 m`` along the same ring edge, a vertex
    the skirt HARD-pins at ``_PIN_ALT`` — the KCLT configuration.  The
    junction pair (corner, pin) has cap 1.5 % · 1 m ≈ 0.015 m but a
    0.4 m step: violated, both endpoints hard, exactly one is datum."""
    runway = _FakeShape(
        ROLE_RUNWAY,
        Polygon([(0.3, 0.3), (50.3, 0.3), (50.3, 20.3), (0.3, 20.3)]),
        altitude=_RWY_ALT)
    junction = _FakeShape(
        ROLE_JUNCTION,
        Polygon([(50.3, 20.3), pin_xy, (60.3, 20.3),
                 (60.3, 30.3), (50.3, 30.3)]),
        node_altitudes=[_RWY_ALT, _PIN_ALT, _PIN_ALT, _PIN_ALT, _PIN_ALT])
    skirt = _FakeShape(
        ROLE_RUNWAY_CLEARANCE,
        Polygon([pin_xy, (55.3, 20.3), (55.3, 16.3), (51.3, 16.3)]),
        ref=REF_RUNWAY_END_SKIRT,
        node_altitudes=[_PIN_ALT, 100.2, 99.8, 99.9])
    return _FakeLayout([runway, junction, skirt]), junction


def _junction_alt_at(layout, junction, xy):
    ring = list(junction.polygon.exterior.coords)
    ring = ring[:-1] if ring[0] == ring[-1] else ring
    for k, (x, y) in enumerate(ring):
        if abs(x - xy[0]) < 1e-6 and abs(y - xy[1]) < 1e-6:
            return float(junction.node_altitudes[k])
    raise AssertionError(f"junction ring vertex {xy} not found")


@pytest.fixture(autouse=True)
def _projection_env(monkeypatch):
    monkeypatch.delenv("O4_FINAL_GRADE_PROJECTION", raising=False)
    monkeypatch.delenv("O4_TORN_DATUM_PIN_RELEASE", raising=False)
    # The projection is active only under the spine gates; force the arc
    # gate on so the test never silently no-ops on a gate flip.
    monkeypatch.setattr(config, "ROUTE_ARC_SPINE", True, raising=False)
    # The skirt HARD-PIN family (B1) must be admitted for the pin to
    # exist — the class under test requires it.
    monkeypatch.setattr(config, "ONE_SOLVE_TERRAIN", True, raising=False)
    monkeypatch.setattr(config, "ONE_SOLVE_TERRAIN_RUNWAY_END_SKIRT", True,
                        raising=False)


def test_skirt_pin_seeded_hard():
    """Precondition of the class: the skirt vertex IS a hard pin at its
    birth value in the projection's own seed (if this stops holding the
    release tests stop testing anything)."""
    layout, _junction = _torn_pin_layout()
    nodes, b2i = SP._build_node_list(layout)
    elev, is_hard, _have = SP._seed_elevations(layout, nodes, b2i)
    k = layout.canonical_points.get_or_add(51.3, 20.3)
    i = b2i[k]
    assert is_hard[i] and elev[i] == pytest.approx(_PIN_ALT)


def test_reseat_moves_torn_skirt_pin_onto_the_datum():
    layout, junction = _torn_pin_layout()
    RP.final_grade_projection(layout, icao="TEST")
    corner = _junction_alt_at(layout, junction, (50.3, 20.3))
    pin = _junction_alt_at(layout, junction, (51.3, 20.3))
    # The runway datum never moves.
    assert corner == pytest.approx(_RWY_ALT, abs=1e-6)
    # The re-seated pin obeys the 1 m ring pair's 1.5 % junction cap
    # (+ the agreement-gate noise tolerance).
    assert abs(pin - corner) <= 0.015 + 0.05, (
        f"pin stayed at a torn value: corner={corner} pin={pin}")


def test_gate_off_preserves_the_shipped_defect():
    """O4_TORN_DATUM_PIN_RELEASE=0 restores the previous behaviour (both
    endpoints frozen, the step survives) — documents that the release is
    what closes the class."""
    layout, junction = _torn_pin_layout()
    import os
    os.environ["O4_TORN_DATUM_PIN_RELEASE"] = "0"
    try:
        RP.final_grade_projection(layout, icao="TEST")
    finally:
        del os.environ["O4_TORN_DATUM_PIN_RELEASE"]
    pin = _junction_alt_at(layout, junction, (51.3, 20.3))
    assert pin == pytest.approx(_PIN_ALT, abs=1e-6)


def test_tile_seam_pin_is_never_released():
    """A pin on an integral lat/lon (identity ``m_to_ll`` → tile seam) is
    the owner's seam law: it must survive the release even when torn
    against the runway datum."""
    layout, junction = _torn_pin_layout(pin_xy=(51.0, 20.3))
    RP.final_grade_projection(layout, icao="TEST")
    pin = _junction_alt_at(layout, junction, (51.0, 20.3))
    assert pin == pytest.approx(_PIN_ALT, abs=1e-6)


def test_reseat_compares_in_emitted_space_across_crown_drops():
    """The KCLT mechanism precisely: the runway corner carries a lateral
    crown drop (z′ = ridge level, emitted = ridge − drop) while the torn
    pin 1 m away holds the RIDGE value with NO drop — z′-LEVEL, so a
    z′-space scan sees nothing, yet the emitted surface steps by the full
    drop.  The re-seat must compare emitted values and land the pin on
    the crowned edge."""
    drop = 0.30
    layout, junction = _torn_pin_layout()
    # The runway's STORED corner value is the emitted (edge) value; the
    # crown transform lifts it to z′ = stored + drop.  A torn pin
    # holding the RIDGE value (stored + drop) with NO drop of its own is
    # z′-LEVEL with the corner while emitting a `drop`-sized step.
    skirt = layout.shapes[2]
    pin_ridge = _RWY_ALT + drop
    junction.node_altitudes = [_RWY_ALT, pin_ridge, pin_ridge,
                               pin_ridge, pin_ridge]
    skirt.node_altitudes = [pin_ridge, 100.2, 99.8, 99.9]
    corner_key = layout.canonical_points.get_or_add(50.3, 20.3)
    layout._crown_drop_key = {corner_key: drop}
    RP.final_grade_projection(layout, icao="TEST")
    corner = _junction_alt_at(layout, junction, (50.3, 20.3))
    pin = _junction_alt_at(layout, junction, (51.3, 20.3))
    # The corner still emits the runway edge value; the re-seated pin
    # must sit within the 1 m pair's cap of THAT emitted value, not be
    # left z′-level (which would ship the full crown-drop step).
    assert corner == pytest.approx(_RWY_ALT, abs=1e-6)
    assert abs(pin - corner) <= 0.015 + 0.05, (
        f"pin not on the crowned edge: corner={corner} pin={pin}")


def test_skirt_ring_keeps_birth_values():
    """The release moves the PAVEMENT node; the skirt shape itself is
    never written back (its immutable ring keeps birth values — the emit
    consensus reconciles the shared node at the pavement value)."""
    layout, _junction = _torn_pin_layout()
    skirt = layout.shapes[2]
    before = list(skirt.node_altitudes)
    RP.final_grade_projection(layout, icao="TEST")
    assert list(skirt.node_altitudes) == before
