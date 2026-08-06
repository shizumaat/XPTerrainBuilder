"""ADJACENT-GROUND — the zone law has exactly ONE authority.

The supply half is the INGEST lane's
(``adjacent_ground.build_zone_constraint_table`` →
``layout.adjacent_ground_zone_boxes``, pinned by
``test_zone_constraint_supply``).  These are the twins for the consuming
half.

THE HISTORY THESE TWINS NOW PIN (cycle-5 solve-certification spec, fix 1).
This module used to assert an ABSOLUTE per-node box, built at fp#8's entry
from the foot lerp ``(1-t)*z[a] + t*z[b]`` and bound through
``one_solve._node_box_arrays``.  The reasoning was that a pairwise
projection cannot state a three-term constraint, so freeze the datum and
state an interval on the zone variable alone.

That box was a SECOND AUTHORITY over a law that already had one, and it
was the frozen one — so it won.  ``fp#8`` moves the pavement that defines
the datum (measured on the over-cap rows: p50 2.340 m, p90 24.949 m, max
88.905 m), while the box went on clamping at seed and after every sweep
against the datum as it stood at ENTRY.  The decisive measurement, over
all 20,135 over-cap ``graded_strip:adjacent_ground`` rows at fp#8 exit:
65.6 % of them sat inside the box implied by the STALE entry datum versus
6.7 % inside the live one.  The residual could not go to zero by binding
harder; binding harder is what produced it.

THE ONE AUTHORITY is the RELATIVE interval edge that already existed and
was already correct: ``solver_primitives._build_adjacent_ground_zone_
constraints`` emits ``(i, j, floor_off, ceil_off)`` — ground ``i`` against
its host pavement ring vertex ``j``, TWO VARIABLES, so it moves with
``j``.  Directedness (the property the box was reached for) is carried by
``interval_yield_from``, which moves only the terrain endpoint of a slab.

So these twins now pin: the relative edge IS the law, the deleted box does
not come back, and the coverage audit proves the deletion lost nothing.

No network, no DEM, no fixtures: a stub layout and arithmetic.
"""
from __future__ import annotations

import inspect

import pytest

from auto_patch.elevation_per_surface import solver_primitives as SP
from auto_patch.elevation_per_surface.route_profile import solve as SV


# ── a stub layout: just the canonical registry the consumers read ────

class _CPS:
    """Exact-coordinate registry (the real one interns within 0.5 m;
    these twins place every point far enough apart that the two agree)."""

    def get_or_add(self, x, y):
        return (round(float(x), 6), round(float(y), 6))


class _Layout:
    def __init__(self, rows, first_zone=2, presolve=None):
        self.canonical_points = _CPS()
        self.adjacent_ground_zone_boxes = rows
        self._adjacent_ground_first_zone_index = first_zone
        self.adjacent_ground_presolve = presolve or []


# node space: 0,1 = pavement ring vertices (the FOOT/host); 2,3 = band.
_A = (0.0, 0.0)
_B = (10.0, 0.0)
_Z = (5.0, 4.0)
_Z2 = (7.0, 4.0)
_B2I = {(0.0, 0.0): 0, (10.0, 0.0): 1, (5.0, 4.0): 2, (7.0, 4.0): 3}
_ELEV = [100.0, 110.0, 41.5, 41.5]          # foot a=100, foot b=110


def _row(**kw):
    row = {"shape_id": 1, "ref": "apr", "key": (5000, 4000), "xy": _Z,
           "kind": "fill", "depth_m": 3.0,
           "floor_off": -1.0, "ceil_off": 2.0, "snap_tol_m": 0.05,
           "foot": {"a": _A, "b": _B, "t": 0.5, "gap_m": 4.0},
           "host": _A, "host_delta": 0.0, "dem_seed": 41.5}
    row.update(kw)
    return row


class _Shape:
    pass


def _presolve(**kw):
    """One presolve entry carrying one zone node — the input the RELATIVE
    law builder consumes."""
    zn = {"xy": _Z, "host": _A, "floor_off": -1.0, "ceil_off": 2.0}
    zn.update(kw)
    return [{"shape": _Shape(), "zone_nodes": [zn]}]


def _entries(presolve, first_zone=2):
    layout = _Layout(None, first_zone=first_zone, presolve=presolve)
    return SP._build_adjacent_ground_zone_constraints(layout, _B2I)


def _coverage(rows, edge_nodes, first_zone=2, n=4):
    layout = _Layout(rows, first_zone=first_zone)
    return SV._zone_law_coverage(layout, _B2I, n, first_zone, edge_nodes)


# ── THE ONE AUTHORITY: a RELATIVE edge on two variables ──────────────

def test_the_zone_law_is_a_relative_edge_on_two_variables():
    """``(i, j, floor_off, ceil_off)`` — the ground node against its host
    pavement ring vertex.  Two variables is the whole point: the
    constraint MOVES when the projection moves the pavement, which is
    exactly what the frozen box could not do."""
    sc, zone_idx, _ = _entries(_presolve())
    assert len(sc) == 1
    edges = sc[0]["edges"]
    assert edges == [(2, 0, -1.0, 2.0)]      # zone node 2 vs host node 0
    assert zone_idx == {2}
    assert sc[0]["ref"] == "adjacent_ground"


def test_the_offsets_are_carried_verbatim_not_re_derived():
    """ONE derivation of the corridor (the supply's).  A consumer that
    recomputed the envelope would be the second copy that made the
    cross-shape collision unarguable for a week."""
    sc, _, _ = _entries(_presolve(floor_off=-0.03, ceil_off=-0.09))
    assert sc[0]["edges"] == [(2, 0, -0.03, -0.09)]
    src = inspect.getsource(SP._build_adjacent_ground_zone_constraints)
    for forbidden in ("envelope_at", "zone_corridor_box",
                      "adjacent_ground_envelope"):
        assert forbidden not in src, forbidden


def test_a_cut_row_arrives_ceiling_only():
    """``floor_off is None`` is the law's CUT rule (below-floor terrain
    inside a cut piece belongs to the fill machinery) — it must arrive as
    an unbounded floor, not as a zero."""
    sc, _, _ = _entries(_presolve(floor_off=None))
    assert sc[0]["edges"] == [(2, 0, None, 2.0)]


def test_a_row_with_no_law_at_all_gets_no_edge():
    sc, _, _ = _entries(_presolve(floor_off=None, ceil_off=None))
    assert sc[0]["edges"] == []


# ── identity: pavement always wins ───────────────────────────────────

def test_a_zone_node_that_adopted_a_pavement_variable_gets_no_edge():
    """Pavement value wins at a pavement node — an IDENTITY, not an
    arbitration.  A band law may never constrain a pavement variable."""
    sc, _, counts = _entries(_presolve(xy=_A))     # index 0 < first_zone
    assert sc[0]["edges"] == []
    assert counts[0] == 1                          # counted, not silent


def test_a_zone_node_equal_to_its_host_gets_no_self_edge():
    sc, _, _ = _entries(_presolve(host=_Z))
    assert sc[0]["edges"] == []


# ── THE COVERAGE AUDIT: the deletion lost nothing ────────────────────

def test_coverage_counts_a_published_row_as_carried():
    """The audit that replaced the box builder.  Every published zone row
    that resolves to a band variable must be carried by a relative
    edge."""
    n_rows, n_resolved, n_carried, n_adopted, n_uncarried = _coverage(
        [_row()], edge_nodes={2})
    assert (n_rows, n_resolved, n_carried, n_adopted, n_uncarried) == (
        1, 1, 1, 0, 0)


def test_coverage_names_an_uncarried_row_instead_of_absorbing_it():
    """A published row with NO relative edge is a zone node whose law
    nothing enforces.  It must surface as a number, not be silently
    dropped — that class is what the box was hiding."""
    assert _coverage([_row()], edge_nodes=set())[4] == 1


def test_coverage_counts_a_pavement_adoption_as_adopted_not_uncarried():
    """An adopted row is LAWFULLY edgeless (pavement identity) — calling
    it uncarried would make the audit cry wolf at every build."""
    n_rows, _, n_carried, n_adopted, n_uncarried = _coverage(
        [_row(xy=_A)], edge_nodes=set())
    assert (n_carried, n_adopted, n_uncarried) == (0, 1, 0)


def test_coverage_skips_a_node_outside_the_pass_node_space():
    assert _coverage([_row(xy=_Z2)], edge_nodes=set(), n=3)[1] == 0


def test_an_absent_table_audits_nothing_and_does_not_raise():
    """A layout that predates the supply lane (or an airport with no
    bands) must degrade silently."""
    layout = _Layout(None)
    assert SV._zone_law_coverage(layout, _B2I, 4, 2, set()) == (
        0, 0, 0, 0, 0)


# ── the deleted box must not come back ───────────────────────────────

def test_the_solve_no_longer_binds_an_absolute_zone_box():
    """THE regression twin for fix 1.  The failure mode is subtle and
    silent: re-introducing a per-node box built from ``elev`` at fp#8
    entry would restore a second authority that out-clamps the live law
    on 65.6 % of the over-cap rows, and every count would still look
    plausible.  So the twin asserts the SITE, not just the outcome."""
    assert not hasattr(SV, "_zone_foot_boxes")
    src = inspect.getsource(SV.solve_route_profile)
    block = src[src.index("ADJACENT-GROUND: ONE AUTHORITY"):]
    block = block[:block.index("NO REFERENCE RODS")]
    body = "\n".join(ln for ln in block.splitlines()
                     if not ln.lstrip().startswith("#"))
    assert "_zone_law_coverage" in body
    # no merge of a zone box into the bounded-yield channel
    assert "_yield_node_bounds" not in body
    assert "_merged_zone" not in body


# ── the writeback carries, it does not value ─────────────────────────

def test_the_writeback_no_longer_re_derives_from_the_dem():
    """``_zv = float(_dem_z)`` discarded the solved value for every
    edge-owning zone node and recomputed ``clamp(raw DEM, ref +
    offsets)``.  The emitted band value must be the SOLVED value."""
    src = inspect.getsource(SV.solve_route_profile)
    zone = src[src.index("ADJACENT-GROUND ZONE-ROW writeback"):]
    zone = zone[:zone.index("RUNWAY-END RESA CUT writeback")]
    body = "\n".join(ln for ln in zone.splitlines()
                     if not ln.lstrip().startswith("#"))
    assert "_dem_z" not in body
    assert "_ZONE_SNAP" not in body
    assert "_elev_emit[_zi]" in body


def test_the_seed_is_the_published_dem_seed():
    """The variable starts where the supply says it starts; no consumer
    re-samples the DEM for a band node."""
    src = inspect.getsource(SV.solve_route_profile)
    seed = src[src.index("ADJACENT-GROUND INGESTION, the SEED"):]
    seed = seed[:seed.index("_psub(0.20")]
    assert 'dem_seed' in seed
    assert "elev[_zi] = float(_zs)" in seed
