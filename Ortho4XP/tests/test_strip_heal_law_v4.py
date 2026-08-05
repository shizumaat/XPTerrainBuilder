"""Twins for the seam-continuity v4 healer law (spec
``docs/specs/seam-continuity-v4-spec.md`` §1-§3, gate
``O4_STRIP_HEAL_LAW``, default "0").

The v4 law is ONE interlocking rule with three halves:

* **§1 grade-aware guard** — the non-worsening guard's per-neighbour
  allowance IS the census pair predicate, so the healer stops refusing
  moves against neighbours its own law already calls lawful drape.  (The
  arithmetic twin lives with the law module,
  ``test_strip_seam_law_module``; here it is exercised end to end.)
* **§2 authority-split clusters** — membership splits at a disagreeing
  ANCHOR pair or a stacked-wall SITE, and the split pair is DEFERRED to
  the wall machinery with a named forensics record.  The healer may
  average only over a population that agrees pairwise under the census
  predicate.
* **§3 cluster-level guard** — one feasible interval for the whole
  sub-cluster, one rigid level for its movers, so mates cannot diverge.

Hermetic: stub shapes and a stub layout (no builds, no DEM, no network).
Anchors are minted the way production does: a strip dot laid ON a
weld-donor pavement exterior (``_welded``) is a ``weld`` anchor; the stub
layout is also anchored so ``x ≈ 0`` falls in the tile-seam band.

Gate discipline: every behavioural twin runs the SAME scene twice, gate
off and gate on, and asserts the gate-off arm is unchanged.  That is the
unit-level half of the pre-registered gate-off byte identity.
"""
from __future__ import annotations

import ast
import inspect
import math
import re
import textwrap

import pytest
from shapely.geometry import Polygon

from auto_patch import adjacent_ground
from auto_patch.adjacent_ground import (
    blend_cross_strip_seam_steps,
    report_strip_seam_joint_pickup,
    strip_wall_site_index,
)
from auto_patch.strip_seam_law import (
    STRIP_SEAM_TEAR_MIN_STEP_M,
    seam_guard_allowance_m,
    seam_pair_is_tear,
)

_JOINT_ROW = re.compile(r"\[strip-seam\] DEFERRED-JOINT ")
_UNPICKED_ROW = re.compile(r"\[strip-seam\] JOINT-UNPICKED ")
_GUARD_DECLINED_ROW = re.compile(r"\[strip-seam\] GUARD-DECLINED ")


class _StubShape:
    def __init__(self, ring, altitudes, role="graded_strip", ref=None):
        self.polygon = Polygon(ring)
        self.node_altitudes = list(altitudes) + [altitudes[0]]
        self.role = role
        self.ref = ref if ref is not None else "adjacent_ground"
        self.altitude = None
        self.altitude_high = None
        self.altitude_low = None


class _StubLayout:
    """Local metres anchored ON a tile meridian: x = 0 maps to an exact
    integer longitude, so small-|x| vertices sit in the tile-seam band and
    are anchors."""

    def __init__(self, shapes, icao="TEST"):
        self.shapes = shapes
        self.icao = icao
        self.canonical_points = None
        self._anchor_lat = -12.2
        self._anchor_lon = -77.0

    def m_to_ll(self, x, y):
        latitude = self._anchor_lat + y / 111320.0
        longitude = self._anchor_lon + x / (
            111320.0 * math.cos(math.radians(latitude)))
        return latitude, longitude


def _square(x0, y0, size=20.0):
    return [(x0, y0), (x0 + size, y0), (x0 + size, y0 + size),
            (x0, y0 + size)]


def _dot(cx, cy, size=0.1):
    """A tiny square centred on (cx, cy) — a controllable single site."""
    return _square(cx - size / 2.0, cy - size / 2.0, size)


def _welded(cx, cy, value, size=0.1):
    """A strip dot plus the DONOR pavement whose exterior it sits on, so
    every one of its four logical nodes is a ``weld`` ANCHOR.  This is
    the only realistic anchor class a stub can mint away from the tile
    meridian (the healer's own ``_anchor_reason``)."""
    ring = _dot(cx, cy, size)
    return [_StubShape(ring, [value] * 4),
            _StubShape(ring, [value] * 4, role="apron", ref="apron")]


def _run(shapes_factory, *, law, monkeypatch):
    if law:
        monkeypatch.setenv("O4_STRIP_HEAL_LAW", "1")
    else:
        monkeypatch.delenv("O4_STRIP_HEAL_LAW", raising=False)
    shapes = shapes_factory()
    layout = _StubLayout(shapes)
    moved = blend_cross_strip_seam_steps(layout.shapes, layout)
    return layout, shapes, moved


# ── §1 ────────────────────────────────────────────────────────────────
def _grade_aware_scene():
    """The CYXY inverted site, synthesised.

    A free cluster (two strips 2.8 m apart disagreeing by 1.8 m) with two
    EXCLUDED radius neighbours whose own values differ by 2.11 m — the
    exact shape the bounds-attribution verdict measured.  Under the bare
    step-floor allowance (±0.95 m) the two neighbour bounds INVERT and the
    guard leaves the step standing; under the census-identical allowance
    they do not, because both neighbours are 3-4 m away where the law's
    own grade conjunct permits far more.
    """
    return [
        # the tearing pair (free: far from the meridian, no donor)
        _StubShape(_dot(300.00, 300.00), [696.70] * 4),      # A
        _StubShape(_dot(297.99, 302.01), [694.90] * 4),      # B, 2.84 m
        # the two EXCLUDED neighbours, 2.11 m apart in level: each agrees
        # with the near member of the pair, so neither joins the cluster.
        _StubShape(_dot(303.21, 300.20), [696.91] * 4),      # N1, 3.21 m
        _StubShape(_dot(296.70, 303.00), [694.80] * 4),      # N2, 4.46 m
    ]


def test_the_bare_allowance_inverts_where_the_census_one_does_not():
    """The mechanism, as arithmetic on the measured numbers: the retired
    allowance inverts on a 2.11 m neighbour spread; the census-identical
    one does not at the distances actually involved."""
    flat = STRIP_SEAM_TEAR_MIN_STEP_M - 0.05
    hi_flat = 694.80 + flat
    lo_flat = 696.91 - flat
    assert lo_flat > hi_flat, "the retired bounds do NOT invert — scene wrong"
    hi_law = 694.80 + seam_guard_allowance_m(4.46)
    lo_law = 696.91 - seam_guard_allowance_m(3.21)
    assert lo_law <= hi_law, "the census-identical bounds still invert"


def test_the_grade_aware_guard_heals_the_inverted_site(monkeypatch, capsys):
    """END TO END: gate off the cluster is GUARD-DECLINED (bounds
    inverted) and nothing moves; gate on it moves, to ONE level, and the
    result is lawful against BOTH excluded neighbours."""
    _, off_shapes, off_moved = _run(_grade_aware_scene, law=False,
                                    monkeypatch=monkeypatch)
    off_out = capsys.readouterr().out
    assert off_moved == 0
    assert [ln for ln in off_out.splitlines()
            if _GUARD_DECLINED_ROW.search(ln)], off_out

    _, on_shapes, on_moved = _run(_grade_aware_scene, law=True,
                                  monkeypatch=monkeypatch)
    capsys.readouterr()
    assert on_moved > 0, "the v4 guard still refuses the measured site"

    levels = {round(float(a), 2)
              for sh in on_shapes[:2] for a in sh.node_altitudes}
    assert len(levels) == 1, f"movers diverged: {levels}"
    level = levels.pop()
    # Lawful against both excluded neighbours under the census predicate.
    for value, distance in ((696.91, 3.21), (694.80, 1.63)):
        assert not seam_pair_is_tear(abs(level - value), distance), (
            f"the healed level {level} tears against {value} at {distance} m")


# ── §2 ────────────────────────────────────────────────────────────────
def _anchor_split_scene():
    """Two WELD-ANCHORED strips 2.4 m apart holding a 5.58 m level
    change — the measured HECA bench pair (bounds-attribution verdict
    mechanism 2).  A third, FREE strip touches both, so union-find would
    otherwise pull all three into one cluster and hand the free node the
    unlawful middle."""
    return (_welded(300.00, 300.00, 100.89)          # anchor HIGH
            + _welded(302.50, 300.00, 95.31)            # anchor LOW, 2.4 m
            + [_StubShape(_dot(301.25, 302.00), [98.00] * 4)])   # free


def test_membership_splits_at_a_disagreeing_anchor_pair(monkeypatch, capsys):
    _, _off, _ = _run(_anchor_split_scene, law=False, monkeypatch=monkeypatch)
    off_out = capsys.readouterr().out
    assert not [ln for ln in off_out.splitlines() if _JOINT_ROW.search(ln)]

    layout, _on, _ = _run(_anchor_split_scene, law=True,
                          monkeypatch=monkeypatch)
    out = capsys.readouterr().out
    rows = [ln for ln in out.splitlines() if _JOINT_ROW.search(ln)]
    assert rows, out
    assert "kind=anchor_split" in " ".join(rows), rows
    joints = getattr(layout, "_strip_seam_deferred_joints", None)
    assert joints, "the joints must travel to the wall pass"
    split = [j for j in joints if j["kind"] == "anchor_split"]
    assert split, joints
    top = split[0]
    assert top["step_m"] == pytest.approx(5.58, abs=0.01)
    assert top["anchors"] == ("weld", "weld")
    assert top["allowance_m"] < top["step_m"]


def test_the_healer_never_averages_a_disagreeing_anchor_population(
        monkeypatch, capsys):
    """The §2 LAW, stated as a property: after the v4 pass, no strip
    value equals the mean of a disagreeing anchor pair (the unlawful
    middle the emit-consensus precedent forbids)."""
    _, shapes, _ = _run(_anchor_split_scene, law=True,
                        monkeypatch=monkeypatch)
    capsys.readouterr()
    middle = round((100.89 + 95.31) / 2.0, 2)
    for sh in shapes:
        for value in sh.node_altitudes:
            assert round(float(value), 2) != middle, (
                f"a node took the mean of two disagreeing anchors "
                f"({middle}) — the v4 §2 law forbids exactly this")


def test_the_shared_wall_site_predicate_is_evaluated_once(monkeypatch):
    """SINGLE PASS: the index is built once and cached on the layout, and
    ``emit_stacked_conflict_walls`` consumes the SAME object (source twin
    — a second derivation is what the ruling forbids)."""
    layout = _StubLayout(_anchor_split_scene())
    first = strip_wall_site_index(layout)
    assert strip_wall_site_index(layout) is first
    assert layout._strip_wall_site_index is first

    src = textwrap.dedent(inspect.getsource(
        adjacent_ground.emit_stacked_conflict_walls))
    tree = ast.parse(src).body[0]
    calls = [n for n in ast.walk(tree)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
             and n.func.id == "strip_wall_site_index"]
    assert len(calls) == 1, (
        "the wall pass must consult the ONE shared index, exactly once")
    assert "wall_index.claims" in src and "wall_index.edges" in src, (
        "the wall pass re-derives the authority claim table instead of "
        "consuming the shared index")


def test_the_pass_order_is_unchanged_by_the_law():
    """THE ORDERING RULING: wall-AWARE healer, NOT reordered wall passes.
    The reconcile unit's order in the pipeline is heal -> pinch-heal ->
    stacked walls, and the v4 gate must not appear in that ordering."""
    from auto_patch import pipeline
    src = inspect.getsource(pipeline.build_airport_pavement)
    order = [name for name in (
        "blend_cross_strip_seam_steps", "_heal_emitted_band_tears",
        "emit_stacked_conflict_walls") if name in src]
    assert order == ["blend_cross_strip_seam_steps",
                     "_heal_emitted_band_tears",
                     "emit_stacked_conflict_walls"]
    positions = [src.index(name) for name in order]
    assert positions == sorted(positions), (
        "the strip reconcile unit's internal order changed — the "
        "heal-before-retreat contract is measured law")
    assert "O4_STRIP_HEAL_LAW" not in src, (
        "the v4 gate must not reorder pipeline passes")


def test_an_unpicked_joint_is_loud(capsys):
    """§2 (iii): a joint the wall pass does NOT pick up is a loud record
    and a pre-registered zero — never silent tolerance."""
    layout = _StubLayout([])
    layout._strip_seam_deferred_joints = [{
        "kind": "anchor_split", "x": 10.0, "y": 20.0,
        "a": (9.0, 20.0, 100.0), "b": (11.0, 20.0, 105.0),
        "step_m": 5.0, "planar_m": 2.0, "allowance_m": 1.0,
        "anchors": ("weld", "weld")}]

    unpicked = report_strip_seam_joint_pickup(layout, [])
    out = capsys.readouterr().out
    assert unpicked == 1
    assert [ln for ln in out.splitlines() if _UNPICKED_ROW.search(ln)], out

    # A face ON the joint picks it up (and says so).
    wall = _StubShape(_square(9.5, 19.5, 1.0), [100.0] * 4,
                      role="retaining_wall")
    assert report_strip_seam_joint_pickup(layout, [wall]) == 0
    picked = capsys.readouterr().out
    assert "1 of 1 picked up" in picked, picked


# ── §3 ────────────────────────────────────────────────────────────────
def _divergent_mates_scene():
    """Two MATES 1.5 m apart in one cluster, each with its OWN excluded
    neighbour at a different level.  Per-node clamping sends them to
    different bounds — the measured 4.26 m cliff-between-mates class;
    the cluster-level interval makes it impossible."""
    return [
        _StubShape(_dot(400.00, 400.00), [100.0] * 4),        # mate A
        _StubShape(_dot(401.50, 400.00), [104.5] * 4),        # mate B
        _StubShape(_dot(397.20, 400.00), [99.0] * 4),         # A's nbr
        _StubShape(_dot(404.70, 400.00), [105.2] * 4),        # B's nbr
    ]


def test_the_cluster_moves_as_one_level(monkeypatch, capsys):
    """§3: no intra-cluster divergence, by construction."""
    _, shapes, _ = _run(_divergent_mates_scene, law=True,
                        monkeypatch=monkeypatch)
    capsys.readouterr()
    levels = {round(float(a), 2)
              for sh in shapes[:2] for a in sh.node_altitudes}
    assert len(levels) == 1, (
        f"the sub-cluster's movers took {len(levels)} different levels "
        f"({sorted(levels)}) — §3 requires ONE")


def test_an_empty_cluster_interval_carries_its_attribution(capsys):
    """§3: an empty interval after §1+§2 is a LOUD guarded record with
    the lawful-assignment check attached — feasibility-is-guaranteed
    means a survivor is attribution, never tolerance."""
    fn = ast.parse(textwrap.dedent(inspect.getsource(
        blend_cross_strip_seam_steps))).body[0]
    src = ast.unparse(fn)
    assert "cluster_blocked" in src
    assert "lawful" in src and "binding_lo" in src and "binding_hi" in src

    layout = _StubLayout([])
    row = {"kind": "cluster_blocked", "x": 1.0, "y": 2.0, "z": 10.0,
           "target_m": 12.0, "applied_m": None, "residual_m": 2.0,
           "bound_lo": 13.0, "bound_hi": 11.0, "nodes": 3,
           "lawful": "per_node_feasible",
           "binding_lo": (0.0, 0.0, 14.0, 2.0),
           "binding_hi": (5.0, 0.0, 10.0, 3.0)}
    adjacent_ground.report_strip_seam_declines([], layout, [row], [])
    out = capsys.readouterr().out
    assert "GUARD-DECLINED" in out
    assert "lawful=per_node_feasible" in out
    assert "binding_lo=" in out and "binding_hi=" in out


def test_the_gate_defaults_off_at_its_one_read_site():
    """ONE read site, default "0" — the per-site default disagreement
    blast reports as a hazard cannot happen with a single reader."""
    src = inspect.getsource(adjacent_ground)
    reads = re.findall(r'environ\.get\(\s*"O4_STRIP_HEAL_LAW"\s*,\s*"(\d)"',
                       src)
    assert reads == ["0"], reads
    callers = re.findall(r"_strip_heal_law_enabled\(\)", src)
    # one definition + the healer + the wall pass
    assert len(callers) >= 3, callers
