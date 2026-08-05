"""ADJACENT-GROUND INGESTION — the zone-law CONSTRAINT SUPPLY.

Single-solve architecture (owner 2026-08-03): *ingest → refine geometry
→ ONE elevation solve carrying ALL grade law → emit verbatim*.  The
adjacent-ground band values were one of the named post-solve
value-writers scheduled for ingestion.

The v2 attempt at boxing them was VACUOUS, and the reason was measured
(``seamv2/RESULTS.md`` §1 part 2): its DATUM was the writeback's own
expression, so the box surrounded the value it was constraining, and it
was carried on a projection channel that runs after the band values are
written.  This module pins the supply side that fixes both:

  * ONE derivation of the box (``zone_corridor_box``) with three
    consumers — the table, the pre-solve zone nodes, and the emit-side
    lockstep reader;
  * a DATUM that is an IDENTITY (``foot``: two ring vertices and a
    parameter — variables the solve already owns), not a value the band
    writer produced;
  * a table published BEFORE the solve, per band node, carrying
    ``shape_id`` so the cross-shape corridor collision (SPJC, 1.56 m
    notch) can be fixed at source rather than clamped at emit.
"""
import ast
import inspect

import pytest

from auto_patch import adjacent_ground as AG


# ── the box: one derivation, the law's own kind rule ────────────────

def _env(_d):
    """A stand-in family envelope: floor −1 m, ceiling +2 m, everywhere."""
    return (-1.0, 2.0)


def _env_of_d(d):
    """Depth-dependent, so the fill width clamp is observable."""
    return (-0.1 * d, 0.2 * d)


def test_cut_rows_are_ceiling_only():
    """A cut band's floor is FREE — below-floor terrain inside a cut
    piece belongs to the fill machinery."""
    floor, ceil = AG.zone_corridor_box(_env, None, "cut", 12.0)
    assert floor is None
    assert ceil == pytest.approx(2.0)


def test_fill_rows_clamp_the_depth_to_the_graded_width():
    """An outer-row vertex whose projection jitters past W stays on the
    shelf instead of reading an unbounded corridor."""
    inside = AG.zone_corridor_box(_env_of_d, 10.0, "fill", 5.0)
    past = AG.zone_corridor_box(_env_of_d, 10.0, "fill", 40.0)
    at_w = AG.zone_corridor_box(_env_of_d, 10.0, "fill", 10.0)
    assert inside == pytest.approx((-0.5, 1.0))
    assert past == pytest.approx(at_w)


def test_cut_depth_is_not_clamped():
    """Only fill clamps — a cut row reads the law at its true depth."""
    _f, ceil = AG.zone_corridor_box(_env_of_d, 10.0, "cut", 40.0)
    assert ceil == pytest.approx(8.0)


def test_the_emit_reader_uses_the_same_derivation():
    """The emit-side corridor reader must CALL ``zone_corridor_box``, not
    re-spell the bounds.  A second copy of these numbers is how the
    cross-shape collision was argued about for a week."""
    src = inspect.getsource(AG._make_solved_band_resampler)
    tree = ast.parse(src.lstrip())
    called = {c.func.id for c in ast.walk(tree)
              if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)}
    assert "zone_corridor_box" in called
    # ...and no local re-spelling of the kind rule survives beside it.
    assert 'floor_offset = None' not in src


# ── the datum: an IDENTITY, not a value ─────────────────────────────

def test_foot_reference_is_two_ring_vertices_and_a_parameter():
    ring = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0)]
    i, t, gap = AG._ring_foot_reference(ring, 5.0, 3.0)
    assert (i, t) == (0, 0.5)
    assert gap == pytest.approx(3.0)


def test_foot_reference_clamps_to_the_segment():
    """A node off the end of the ring feet on the endpoint, never on an
    extrapolation of it."""
    ring = [(0.0, 0.0), (10.0, 0.0)]
    i, t, _gap = AG._ring_foot_reference(ring, -50.0, 0.0)
    assert (i, t) == (0, 0.0)
    i, t, _gap = AG._ring_foot_reference(ring, 50.0, 0.0)
    assert (i, t) == (0, 1.0)


def test_foot_reference_needs_two_points():
    assert AG._ring_foot_reference([(0.0, 0.0)], 1.0, 1.0) is None


# ── the table: the contract the KILL and SEATS lanes consume ────────

class _Layout:
    def __init__(self, entries):
        self.adjacent_ground_presolve = entries


_BOX = {
    "shape_id": 1, "ref": "apr", "key": (1000, 2000), "xy": (1.0, 2.0),
    "kind": "fill", "depth_m": 3.0, "floor_off": -1.0, "ceil_off": 2.0,
    "snap_tol_m": 0.05,
    "foot": {"a": (0.0, 0.0), "b": (10.0, 0.0), "t": 0.1, "gap_m": 2.0},
    "host": (0.0, 0.0), "host_delta": 0.0, "dem_seed": 41.5,
}

_REQUIRED = ("shape_id", "ref", "key", "xy", "kind", "depth_m",
             "floor_off", "ceil_off", "snap_tol_m", "foot", "host",
             "host_delta", "dem_seed")


def test_the_table_is_published_on_the_layout():
    layout = _Layout([{"zone_boxes": [_BOX, dict(_BOX, key=(3, 4))]},
                      {"zone_boxes": []}])
    assert AG.build_zone_constraint_table(layout) == 2
    assert len(layout.adjacent_ground_zone_boxes) == 2


def test_every_record_carries_the_whole_contract():
    """The consumers are other lanes; a missing field is a silent
    mis-bind, not a crash."""
    layout = _Layout([{"zone_boxes": [_BOX]}])
    AG.build_zone_constraint_table(layout)
    row = layout.adjacent_ground_zone_boxes[0]
    for field in _REQUIRED:
        assert field in row, field
    assert set(row["foot"]) == {"a", "b", "t", "gap_m"}


def test_an_empty_construct_publishes_an_empty_table():
    """A reader must be able to tell "no bands" from "old layout"."""
    layout = _Layout([])
    assert AG.build_zone_constraint_table(layout) == 0
    assert layout.adjacent_ground_zone_boxes == []


def test_the_construct_publishes_the_table_itself():
    """Single-pass: the table is built in the construct's own loop, not
    re-derived by a later caller walking the geometry again."""
    src = inspect.getsource(AG.construct_adjacent_ground_presolve)
    assert "build_zone_constraint_table(layout)" in src
    assert "zone_boxes" in src
