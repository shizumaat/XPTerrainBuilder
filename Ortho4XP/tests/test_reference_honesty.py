"""Reference honesty — spec ``docs/specs/reference-honesty-and-terracing-
spec.md`` Track 1.

The defect these pin: every reference surface built AFTER
``one_solve.feasibility_project``'s quarantine blend was sampling that
blend.  A quarantined value is by definition one the law REFUSED to admit,
so anchoring on it drags the whole free interior toward it.

Covered here:

* ``solve._rod_string_values`` — the ROD-HELD STRING: the rod's Δ shape at
  the least-displacement level of the chain's LAW-TRUE members, split at
  branch vertices (memory ``rod-chains-split-at-branches``);
* ``apron_reference.apron_reference_values``'s anchor ladder — hard →
  un-quarantined ``elev`` → rod string → band-softened → refused, with the
  gate-off / no-context paths byte-identical to the legacy sampling;
* the RIGID BRANCH VERTEX placement in ``one_solve``'s chain-rigid blend
  (Track 1 step 3), including the ★ hard-neighbour clamp that guards the
  05C runway kink.
"""
import os

import pytest

from auto_patch.elevation_per_surface.apron_reference import (
    _band_clamp, _law_true_anchors)
from auto_patch.elevation_per_surface.route_profile.solve import (
    _BandView, _rod_string_values)
from auto_patch.elevation_per_surface.route_profile.one_solve import (
    feasibility_project)


# ── the rod-held string ──────────────────────────────────────────────────

def _rod(a, b, delta, eps=0.02):
    """One interval-rod slab ``z[a] − z[b] ∈ [Δ−ε, Δ+ε]``."""
    return (a, b, delta - eps, delta + eps)


def test_rod_string_keeps_the_shape_and_takes_the_law_true_level():
    # 0-1-2-3 corridor climbing 1 m per link.  The blend has bent nodes
    # 1 and 2 downward by metres; node 0 and node 3 are law-true.
    elev = [100.0, 90.0, 88.0, 103.0]
    rod = [_rod(1, 0, 1.0), _rod(2, 1, 1.0), _rod(3, 2, 1.0)]
    out = _rod_string_values(rod, elev, {1, 2}, 4)
    assert set(out) == {0, 1, 2, 3}
    # the SHAPE is the rod's: exactly 1 m per link, sag gone.
    for k in range(3):
        assert abs((out[k + 1] - out[k]) - 1.0) < 1e-9
    # the LEVEL comes from the law-true members only (0 and 3), whose
    # de-shaped values are 100.0 and 100.0 → the string reproduces them.
    assert abs(out[0] - 100.0) < 1e-9
    assert abs(out[3] - 103.0) < 1e-9


def test_rod_string_falls_back_to_all_members_when_none_are_law_true():
    """A wholly quarantined chain still gets the rod's SHAPE — the bend is
    removed — at the least-displacement level of what the pass has.  What
    it must never do is silently re-import one node's raw value for the
    rest of the chain."""
    elev = [100.0, 90.0, 88.0, 103.0]
    rod = [_rod(1, 0, 1.0), _rod(2, 1, 1.0), _rod(3, 2, 1.0)]
    out = _rod_string_values(rod, elev, {0, 1, 2, 3}, 4)
    for k in range(3):
        assert abs((out[k + 1] - out[k]) - 1.0) < 1e-9
    # least displacement: mean of the de-shaped values (100, 89, 86, 100).
    assert abs(out[0] - (100.0 + 89.0 + 86.0 + 100.0) / 4.0) < 1e-9


def test_rod_string_splits_at_branch_vertices_and_bridges_them():
    """★ memory ``rod-chains-split-at-branches``: corridors SHARE junction
    vertices, so a rod component is one blob and a single rigid translation
    of it degenerates.  Node 0 here has rod degree 3."""
    # branch 0 with three legs: 0-1-2, 0-3-4, 0-5-6.
    elev = [50.0] * 7
    rod = [_rod(1, 0, 1.0), _rod(2, 1, 1.0),
           _rod(3, 0, 2.0), _rod(4, 3, 2.0),
           _rod(5, 0, -1.0), _rod(6, 5, -1.0)]
    out = _rod_string_values(rod, elev, set(), 7)
    # every leg is placed, AND the junction is bridged onto the string
    # (Track 1 step 3's motivation: a junction left on its pointwise value
    # is the ~1.2 m corridor-mouth step).
    assert set(out) == set(range(7))
    for (leg, step) in (((1, 2), 1.0), ((3, 4), 2.0), ((5, 6), -1.0)):
        assert abs((out[leg[1]] - out[leg[0]]) - step) < 1e-9


def test_rod_string_is_empty_without_a_rod():
    assert _rod_string_values([], [1.0, 2.0], set(), 2) == {}
    assert _rod_string_values(None, [1.0, 2.0], set(), 2) == {}


# ── the band view / band clamp ───────────────────────────────────────────

def test_band_view_reads_the_node_band_list_without_materialising_a_dict():
    view = _BandView([None, (10.0, 20.0), None])
    assert view.get(0) is None
    assert view.get(1) == (10.0, 20.0)
    assert view.get(2) is None
    assert view.get(99) is None                 # out of range, not an error
    assert view.get(-1) is None


@pytest.mark.parametrize("band,value,expected", [
    ((10.0, 20.0), 5.0, 10.0),                  # blended below the floor
    ((10.0, 20.0), 25.0, 20.0),                 # above the ceiling
    ((10.0, 20.0), 15.0, 15.0),                 # already inside
    (None, 15.0, None),                         # no band → no soft value
    ((20.0, 10.0), 15.0, None),                 # inverted → no interval
    ((float("-inf"), 10.0), 15.0, None),        # non-finite → refuse
])
def test_band_clamp(band, value, expected):
    assert _band_clamp(value, band) == expected


def test_law_true_gate_default_on_and_switchable(monkeypatch):
    monkeypatch.delenv("O4_APRON_R_LAW_TRUE", raising=False)
    assert _law_true_anchors() is True
    monkeypatch.setenv("O4_APRON_R_LAW_TRUE", "0")
    assert _law_true_anchors() is False


# ── the anchor ladder ────────────────────────────────────────────────────

class _Poly:
    """Minimal shapely stand-in: an apron ring the reference builder can
    walk (it only needs ``exterior.coords`` and the empty flag)."""

    is_empty = False

    def __init__(self, ring):
        self.exterior = type("E", (), {"coords": list(ring) + [ring[0]]})()


class _Shape:
    def __init__(self, role, ring):
        self.role = role
        self.polygon = _Poly(ring)


class _CPS:
    def __init__(self):
        self._keys = {}

    def get_or_add(self, x, y):
        return self._keys.setdefault((round(x, 3), round(y, 3)),
                                     len(self._keys))


class _Layout:
    def __init__(self, shapes, cps):
        self.shapes = shapes
        self.canonical_points = cps


def _square_apron():
    """One 40 m square apron: 4 ring nodes, 0..3."""
    from auto_patch.layout import ROLE_APRON
    ring = [(0.0, 0.0), (40.0, 0.0), (40.0, 40.0), (0.0, 40.0)]
    cps = _CPS()
    b2i = {cps.get_or_add(x, y): k for k, (x, y) in enumerate(ring)}
    return _Layout([_Shape(ROLE_APRON, ring)], cps), b2i


def _reference(elev, *, hard, spine, **kwargs):
    from auto_patch.elevation_per_surface.apron_reference import (
        apron_reference_values)
    layout, b2i = _square_apron()
    stats = {}
    apron_reference_values(layout, b2i, elev, n=len(elev), hard_idx=hard,
                           spine_idx=spine, pad_ref={}, stats_out=stats,
                           **kwargs)
    return stats


def test_ladder_is_inert_without_a_quarantine_set():
    """No ``broken_idx`` ⇒ the legacy raw-``elev`` sampling, unchanged."""
    stats = _reference([100.0, 101.0, 102.0, 103.0],
                       hard={0}, spine={1, 2})
    assert stats["honest"] is False
    assert stats["anchors"] == 3
    assert stats.get("spine") == 2 and stats.get("hard") == 1


def test_ladder_is_inert_when_the_gate_is_off(monkeypatch):
    monkeypatch.setenv("O4_APRON_R_LAW_TRUE", "0")
    stats = _reference([100.0, 101.0, 102.0, 103.0],
                       hard={0}, spine={1, 2}, broken_idx={1, 2})
    assert stats["honest"] is False
    assert stats["anchors"] == 3            # the blended anchors survive


def test_quarantined_spine_anchor_takes_the_rod_string(monkeypatch):
    monkeypatch.delenv("O4_APRON_R_LAW_TRUE", raising=False)
    stats = _reference([100.0, 88.0, 89.0, 103.0],
                       hard={0}, spine={1, 2}, broken_idx={1, 2},
                       string_value={1: 101.0, 2: 102.0})
    assert stats["honest"] is True
    assert stats.get("spine_rod") == 2
    assert stats.get("spine") is None       # nothing sampled raw
    assert stats["anchors"] == 3


def test_quarantined_anchor_without_a_rod_is_band_softened(monkeypatch):
    monkeypatch.delenv("O4_APRON_R_LAW_TRUE", raising=False)
    stats = _reference([100.0, 88.0, 89.0, 103.0],
                       hard={0}, spine={1, 2}, broken_idx={1, 2},
                       band_of={1: (100.5, 105.0), 2: (100.5, 105.0)})
    assert stats.get("spine_band") == 2
    assert stats["anchors"] == 3


def test_quarantined_anchor_with_nothing_law_true_is_refused(monkeypatch):
    monkeypatch.delenv("O4_APRON_R_LAW_TRUE", raising=False)
    stats = _reference([100.0, 88.0, 89.0, 103.0],
                       hard={0}, spine={1, 2}, broken_idx={1, 2})
    assert stats.get("refused_spine") == 2
    assert stats["anchors"] == 1            # only the hard hold survives
    assert stats["free"] == 3


def test_hard_anchors_are_never_refused(monkeypatch):
    """A hard hold is the pass's own truth (priority 1).  ``pre_broken`` at
    the final projection is a CARRIED set and can legitimately name a node
    this pass holds — refusing it would strip a real boundary condition."""
    monkeypatch.delenv("O4_APRON_R_LAW_TRUE", raising=False)
    stats = _reference([100.0, 101.0, 102.0, 103.0],
                       hard={0, 1}, spine={2}, broken_idx={0, 1, 2})
    assert stats.get("hard") == 2
    assert stats.get("refused_spine") == 1


# ── rigid branch vertices (Track 1 step 3) ───────────────────────────────

def _branch_case(env_value):
    """Three rod chains meeting at a junction, every node quarantined by a
    pair of contradictory hard anchors, so the whole rod graph lands in the
    broken branch.  Node 3 is the junction (rod degree 3)."""
    # nodes: 0,1 = hard contradiction pair;  2..8 = fabric.
    # rod legs: 3-4-5, 3-6-7, 3-8  (3 has degree 3 → branch vertex).
    n = 9
    elev = [200.0, 100.0] + [150.0] * 7
    # A tight symmetric web between the two contradictory anchors makes
    # every fabric node broken (floor from 0, ceiling from 1).
    edges = []
    for i in range(2, n):
        edges.append((0, i, 0.5))
        edges.append((1, i, 0.5))
    rod_edges = [(4, 3, 0.98, 1.02), (5, 4, 0.98, 1.02),
                 (6, 3, 1.98, 2.02), (7, 6, 1.98, 2.02),
                 (8, 3, -1.02, -0.98)]
    constraints = [{"edges": edges},
                   {"edges": rod_edges, "envelope_skip": True}]
    old = os.environ.get("O4_BRANCH_RIGID_BLEND")
    os.environ["O4_BRANCH_RIGID_BLEND"] = env_value
    try:
        broken = set()
        feasibility_project(elev, constraints, {0, 1}, max_iters=200,
                            broken_out=broken)
    finally:
        if old is None:
            os.environ.pop("O4_BRANCH_RIGID_BLEND", None)
        else:
            os.environ["O4_BRANCH_RIGID_BLEND"] = old
    return elev, broken


def _worst_mouth_step(elev):
    """The largest rod-slab violation AT THE JUNCTION — the ~1.2 m
    corridor-mouth step memory ``rod-chains-split-at-branches`` names as
    the chain-rigid pass's known residual."""
    return max(abs((elev[leg] - elev[3]) - delta)
               for (leg, delta) in ((4, 1.0), (6, 2.0), (8, -1.0)))


def test_branch_vertex_lands_on_the_string_when_the_gate_is_on():
    elev, broken = _branch_case("1")
    assert {3, 4, 5, 6, 7, 8} <= broken, broken
    # The junction takes the LEAST-DISPLACEMENT point among the levels its
    # rod slabs to the (now rigidly placed) legs imply.  It cannot satisfy
    # three mutually disagreeing legs exactly — that residual is honest —
    # but it is on the string, not on the pointwise blend.
    implied = [elev[4] - 1.0, elev[6] - 2.0, elev[8] + 1.0]
    assert elev[3] == pytest.approx(sum(implied) / len(implied))


def test_branch_rigid_shrinks_the_mouth_step_and_leaves_the_chains_alone():
    off, _ = _branch_case("0")
    on, _ = _branch_case("1")
    for leg in (4, 5, 6, 7):
        assert off[leg] == pytest.approx(on[leg]), \
            "the CHAINS are placed identically — only the junction moves"
    assert _worst_mouth_step(on) < _worst_mouth_step(off)


def test_branch_rigid_gate_off_is_the_landed_pointwise_behaviour():
    """Gate-off must leave the junction on its blend value exactly (the
    byte-identity arm of the gate)."""
    off, _ = _branch_case("0")
    # the pointwise blend of a node midway between two contradictory
    # anchors 0.5 m-reachable from each: hi + (lo − hi)·t.
    assert off[3] == pytest.approx(off[2]), \
        "an unstrung broken node and the junction share the blend"
