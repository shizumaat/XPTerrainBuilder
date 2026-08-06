"""Cycle-7 fix 3 twin — the certificate's route follows the REACH LAW.

OWNER RULING 2026-08-06 ("Certificate routes follow the reach law"),
verbatim: *"certificate routes follow the same law as reach —
centerlines and lawful surfaces, never through pad interiors, no
zero-budget hops. The route in the KML is invalid."*

THE KNOWN ANSWER (RULINGS 2026-08-06 "Instrument truth is law", item 1 —
a calibration case whose answer is known independently): the owner
reviewed a KML of ``_stall_envelope_gap``'s own specimen route at HECA
(anchors 2864 ↔ 7478, 33.377 m priced over 149 edges) and adjudicated it
INVALID — it crossed a 40-node pad group as a 586 m hop at budget 0, 24
of its 149 edges were priced under 0.9 % of their own chord, and 29 of
its 150 nodes lay more than 100 m from any taxi centerline.  On the
shipped HECA dump the two rules below move the verdict
13,370 → 1,226 infeasible nodes and the max gap 19.195118 → 1.107253 m,
with the pad rule owning ~92 % of it (13 zero-budget edges exist in the
whole 165,043-edge cap graph, so rule 1 is nearly inert alone).

These twins are the same arithmetic in six nodes.
"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

np = pytest.importorskip("numpy")
pytest.importorskip("scipy")

from auto_patch.elevation_per_surface.route_profile import (  # noqa: E402
    one_solve as OS)


def _system(pad_budget=0.1, shortcut=True):
    """Two pinned anchors, a LAWFUL route that PRICES ENOUGH, and a pad
    shortcut that does not.

    Nodes 0 and 5 are pinned 10 m apart.  The lawful way round
    (0-1-2-3-5) prices 4 x 3.0 = 12.0 m of budget — the demand is met and
    the system is FEASIBLE.  Node 4 is a flat-group REPRESENTATIVE
    touching both ends: because a whole pad collapses to ONE node, walking
    into it and out again prices only two short frontage chords, and the
    envelope's Dijkstra takes the MINIMUM-budget path — so the pad route
    (0.2 m) wins and the same feasible system is reported INFEASIBLE by
    9.8 m.  That is the direction the HECA measurement shows: the invalid
    route OVER-states infeasibility (13,370 -> 1,226 once it is barred).
    """
    edges = [(0, 1, 3.0), (1, 2, 3.0), (2, 3, 3.0), (3, 5, 3.0)]
    if shortcut:
        edges += [(0, 4, pad_budget), (4, 5, pad_budget)]
    ei = np.array([e[0] for e in edges], dtype=np.intp)
    ej = np.array([e[1] for e in edges], dtype=np.intp)
    eb = np.array([e[2] for e in edges], dtype=np.float64)
    im = np.zeros(len(edges), dtype=bool)
    # every node free except 0 and 5 (weight 0 on every incident edge)
    wi = np.array([0.0 if e[0] in (0, 5) else 0.5 for e in edges])
    wj = np.array([0.0 if e[1] in (0, 5) else 0.5 for e in edges])
    z = np.array([0.0, 0.0, 0.0, 0.0, 0.0, 10.0])
    return ei, ej, eb, im, wi, wj, z, 6


def _gap(flat_group_reps, pad_budget=0.1, shortcut=True):
    ei, ej, eb, im, wi, wj, z, n = _system(pad_budget=pad_budget,
                                           shortcut=shortcut)
    return OS._stall_envelope_gap(np, ei, ej, eb, im, wi, wj, z, n,
                                  [(0, 5)], flat_group_reps=flat_group_reps)


def test_a_route_through_a_pad_interior_MINTS_infeasibility():
    """THE DEFECT, stated as a test.  A feasible system (12.0 m of lawful
    budget against a 10 m demand) is reported INFEASIBLE by 9.8 m because
    the cheapest path in the graph runs through a building."""
    v = _gap(flat_group_reps=None)
    assert v["infeasible"] > 0
    assert v["max_gap"] == pytest.approx(10.0 - 0.2, abs=1e-6)


def test_the_pad_may_not_be_TRANSITED():
    """A flat group is a SEATED SURFACE, not a free edge.

    Barred, the only lawful route between the two anchors is the way
    round — 12.0 m of budget against a 10 m demand — so BOTH ANCHORS
    read feasible, which they always were.  What survives is node 4
    itself: a pad whose two frontage chords (0.1 m each) cannot both
    reach anchors 10 m apart is genuinely over-constrained, and that is
    the split-level sectioned-seat law's finding, not a route artefact.
    Telling those two apart is exactly what the reprice buys.
    """
    v = _gap(flat_group_reps={4})
    assert v["gap"][0] <= 0.0 and v["gap"][5] <= 0.0, "the anchors are free"
    assert int((v["gap"] > 1e-9).sum()) == 1
    assert v["gap"][4] > 0.0, "the pad's OWN frontage contradiction stands"


def test_the_pad_is_still_REACHED_and_still_bounded():
    """"Never transited" is not "deleted": the pad keeps its own envelope
    value, because its frontage chord still bounds it."""
    v = _gap(flat_group_reps={4})
    assert np.isfinite(v["gap"][4]), "the pad must still be reachable"


def test_a_zero_budget_edge_is_not_a_free_hop():
    """A rigid coupling is not a road.  At budget 0.1 the pad route is the
    cheapest path and mints a 9.8 m contradiction; at budget 0 the edges
    are dropped outright, the lawful 12.0 m route is the only one, and the
    system reads feasible — which it is.  Rule 1 needs no pad set: a
    zero-budget hop is never a route, wherever it sits."""
    assert _gap(flat_group_reps=None, pad_budget=0.1)["max_gap"] == \
        pytest.approx(9.8, abs=1e-6)
    assert _gap(flat_group_reps=None, pad_budget=0.0)["max_gap"] == \
        pytest.approx(0.0)


def test_the_rules_only_ever_ADD_lawful_budget():
    """Both rules REMOVE routes from the MINIMUM-path search, so the
    priced budget can only rise and the verdict can only get LESS
    infeasible — never more.  That is what keeps a positive verdict
    conservative-and-certain."""
    without = _gap(flat_group_reps=None)
    with_ = _gap(flat_group_reps={4})
    assert with_["max_gap"] <= without["max_gap"]
    assert with_["infeasible"] <= without["infeasible"]


def test_no_pad_set_reproduces_the_pre_ruling_graph():
    ei, ej, eb, im, wi, wj, z, n = _system(shortcut=False)
    a = OS._stall_envelope_gap(np, ei, ej, eb, im, wi, wj, z, n, [(0, 5)])
    b = OS._stall_envelope_gap(np, ei, ej, eb, im, wi, wj, z, n, [(0, 5)],
                               flat_group_reps=set())
    assert a["infeasible"] == b["infeasible"]
    assert a["max_gap"] == pytest.approx(b["max_gap"])
