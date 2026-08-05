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
    # CANONICAL-IDENTITY KEYS (debug lane A 2026-08-05): the published
    # hard-truth map is keyed by the node's canonical POINT, never by a
    # node index — see ``test_the_hard_truth_join_survives_a_node_list_
    # rebuild`` for why an index key is not a valid identity.
    return _G(runway_anchor, spine_adj, pos), {pos[2]: 60.790}


# ── (a) STANDING LAW (the gate AND its predicate are retired) ────────────

def test_band_seed_completeness_is_standing_law():
    """docs/RULINGS.md 2026-08-05, build-complete-then-debug: "NO GATES.
    Every believed-in law becomes standing law; O4_ law gates and their
    env overrides are DELETED as their territory is touched."  A band
    whose own seeds are the runway anchors may not floor a runway node
    above its own runway value, so the completeness is the law.

    The SEATS lane removed the predicate itself, not just its env read: a
    constant-true ``band_seed_complete_enabled()`` would be a gate-shaped
    hole a future edit could re-open.  Both must be gone."""
    import auto_patch.elevation_per_surface.building_feasibility as BF

    assert not hasattr(BF, "band_seed_complete_enabled")
    assert 'O4_BAND_SEED_COMPLETE"' not in open(BF.__file__).read()


# ── (a2) the PRE-SOLVE context ───────────────────────────────────────────

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
    layout._seed_hard_truth_values = {G.pos[2]: 115.242 - 10.0}
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
        G.pos[2]: floor_at_2 - 0.5 * FINAL_BAND_INVERSION_TOL_M}
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


# ── (e) THE IDENTITY LAW — canonical point, never node index ─────────────

def test_the_hard_truth_join_survives_a_node_list_rebuild():
    """REGRESSION TWIN (debug lane A 2026-08-05).

    THE DEFECT.  ``layout._seed_hard_truth_values`` was keyed by the
    SOLVE's node index.  A node index is meaningful only inside the one
    ``_build_node_list`` call that assigned it: the space is handed out by
    walking ``layout.shapes``, and every post-solve consumer
    (``route_band_violations``, the tools) rebuilds it on a layout that has
    since GROWN.  Index ``i`` then names a different node, so a runway's
    hard elevation was seeded at an unrelated point and the value fields
    inverted around it.  Measured at SPJC on the composed tree: 448 of 455
    resolvable seeds landed on the wrong node (|published − emitted| p50
    7.15 m, max 16.96 m), inverting 795 field nodes (worst 20.197 m) and
    minting 1,208 of its 1,326 route-band violations.

    THE LAW.  The join is by CANONICAL IDENTITY.  Here the SAME published
    map is consumed against a graph whose indices have been shifted (a
    rebuild that admitted one extra node ahead of the others) — the value
    must still land on the node at the published POSITION.  An index-keyed
    map cannot pass this: it would put 60.790 on whatever now holds index
    2.
    """
    G, hard = _heca_shape()
    layout = _Layout()
    layout._seed_hard_truth_values = hard
    from auto_patch.elevation_per_surface.building_feasibility import (
        _hard_truth_spine_seeds)

    # BEFORE the rebuild: node 2 carries the hard value.
    assert _hard_truth_spine_seeds(layout, G) == {2: 60.790}

    # A REBUILD shifts every index by one (an extra node was admitted
    # ahead of them) — the geometry is untouched, only the numbering.
    shifted = _G({k + 1: v for k, v in G.runway_anchor.items()},
                 {k + 1: [(v + 1, b) for (v, b) in adj]
                  for k, adj in G.spine_adj.items()},
                 {k + 1: p for k, p in G.pos.items()})
    seeds = _hard_truth_spine_seeds(layout, shifted)
    assert seeds == {3: 60.790}, (
        "the hard value must follow its POSITION through a node-list "
        f"rebuild, not its old index; got {seeds}")

    # and the fields it seeds are the same field, just renumbered.
    ceiling, _floor = spine_value_fields(layout, shifted)
    assert ceiling[3] == pytest.approx(60.790, abs=1e-9)
    assert ceiling[2] == pytest.approx(60.790 + 8.928, abs=1e-9)


def test_the_published_map_is_not_index_keyed():
    """ANTI-REGRESSION: an integer-keyed map must NOT resolve.  Without
    this, re-introducing the index key would silently pass every other
    twin in this file (they would just look up ``truth[2]`` again)."""
    G, _ = _heca_shape()
    layout = _Layout()
    layout._seed_hard_truth_values = {2: 60.790}      # the retired schema
    from auto_patch.elevation_per_surface.building_feasibility import (
        _hard_truth_spine_seeds)
    assert _hard_truth_spine_seeds(layout, G) == {}, (
        "an index-keyed hard-truth map must resolve to NOTHING — it is "
        "the schema whose ambiguity minted 1,208 SPJC route-band rows")
