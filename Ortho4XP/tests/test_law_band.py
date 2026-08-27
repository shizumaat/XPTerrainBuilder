"""Twins for THE UNIFIED LAW BAND — spec
``docs/specs/unified-law-band-spec.md`` §2 (owner ruling RULINGS
2026-08-27, "REFINE THE REACH BAND FIRST").

THE LAW UNDER TEST.  ``reach_band_unified``'s per-node interval is
``[max_a (v_a - d_law(a, n)), min_a (v_a + d_law(a, n))]`` where
``d_law`` is the shortest-path budget in the FULL law graph: the
route-spine edges it always had PLUS the pad frontage chords, the apron
membrane law edges and the airside no-step direct-distance enumeration.

THE MEASURED DEFECT IT CLOSES (spec §0).  HECA building25's route-only
band was ``[77.74, 134.38]`` — 56.6 m wide, because the binding route to
the 05C/23C anchor is 1,752 m at 1.5 %.  The seat landed at 82.52 beside
an apron vertex 72.1 m away that solved at 92.00: both endpoints
individually in-band, the pair 9.77 m over a 1 % x 72 m = 0.72 m chord
cap.  The seat solve and the chord law never met, because the band could
not see the chord.  Twin 1 is that shape in miniature.
"""
import pytest

from auto_patch import law_band as LB
from auto_patch.elevation_per_surface.building_feasibility import (
    spine_value_fields)


# ── the minimal stand-ins (the ``test_band_seed_completeness`` pattern) ──

class _G:
    """The four attributes ``spine_value_fields`` reads."""

    def __init__(self, runway_anchor, spine_adj, pos):
        self.runway_anchor = dict(runway_anchor)
        self.spine_adj = dict(spine_adj)
        self.pos = dict(pos)
        self.service_spine_pairs = set()


class _Layout:
    """Enough layout for the de-crowning, the recorder and the refusal."""

    def __init__(self):
        self.shapes = []
        self.anchor = (0.0, 0.0)
        self.canonical_points = None

    def m_to_ll(self, x, y):
        # A fixed, invertible stand-in: the refusal message must be able
        # to NAME a site, and the twin asserts it does.
        return (30.0 + y / 111_000.0, 31.0 + x / 96_000.0)


def _fields(layout, G):
    return spine_value_fields(layout, G)


# ══════════════════════════════════════════════════════════════════════
# TWIN 1 — the WIDE-ROUTE fixture (spec §2, first bullet)
# ══════════════════════════════════════════════════════════════════════
#
#   node 0  a runway anchor at 100.00, 1,333 m of route away at 1.5 %
#           => budget 20.0 m, so the ROUTE-ONLY band at node 1 is
#           [80.00, 120.00] — the building25 shape: wide, and wrong.
#   node 1  the pad's frontage contact node.
#   node 2  an apron vertex ANCHORED at 90.00, 90 m from node 1 with a
#           1 % frontage chord => budget 0.90 m.
#
# The chord says node 1 may not exceed 90.90.  The route says 120.00.
# Only the law band sees both.

def _wide_route_fixture():
    G = _G(runway_anchor={0: 100.0, 2: 90.0},
           spine_adj={0: [(1, 20.0)], 1: [(0, 20.0)], 2: []},
           pos={0: (0.0, 0.0), 1: (1333.0, 0.0), 2: (1423.0, 0.0)})
    return _Layout(), G


def _publish_frontage_chord(layout, G, budget=0.90):
    return LB.publish_law_band_edges(
        layout, node_pos=G.pos,
        classes={"frontage_chord": [(1, 2, budget)]})


def test_the_frontage_chord_narrows_a_wide_route_band(monkeypatch):
    """§1.1a — the chord is IN the metric, so the ceiling is the chord's.

    RED without the law edge (the shipped defect): the ceiling is the
    route's 120.00 and a seat may be chosen 29 m above a level its own
    frontage can reach.
    """
    from auto_patch import config
    monkeypatch.setattr(config, "BAND_FULL_LAW_GRAPH", True)
    monkeypatch.setattr(config, "BAND_SEAT_ANCHORS", False)
    layout, G = _wide_route_fixture()

    # (a) the ROUTE-ONLY band — nothing published yet.
    ceil0, floor0 = _fields(layout, G)
    assert ceil0[1] == pytest.approx(120.0)
    assert floor0[1] == pytest.approx(80.0)
    assert ceil0[1] - floor0[1] == pytest.approx(40.0)

    # (b) the LAW band — the frontage chord to the 90.00 apron binds.
    layout2, G2 = _wide_route_fixture()
    rep = _publish_frontage_chord(layout2, G2)
    assert rep["by_class"]["frontage_chord"] == 1
    ceil1, floor1 = _fields(layout2, G2)
    assert ceil1[1] == pytest.approx(90.90)
    assert floor1[1] == pytest.approx(89.10)
    # The interval a seat is now chosen from is a few metres wide, not 40.
    assert ceil1[1] - floor1[1] == pytest.approx(1.80)


def test_the_flag_off_reproduces_the_wide_band(monkeypatch):
    """§1.7 — OFF is byte-identical to the pre-ruling band."""
    from auto_patch import config
    monkeypatch.setattr(config, "BAND_FULL_LAW_GRAPH", False)
    monkeypatch.setattr(config, "BAND_SEAT_ANCHORS", False)
    layout, G = _wide_route_fixture()
    _publish_frontage_chord(layout, G)
    ceil, floor = _fields(layout, G)
    assert ceil[1] == pytest.approx(120.0)
    assert floor[1] == pytest.approx(80.0)
    # …and nothing was resolved into the graph at all.
    assert LB.law_adjacency_for(layout, G) == {}


def test_a_membrane_edge_narrows_the_same_way(monkeypatch):
    """§1.1b — the membrane population is the same kind of law edge.

    One law, one metric: the class label is REPORTING, never a different
    relaxation rule.
    """
    from auto_patch import config
    monkeypatch.setattr(config, "BAND_FULL_LAW_GRAPH", True)
    monkeypatch.setattr(config, "BAND_SEAT_ANCHORS", False)
    layout, G = _wide_route_fixture()
    LB.publish_law_band_edges(layout, node_pos=G.pos,
                              classes={"membrane": [(1, 2, 0.90)]})
    ceil, _floor = _fields(layout, G)
    assert ceil[1] == pytest.approx(90.90)


def test_a_no_step_edge_narrows_the_same_way(monkeypatch):
    """§1.1c — likewise the direct-distance enumeration."""
    from auto_patch import config
    monkeypatch.setattr(config, "BAND_FULL_LAW_GRAPH", True)
    monkeypatch.setattr(config, "BAND_SEAT_ANCHORS", False)
    layout, G = _wide_route_fixture()
    LB.publish_law_band_edges(layout, node_pos=G.pos,
                              classes={"no_step": [(1, 2, 0.90)]})
    ceil, _floor = _fields(layout, G)
    assert ceil[1] == pytest.approx(90.90)


# ══════════════════════════════════════════════════════════════════════
# TWIN 2 — the CONTRADICTORY fixture (the building146 class)
# ══════════════════════════════════════════════════════════════════════
#
# A frontage chord demands ``<= 90.90`` at node 1 while a membrane path
# from a 95.00 authority demands ``>= 94.50``.  No elevation satisfies
# both: the interval is EMPTY, and §1.4 makes that a loud PRE-SOLVE
# refusal naming the node, not a seat chosen out of nonsense.

def _contradictory_fixture():
    G = _G(runway_anchor={0: 100.0, 2: 90.0, 3: 95.0},
           spine_adj={0: [(1, 20.0)], 1: [(0, 20.0)], 2: [], 3: []},
           pos={0: (0.0, 0.0), 1: (1333.0, 0.0), 2: (1423.0, 0.0),
                3: (1383.0, 40.0)})
    return _Layout(), G


def test_a_contradictory_site_gives_an_empty_interval(monkeypatch):
    from auto_patch import config
    monkeypatch.setattr(config, "BAND_FULL_LAW_GRAPH", True)
    monkeypatch.setattr(config, "BAND_SEAT_ANCHORS", False)
    monkeypatch.setattr(config, "BAND_LAW_REFUSE", False)
    layout, G = _contradictory_fixture()
    LB.publish_law_band_edges(
        layout, node_pos=G.pos,
        classes={"frontage_chord": [(1, 2, 0.90)],
                 "membrane": [(1, 3, 0.50)]})
    ceil, floor = _fields(layout, G)
    assert ceil[1] == pytest.approx(90.90)
    assert floor[1] == pytest.approx(94.50)
    assert floor[1] > ceil[1]                      # EMPTY, by 3.60 m


def test_an_empty_interval_is_a_loud_pre_solve_refusal(monkeypatch):
    """§1.4 — refusal, naming the node's lat/lon, both binding anchors
    and both binding chains.  Before any patch is written."""
    from auto_patch import config
    monkeypatch.setattr(config, "BAND_FULL_LAW_GRAPH", True)
    monkeypatch.setattr(config, "BAND_SEAT_ANCHORS", False)
    monkeypatch.setattr(config, "BAND_LAW_REFUSE", True)
    layout, G = _contradictory_fixture()
    LB.publish_law_band_edges(
        layout, node_pos=G.pos,
        classes={"frontage_chord": [(1, 2, 0.90)],
                 "membrane": [(1, 3, 0.50)]})
    _fields(layout, G)
    with pytest.raises(LB.LawBandRefusal) as exc:
        LB.refuse_on_inverted_band(layout, "TEST")
    msg = str(exc.value)
    assert "node 1" in msg
    # THE SITE, named: a refusal a reader cannot locate is a statistic.
    assert "30.0000000,31.0138854" in msg
    # BOTH binding anchors and BOTH chains.
    assert "CEILING binds from anchor 2" in msg
    assert "FLOOR   binds from anchor 3" in msg
    assert "chain [2, 1]" in msg
    assert "chain [3, 1]" in msg


def test_a_sub_materiality_crossing_is_a_pass_with_residual(monkeypatch):
    """The convergence guards' materiality floor is law here too: a
    crossing under 0.01 m is reported, never refused."""
    from auto_patch import config
    monkeypatch.setattr(config, "BAND_FULL_LAW_GRAPH", True)
    monkeypatch.setattr(config, "BAND_SEAT_ANCHORS", False)
    monkeypatch.setattr(config, "BAND_LAW_REFUSE", True)
    layout, G = _contradictory_fixture()
    # ceiling 90.900 (from 90.00 + 0.90); floor 90.905 (95.00 - 4.095)
    LB.publish_law_band_edges(
        layout, node_pos=G.pos,
        classes={"frontage_chord": [(1, 2, 0.90)],
                 "membrane": [(1, 3, 4.095)]})
    _fields(layout, G)
    # No exception: every crossing here is under the floor.  (The two
    # anchor nodes cross each other by the same hair through node 1, so
    # the count is the whole sub-material population, not just node 1.)
    residual = LB.refuse_on_inverted_band(layout, "TEST")
    assert residual >= 1


# ══════════════════════════════════════════════════════════════════════
# TWIN 3 — NON-NEGATIVITY IS A PINNED INVARIANT (spec §1.2)
# ══════════════════════════════════════════════════════════════════════
#
# The 2026-08-13 reach-envelope blowup: SIGNED slabs turned the envelope
# Dijkstra into a negative-cycle search and it took 26-56 GB before
# SIGKILL.  A signed law budget here is the same failure, so the refusal
# is at GRAPH-BUILD time — before any heap exists.

def test_a_negative_budget_is_refused_at_graph_build():
    layout, G = _wide_route_fixture()
    with pytest.raises(LB.LawBandNegativeBudget) as exc:
        LB.publish_law_band_edges(
            layout, node_pos=G.pos,
            classes={"frontage_chord": [(1, 2, -0.90)]})
    assert "must be >= 0" in str(exc.value)
    # Nothing was stored: the store is not half-written on the way out.
    assert not getattr(layout, "_law_band_edges_m", None)


def test_a_nan_budget_is_refused_the_same_way():
    layout, G = _wide_route_fixture()
    with pytest.raises(LB.LawBandNegativeBudget):
        LB.publish_law_band_edges(
            layout, node_pos=G.pos,
            classes={"no_step": [(1, 2, float("nan"))]})


def test_a_zero_budget_is_lawful():
    """Zero is a real budget (a flat-coupled pair), not a defect."""
    layout, G = _wide_route_fixture()
    rep = LB.publish_law_band_edges(
        layout, node_pos=G.pos, classes={"membrane": [(1, 2, 0.0)]})
    assert rep["edges"] == 1


# ══════════════════════════════════════════════════════════════════════
# TWIN 4 — SEATS INCREMENT, NEVER RECOMPUTE (spec §1.5d / §2)
# ══════════════════════════════════════════════════════════════════════

def _chain_graph(n=40, budget=1.0):
    """A path 0-1-...-n-1 plus a rung, so the improvement region of a new
    source is a genuine sub-graph rather than the whole thing."""
    adj = {}
    for i in range(n - 1):
        adj.setdefault(i, []).append((i + 1, budget))
        adj.setdefault(i + 1, []).append((i, budget))
    adj.setdefault(5, []).append((25, 3.0))
    adj.setdefault(25, []).append((5, 3.0))
    return adj


#: Seat nodes are FREE nodes, never an existing anchor: ``add_anchor``
#: ADDS a source to the min/max, it does not revalue one.  Revaluing an
#: anchor is not an increment at all — it can LOOSEN a bound, and no
#: pruned walk can discover that.  Seats are new sources by construction
#: (a pad's contact nodes are not runway anchors), so the contract is the
#: one the solve needs; stating it here is what keeps it honest.
@pytest.mark.parametrize("seat_node,seat_value", [
    (20, 5.0), (1, 100.0), (38, -3.0), (25, 12.25), (12, 0.0)])
def test_an_incremental_seat_anchor_equals_a_full_recompute(
        seat_node, seat_value):
    """§1.5(d)'s twin, stated exactly as the spec states it.

    The fields are ``min over anchors (v_a + d(a, .))``; a placed seat
    adds one term.  The incremental relaxation prunes every branch that
    cannot tighten — sound precisely because budgets are ``>= 0`` (§1.2)
    — so it must agree with the full recompute, dict for dict.
    """
    adj = _chain_graph()
    base = {0: 10.0, 39: 40.0}
    inc = LB.full_anchor_field(adj, dict(base))
    inc.add_anchor(seat_node, seat_value)
    full = LB.full_anchor_field(adj, {**base, seat_node: seat_value})
    assert inc.ceiling == full.ceiling
    assert inc.floor == full.floor


def test_many_incremental_seats_equal_one_full_recompute():
    """Seats are placed one after another; the invariant must survive the
    whole sequence, not just the first."""
    adj = _chain_graph()
    base = {0: 10.0, 39: 40.0}
    seats = {7: 11.0, 18: 9.5, 30: 33.0, 25: 12.25}
    inc = LB.full_anchor_field(adj, dict(base))
    for k in sorted(seats):
        inc.add_anchor(k, seats[k])
    full = LB.full_anchor_field(adj, {**base, **seats})
    assert inc.ceiling == full.ceiling
    assert inc.floor == full.floor


def test_the_batched_seat_set_equals_the_one_by_one_sequence():
    """§1.5(d)'s EFFICIENCY half: the whole placed-seat set is ONE
    multi-source pruned walk per bound, and it must land exactly where
    the per-seat sequence — and the full recompute — land.

    Measured reason this is the shipped path: per-seat relaxation is one
    Dijkstra AND one grid refresh per seat, and a HECA build on that arm
    passed 20 minutes inside the seat loop before it was killed.
    """
    adj = _chain_graph()
    base = {0: 10.0, 39: 40.0}
    seats = {7: 11.0, 18: 9.5, 30: 33.0, 25: 12.25}
    one_by_one = LB.full_anchor_field(adj, dict(base))
    for k in sorted(seats):
        one_by_one.add_anchor(k, seats[k])
    batched = LB.full_anchor_field(adj, dict(base))
    batched.add_anchors(seats)
    full = LB.full_anchor_field(adj, {**base, **seats})
    assert batched.ceiling == one_by_one.ceiling == full.ceiling
    assert batched.floor == one_by_one.floor == full.floor
    # …and it did it in ONE walk per side, not four.
    assert batched.updates == len(seats)


def test_a_seat_that_cannot_tighten_costs_no_relaxation():
    """The EARLY EXIT §1.5(d) names: a seat whose value is already inside
    the band at its own node relaxes nothing at all."""
    adj = _chain_graph()
    inc = LB.full_anchor_field(adj, {0: 10.0, 39: 40.0})
    ceil_before = dict(inc.ceiling)
    ch = inc.add_anchor(20, inc.ceiling[20])
    # The ceiling side cannot be tightened by a source sitting ON it, so
    # the bounded walk stops at the source itself and NOTHING is rewritten.
    assert ch["ceiling"] == {}
    assert inc.ceiling == ceil_before


def test_the_merged_adjacency_is_a_view_not_a_copy():
    """One graph duplication per band build is exactly the cost the
    efficiency contract forbids."""
    spine = {1: [(2, 3.0)]}
    law = {1: [(3, 0.5)], 4: [(5, 1.0)]}
    m = LB.MergedAdjacency(spine, law)
    assert sorted(m.get(1)) == [(2, 3.0), (3, 0.5)]
    assert m.get(4) == [(5, 1.0)]
    assert m.get(9, ()) == ()
    spine[1].append((6, 2.0))                    # a view sees the change
    assert (6, 2.0) in m.get(1)


# ══════════════════════════════════════════════════════════════════════
# TWIN 5 — OFF IS BYTE-IDENTICAL (spec §1.7)
# ══════════════════════════════════════════════════════════════════════

def test_off_is_byte_identical_to_publishing_nothing(monkeypatch):
    from auto_patch import config
    monkeypatch.setattr(config, "BAND_FULL_LAW_GRAPH", False)
    monkeypatch.setattr(config, "BAND_SEAT_ANCHORS", False)
    la, Ga = _contradictory_fixture()
    LB.publish_law_band_edges(
        la, node_pos=Ga.pos,
        classes={"frontage_chord": [(1, 2, 0.90)],
                 "membrane": [(1, 3, 0.50)]})
    ca, fa = _fields(la, Ga)
    lb, Gb = _contradictory_fixture()
    cb, fb = _fields(lb, Gb)
    assert ca == cb and fa == fb
    # …and the refusal is inert with the flag off, whatever was published.
    assert LB.refuse_on_inverted_band(la, "TEST") == 0


# ══════════════════════════════════════════════════════════════════════
# STORE HYGIENE — the things a silent store gets wrong
# ══════════════════════════════════════════════════════════════════════

def test_a_pair_stated_twice_carries_one_law(monkeypatch):
    """Two copies of one law in the metric is the round-3 station build's
    own reason for dropping restated pairs; the TIGHTER budget wins."""
    layout, G = _wide_route_fixture()
    rep = LB.publish_law_band_edges(
        layout, node_pos=G.pos,
        classes={"frontage_chord": [(1, 2, 0.90)],
                 "no_step": [(2, 1, 0.40)]})
    assert rep["edges"] == 1
    assert rep["duplicate_pairs"] == 1
    from auto_patch import config
    monkeypatch.setattr(config, "BAND_FULL_LAW_GRAPH", True)
    monkeypatch.setattr(config, "BAND_SEAT_ANCHORS", False)
    ceil, _floor = _fields(layout, G)
    assert ceil[1] == pytest.approx(90.40)


def test_an_endpoint_off_the_graph_is_counted_never_silent(monkeypatch):
    from auto_patch import config
    monkeypatch.setattr(config, "BAND_FULL_LAW_GRAPH", True)
    layout, G = _wide_route_fixture()
    LB.publish_law_band_edges(layout, node_pos=G.pos,
                              classes={"membrane": [(1, 2, 0.9)]})
    # A graph that does not carry node 2 at all.
    G2 = _G(runway_anchor={0: 100.0},
            spine_adj={0: [(1, 20.0)], 1: [(0, 20.0)]},
            pos={0: (0.0, 0.0), 1: (1333.0, 0.0)})
    assert LB.law_adjacency_for(layout, G2) == {}
    assert LB.law_adjacency_stats(G2)["unresolved"] == 1


def test_the_report_names_every_class():
    layout, G = _wide_route_fixture()
    rep = LB.publish_law_band_edges(layout, node_pos=G.pos, classes={})
    line = LB.format_law_band_report("TEST", rep)
    for klass in LB.LAW_EDGE_CLASSES:
        assert klass in line
    assert "OFF" in LB.format_law_band_report("TEST", None)
