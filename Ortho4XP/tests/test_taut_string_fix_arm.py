"""Headless tests for the three taut-string fix-arm fixes.

Spec: ``docs/specs/taut-string-fix-arm-spec.md`` §§1-3, acceptance §4.1.

* **Fix 1 — grip completeness (pin-vs-hard pairs).**  Inside the existing
  string gate; the switch is whether ``filter_pins_by_grade_law`` receives
  ``elev``.  ``elev=None`` (every pre-fix caller) ⇒ the pin-vs-pin walk,
  unchanged.
* **Fix 2 — Ruling 55 neighbour bounding.**  Gate
  ``O4_HARD_NEIGHBOUR_BOUND``, default ``"0"``.  BOUNDING, never freezing:
  a blend/clamp candidate adjacent to a hard node may still descend away
  from it at cap rate.  An EMPTY intersection is a DECLARED conflict — the
  node keeps its own-law value and the triple rides ``declared_out``.
* **Fix 3 — pins carried through the final projections.**  Gate
  ``O4_STRING_PINS_FINAL_HOLD``, default ``"0"``.  The crossing is by
  CANONICAL KEY (``_string_pin_hold_indexes``) and the hold is set
  membership in the pass's ``hard`` — exactly Ruling 54's mechanism — so
  it is driven here on the real projection.

No network, no X-Plane install, no DEM: pure arithmetic + ``tmp_path``.
"""
from __future__ import annotations

import pytest

from auto_patch.elevation_per_surface.route_profile.one_solve import (
    feasibility_project)
from auto_patch.elevation_per_surface.route_profile.solve import (
    _pins_on_frozen_graph, _stamp_pin_ledger, _string_pin_hold_indexes)
from auto_patch.elevation_per_surface.route_profile.taut_string import (
    filter_pins_by_grade_law)


# ══════════════════════════════════════════════════════════════════════
# fix 1 — grip completeness: pin-vs-hard pairs
# ══════════════════════════════════════════════════════════════════════
def _chain(zs, budget=0.15):
    """A pinned chain; ``adj`` carries the per-pair budget both ways."""
    adj: dict = {}
    for i in range(len(zs) - 1):
        adj.setdefault(i, []).append((i + 1, budget))
        adj.setdefault(i + 1, []).append((i, budget))
    return adj


def test_fix1_off_by_construction_when_elev_is_absent():
    """``elev=None`` is the pre-fix behaviour, verbatim: a pin one edge
    from an over-cap HARD anchor is not even examined."""
    pins = {1: 100.0, 2: 100.1}          # node 0 is hard at 110.0
    adj = _chain([110.0, 100.0, 100.1])
    kept, rel = filter_pins_by_grade_law(pins, adj, hard={0})
    assert kept == pins and rel == []


def test_fix1_releases_the_pin_against_a_hard_anchor():
    """Over cap against a hard node ⇒ the PIN is the release candidate
    (a hard node is never a candidate), witnessed as ``pin_vs_hard``."""
    elev = [110.0, 100.0, 100.1]
    pins = {1: 100.0, 2: 100.1}
    adj = _chain(elev)
    kept, rel = filter_pins_by_grade_law(pins, adj, hard={0}, elev=elev)
    assert set(kept) == {2}, kept
    assert len(rel) == 1
    w = rel[0]
    assert w["released"] == 1 and w["pair"] == [0, 1]
    assert w["rule"] == "pin_vs_hard"
    assert abs(w["chord_dz_m"] - 10.0) < 1e-9
    assert abs(w["excess_m"] - (10.0 - 0.15)) < 1e-9
    # the surviving pin is lawful against every hard neighbour it has
    for i, lst in adj.items():
        for (j, b) in lst:
            if i in kept and j == 0:
                assert abs(kept[i] - elev[0]) <= b + 1e-9


def test_fix1_never_releases_when_both_ends_are_hard():
    """A pin that is ITSELF a law anchor beside another law anchor is the
    projection's pre-existing genuine step, not ours."""
    elev = [110.0, 100.0]
    pins = {0: 110.0, 1: 100.0}
    adj = _chain(elev)
    kept, rel = filter_pins_by_grade_law(pins, adj, hard={0, 1}, elev=elev)
    assert kept == pins and rel == []


def test_fix1_minimality_and_endpoints_run_over_both_families():
    """Ruling 52's re-admission pass and endpoint protection see the UNION
    of the pin-pin and pin-hard families, so a release justified only by a
    pin-hard pair is kept and no unnecessary release survives."""
    #   0 hard 110 | 1 pin 100 | 2 pin 100.05 | 3 pin 100.10
    elev = [110.0, 100.0, 100.05, 100.10]
    pins = {1: 100.0, 2: 100.05, 3: 100.10}
    adj = _chain(elev)
    depth = {1: 10.0, 2: 5.0, 3: 0.0}
    kept, rel = filter_pins_by_grade_law(pins, adj, hard={0}, elev=elev,
                                         endpoint_depth=depth, )
    assert set(kept) == {2, 3}, kept                 # only pin 1 released
    assert [w["rule"] for w in rel] == ["pin_vs_hard"]
    # MINIMALITY: re-admitting pin 1 re-creates the pin-hard over-cap pair
    assert abs(pins[1] - elev[0]) > 0.15 + 1e-9


def test_fix1_is_deterministic_with_the_hard_family():
    elev = [110.0, 100.0, 101.0, 101.05]
    pins = {1: 100.0, 2: 101.0, 3: 101.05}
    adj = _chain(elev)
    a = filter_pins_by_grade_law(pins, adj, hard={0}, elev=elev)
    b = filter_pins_by_grade_law(dict(reversed(list(pins.items()))), adj,
                                 hard={0}, elev=elev)
    assert a[0] == b[0]
    assert [w["released"] for w in a[1]] == [w["released"] for w in b[1]]


# ══════════════════════════════════════════════════════════════════════
# ROUND 2 §1 — the grip's pair graph is the LAW's pair graph
# ══════════════════════════════════════════════════════════════════════
def _isolated(zs):
    """Every node in ``pins``/``elev``, NO spine edges at all — so the only
    law is whatever ``law_edges`` carries (§1a) or a two-hop path (§1b)."""
    return {i: [] for i in range(len(zs))}


def test_1a_a_ring_edge_the_spine_graph_lacks_is_now_filtered():
    """The measured defect: two kept pins contradicting across a junction
    RING edge (HECA -12539, s9 112.386 vs s2 104.410 over 3.69 m).  The
    spine graph does not contain that edge, so round 1 never saw it."""
    elev = [112.386, 104.410]
    pins = {0: 112.386, 1: 104.410}
    ring = [(0, 1, 0.0554)]                      # 1.5 % of 3.69 m
    kept, rel = filter_pins_by_grade_law(pins, _isolated(elev), elev=elev)
    assert kept == pins and rel == []            # law_edges absent ⇒ round 1
    kept, rel = filter_pins_by_grade_law(pins, _isolated(elev), elev=elev,
                                         law_edges=ring)
    assert len(kept) == 1 and len(rel) == 1
    assert rel[0]["rule"] == "ring_edge"
    assert abs(rel[0]["chord_dz_m"] - 7.976) < 1e-9
    assert rel[0]["released"] in (0, 1)


def test_1a_law_edges_may_be_a_single_use_iterator():
    """The caller streams the solve's own constraints object; consuming it
    twice would silently halve the pair universe."""
    elev = [110.0, 100.0]
    pins = {0: 110.0, 1: 100.0}
    stream = iter([(0, 1, 0.15)])
    kept, rel = filter_pins_by_grade_law(pins, _isolated(elev), elev=elev,
                                         law_edges=stream)
    assert len(rel) == 1 and rel[0]["rule"] == "ring_edge"


def test_1a_ring_edge_against_a_hard_node_releases_the_pin():
    elev = [110.0, 100.0]
    pins = {1: 100.0}
    kept, rel = filter_pins_by_grade_law(
        pins, _isolated(elev), hard={0}, elev=elev,
        law_edges=[(0, 1, 0.15)])
    assert kept == {} and len(rel) == 1
    assert rel[0]["released"] == 1               # a hard node is no candidate
    assert rel[0]["rule"] == "ring_edge"


def test_1a_hard_hard_ring_edges_stay_the_pre_existing_genuine_step():
    elev = [110.0, 100.0]
    kept, rel = filter_pins_by_grade_law(
        {}, _isolated(elev), hard={0, 1}, elev=elev,
        law_edges=[(0, 1, 0.15)])
    assert kept == {} and rel == []


def test_1a_the_tightest_carrier_is_the_law_for_a_pair_in_both_graphs():
    """A pair the spine graph carries loosely and a within-shape edge
    carries tightly is judged against the TIGHT one — the law demands
    every carrier be satisfied — while keeping the spine pair's rule."""
    elev = [100.0, 100.5]
    pins = {0: 100.0, 1: 100.5}
    adj = _chain(elev, budget=1.0)               # satisfied on the spine
    kept, rel = filter_pins_by_grade_law(pins, adj, elev=elev)
    assert kept == pins and rel == []
    kept, rel = filter_pins_by_grade_law(pins, adj, elev=elev,
                                         law_edges=[(0, 1, 0.1)])
    assert len(rel) == 1
    assert rel[0]["cap_budget_m"] == 0.1
    assert rel[0]["rule"] == "grade_law_over_cap"   # provenance is the spine


def test_1b_two_pins_through_one_free_node_are_a_pair():
    """§1b: the interval the law leaves for the free node between two pins
    is ``budget(i,v) + budget(v,j)``; over that, no value of the free node
    satisfies both edges — which is exactly the empty interval round 1
    DECLARED (2,375 of 5,252 declared rows had both authors kept pins)."""
    elev = [100.0, 0.0, 101.0]                   # node 1 is FREE
    pins = {0: 100.0, 2: 101.0}
    adj = {0: [(1, 0.15)], 1: [(0, 0.15), (2, 0.15)], 2: [(1, 0.15)]}
    kept, rel = filter_pins_by_grade_law(pins, adj, elev=elev)
    assert len(kept) == 1 and len(rel) == 1
    w = rel[0]
    assert w["rule"] == "through_free"
    assert w["pair"] == [0, 2]
    assert abs(w["cap_budget_m"] - 0.30) < 1e-12
    assert abs(w["chord_dz_m"] - 1.0) < 1e-12


def test_1b_pin_through_free_to_hard_releases_the_pin():
    elev = [110.0, 0.0, 100.0]                   # 0 hard, 1 free, 2 pin
    pins = {2: 100.0}
    adj = {0: [(1, 0.15)], 1: [(0, 0.15), (2, 0.15)], 2: [(1, 0.15)]}
    kept, rel = filter_pins_by_grade_law(pins, adj, hard={0}, elev=elev)
    assert kept == {} and len(rel) == 1
    assert rel[0]["released"] == 2 and rel[0]["rule"] == "through_free"


def test_1b_hard_through_free_to_hard_is_not_ours():
    elev = [110.0, 0.0, 100.0]
    kept, rel = filter_pins_by_grade_law({}, {0: [(1, 0.15)],
                                             1: [(0, 0.15), (2, 0.15)],
                                             2: [(1, 0.15)]},
                                         hard={0, 2}, elev=elev)
    assert kept == {} and rel == []


def test_1b_two_hop_crosses_the_spine_and_the_shape_graph():
    """The free node's neighbours come from the UNION: one leg on the
    spine, the other a within-shape edge."""
    elev = [100.0, 0.0, 101.0]
    pins = {0: 100.0, 2: 101.0}
    adj = {0: [(1, 0.15)], 1: [(0, 0.15)]}
    kept, rel = filter_pins_by_grade_law(pins, adj, elev=elev,
                                         law_edges=[(1, 2, 0.15)])
    assert len(rel) == 1 and rel[0]["rule"] == "through_free"
    assert abs(rel[0]["cap_budget_m"] - 0.30) < 1e-12


def test_1b_a_tighter_direct_edge_keeps_the_pair_and_its_rule():
    """A direct carrier tighter than the two-hop sum wins the budget and
    the provenance (this is also the all-pair-apron short circuit: inside
    one shape every two-hop pair is already a direct edge)."""
    elev = [100.0, 0.0, 101.0]
    pins = {0: 100.0, 2: 101.0}
    adj = {0: [(1, 0.15), (2, 0.10)], 1: [(0, 0.15), (2, 0.15)],
           2: [(1, 0.15), (0, 0.10)]}
    kept, rel = filter_pins_by_grade_law(pins, adj, elev=elev)
    assert len(rel) == 1
    assert rel[0]["cap_budget_m"] == 0.10
    assert rel[0]["rule"] == "grade_law_over_cap"


def test_1c_one_cover_one_minimality_pass_over_all_four_families():
    """§1c: both new families feed the EXISTING machinery — one ``over``
    list, one greedy cover, one re-admission pass, the same
    endpoint-protective rank.  Here pin 1 covers a spine pair, a ring pair
    and a two-hop pair at once; releasing it alone clears all three."""
    #  0 hard 110 | 1 pin 100 | 2 pin 100.02 | 3 free | 4 pin 100.05
    #  (0,1) spine over cap; (1,2) a ring edge; (1,4) two-hop through 3.
    elev = [110.0, 100.0, 100.02, 0.0, 100.05]
    pins = {1: 100.0, 2: 100.02, 4: 100.05}
    adj = {0: [(1, 0.15)], 1: [(0, 0.15), (3, 0.005)],
           3: [(1, 0.005), (4, 0.005)], 4: [(3, 0.005)]}
    stats: dict = {}
    kept, rel = filter_pins_by_grade_law(
        pins, adj, hard={0}, elev=elev,
        law_edges=[(1, 2, 0.001)], stats_out=stats,
        endpoint_depth={1: 10.0, 2: 0.0, 4: 0.0})
    assert set(kept) == {2, 4}, kept
    assert {w["rule"] for w in rel} == {"pin_vs_hard", "ring_edge",
                                        "through_free"}
    assert {w["released"] for w in rel} == {1}
    assert stats["n_over"] == 3
    assert stats["n_over_by_rule"] == {"pin_vs_hard": 1, "ring_edge": 1,
                                       "through_free": 1}
    assert stats["n_law_edges_in"] == 1
    assert stats["n_two_hop_free_nodes"] == 1


def test_1c_is_deterministic_across_all_families():
    elev = [110.0, 100.0, 101.0, 0.0]
    pins = {1: 100.0, 2: 101.0}
    adj = {0: [(1, 0.15)], 1: [(0, 0.15), (3, 0.05)],
           3: [(1, 0.05), (2, 0.05)], 2: [(3, 0.05)]}
    law = [(1, 2, 0.02)]
    a = filter_pins_by_grade_law(pins, adj, hard={0}, elev=elev,
                                 law_edges=list(law))
    b = filter_pins_by_grade_law(dict(reversed(list(pins.items()))), adj,
                                 hard={0}, elev=elev,
                                 law_edges=list(reversed(law)))
    assert a[0] == b[0]
    assert sorted((w["released"], tuple(w["pair"]), w["rule"])
                  for w in a[1]) == sorted(
        (w["released"], tuple(w["pair"]), w["rule"]) for w in b[1])


def test_1a_law_edge_stream_honours_the_constraint_edge_contract():
    """``shape_constraints`` edges are NOT all symmetric budgets: an
    UNREGULATED edge carries ``None``/negative, and a Stage-B0 INTERVAL
    edge is a 4-tuple.  The stream reads them exactly as
    ``one_solve._build_adjacency`` does — the loosest symmetric slab that
    contains the interval, one-sided skipped — so the grip can never
    release a pin an asymmetric law would have allowed.  (SPJC's very
    first gate-on build died on a ``None`` budget: the contract is real.)
    """
    from auto_patch.elevation_per_surface.route_profile.solve import (
        _law_edge_stream)
    sc = [{"edges": [(0, 1, 0.15),            # plain symmetric
                     (1, 2, None),            # unregulated -> skipped
                     (2, 3, -1.0),            # unregulated -> skipped
                     (3, 4, -0.2, 0.5),       # interval -> max(|lo|,|hi|)
                     (4, 5, None, 0.5),       # one-sided -> skipped
                     (5, 6, -0.2, None)]}]    # one-sided -> skipped
    assert list(_law_edge_stream(sc)) == [(0, 1, 0.15), (3, 4, 0.5)]


def test_1c_lawful_pairs_release_nothing_anywhere():
    """No release without a violated pair — the grip is not a thinner."""
    elev = [100.0, 100.01, 100.02, 100.03]
    pins = {0: 100.0, 2: 100.02}
    adj = {0: [(1, 1.0)], 1: [(0, 1.0), (2, 1.0)], 2: [(1, 1.0)]}
    stats: dict = {}
    kept, rel = filter_pins_by_grade_law(pins, adj, elev=elev,
                                         law_edges=[(0, 2, 1.0), (2, 3, 1.0)],
                                         stats_out=stats)
    assert kept == pins and rel == []
    # (0,2) is carried directly; (1,*) and (3,*) have a FREE end, so they
    # never become pairs — only their two-hop composition can, and here it
    # is looser than the direct carrier, so nothing is added.
    assert stats["n_over"] == 0 and stats["n_pairs"] == 1


# ══════════════════════════════════════════════════════════════════════
# fix 2 — Ruling 55 neighbour bounding
# ══════════════════════════════════════════════════════════════════════
def _corridor():
    """Node 0 hard at 110; a 4-node corridor 10 m below it at 0.15 m/edge
    budget — the projection's clamp/blend phase owns node 1."""
    elev = [110.0, 100.0, 100.0, 100.0, 100.0]
    sc = [{"edges": [(0, 1, 0.15), (1, 2, 0.15), (2, 3, 0.15),
                     (3, 4, 0.15)]}]
    return elev, sc


def test_fix2_gate_off_is_byte_identical(monkeypatch):
    monkeypatch.delenv("O4_HARD_NEIGHBOUR_BOUND", raising=False)
    a, sc_a = _corridor()
    feasibility_project(a, sc_a, {0})
    monkeypatch.setenv("O4_HARD_NEIGHBOUR_BOUND", "0")
    b, sc_b = _corridor()
    declared: list = []
    feasibility_project(b, sc_b, {0}, declared_out=declared)
    assert a == b, (a, b)
    assert declared == []


def test_fix2_costs_nothing_where_the_law_is_already_satisfied(monkeypatch):
    """BOUNDING, never freezing: on a corridor the envelope already keeps
    lawful, the bound changes not one value — every node still descends a
    full budget per edge away from the anchor."""
    monkeypatch.setenv("O4_HARD_NEIGHBOUR_BOUND", "0")
    off, sc_off = _corridor()
    feasibility_project(off, sc_off, {0})
    monkeypatch.setenv("O4_HARD_NEIGHBOUR_BOUND", "1")
    elev, sc = _corridor()
    declared: list = []
    feasibility_project(elev, sc, {0}, declared_out=declared)
    assert elev == off, (elev, off)
    assert elev[0] == 110.0                      # hard never moves
    assert declared == []                        # nothing contradicts
    for k in range(4):                           # still descending at cap
        assert elev[k] > elev[k + 1], elev
    assert elev[4] < elev[1] - 0.2, elev


@pytest.mark.xfail(strict=True, reason=(
    "EXPOSED CONSUMER, kill-half §2 (2026-08-04): fix-arm SITE 2 was the "
    "break blend itself, and the blend is deleted.  Site 1 (the envelope "
    "clamp) is untouched and still tested above.  Left failing on purpose "
    "— O4_HARD_NEIGHBOUR_BOUND is not this spec's to retire."))
def test_fix2_stops_the_blend_manufacturing_an_over_cap_pair(monkeypatch):
    """THE mechanism Ruling 55 names.  Two anchors 20 m apart through a
    3-edge chain make the interior nodes BROKEN, and the distance-weighted
    break blend then parks node 1 at 103.33 — 6.5 m from its own hard
    neighbour at 110 across a 0.15 m budget, an over-cap pair no anchor
    asked for.  Under the bound node 1 stays inside ``[hard ± cap·d]`` and
    the residual break concentrates where the anchors genuinely disagree.

    POST-§2 MEASUREMENT (recorded, not hidden): with no blend the interior
    nodes are placed by the sweeps at 100.07/99.93, so the over-cap pair
    against the hard neighbour survives on this genuinely infeasible
    synthetic system — 20 m of anchor disagreement across 0.45 m of total
    budget.  On the five-airport battery the FINAL band carries no material
    inversion at all (spec §3), so no production surface takes this path.
    """
    sc = [{"edges": [(0, 1, 0.15), (1, 2, 0.15), (2, 3, 0.15)]}]
    monkeypatch.setenv("O4_HARD_NEIGHBOUR_BOUND", "0")
    off = [110.0, 100.0, 100.0, 90.0]
    rem_off, _ = feasibility_project(off, sc, {0, 3})
    assert abs(off[1] - off[0]) > 0.15 + 1e-9, off      # manufactured
    monkeypatch.setenv("O4_HARD_NEIGHBOUR_BOUND", "1")
    on = [110.0, 100.0, 100.0, 90.0]
    declared: list = []
    rem_on, _ = feasibility_project(on, sc, {0, 3}, declared_out=declared)
    assert on[0] == 110.0 and on[3] == 90.0            # anchors never move
    # each interior node now obeys its own hard neighbour's cap budget
    assert abs(on[1] - on[0]) <= 0.15 + 1e-9, on
    assert abs(on[2] - on[3]) <= 0.15 + 1e-9, on
    # ...and the genuine anchor disagreement is still REPORTED, not hidden
    assert rem_on < rem_off, (rem_on, rem_off)
    assert rem_on >= 1
    assert declared == []       # neither node has contradicting neighbours


def test_fix2_declares_an_empty_intersection_and_keeps_the_own_law_value(
        monkeypatch):
    """Two hard nodes that disagree beyond their budgets THROUGH a node:
    the node keeps whatever its own law puts it at and the triple is
    declared, author-carrying.  Suppressing it is the one thing the ruling
    forbids."""
    #  hard 0 at 110 and hard 2 at 90, both one 0.15 m edge from node 1:
    #  [109.85, 110.15] ∩ [89.85, 90.15] = ∅.
    elev = [110.0, 100.0, 90.0]
    sc = [{"edges": [(0, 1, 0.15), (1, 2, 0.15)]}]
    monkeypatch.setenv("O4_HARD_NEIGHBOUR_BOUND", "0")
    control = list(elev)
    feasibility_project(control, sc, {0, 2})
    monkeypatch.setenv("O4_HARD_NEIGHBOUR_BOUND", "1")
    declared: list = []
    feasibility_project(elev, sc, {0, 2}, declared_out=declared)
    assert elev == control, (elev, control)      # own law, untouched
    assert declared, "an empty intersection must be DECLARED"
    row = declared[0]
    assert row["marker"] == "declared_hard_conflict"
    assert row["node"] == 1
    assert {row["hard_lo_author"], row["hard_hi_author"]} == {0, 2}
    assert row["deficit_m"] > 0.0
    assert row["site"] in ("envelope_clamp", "break_blend", "chain_rigid",
                           "branch_rigid")


def test_fix2_declared_out_is_write_only_and_optional(monkeypatch):
    """``declared_out=None`` under the gate must behave exactly like the
    list arm — the channel is delivery, never law."""
    monkeypatch.setenv("O4_HARD_NEIGHBOUR_BOUND", "1")
    elev = [110.0, 100.0, 90.0]
    sc = [{"edges": [(0, 1, 0.15), (1, 2, 0.15)]}]
    with_out: list = []
    a = list(elev)
    feasibility_project(a, sc, {0, 2}, declared_out=with_out)
    b = list(elev)
    feasibility_project(b, sc, {0, 2})
    assert a == b
    assert with_out


# ══════════════════════════════════════════════════════════════════════
# fix 3 — the kept pins cross into the final projections
# ══════════════════════════════════════════════════════════════════════
class _Layout:
    def __init__(self, pin_keys=None):
        if pin_keys is not None:
            self._string_pin_keys = pin_keys


def test_fix3_crossing_is_by_canonical_key_and_drops_the_unresolved():
    """An index carry does not survive a node-list rebuild; a key does.
    A pin the rebuild dropped (emit decimation) must fall out rather than
    be resolved onto some other node."""
    layout = _Layout({("a",): 100.0, ("b",): 101.0, ("gone",): 102.0})
    b2i = {("b",): 0, ("a",): 1, ("other",): 2}
    assert _string_pin_hold_indexes(layout, b2i, n=3) == {0, 1}
    # out-of-range indices (a rebuilt list shorter than the map) drop too
    assert _string_pin_hold_indexes(layout, b2i, n=1) == {0}


def test_fix3_no_export_means_no_hold():
    """Gate off in the solve ⇒ no attribute ⇒ empty set ⇒ the pass's hard
    set is untouched (this is what makes the gate-off arm identical)."""
    assert _string_pin_hold_indexes(_Layout(), {("a",): 0}, n=1) == set()
    assert _string_pin_hold_indexes(_Layout({}), {("a",): 0}, n=1) == set()


def test_fix3_membership_holds_the_pin_through_the_projection(monkeypatch):
    """The hold IS set membership in the pass's ``hard`` — Ruling 54's
    mechanism — so a resolved pin stops moving, and its neighbour takes
    the law instead."""
    monkeypatch.delenv("O4_HARD_NEIGHBOUR_BOUND", raising=False)
    layout = _Layout({("p",): 100.0})
    b2i = {("p",): 2}
    sc = [{"edges": [(0, 1, 0.15), (1, 2, 0.15), (2, 3, 0.15)]}]

    free = [110.0, 100.0, 100.0, 100.0]
    feasibility_project(free, sc, {0})
    held = [110.0, 100.0, 100.0, 100.0]
    hold = _string_pin_hold_indexes(layout, b2i, n=4)
    assert hold == {2}
    feasibility_project(held, sc, {0} | hold)
    assert free[2] != 100.0, "the unheld arm must drag the pin"
    assert held[2] == 100.0, "the held arm must not"


def test_fix3_a_held_pin_is_still_law_overridable_via_fix2(monkeypatch):
    """Held, but the law still overrules: with fix 2's gate on, a pin
    whose hard neighbourhood cannot be satisfied surfaces as a DECLARED
    conflict rather than freezing into a silent violation."""
    monkeypatch.setenv("O4_HARD_NEIGHBOUR_BOUND", "1")
    layout = _Layout({("p",): 100.0})
    b2i = {("p",): 1}
    # node 1 is the held pin; nodes 0 and 2 are truth anchors that
    # disagree through it.
    elev = [110.0, 100.0, 90.0, 90.0]
    sc = [{"edges": [(0, 1, 0.15), (1, 2, 0.15), (2, 3, 0.15)]}]
    hold = _string_pin_hold_indexes(layout, b2i, n=4)
    declared: list = []
    rem, bh = feasibility_project(elev, sc, {0, 2} | hold,
                                  declared_out=declared)
    assert elev[1] == 100.0, "a held pin is hard: it does not move"
    # its over-cap pairs are REPORTED as both-hard, never silently forced
    assert bh >= 1, bh


# ══════════════════════════════════════════════════════════════════════
# ROUND 4 §1 — pins live on the frozen graph
# ══════════════════════════════════════════════════════════════════════
# ``_solve_spine_profile`` applies every kept pin but freezes only
# ``spine_adj``-keyed nodes, so an off-graph pin is written, overwritten by
# phase B, and then held at phase B's value by Ruling 54.  Restricting the
# applied set to the freeze-covered graph is the fix; off-graph targets are
# LEDGERED, never applied.
def _spine(zs, budget=0.15):
    """Same chain as ``_chain`` — used here as the FREEZE's key set."""
    return _chain(zs, budget)


def test_r4_off_graph_targets_leave_the_applied_set():
    """A kept target with no ``spine_adj`` entry is not applied — it is
    exactly the population phase B overwrites."""
    spine = _spine([100.0, 100.1, 100.2])          # keys 0, 1, 2
    kept = {1: 100.1, 2: 100.2, 7: 105.0}          # 7 is off-graph
    applied, off = _pins_on_frozen_graph(kept, spine, n=10)
    assert applied == {1: 100.1, 2: 100.2}
    assert off == {7: 105.0}
    # the split is a partition: nothing invented, nothing lost
    assert {**applied, **off} == kept
    assert not set(applied) & set(off)


def test_r4_out_of_range_indices_are_off_graph_too():
    """The freeze is ``{k for k in spine_adj if k < len(elev)}``: a
    spine-keyed node past the end of ``elev`` is frozen by neither
    clause, so it is off-graph on the same one bit."""
    spine = {0: [], 1: [], 9: []}
    applied, off = _pins_on_frozen_graph({1: 100.0, 9: 101.0}, spine, n=5)
    assert applied == {1: 100.0} and off == {9: 101.0}
    applied, off = _pins_on_frozen_graph({-1: 100.0}, {-1: []}, n=5)
    assert applied == {} and off == {-1: 100.0}


def test_r4_an_all_on_graph_airport_is_untouched():
    """HECA's pre-registered case: zero off-graph pins ⇒ the applied set
    IS the grip's kept set and nothing about the arm changes."""
    spine = _spine([100.0, 100.1, 100.2])
    kept = {0: 100.0, 1: 100.1, 2: 100.2}
    applied, off = _pins_on_frozen_graph(kept, spine, n=3)
    assert applied == kept and off == {}


def test_r4_ledger_stamps_disposition_and_the_pin_frozen_bit():
    """Three dispositions, one new bit.  ``pin_frozen`` is a pure function
    of the vertex, so a RELEASED row carries it too; the affected string
    ids come back for the summary."""
    spine = _spine([100.0, 100.1, 100.2])
    kept = {1: 100.1, 7: 105.0}
    applied, off = _pins_on_frozen_graph(kept, spine, n=10)
    rows = [{"vertex": 1, "string": 3, "grip": "offered"},
            {"vertex": 7, "string": 43, "grip": "offered"},
            {"vertex": 8, "string": 43, "grip": "offered"},   # released
            {"vertex": 2, "string": 3, "grip": "offered"}]    # released
    strings, n_off_targets = _stamp_pin_ledger(rows, applied, off,
                                               spine, n=10)
    assert [r["grip"] for r in rows] == ["kept", "off_graph",
                                         "released", "released"]
    assert [r["pin_frozen"] for r in rows] == [True, False, False, True]
    assert strings == [43]
    # TARGET-level: vertices 7 and 8 are both off the frozen graph, but
    # only 7 was kept — the two populations must not be conflated.
    assert n_off_targets == 2
    assert len(off) == 1


def test_r4_the_ledger_is_the_readers_only_kept_set():
    """Every offline reader selects ``grip == "kept"``.  After the stamp
    that set is the APPLIED set — so an off-graph target can never be
    counted as a held pin by any downstream census."""
    spine = _spine([100.0, 100.1])
    applied, off = _pins_on_frozen_graph({0: 100.0, 5: 100.0}, spine, n=6)
    rows = [{"vertex": 0, "string": 1, "grip": "offered"},
            {"vertex": 5, "string": 1, "grip": "offered"}]
    _stamp_pin_ledger(rows, applied, off, spine, n=6)
    assert {r["vertex"] for r in rows if r["grip"] == "kept"} == set(applied)
    assert 5 not in {r["vertex"] for r in rows if r["grip"] == "kept"}


def test_r4_the_drag_and_watch_populations_are_the_applied_pins():
    """G2 population rule: the mover watch set (Ruling 54 + probe A) and
    the pin-drag rows are built from the pin dict the solve is handed, and
    that dict is now ``applied``.  An off-graph target is not a drag
    population member and is not watched."""
    spine = _spine([100.0, 100.1, 100.2])
    applied, off = _pins_on_frozen_graph({1: 100.1, 7: 105.0}, spine, n=10)
    # Ruling 54 / probe A, verbatim: pins ∪ their spine neighbours.
    watch = set(applied)
    for v in applied:
        watch |= {j for (j, _b) in spine.get(v, ())}
    assert watch == {0, 1, 2}
    assert not watch & set(off)
    # the pin-drag delivery iterates the same dict, one row per applied pin
    assert sorted(applied) == [1]
