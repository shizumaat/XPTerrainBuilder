"""THE PROBE GATES — committed, default-OFF, and inert until asked.

Spec: ``docs/specs/cycle10-roadfeed-verdict-spec.md`` fix 2.

WHY THEY ARE COMMITTED.  The cycle-9 probe's knives
(``O4_PROBE_NO_SERVICE_EDGES`` / ``O4_PROBE_NO_MOUTHS``) lived in a dirty
working tree, in no commit and no stash.  They died with it, so cycle 10
had to re-derive the whole measurement — and the re-run then found the
original probe confounded three ways, one of which was that its knife had
been applied to a tree that ALREADY carried the cure (inert by
construction, which no one could see because the knife was unreadable).
A knife that cannot be read cannot be audited.  All three now land as
committed gates, each naming what it WITHHOLDS:

* ``O4_PROBE_NO_SERVICE_EDGES`` — the service/road route EDGES, from the
  ONE graph, for every consumer (``solve.adj_without_pairs``).
* ``O4_PROBE_NO_MOUTHS`` — every service-road MOUTH seat, so nothing
  groundside reaches a band from airside
  (``building_feasibility.service_mouths``).
* ``O4_PROBE_ROAD_PAIR_LAW_AIRSIDE`` — THE ONE INVERTED GATE.  Its arm
  (road pair law withheld from the AIRSIDE pass of the partitioned
  projection, edges left in the graph — ``one_solve._withhold_road_pair_law``)
  became the PRODUCTION DEFAULT in
  ``docs/specs/road-pair-receiver-only-spec.md``, so what the gate now
  restores is the OLD form: the road's pair law binding airside values.
  It replaces the measurement-era name ``O4_PROBE_NO_ROAD_PAIR_LAW``,
  which is retired — the registry test below is what stops the retired
  spelling from lingering as a gate that silently does nothing.

EACH TEST COMES IN TWO ARMS: gate unset ⇒ INERT (asserted by object
identity or by a never-called sentinel, not by eyeballing a number), gate
set ⇒ the named withholding actually happens.  For the inverted gate the
same discipline reads the other way round — gate unset ⇒ the withholding
DOES happen (it is the default) and the old form's code path is never
reached; gate set ⇒ the knife is not so much as called.  Patch-level
byte-identity is the build-side half of the same claim and is recorded in
the cycle-10 measurement: gates unset the two remaining gates are inert
(arm B body shas ``da78f97768ff`` / ``29ed04fcf7bb`` reproduced on
``c87070e``), and the receiver-only default reproduces the M1 KNIFE arm
exactly (``2a2e26f13423`` @10 000 m / ``f7de0c4855a2`` @−500).

Hand-built structures, no build, no network.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from auto_patch.elevation_per_surface import building_feasibility as BF  # noqa: E402
from auto_patch.elevation_per_surface.route_profile import (            # noqa: E402
    one_solve as OS, solve as SOLVE)

GATES = ("O4_PROBE_NO_SERVICE_EDGES", "O4_PROBE_NO_MOUTHS",
         "O4_PROBE_ROAD_PAIR_LAW_AIRSIDE")

#: Gate spellings that once existed and must NOT come back — a retired
#: gate name left in the source is a knife nobody can see (the cycle-9
#: confound), and one left in a shell is a knife that silently does
#: nothing now that its arm is the default.
RETIRED_GATES = ("O4_PROBE_NO_ROAD_PAIR_LAW",)


@pytest.fixture(autouse=True)
def _no_probe_env(monkeypatch):
    """Every test starts from the PRODUCTION environment: all three gates
    unset.  A gate leaking in from the shell would make the inertness arms
    pass for the wrong reason."""
    for g in GATES + RETIRED_GATES:
        monkeypatch.delenv(g, raising=False)


_GATE_SOURCES = (
    "src/auto_patch/elevation_per_surface/route_profile/solve.py",
    "src/auto_patch/elevation_per_surface/route_profile/one_solve.py",
    "src/auto_patch/elevation_per_surface/building_feasibility.py",
)


def _gate_spellings_in_source() -> set:
    import re
    seen = set()
    for rel in _GATE_SOURCES:
        seen |= set(re.findall(r"O4_PROBE_[A-Z_]+", (ROOT / rel).read_text()))
    return seen


def test_the_gate_names_are_the_three_the_spec_names():
    """A registry, so a fourth undocumented probe gate cannot appear in
    this family without this test naming it."""
    assert _gate_spellings_in_source() == set(GATES)


def test_no_retired_gate_spelling_survives_in_the_source():
    """``O4_PROBE_NO_ROAD_PAIR_LAW``'s arm IS the default now.  If the old
    spelling were still read anywhere, setting it would do nothing while
    reading like a knife — the exact failure mode the committed-gate rule
    exists to prevent."""
    assert not (_gate_spellings_in_source() & set(RETIRED_GATES))


# ── 1. O4_PROBE_NO_SERVICE_EDGES ─────────────────────────────────────

_ADJ = {0: [(1, 5.0), (2, 5.0)], 1: [(0, 5.0)], 2: [(0, 5.0)]}


def test_the_edge_filter_is_inert_by_identity_on_an_empty_pair_set():
    """Not "equal to" — the SAME OBJECT, which is what makes the un-gated
    production path provably untouched."""
    assert SOLVE.adj_without_pairs(_ADJ, set()) is _ADJ
    assert SOLVE.adj_without_pairs(_ADJ, None) is _ADJ


def test_the_edge_filter_drops_exactly_the_named_pairs():
    out = SOLVE.adj_without_pairs(_ADJ, {(0, 2)})
    assert out == {0: [(1, 5.0)], 1: [(0, 5.0)]}, (
        "the filter dropped the wrong edges, or left a node with an "
        "empty list where it should have been removed")


# ── 2. O4_PROBE_NO_MOUTHS ────────────────────────────────────────────

def _mouth_inputs():
    G = SimpleNamespace(service_spine_pairs={(1, 2)}, pos={})
    return G, {1: 5.0, 2: 6.0}, {1: 1.0, 2: 2.0}


def test_mouths_are_seated_with_the_gate_unset():
    """The positive control: the same call the gate suppresses does seat
    both endpoints of a service spine pair from the airside field."""
    G, ceiling, floor = _mouth_inputs()
    out = BF.service_mouths(object(), G, ceiling, floor)
    assert out == {1: (1.0, 5.0), 2: (2.0, 6.0)}


def test_the_mouth_gate_withholds_every_mouth(monkeypatch):
    monkeypatch.setenv("O4_PROBE_NO_MOUTHS", "1")
    G, ceiling, floor = _mouth_inputs()
    assert BF.service_mouths(object(), G, ceiling, floor) == {}


# ── 3. O4_PROBE_ROAD_PAIR_LAW_AIRSIDE (INVERTED — its arm is the
#       production default) ─────────────────────────────────────────────
#
# Two airside nodes WELDED to a road ring (so neither is a receiver, and
# the road's own pair law WOULD be enforced in the AIRSIDE pass), one
# slack apron pair over them, and one genuinely groundside pair.
#
# KNOWN ANSWER, by hand: the apron's own law over nodes 0,1 has a 2.0 m
# budget and |1.0 − 0.0| = 1.0 m, so airside alone leaves both nodes
# where they are.  The road pair's budget is 0.1 m.  Therefore any
# movement of nodes 0/1 is the ROAD's law authoring airside values, and
# no movement is the receiver-only default holding.  Nothing here is
# read off a solver; both outcomes are decidable on paper.

def _pair_law_case():
    apron = {"role": "apron", "nodes": [0, 1], "flat": False,
             "edges": [(0, 1, 2.0)]}                    # slack
    road = {"role": "service_junction", "nodes": [0, 1], "flat": False,
            "edges": [(0, 1, 0.1)]}                     # the binding law
    lot = {"role": "groundside_pavement", "nodes": [2, 3], "flat": False,
           "edges": [(2, 3, 5.0)]}
    return [apron, road, lot]


def _run_partitioned():
    elev = [0.0, 1.0, 0.0, 0.0]
    OS.feasibility_project_partitioned(
        elev, _pair_law_case(), set(),
        receiver_nodes={3}, n_nodes=4)
    return elev


def test_the_road_pair_law_is_receiver_pass_law_by_default():
    """THE DEFAULT ARM (this is the spec's whole change): with no env at
    all the road entry is enforced in the RECEIVER pass, where every
    non-receiver is frozen — so the welded airside nodes keep their
    values and only the apron's own slack law applies to them.  ZERO pull
    back, structurally (RULINGS 2026-08-06 ONE-graph, binding point 2)."""
    elev = _run_partitioned()
    assert elev[0] == 0.0 and elev[1] == 1.0, (
        "a groundside road's pair law moved an airside value — the "
        "pull-back the receiver-only default exists to forbid")


def test_the_probe_gate_restores_the_old_airside_form(monkeypatch):
    """POSITIVE CONTROL, and the reason the default is not inert by
    construction: with the gate SET the road's 0.1 m budget is enforced
    in the AIRSIDE pass again and pulls both welded airside nodes
    together — the M1 CTL arm, one env var away."""
    monkeypatch.setenv("O4_PROBE_ROAD_PAIR_LAW_AIRSIDE", "1")
    elev = _run_partitioned()
    assert abs(elev[0] - elev[1]) <= 0.1 + 1e-6
    assert elev[0] > 0.0 and elev[1] < 1.0, "neither airside node moved"


def test_the_retired_gate_spelling_no_longer_changes_anything(monkeypatch):
    """Setting the retired name must not resurrect the old form by
    accident — it is not a gate any more, and the surface it produces is
    the default's."""
    monkeypatch.setenv("O4_PROBE_NO_ROAD_PAIR_LAW", "1")
    elev = _run_partitioned()
    assert elev[0] == 0.0 and elev[1] == 1.0


def test_the_knife_moves_the_law_rather_than_deleting_it():
    givers = _pair_law_case()[:2]
    receivers = _pair_law_case()[2:]
    keep, moved = OS._withhold_road_pair_law(givers, receivers)
    assert [sc["role"] for sc in keep] == ["apron"]
    assert [sc["role"] for sc in moved] == ["groundside_pavement",
                                            "service_junction"]
    assert moved[-1] is givers[1], "the entry was copied, not moved"


def test_the_old_form_is_never_reached_by_default(monkeypatch):
    """INERTNESS BY SENTINEL, inverted with the gate: by default the
    partition MUST route through the withholding — 'it ran and changed
    nothing' is the cycle-9 confound in miniature, and here it would be
    the pull-back surviving unseen."""
    calls = []
    real = OS._withhold_road_pair_law
    monkeypatch.setattr(
        OS, "_withhold_road_pair_law",
        lambda g, r: (calls.append(1), real(g, r))[1])
    _run_partitioned()
    assert calls == [1], ("the default did not withhold the road pair law "
                          "from the airside pass")


def test_the_knife_is_never_reached_with_the_gate_set(monkeypatch):
    """The gate's own inertness claim: with
    ``O4_PROBE_ROAD_PAIR_LAW_AIRSIDE=1`` the projection must not so much
    as call the knife, so the gated arm is the pre-spec code path and not
    a re-derivation of it."""
    def _boom(*_a, **_k):
        raise AssertionError("the road-pair-law knife ran with "
                             "O4_PROBE_ROAD_PAIR_LAW_AIRSIDE=1")
    monkeypatch.setenv("O4_PROBE_ROAD_PAIR_LAW_AIRSIDE", "1")
    monkeypatch.setattr(OS, "_withhold_road_pair_law", _boom)
    _run_partitioned()
