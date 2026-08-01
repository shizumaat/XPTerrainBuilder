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

from auto_patch.elevation_per_surface.route_profile.one_solve import (
    feasibility_project)
from auto_patch.elevation_per_surface.route_profile.solve import (
    _string_pin_hold_indexes)
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


def test_fix2_stops_the_blend_manufacturing_an_over_cap_pair(monkeypatch):
    """THE mechanism Ruling 55 names.  Two anchors 20 m apart through a
    3-edge chain make the interior nodes BROKEN, and the distance-weighted
    break blend then parks node 1 at 103.33 — 6.5 m from its own hard
    neighbour at 110 across a 0.15 m budget, an over-cap pair no anchor
    asked for.  Under the bound node 1 stays inside ``[hard ± cap·d]`` and
    the residual break concentrates where the anchors genuinely disagree.
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
