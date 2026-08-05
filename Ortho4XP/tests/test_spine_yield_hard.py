"""Headless tests for the spine-freeze round.

Spec: ``docs/specs/spine-freeze-round-spec.md``.  STANDING LAW — the
``O4_SPINE_YIELD_HARD`` gate was deleted in the build-complete-then-debug
round.

The phase-A spine certifies on its own 1.5-4.8 k-edge graph and was then
frozen ``base_hard`` into 64-272 k-edge projections whose law its values
violate — 84-85 % of ALL violated anchors at HEAZ and HECA
(``carrier_attrib/DOSSIER.md`` §9).  Those nodes now enter the downstream
projections as YIELD-HARD members: simply NOT in ``hard``, so they settle
wherever the full graph's law admits.  (Until the kill they were
additionally held by a §7 reference rod at the phase-A value; that
channel is retired — a phase-A ESTIMATE is not an authority the full-graph
law has to be talked out of.)  Runway/CIFP values, runway joins, seats and
seam pins stay ``base_hard`` — the preserved set, enumerated and tested
here.

No network, no X-Plane install, no DEM: pure arithmetic + ``monkeypatch``.
"""
from __future__ import annotations

import pytest

from auto_patch.elevation_per_surface.route_profile.one_solve import (
    feasibility_project)
from auto_patch.elevation_per_surface.route_profile.solve import (
    _spine_yield_binding, _spine_yield_membership,
    _spine_yield_movement_report)


@pytest.fixture(autouse=True)
def _pinned_env(monkeypatch):
    """Pin every knob these tests read so a stray shell export cannot
    move an assertion."""
    monkeypatch.delenv("O4_HARD_NEIGHBOUR_BOUND", raising=False)
    monkeypatch.delenv("O4_BREAK_FORENSICS", raising=False)
    monkeypatch.delenv("O4_STEP_DEBUG", raising=False)


# ══════════════════════════════════════════════════════════════════════
# the gate is GONE
# ══════════════════════════════════════════════════════════════════════
def test_the_gate_no_longer_exists():
    """The membership is standing law: no env read may resurrect the
    freeze arm."""
    import auto_patch.elevation_per_surface.route_profile.solve as SV
    assert not hasattr(SV, "spine_yield_hard_enabled")
    src = open(SV.__file__).read()
    assert 'environ.get("O4_SPINE_YIELD_HARD"' not in src


# ══════════════════════════════════════════════════════════════════════
# §1 — YIELD-VS-PRESERVED MEMBERSHIP
# ══════════════════════════════════════════════════════════════════════
def test_membership_is_a_partition_of_the_frozen_set():
    """Every in-range frozen node lands in exactly one of the two sets —
    nothing may fall out of both (the silent-loss shape)."""
    frozen = {0, 1, 2, 3, 4, 5}
    preserved, yielded = _spine_yield_membership(
        frozen, 6, truth_hard={0, 1}, runway_nodes={2},
        building_seats={3: 12.0}, runway_anchor={1: 9.0}, seam_pins={4})
    assert yielded == {5}
    assert (frozen & preserved) | yielded == frozen
    assert not (yielded & preserved)


@pytest.mark.parametrize("field", ["truth_hard", "runway_nodes",
                                   "building_seats", "runway_anchor",
                                   "seam_pins"])
def test_each_preserved_class_protects_its_node(field):
    """The preserved set is ENUMERATED, so each of the five named classes
    is individually load-bearing: drop one and its node yields."""
    kw = dict(truth_hard=set(), runway_nodes=set(), building_seats={},
              runway_anchor={}, seam_pins=set())
    kw[field] = {7: 1.0} if field in ("building_seats",
                                      "runway_anchor") else {7}
    preserved, yielded = _spine_yield_membership({7, 8}, 9, **kw)
    assert 7 in preserved and 7 not in yielded
    assert yielded == {8}
    # and without that class the very same node yields
    kw[field] = {} if field in ("building_seats", "runway_anchor") else set()
    _p2, y2 = _spine_yield_membership({7, 8}, 9, **kw)
    assert y2 == {7, 8}


def test_membership_drops_out_of_range_indices():
    """``frozen`` is keyed in the spine's own space; a node past the
    projection's node list is not a member of anything."""
    preserved, yielded = _spine_yield_membership(
        {1, 99}, 3, truth_hard=set(), runway_nodes=set(),
        building_seats={}, runway_anchor={}, seam_pins={99})
    assert yielded == {1}
    assert 99 not in preserved and 99 not in yielded


def test_membership_empty_when_nothing_is_frozen():
    preserved, yielded = _spine_yield_membership(
        (), 4, truth_hard={0}, runway_nodes=set(), building_seats={},
        runway_anchor={}, seam_pins=set())
    assert yielded == set() and preserved == {0}


# ══════════════════════════════════════════════════════════════════════
# §2 — A SPINE VALUE THAT VIOLATES THE FULL GRAPH'S LAW
# ══════════════════════════════════════════════════════════════════════
# Synthetic twin of DOSSIER §1, the HEAZ carrier: node 0 is the runway
# 18/36 seam (1512) at 77.740, hard; node 1 is a free junction (2725);
# node 2 is the phase-A frozen spine node (2631) at 74.881.  Budgets are
# the measured ones — 0.8549 m over 57.7 m and 0.3075 m over 21 m — so
# the runway's law permits node 2 no lower than 77.740 − 1.1624 = 76.578,
# and the freeze put it 1.697 m below that with 11 m of its OWN reach band
# still above it.
_RWY_Z = 77.740
_SPINE_Z = 74.881
_SC = [{"edges": [(0, 1, 0.8549), (1, 2, 0.3075)]}]
_LAWFUL_MIN = _RWY_Z - (0.8549 + 0.3075)


def _worst_excess(elev):
    return max(abs(elev[a] - elev[b]) - budget
               for (a, b, budget) in _SC[0]["edges"])


def test_frozen_spine_ships_its_unlawful_value_today():
    """The base case this round exists to fix: frozen ``base_hard``, the
    node cannot move, and the residual is the anchor contradiction."""
    elev = [_RWY_Z, 76.037, _SPINE_Z]
    feasibility_project(elev, _SC, {0, 2})
    assert elev[2] == _SPINE_Z, "a hard node never moves"
    assert elev[2] < _LAWFUL_MIN - 1.6
    assert _worst_excess(elev) > 1.6


def test_yield_hard_membership_moves_the_spine_toward_its_lawful_value():
    """YIELD-HARD: out of ``hard``, and that is the whole mechanism.  The
    node yields to the law it violated and the worst residual on the
    chain collapses."""
    hard_arm = [_RWY_Z, 76.037, _SPINE_Z]
    feasibility_project(hard_arm, _SC, {0, 2})
    yield_arm = [_RWY_Z, 76.037, _SPINE_Z]
    feasibility_project(yield_arm, _SC, {0})
    assert yield_arm[2] > _SPINE_Z + 1.4, yield_arm
    assert _worst_excess(hard_arm) - _worst_excess(yield_arm) > 1.0
    # the preserved runway anchor is untouched in BOTH arms, bit for bit
    assert hard_arm[0] == yield_arm[0] == _RWY_Z


def test_a_lawful_spine_value_is_left_where_it_is():
    """A frozen value the full graph already admits is not moved: the
    projection only corrects VIOLATED pairs, so a lawful entry state
    comes back untouched."""
    lawful = _RWY_Z - 1.0                     # inside the chain's budget
    elev = [_RWY_Z, _RWY_Z - 0.5, lawful]
    feasibility_project(elev, _SC, {0})
    assert elev[2] == lawful
    # RAW LAW (standing raw-law sweeps, docs/RULINGS.md 2026-08-05): the
    # retired emit margin used to leave 0.01 m of slack that hid IEEE
    # round-off; against the raw budget a value sitting exactly AT cap
    # reads a few ULPs over.  The floor is float noise, not a law breach
    # (emit quantizes at 0.01 m — twelve orders of magnitude above it).
    assert _worst_excess(elev) <= 1e-12


def test_the_yield_is_a_membership_not_a_value_channel():
    """The ONLY difference between preserved and yielded is set
    membership in ``hard`` — there is no second argument that carries a
    phase-A value into the projection."""
    import inspect
    params = inspect.signature(feasibility_project).parameters
    assert "node_refs" not in params and "group_refs" not in params


# ══════════════════════════════════════════════════════════════════════
# §3 — THE MOVEMENT REPORT
# ══════════════════════════════════════════════════════════════════════
def test_binding_constraint_is_the_least_slack_edge():
    elev = [10.0, 10.5, 12.0]
    adj = {1: [(0, 1.0), (2, 1.0)]}
    j, budget, dz, slack, kind = _spine_yield_binding(1, elev, adj)
    assert j == 2 and kind == "symmetric"
    assert budget == 1.0
    assert dz == pytest.approx(-1.5)
    assert slack == pytest.approx(-0.5)


def test_binding_constraint_reads_interval_edges_too():
    """Signed interval (slab) edges are carried verbatim, not collapsed
    to a symmetric budget."""
    elev = [10.0, 12.0]
    adj = {1: [(0, (0.5, 1.5))]}
    j, budget, dz, slack, kind = _spine_yield_binding(1, elev, adj)
    assert (j, kind, budget) == (0, "interval", (0.5, 1.5))
    assert dz == pytest.approx(2.0)
    assert slack == pytest.approx(-0.5)      # 1.5 − 2.0, the tighter side


def test_binding_constraint_reports_a_node_with_no_law_edge():
    """A node that moved with nothing binding it is itself a finding —
    reported as ``kind="none"``, never dropped."""
    j, budget, dz, slack, kind = _spine_yield_binding(3, [0.0] * 4, {})
    assert j is None and kind == "none" and budget is None


def test_movement_report_rows_carry_the_spec_columns(capsys):
    """node, phase-A value, shipped value, and the binding constraint."""
    phase_a = {2: _SPINE_Z, 3: 50.0}
    elev = [_RWY_Z, 76.60946874624, 76.31196874624, 50.0]
    rows = _spine_yield_movement_report(
        "TEST", phase_a, elev, 4,
        [{"edges": [(0, 1, 0.8549), (1, 2, 0.3075)]}],
        preserved={0}, yield_idx={2, 3})
    # node 3 never moved ⇒ no row (the report is of MOVEMENTS)
    assert [r["node"] for r in rows] == [2]
    row = rows[0]
    assert row["z_phase_a"] == pytest.approx(_SPINE_Z)
    assert row["z_shipped"] == pytest.approx(76.31196874624)
    assert row["delta_m"] == pytest.approx(1.43096874624)
    assert row["binding_neighbour"] == 1
    assert row["binding_neighbour_class"] == "free"
    assert row["binding_budget"] == pytest.approx(0.3075)
    assert row["binding_slack_m"] == pytest.approx(0.3075 - 0.2975)
    out = capsys.readouterr().out
    assert "[spine-yield] TEST" in out and "1 moved" in out


def test_movement_report_classifies_the_binding_neighbour():
    """The binding neighbour is named by CLASS — which authority moved
    the value is the whole point of the report."""
    phase_a = {1: 10.0, 2: 10.0}
    elev = [12.0, 11.5, 11.2]
    rows = _spine_yield_movement_report(
        "TEST", phase_a, elev, 3,
        [{"edges": [(0, 1, 0.5), (1, 2, 0.5)]}],
        preserved={0}, yield_idx={1, 2})
    by_node = {r["node"]: r for r in rows}
    assert by_node[1]["binding_neighbour_class"] == "preserved_anchor"
    assert by_node[2]["binding_neighbour_class"] == "spine_yield"


def test_movement_report_writes_the_forensics_csv(tmp_path, monkeypatch):
    """It rides the EXISTING forensics channel (``O4_BREAK_FORENSICS``),
    with a ``.spine_yield.`` infix so it cannot collide with the break
    report written to the same path."""
    path = tmp_path / "forensics.csv"
    monkeypatch.setenv("O4_BREAK_FORENSICS", str(path))
    _spine_yield_movement_report(
        "TEST", {2: _SPINE_Z}, [_RWY_Z, 76.6, 76.3], 3,
        [{"edges": [(0, 1, 0.8549), (1, 2, 0.3075)]}],
        preserved={0}, yield_idx={2},
        latlon_of=lambda i: (30.0 + i, 31.0 + i))
    out = tmp_path / "forensics.spine_yield.csv"
    assert out.exists()
    lines = out.read_text().strip().splitlines()
    assert lines[0].startswith("node,lat,lon,z_phase_a,z_shipped,delta_m,")
    assert lines[1].startswith("2,32.0000000,33.0000000,74.8810,76.3000,")


def test_movement_report_is_write_only(monkeypatch):
    """It never writes ``elev`` — the instrument may not move the
    surface it measures."""
    elev = [_RWY_Z, 76.6, 76.3]
    before = list(elev)
    _spine_yield_movement_report(
        "TEST", {2: _SPINE_Z}, elev, 3,
        [{"edges": [(0, 1, 0.8549), (1, 2, 0.3075)]}],
        preserved={0}, yield_idx={2})
    assert elev == before
