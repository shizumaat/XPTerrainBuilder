"""Stage-2 tests: the airside cut-back seam re-pin.

Owner ruling 2026-07-25 — every node along a tile-seam cut-back sits at
the DEM.  ``tile_cut.repin_airside_seam_cutbacks`` densifies each airside
cut-back edge onto the shared absolute stations, pins every seam vertex to
``dem.alt`` at its own position, and registers the buckets the per-surface
solver hard-holds.

★ Owner ruling 2026-07-26 (``config.RUNWAY_SEAM_CUTBACK_DEM_ANCHORS``):

    "ALL nodes along the seam MUST be at exact DEM and anchored BEFORE the
     solve, then the solver can grade between them and its other anchors to
     maintain grade."

ROLE_RUNWAY, exempt until then, JOINS the sweep.  The exemption is what
left SPLP's oblique cut-back edge with only its two slice crossings 148 m
apart — every node between them was minted later (emit-time chord
densification / the epsilon-wedge weld) by PLAIN LERP and floated up to
0.45 m above the terrain the 10 m gap renders.  ``O4_RUNWAY_SEAM_CUTBACK_
DEM=0`` restores the exemption.

Headless: a synthetic sloping DEM and a hand-built layout, no network, no
X-Plane install.
"""

import importlib
import math

import pytest
from shapely.geometry import Polygon

from auto_patch import tile_cut as TC
from auto_patch.layout import (
    BuiltShape, PavementLayout, R_EARTH, ROLE_APRON, ROLE_JUNCTION,
    ROLE_RUNWAY, vertex_bucket,
)


# =====================================================================
# Fixtures
# =====================================================================
class _RampDEM:
    """A DEM whose altitude ramps with latitude — so a chord across a
    cut-back edge is measurably wrong and a densified one is not."""

    nodata = -32768

    def alt(self, node):
        x, y = node
        return 50.0 + 400.0 * y + 10.0 * x


def _layout(anchor_lat=-12.16, anchor_lon=-77.02):
    return PavementLayout(icao="TEST", anchor=(anchor_lat, anchor_lon),
                          shapes=[])


def _x_of_lon(layout, lon):
    """Local-metre x of an absolute longitude in the layout frame."""
    lat0, lon0 = layout.anchor
    return math.radians(lon - lon0) * R_EARTH * math.cos(math.radians(lat0))


def _seam_shape(layout, role, x_cutback, y_lo, y_hi, depth=40.0,
                node_altitudes=None):
    """A rectangle whose EAST edge lies on the cut-back line at
    ``x_cutback`` and runs from ``y_lo`` to ``y_hi``."""
    ring = [(x_cutback - depth, y_lo), (x_cutback, y_lo),
            (x_cutback, y_hi), (x_cutback - depth, y_hi),
            (x_cutback - depth, y_lo)]
    shape = BuiltShape(Polygon(ring), role)
    if node_altitudes is not None:
        shape.node_altitudes = list(node_altitudes)
    layout.shapes.append(shape)
    return shape


def _cutback_x(layout, half_width_m=TC.TILE_CUT_HALF_WIDTH_M):
    """The WEST cut-back line's local x for the lon = -77 seam."""
    return _x_of_lon(layout, -77.0) - half_width_m


def _wide_layout(role=ROLE_JUNCTION, span=95.0, alts=True):
    """A layout straddling lon -77 with one seam-touching airside shape.

    A second, far-away shape gives the footprint enough longitude span
    that ``derive_tile_cut_lines`` finds the -77 meridian strictly inside
    it (the cut only fires on a real straddle).
    """
    layout = _layout()
    x_cut = _cutback_x(layout)
    ring_alts = [10.0, 10.0, 10.0, 10.0, 10.0] if alts else None
    shape = _seam_shape(layout, role, x_cut, 0.0, span,
                        node_altitudes=ring_alts)
    east = Polygon([(x_cut + 400.0, 0.0), (x_cut + 900.0, 0.0),
                    (x_cut + 900.0, 200.0), (x_cut + 400.0, 200.0)])
    layout.shapes.append(BuiltShape(east, ROLE_APRON))
    return layout, shape


# =====================================================================
# The shared station math (one source with the graded-strip pin)
# =====================================================================
def test_cutback_stations_are_absolute_multiples():
    assert TC.cutback_stations(0.0, 35.0) == [10.0, 20.0, 30.0]
    assert TC.cutback_stations(4.0, 26.0) == [10.0, 20.0]
    # Reversed traversal keeps ring order.
    assert TC.cutback_stations(35.0, 0.0) == [30.0, 20.0, 10.0]
    # An already-densified edge (exactly one step) yields nothing — this
    # is what makes a second sweep insert nothing.
    assert TC.cutback_stations(10.0, 20.0) == []
    assert TC.cutback_stations(0.0, 6.0) == []


def test_cut_lines_are_derived_once():
    """``derive_tile_cut_lines`` is the single source both the cut and
    the re-pin locate the seam from."""
    layout, _shape = _wide_layout()
    lines = TC.derive_tile_cut_lines(layout)
    assert len(lines) == 1
    specs = TC._cutback_line_specs(lines, TC.TILE_CUT_HALF_WIDTH_M)
    # One meridian -> two cut-back lines, 10 m apart, both vertical.
    assert [axis for axis, _c in specs] == [0, 0]
    assert abs(abs(specs[0][1] - specs[1][1]) - 10.0) < 1e-6


def test_single_tile_layout_has_no_cut_lines():
    layout = _layout()
    _seam_shape(layout, ROLE_JUNCTION, 100.0, 0.0, 50.0)
    assert TC.derive_tile_cut_lines(layout) == []


# =====================================================================
# The sweep
# =====================================================================
def test_densifies_and_pins_a_cutback_edge():
    layout, shape = _wide_layout(span=95.0)
    dem = _RampDEM()
    n_new, n_pinned = TC.repin_airside_seam_cutbacks(layout, dem, -13, -78)
    assert n_new > 0 and n_pinned > 0

    ring = list(shape.polygon.exterior.coords)[:-1]
    x_cut = _cutback_x(layout)
    on_line = [(x, y) for (x, y) in ring if abs(x - x_cut) <= 1e-6]
    # 0 and 95 are the original crossings; stations 10..90 are minted.
    ys = sorted(y for _x, y in on_line)
    assert ys[0] == pytest.approx(0.0)
    assert ys[-1] == pytest.approx(95.0)
    assert [y for y in ys if 0.0 < y < 95.0] == [
        pytest.approx(v) for v in range(10, 100, 10)]
    # No cut-back chord longer than one step survives.
    assert max(b - a for a, b in zip(ys, ys[1:])) <= 10.0 + 1e-6

    # Every seam node carries the DEM at its OWN position.
    alts = list(shape.node_altitudes)
    for i, (x, y) in enumerate(ring):
        if abs(x - x_cut) > 1e-6:
            continue
        lat, lon = layout.m_to_ll(x, y)
        expected = dem.alt((lon - (-78), lat - (-13)))
        assert alts[i] == pytest.approx(round(expected, 2), abs=1e-9)


def test_seam_buckets_are_registered_for_the_solver():
    layout, shape = _wide_layout(span=95.0)
    TC.repin_airside_seam_cutbacks(layout, _RampDEM(), -13, -78)
    keys = getattr(layout, "_seam_anchor_keys")
    x_cut = _cutback_x(layout)
    seam_vertices = [(x, y)
                     for (x, y) in list(shape.polygon.exterior.coords)[:-1]
                     if abs(x - x_cut) <= 1e-6]
    assert seam_vertices
    for (x, y) in seam_vertices:
        assert vertex_bucket(float(x), float(y)) in keys


def test_runway_joins_the_sweep():
    """★ Owner ruling 2026-07-26: "ALL nodes along the seam MUST be at
    exact DEM and anchored BEFORE the solve, then the solver can grade
    between them and its other anchors to maintain grade."

    The runway takes the SAME pre-solve densify + DEM pin + bucket
    registration as every other airside role."""
    layout, shape = _wide_layout(role=ROLE_RUNWAY, span=95.0)
    dem = _RampDEM()
    n_new, n_pinned = TC.repin_airside_seam_cutbacks(layout, dem, -13, -78)
    assert n_new > 0 and n_pinned > 0

    ring = list(shape.polygon.exterior.coords)[:-1]
    x_cut = _cutback_x(layout)
    ys = sorted(y for (x, y) in ring if abs(x - x_cut) <= 1e-6)
    assert [y for y in ys if 0.0 < y < 95.0] == [
        pytest.approx(v) for v in range(10, 100, 10)]
    # ...at the DEM, and hard-held by the solver.
    alts = list(shape.node_altitudes)
    keys = layout._seam_anchor_keys
    for i, (x, y) in enumerate(ring):
        if abs(x - x_cut) > 1e-6:
            continue
        lat, lon = layout.m_to_ll(x, y)
        assert alts[i] == pytest.approx(
            round(dem.alt((lon - (-78), lat - (-13))), 2), abs=1e-9)
        assert vertex_bucket(float(x), float(y)) in keys


def test_gate_off_restores_the_runway_exemption(monkeypatch):
    """``O4_RUNWAY_SEAM_CUTBACK_DEM=0`` = the 2026-07-25 behaviour: the
    runway keeps its own reconciled seam path and the sweep never touches
    its ring."""
    monkeypatch.setenv("O4_RUNWAY_SEAM_CUTBACK_DEM", "0")
    import auto_patch.config as CFG
    importlib.reload(CFG)
    try:
        layout, shape = _wide_layout(role=ROLE_RUNWAY, span=95.0)
        before_ring = list(shape.polygon.exterior.coords)
        before_alts = list(shape.node_altitudes)
        n_new, n_pinned = TC.repin_airside_seam_cutbacks(layout, _RampDEM(),
                                                         -13, -78)
        assert (n_new, n_pinned) == (0, 0)
        assert list(shape.polygon.exterior.coords) == before_ring
        assert list(shape.node_altitudes) == before_alts
        assert not getattr(layout, "_seam_anchor_keys", set())
    finally:
        monkeypatch.delenv("O4_RUNWAY_SEAM_CUTBACK_DEM", raising=False)
        importlib.reload(CFG)


def test_idempotent():
    layout, shape = _wide_layout(span=95.0)
    dem = _RampDEM()
    first = TC.repin_airside_seam_cutbacks(layout, dem, -13, -78)
    ring_after_first = list(shape.polygon.exterior.coords)
    alts_after_first = list(shape.node_altitudes)
    keys_after_first = set(layout._seam_anchor_keys)

    second = TC.repin_airside_seam_cutbacks(layout, dem, -13, -78)
    assert second[0] == 0, "a second sweep inserted vertices"
    assert first[0] > 0
    assert list(shape.polygon.exterior.coords) == ring_after_first
    assert list(shape.node_altitudes) == alts_after_first
    assert set(layout._seam_anchor_keys) == keys_after_first


def test_soft_shape_stays_soft():
    """A pre-solve shape with no altitudes must NOT be given a fabricated
    array — the solver seeds it from the DEM and hard-holds exactly the
    buckets this sweep registered."""
    layout, shape = _wide_layout(span=95.0, alts=False)
    assert shape.node_altitudes is None
    n_new, n_pinned = TC.repin_airside_seam_cutbacks(layout, _RampDEM(),
                                                     -13, -78)
    assert n_new > 0 and n_pinned > 0
    assert shape.node_altitudes is None
    assert layout._seam_anchor_keys          # still solver-anchored


def test_no_dem_is_a_noop():
    layout, shape = _wide_layout()
    before = list(shape.polygon.exterior.coords)
    assert TC.repin_airside_seam_cutbacks(layout, None, -13, -78) == (0, 0)
    assert list(shape.polygon.exterior.coords) == before


def test_single_tile_airport_is_untouched():
    layout = _layout()
    shape = _seam_shape(layout, ROLE_JUNCTION, 100.0, 0.0, 95.0,
                        node_altitudes=[10.0] * 5)
    before = list(shape.polygon.exterior.coords)
    assert TC.repin_airside_seam_cutbacks(layout, _RampDEM(),
                                          -13, -78) == (0, 0)
    assert list(shape.polygon.exterior.coords) == before


def test_gate_off_is_byte_identical(monkeypatch):
    monkeypatch.setenv("O4_AIRSIDE_SEAM_DEM_REPIN", "0")
    import auto_patch.config as CFG
    importlib.reload(CFG)
    try:
        layout, shape = _wide_layout(span=95.0)
        before_ring = list(shape.polygon.exterior.coords)
        before_alts = list(shape.node_altitudes)
        assert TC.repin_airside_seam_cutbacks(layout, _RampDEM(),
                                              -13, -78) == (0, 0)
        assert list(shape.polygon.exterior.coords) == before_ring
        assert list(shape.node_altitudes) == before_alts
        assert not getattr(layout, "_seam_anchor_keys", set())
    finally:
        monkeypatch.delenv("O4_AIRSIDE_SEAM_DEM_REPIN", raising=False)
        importlib.reload(CFG)
