"""STRING ENDS MUST NOT BE DELETED (owner ruling 2026-07-29).

``emit_decimate.decimate_emit_nodes`` removes 3D-collinear ring vertices
between the solve and ``final_grade_projection``'s node rebuild.  The
taut-string rod survives that by COMPOSING its links across a removed run
(the kept pair's grade is the length-weighted mean of the removed
sub-segments), but composition has no answer at a chain's FIRST/LAST
strung vertex: delete it and there is no second survivor to compose to,
so the link is lost — the audited residual terminal-run drops (HECA 218 /
CYXY 46).  A chain terminal is therefore force-kept, exactly like a
tile-seam or crown-spine-weld anchor.

Hermetic: pure geometry, no DEM, no build.
"""
import pytest
from shapely.geometry import Polygon

from auto_patch.emit_decimate import decimate_emit_nodes

ROW_NODES = 41
STEP_M = 8.0
WIDTH_M = 6.0
ALT_M = 100.0


class _Shape:
    def __init__(self, polygon, node_altitudes, role="apron"):
        self.polygon = polygon
        self.node_altitudes = node_altitudes
        self.role = role


class _Layout:
    def __init__(self, shapes, chains=None):
        self.shapes = shapes
        if chains is not None:
            self._taut_rod_key_chains = chains


def _straight_apron():
    """A thin two-row apron at ONE altitude: every interior vertex is
    3D-collinear, so decimation removes all of them but the chord cap's
    survivors."""
    bottom = [(i * STEP_M, 0.0) for i in range(ROW_NODES)]
    top = [(i * STEP_M, WIDTH_M) for i in range(ROW_NODES - 1, -1, -1)]
    ring = bottom + top
    return _Shape(Polygon(ring), [ALT_M] * len(ring)), bottom


def _ring_coords(shape):
    coords = list(shape.polygon.exterior.coords)
    return {(round(x, 3), round(y, 3)) for (x, y) in coords}


def _chains_at(points):
    """One rod chain per consecutive pair — its ends are ``points``."""
    return [[(tuple(points[0]), tuple(points[1]), -0.02, 0.02)]]


def test_chain_end_vertices_survive_decimation():
    shape, bottom = _straight_apron()
    ends = [bottom[13], bottom[14]]
    n_before = len(shape.polygon.exterior.coords)
    removed = decimate_emit_nodes(_Layout([shape], _chains_at(ends)))
    assert removed > 0, "the straight apron must still decimate"
    kept = _ring_coords(shape)
    for (x, y) in ends:
        assert (round(x, 3), round(y, 3)) in kept, \
            f"string end ({x}, {y}) was deleted"
    assert len(shape.polygon.exterior.coords) < n_before


def test_gate_off_restores_todays_behavior(monkeypatch):
    """``O4_ROD_KEEP_CHAIN_ENDS=0`` decimates exactly as before — and the
    same run WITHOUT the gate proves the ends were genuinely at risk."""
    ends_shape, bottom = _straight_apron()
    ends = [bottom[13], bottom[14]]
    monkeypatch.setenv("O4_ROD_KEEP_CHAIN_ENDS", "0")
    decimate_emit_nodes(_Layout([ends_shape], _chains_at(ends)))
    off_ring = _ring_coords(ends_shape)
    assert any((round(x, 3), round(y, 3)) not in off_ring for (x, y) in ends), \
        "fixture is not exercising the protection: the ends survive anyway"

    bare_shape, _bottom = _straight_apron()
    decimate_emit_nodes(_Layout([bare_shape]))       # no chains at all
    assert _ring_coords(bare_shape) == off_ring      # byte-identical outcome


def test_chain_interior_vertices_are_still_removable():
    """Only the TERMINALS are protected — interior strung vertices stay
    removable (their links compose across the run, which is the whole
    point of the composition pass)."""
    shape, bottom = _straight_apron()
    interior = bottom[10:20]
    chain = [(tuple(interior[k]), tuple(interior[k + 1]), -0.02, 0.02)
             for k in range(len(interior) - 1)]
    decimate_emit_nodes(_Layout([shape], [chain]))
    kept = _ring_coords(shape)
    assert (round(interior[0][0], 3), 0.0) in kept
    assert (round(interior[-1][0], 3), 0.0) in kept
    assert any((round(x, 3), round(y, 3)) not in kept
               for (x, y) in interior[1:-1])


def test_no_chains_attribute_is_inert():
    shape, _bottom = _straight_apron()
    assert decimate_emit_nodes(_Layout([shape])) > 0


@pytest.mark.parametrize("bad", [[], [[]], [[((0.0,), (1.0,), 0, 0)]]])
def test_malformed_chain_export_does_not_crash(bad):
    shape, _bottom = _straight_apron()
    assert decimate_emit_nodes(_Layout([shape], bad)) > 0
