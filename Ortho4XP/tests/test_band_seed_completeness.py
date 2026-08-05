"""Twins for the SEED-FIX round §2 — BAND-SEED COMPLETENESS + the
FLOOR-ABOVE-OWN-HARD-VALUE inversion class (spec
``docs/specs/seed-fix-round-spec.md`` §2).

THE DEFECT.  ``spine_value_fields`` seeds its two value fields from
``G.runway_anchor`` alone.  That map is the runway-JOIN anchor set, not
the HARD TRUTH set: at HECA 8 of the 31 on-spine ``seed_rwy_seam`` nodes
are absent (2863, 3610, 3631, 4818, 6907, 7236, 7298, 7493), and at 2 of
them the band FLOOR then sits above the node's own hard runway value
(4818 by +2.344 m, 2863 by +1.522 m).  That is one instrument
contradicting itself, and it is INVISIBLE to the existing
``floor > ceiling`` law whenever the ceiling sits higher still.

The synthetic below encodes HECA's shape: a hard runway node reachable
from a HIGHER runway anchor across too little budget, so the floor
overshoots it.

  (a) the PRE-SOLVE context (no hard-truth map published yet) honestly
      keeps the runway-anchor-only field;
  (b) RED BEFORE — the extended law sees the class the old law missed;
  (c) GREEN AFTER — completing the seed set puts the missing hard node's
      own value into the fields;
  (d) the assertion names the class distinctly (a wrong-value message
      sends the reader to the wrong fix).
"""
import pytest

from auto_patch.elevation_per_surface.building_feasibility import (
    BandInversionError, FINAL_BAND_INVERSION_TOL_M,
    assert_no_final_band_inversion, spine_value_fields)


class _G:
    """Minimal unified-graph stand-in: the two attributes
    ``spine_value_fields`` reads plus ``pos`` for the report."""

    def __init__(self, runway_anchor, spine_adj, pos):
        self.runway_anchor = dict(runway_anchor)
        self.spine_adj = dict(spine_adj)
        self.pos = dict(pos)
        self.service_spine_pairs = set()


class _Layout:
    """Enough layout for ``_decrowned_anchor_seeds`` (which asks
    ``crown.crown_drop_at``, 0.0 with no crown field) and the recorder."""

    def __init__(self):
        self.shapes = []
        self.anchor = (0.0, 0.0)


def _heca_shape():
    """Three spine nodes in a line.

    * node 0 — HIGH runway anchor, value 115.24 (HECA's 7157 class);
    * node 1 — a free corridor node;
    * node 2 — HARD runway truth at 60.79 (HECA's 2863) that is NOT in
      ``runway_anchor``.

    Budgets: 0->1 is 40.0 m, 1->2 is 8.93 m, so node 2's floor from node 0
    is ``115.24 - 48.93 = 66.31`` — 5.52 m ABOVE its own hard value, and
    its ceiling from node 0 is ``115.24 + 48.93``, comfortably higher.
    The old law sees a perfectly ordered band.
    """
    runway_anchor = {0: 115.242}
    spine_adj = {0: [(1, 40.0)], 1: [(0, 40.0), (2, 8.928)],
                 2: [(1, 8.928)]}
    pos = {0: (0.0, 0.0), 1: (100.0, 0.0), 2: (120.0, 0.0)}
    return _G(runway_anchor, spine_adj, pos), {2: 60.790}


# ── (a) the PRE-SOLVE context ────────────────────────────────────────────

def test_the_presolve_band_keeps_the_runway_anchor_only_field():
    """The construct band runs BEFORE ``_seed_elevations`` hardens
    anything, so there is no hard-truth map to union in.  Standing law or
    not, that context must keep the field it has always had — the law
    completes a seed set, it never invents one."""
    G, _hard = _heca_shape()
    layout = _Layout()                       # nothing published
    assert not hasattr(layout, "_seed_hard_truth_values")
    ceiling, floor = spine_value_fields(layout, G)
    # the missing hard node contributes nothing: its own value is not a
    # source, so the ceiling at node 2 still comes from node 0.
    assert floor[2] == pytest.approx(115.242 - 48.928, abs=1e-9)
    assert ceiling[2] == pytest.approx(115.242 + 48.928, abs=1e-9)
    # and the old law is silent — the band reads perfectly ordered.
    assert assert_no_final_band_inversion(layout, "TEST") == 0


# ── (b) RED BEFORE / (c) GREEN AFTER ─────────────────────────────────────

def test_the_extended_law_sees_the_floor_above_own_hard_value():
    """RED: with the class recorded, HECA's shape is a LAW VIOLATION the
    old ``floor > ceiling`` test could never have caught."""
    G, hard = _heca_shape()
    layout = _Layout()
    # the hard node is published but DELIBERATELY still absent from
    # ``runway_anchor`` — the seed union is what fixes that, and this
    # arm isolates the DETECTION half.
    layout._seed_hard_truth_values = hard
    G.spine_adj = dict(G.spine_adj)
    _ceiling, floor = spine_value_fields(layout, G)
    rows = layout._final_band_inversions
    own = [r for r in rows if r["klass"] == "floor_above_own_hard_value"]
    assert len(own) == 1
    assert own[0]["node"] == 2
    assert own[0]["own_hard_value"] == pytest.approx(60.790)
    assert own[0]["deficit_m"] == pytest.approx(
        floor[2] - 60.790, abs=1e-9)
    assert own[0]["deficit_m"] > FINAL_BAND_INVERSION_TOL_M
    with pytest.raises(BandInversionError) as caught:
        assert_no_final_band_inversion(layout, "TEST")
    assert "OWN hard runway/seam value" in str(caught.value), (
        "the message must name the CLASS — a floor-vs-ceiling wording "
        "sends the reader to the wrong fix")


def test_completing_the_seed_set_puts_the_hard_value_in_the_fields():
    """GREEN: seeded, the node's own hard value bounds its own ceiling —
    the field can no longer claim the node is unreachably high, and the
    contradiction is now VISIBLE as a plain ``floor > ceiling`` (the two
    runway values genuinely disagree over that budget, which is the
    attribution the law is supposed to hand back)."""
    G, hard = _heca_shape()
    layout = _Layout()
    layout._seed_hard_truth_values = hard
    ceiling, _floor = spine_value_fields(layout, G)
    assert ceiling[2] == pytest.approx(60.790, abs=1e-9), (
        "the hard node's OWN value is now a ceiling source at distance 0")
    # and it propagates: node 1 is now capped by the low runway truth.
    assert ceiling[1] == pytest.approx(60.790 + 8.928, abs=1e-9)


def test_a_consistent_pair_of_anchors_stays_silent():
    """The falsifier: when the two runway values DO reconcile over the
    route budget, seeding completely changes nothing and no class fires.
    Without this the twin would pass for a detector that always fires."""
    G, _ = _heca_shape()
    layout = _Layout()
    # node 2's hard value is now within the 48.928 m budget of node 0.
    layout._seed_hard_truth_values = {2: 115.242 - 10.0}
    spine_value_fields(layout, G)
    assert assert_no_final_band_inversion(layout, "TEST") == 0
    assert layout._final_band_inversions == []


def test_a_sub_materiality_overshoot_is_pass_with_residual():
    """Convergence guards: a deficit under the 0.01 m materiality floor is
    reported, never raised."""
    G, _ = _heca_shape()
    layout = _Layout()
    floor_at_2 = 115.242 - 48.928
    layout._seed_hard_truth_values = {
        2: floor_at_2 - 0.5 * FINAL_BAND_INVERSION_TOL_M}
    spine_value_fields(layout, G)
    residual = assert_no_final_band_inversion(layout, "TEST")
    assert residual >= 1
    klasses = {r["klass"] for r in layout._final_band_inversions}
    assert "floor_above_own_hard_value" in klasses, (
        "the new class is recorded even when sub-materiality — the "
        "PASS-with-residual count is a count, not a silence")
    # once seeded, the node's own value IS its ceiling, so the same
    # overshoot is visible to BOTH classes; each is recorded once.
    assert klasses == {"floor_above_own_hard_value", "floor_above_ceiling"}
