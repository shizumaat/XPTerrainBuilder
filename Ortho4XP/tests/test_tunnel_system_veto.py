"""Unit tests for the tunnel-system adjacent-road veto.

Plan item W4d (``docs/specs/below-grade-cutouts-and-deck-flush-plan.md``):
``_compute_tunnel_system_veto`` has never had a test anywhere, and the
only evidence for its behaviour is the LMML / CYUL airport builds — seven
minutes each.  W4b proposes to narrow the veto (emit ONE merged trench
where the crossing road is modelled instead of vetoing the whole system),
so the cheap evidence has to exist first.

The law under test (user 2026-06-12 LMML, 2026-07-04 CYUL): tunnel
candidates are grouped into SYSTEMS by geometric proximity, and the
adjacent-road verdict propagates across a whole system.  A clean
divided-highway underpass emits whole; an interchange tangle stays out
whole.  Half-emitting a tangle is what overlapped ramps onto vetoed roads
at LMML (baseline 0 -> 8 vertex + 25 mid-edge steps, measured).

Everything here is synthetic geometry in local metres — no pack, no DEM,
no build.
"""
import os
import sys

from shapely.geometry import LineString
from shapely.strtree import STRtree

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (os.path.join(ROOT, "src"), ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from auto_patch.bridges import (  # noqa: E402
    _compute_tunnel_system_veto,
    _tunnel_has_adjacent_road,
)

ADJACENT_DIST_M = 20.0
# Systems group at adjacent_road_dist_m * 1.5 (the union-find pass).
GROUPING_DIST_M = ADJACENT_DIST_M * 1.5
# A twin bore inside the grouping distance but OUTSIDE the adjacency
# distance of the crossing road: 26 < 30 groups it, 25 > 20 keeps it from
# being vetoed on its own account.  Both margins are asserted below, so a
# propagation test can never pass by direct adjacency instead.
TWIN_OFFSET_M = 26.0


def _tunnel_way(way_id, points, first_node):
    """One tunnel candidate: (way_id, node refs, tags) plus its nodes.

    Node ids are unique per way, so no two candidates share a node —
    exactly the twin-carriageway case the system grouping exists for
    (``twin bores never share nodes``).
    """
    node_ids = [first_node + index for index in range(len(points))]
    tags = {"highway": "primary", "tunnel": "yes"}
    return (way_id, node_ids, tags), dict(zip(node_ids, points))


def _road(way_id, points, first_node):
    """One foreign surface road for the adjacent-road index."""
    node_ids = {first_node + index for index in range(len(points))}
    return (LineString(points), node_ids, way_id)


def _veto(ways, nodes, roads, *, skip_if_adjacent_road=True):
    lines = list(roads)
    tree = STRtree([line for line, _nodes, _wid in lines]) if lines else None
    tunnel_all_nodes = {
        node for _wid, node_refs, _tags in ways for node in node_refs
    }
    return _compute_tunnel_system_veto(
        list(ways),
        dict(nodes),
        set(),
        ADJACENT_DIST_M,
        skip_if_adjacent_road,
        lines,
        tree,
        tunnel_all_nodes,
    )


class TestSystemVeto:
    def test_lone_tunnel_with_no_road_emits(self):
        """Nothing near it: the way is a candidate, verdict False."""
        way, nodes = _tunnel_way("T1", [(0.0, 0.0), (100.0, 0.0)], 1000)
        verdicts = _veto([way], nodes, [])
        assert verdicts == {"T1": False}

    def test_crossing_road_vetoes(self):
        """A foreign road crossing the bore vetoes it."""
        way, nodes = _tunnel_way("T1", [(0.0, 0.0), (100.0, 0.0)], 1000)
        crossing = _road("R1", [(50.0, -40.0), (50.0, 40.0)], 5000)
        verdicts = _veto([way], nodes, [crossing])
        assert verdicts == {"T1": True}

    def test_distant_road_does_not_veto(self):
        """A road further than adjacent_road_dist_m and not crossing is
        not adjacent."""
        way, nodes = _tunnel_way("T1", [(0.0, 0.0), (100.0, 0.0)], 1000)
        parallel = _road(
            "R1",
            [(0.0, ADJACENT_DIST_M * 3), (100.0, ADJACENT_DIST_M * 3)],
            5000,
        )
        verdicts = _veto([way], nodes, [parallel])
        assert verdicts == {"T1": False}

    def test_twin_bore_is_not_adjacent_on_its_own_account(self):
        """Guard on the two tests below: with T2 at TWIN_OFFSET_M the
        crossing road is 25 m away, outside the 20 m adjacency band, so
        T2's OWN verdict is False.  Without this the propagation test
        would pass by direct adjacency and prove nothing."""
        way_b, nodes_b = _tunnel_way(
            "T2", [(0.0, TWIN_OFFSET_M), (100.0, TWIN_OFFSET_M)], 2000
        )
        crossing = _road("R1", [(50.0, -40.0), (50.0, 1.0)], 5000)
        tree = STRtree([crossing[0]])
        assert not _tunnel_has_adjacent_road(
            "T2", way_b[1], set(way_b[1]), nodes_b,
            ADJACENT_DIST_M, [crossing], tree,
        )
        assert TWIN_OFFSET_M < GROUPING_DIST_M          # groups
        assert TWIN_OFFSET_M - 1.0 > ADJACENT_DIST_M    # not adjacent

    def test_veto_propagates_across_a_system(self):
        """THE LAW.  Two twin bores close enough to group; only ONE is
        crossed by a foreign road, and the other is provably outside the
        road's adjacency band (test above).  Both must be vetoed —
        vetoing just the crossed one is what half-emitted the LMML
        tangle."""
        way_a, nodes_a = _tunnel_way("T1", [(0.0, 0.0), (100.0, 0.0)], 1000)
        way_b, nodes_b = _tunnel_way(
            "T2", [(0.0, TWIN_OFFSET_M), (100.0, TWIN_OFFSET_M)], 2000
        )
        # Crosses T1 at (50, 0); nearest approach to T2 is 25 m.
        crossing = _road("R1", [(50.0, -40.0), (50.0, 1.0)], 5000)
        verdicts = _veto(
            [way_a, way_b], {**nodes_a, **nodes_b}, [crossing]
        )
        assert verdicts == {"T1": True, "T2": True}

    def test_separate_systems_keep_separate_verdicts(self):
        """The CYUL runway-24 case: a clean underpass far from the
        tangle emits whole.  IDENTICAL to the test above except that T2
        is moved past the grouping distance — so the pair isolates the
        grouping as the cause of T2's verdict."""
        far = GROUPING_DIST_M * 4.0
        way_a, nodes_a = _tunnel_way("T1", [(0.0, 0.0), (100.0, 0.0)], 1000)
        way_b, nodes_b = _tunnel_way("T2", [(0.0, far), (100.0, far)], 2000)
        crossing = _road("R1", [(50.0, -40.0), (50.0, 1.0)], 5000)
        verdicts = _veto(
            [way_a, way_b], {**nodes_a, **nodes_b}, [crossing]
        )
        assert verdicts == {"T1": True, "T2": False}

    def test_shared_node_road_is_the_tunnels_own_continuation(self):
        """A road sharing a node with the bore is its own surface
        continuation, not a foreign road — never a veto."""
        way, nodes = _tunnel_way("T1", [(0.0, 0.0), (100.0, 0.0)], 1000)
        continuation = LineString([(100.0, 0.0), (200.0, 0.0)])
        # Shares node 1001 (the bore's far end).
        shared = (continuation, {1001, 6000}, "R1")
        verdicts = _veto([way], nodes, [shared])
        assert verdicts == {"T1": False}

    def test_gate_off_yields_no_verdicts(self):
        """With skip_if_adjacent_road off the map is empty, and the
        caller's ``system_veto.get(tw_id, False)`` therefore emits
        everything."""
        way, nodes = _tunnel_way("T1", [(0.0, 0.0), (100.0, 0.0)], 1000)
        crossing = _road("R1", [(50.0, -40.0), (50.0, 40.0)], 5000)
        verdicts = _veto(
            [way], nodes, [crossing], skip_if_adjacent_road=False
        )
        assert verdicts == {}

    def test_non_tunnel_ways_are_not_candidates(self):
        """Only ``tunnel=yes`` on a tunnelable highway/railway is a
        candidate; ``building_passage`` is excluded from PORTAL
        emission (KPHL terminal service passages)."""
        way, nodes = _tunnel_way("T1", [(0.0, 0.0), (100.0, 0.0)], 1000)
        passage = (
            way[0] + "_p",
            [n + 500 for n in way[1]],
            {"highway": "primary", "tunnel": "building_passage"},
        )
        passage_nodes = {
            node + 500: point for node, point in nodes.items()
        }
        verdicts = _veto(
            [way, passage], {**nodes, **passage_nodes}, []
        )
        assert verdicts == {"T1": False}
