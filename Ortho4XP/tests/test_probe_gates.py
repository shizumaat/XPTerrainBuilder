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
* ``O4_PROBE_NO_ROAD_PAIR_LAW`` — the ROAD shapes' pair law, from the
  AIRSIDE pass of the partitioned projection, edges left in the graph
  (``one_solve._withhold_road_pair_law``).

EACH TEST COMES IN TWO ARMS: gate unset ⇒ INERT (asserted by object
identity or by a never-called sentinel, not by eyeballing a number), gate
set ⇒ the named withholding actually happens.  Patch-level byte-identity
with every gate unset is the build-side half of the same claim and is
recorded in the cycle-10 measurement (arm B body shas ``da78f97768ff`` /
``29ed04fcf7bb``, reproduced on this tip).

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
         "O4_PROBE_NO_ROAD_PAIR_LAW")


@pytest.fixture(autouse=True)
def _no_probe_env(monkeypatch):
    """Every test starts from the PRODUCTION environment: all three gates
    unset.  A gate leaking in from the shell would make the inertness arms
    pass for the wrong reason."""
    for g in GATES:
        monkeypatch.delenv(g, raising=False)


def test_the_gate_names_are_the_three_the_spec_names():
    """A registry, so a fourth undocumented probe gate cannot appear in
    this family without this test naming it."""
    import re
    seen = set()
    for rel in ("src/auto_patch/elevation_per_surface/route_profile/solve.py",
                "src/auto_patch/elevation_per_surface/route_profile/"
                "one_solve.py",
                "src/auto_patch/elevation_per_surface/building_feasibility.py"):
        seen |= set(re.findall(r"O4_PROBE_[A-Z_]+", (ROOT / rel).read_text()))
    assert seen == set(GATES)


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


# ── 3. O4_PROBE_NO_ROAD_PAIR_LAW ─────────────────────────────────────
#
# Two airside nodes WELDED to a road ring (so neither is a receiver, and
# the road's own pair law is enforced in the AIRSIDE pass), one slack
# apron pair over them, and one genuinely groundside pair.

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


def test_the_road_pair_law_binds_airside_with_the_gate_unset():
    """POSITIVE CONTROL, and the reason the arm is not inert by
    construction: with the gate unset the road's 0.1 m budget is enforced
    in the AIRSIDE pass and pulls both welded airside nodes together."""
    elev = _run_partitioned()
    assert abs(elev[0] - elev[1]) <= 0.1 + 1e-6
    assert elev[0] > 0.0 and elev[1] < 1.0, "neither airside node moved"


def test_the_knife_withholds_the_road_pair_law_from_the_airside_pass(
        monkeypatch):
    """Gate on: the road entry is enforced in the RECEIVER pass, where
    every non-receiver is frozen — so the airside nodes keep their
    values and only the apron's own slack law applies to them."""
    monkeypatch.setenv("O4_PROBE_NO_ROAD_PAIR_LAW", "1")
    elev = _run_partitioned()
    assert elev[0] == 0.0 and elev[1] == 1.0, (
        "airside moved under a road pair the knife withheld")


def test_the_knife_moves_the_law_rather_than_deleting_it():
    givers = _pair_law_case()[:2]
    receivers = _pair_law_case()[2:]
    keep, moved = OS._withhold_road_pair_law(givers, receivers)
    assert [sc["role"] for sc in keep] == ["apron"]
    assert [sc["role"] for sc in moved] == ["groundside_pavement",
                                            "service_junction"]
    assert moved[-1] is givers[1], "the entry was copied, not moved"


def test_the_knife_is_never_reached_with_the_gate_unset(monkeypatch):
    """INERTNESS BY SENTINEL: the un-gated projection must not so much as
    call the knife (a knife that runs and 'changes nothing' is the
    cycle-9 confound in miniature)."""
    def _boom(*_a, **_k):
        raise AssertionError("the road-pair-law knife ran with its gate "
                             "unset")
    monkeypatch.setattr(OS, "_withhold_road_pair_law", _boom)
    _run_partitioned()
