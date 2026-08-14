"""THE STAGE TAG — rail twins (staged-solve round, lane S1b).

The law under test (spec ``docs/specs/staged-solve-round-spec.md``, S1b +
"The law this round lands"):

* stage membership is a FIRST-CLASS TAG stamped where each constraint
  entry is MINTED — never re-derived from ``sc["role"]``, which is
  structurally blind to the §10 rod interval and to the unified-graph
  entry (couplings 3, 4, 6 of ``tmp/s1_attribution.md``);
* EVERY entry reaching the solve or any projection carries it — an
  untagged entry is a CONSTRUCTOR DEFECT and fails loudly, the same
  never-silent posture as the axes sidecar;
* stage A solves with airside-tagged entries AND airside variables only;
* stage B solves with stage-A values immutable.

Both directions are covered: the tag must be present and correct where
the constructors mint it, and the partition must REFUSE where it is not.
"""

import pytest

from auto_patch import solve_stage as ST
from auto_patch.layout import (GROUNDSIDE_ROLES, ROLE_APRON, ROLE_JUNCTION,
                                ROLE_RUNWAY, ROLE_BUILDING,
                                ROLE_GRADED_STRIP, ROLE_SERVICE_ROAD,
                                ROLE_SERVICE_JUNCTION,
                                ROLE_GROUNDSIDE_PAVEMENT)


class _Shape:
    def __init__(self, role):
        self.role = role


# ── the partition itself ──────────────────────────────────────────────

def test_every_groundside_role_is_stage_b_and_nothing_else_is():
    """The partition IS ``layout.GROUNDSIDE_ROLES``, read from the one
    authority — not a second literal list that can drift from it."""
    for role in GROUNDSIDE_ROLES:
        assert ST.stage_of_role(role) == ST.STAGE_B, role
    for role in (ROLE_APRON, ROLE_JUNCTION, ROLE_RUNWAY, ROLE_BUILDING,
                 ROLE_GRADED_STRIP):
        assert ST.stage_of_role(role) == ST.STAGE_A, role


def test_unknown_and_missing_roles_take_the_conservative_side():
    """Airside is the conservative default: a wrong stage-B tag would let
    groundside law bind an airside row; a wrong stage-A tag only
    over-constrains stage A with its own kind."""
    assert ST.stage_of_role(None) == ST.STAGE_A
    assert ST.stage_of_role("a_role_that_does_not_exist") == ST.STAGE_A
    assert ST.stage_of_shape(_Shape(ROLE_SERVICE_ROAD)) == ST.STAGE_B
    assert ST.stage_of_shape(_Shape(ROLE_APRON)) == ST.STAGE_A


def test_a_shared_node_is_airside_because_airside_is_king():
    """A service-road MOUTH vertex on an apron ring is stage A: airside
    wins the seat (RULINGS 2026-08-06) and the road grades from it."""
    assert ST.stage_of_roles({ROLE_SERVICE_ROAD}) == ST.STAGE_B
    assert ST.stage_of_roles({ROLE_SERVICE_ROAD, ROLE_APRON}) == ST.STAGE_A
    assert ST.stage_of_roles({ROLE_SERVICE_ROAD,
                              ROLE_SERVICE_JUNCTION}) == ST.STAGE_B
    assert ST.stage_of_roles(set()) == ST.STAGE_A


# ── never-silent: an untagged entry FAILS ─────────────────────────────

def test_an_untagged_entry_raises_and_names_itself():
    entries = [{"edges": [(0, 1, 1.0)], ST.STAGE_KEY: ST.STAGE_A},
               {"edges": [(1, 2, 1.0)], "family": "rod_interval"}]
    with pytest.raises(ST.UntaggedConstraintError) as exc:
        ST.assert_tagged(entries, "a_projection")
    msg = str(exc.value)
    assert "a_projection" in msg
    assert "rod_interval" in msg, "the offender must be nameable"


def test_a_bogus_stage_value_is_not_a_tag():
    with pytest.raises(ST.UntaggedConstraintError):
        ST.assert_tagged([{"edges": [], ST.STAGE_KEY: "airside"}], "x")
    with pytest.raises(ValueError):
        ST.tag({}, "airside")


def test_an_unmapped_unified_edge_raises_rather_than_picking_a_side():
    """The unified graph's failure mode was one bare entry carrying every
    shape's pairs.  An edge whose minting shape registered no stage must
    never be silently assigned to the airside pass again."""
    pair_stage = {ST.pair_key(0, 1): ST.STAGE_A}
    with pytest.raises(ST.UntaggedConstraintError):
        ST.split_edges_by_stage([(0, 1, 1.0), (5, 6, 1.0)],
                                pair_stage, "unified")


def test_split_edges_by_stage_partitions_exactly():
    pair_stage = {ST.pair_key(0, 1): ST.STAGE_A,
                  ST.pair_key(2, 3): ST.STAGE_B,
                  ST.pair_key(3, 2): ST.STAGE_B}
    a, b = ST.split_edges_by_stage(
        [(0, 1, 1.0), (3, 2, 2.0)], pair_stage, "unified")
    assert a == [(0, 1, 1.0)]
    assert b == [(3, 2, 2.0)]


# ── the projection partition ──────────────────────────────────────────

def _one_solve():
    from auto_patch.elevation_per_surface.route_profile import one_solve
    return one_solve


def test_stage_b_entries_leave_the_airside_pass_even_with_no_role_key():
    """THE COUPLING-4 REGRESSION TWIN.  The predecessor keyed on
    ``sc["role"] in ROAD_ROLES``; the live §10 rod interval reaches the
    projection as ``family="rod_interval"`` with NO role key, so it was
    invisible and a SERVICE corridor's rod bound an airside endpoint in
    the airside pass."""
    os_ = _one_solve()
    rod = {"edges": [(0, 1, -0.1, 0.1)], "envelope_skip": True,
           "family": "rod_interval", ST.STAGE_KEY: ST.STAGE_B}
    apron = {"edges": [(2, 3, 1.0)], "role": ROLE_APRON,
             ST.STAGE_KEY: ST.STAGE_A}
    keep, moved = os_._partition_by_stage([rod, apron], [], "twin")
    assert keep == [apron]
    assert moved == [rod]


def test_groundside_pavement_is_partitioned_although_road_roles_omits_it():
    """``lateral_contiguity.ROAD_ROLES`` is {service_road,
    service_junction} — a groundside LOT's pairs on airside-claimed
    (shared) nodes were caught by neither the role test nor the receiver
    test, and were enforced against airside rows."""
    from auto_patch.lateral_contiguity import ROAD_ROLES
    assert ROLE_GROUNDSIDE_PAVEMENT not in ROAD_ROLES, (
        "premise of this twin: the predecessor's role set omits it")
    assert ST.stage_of_role(ROLE_GROUNDSIDE_PAVEMENT) == ST.STAGE_B
    os_ = _one_solve()
    lot = {"edges": [(0, 1, 1.0)], "role": ROLE_GROUNDSIDE_PAVEMENT,
           ST.STAGE_KEY: ST.STAGE_B}
    keep, moved = os_._partition_by_stage([lot], [], "twin")
    assert keep == []
    assert moved == [lot]


def test_the_partition_refuses_an_untagged_entry():
    os_ = _one_solve()
    with pytest.raises(ST.UntaggedConstraintError):
        os_._partition_by_stage([{"edges": [(0, 1, 1.0)]}], [], "twin")


def test_the_partition_moves_never_deletes():
    os_ = _one_solve()
    a = {"edges": [(0, 1, 1.0)], ST.STAGE_KEY: ST.STAGE_A}
    b1 = {"edges": [(2, 3, 1.0)], ST.STAGE_KEY: ST.STAGE_B}
    b2 = {"edges": [(4, 5, 1.0)], ST.STAGE_KEY: ST.STAGE_B}
    keep, moved = os_._partition_by_stage([a, b1], [b2], "twin")
    assert len(keep) + len(moved) == 3, "no entry may be dropped"
    assert b2 in moved and b1 in moved


# ── mint coverage ─────────────────────────────────────────────────────

def test_the_unified_graph_stamps_a_stage_per_edge_at_mint():
    """``edge_stage`` is index-parallel to ``edges`` — the same contract
    ``edge_family`` holds, and what makes the pair map derivable."""
    from auto_patch.grade_graph import UnifiedGraph
    G = UnifiedGraph()
    assert hasattr(G, "edge_stage")
    G.edges.append((0, 1, 1.0, False))
    G.edge_stage.append(ST.STAGE_A)
    G.edges.append((1, 2, 1.0, False))
    G.edge_stage.append(ST.STAGE_B)
    assert G.stage_by_pair() == {(0, 1): ST.STAGE_A, (1, 2): ST.STAGE_B}


def test_a_pair_two_shapes_mint_keeps_the_airside_stage():
    """AIRSIDE IS KING at a shared law pair: an apron that also owns the
    pair enforces it in its own pass, whichever shape minted it first."""
    from auto_patch.grade_graph import UnifiedGraph
    for order in ((ST.STAGE_B, ST.STAGE_A), (ST.STAGE_A, ST.STAGE_B)):
        G = UnifiedGraph()
        for st in order:
            G.edges.append((7, 4, 1.0, False))
            G.edge_stage.append(st)
        assert G.stage_by_pair() == {(4, 7): ST.STAGE_A}


def test_unified_entries_split_and_tag(monkeypatch):
    from auto_patch.elevation_per_surface.route_profile import solve as SV
    pair_stage = {ST.pair_key(0, 1): ST.STAGE_A,
                  ST.pair_key(2, 3): ST.STAGE_B}
    out = SV._unified_entries([(0, 1, 1.0), (2, 3, 1.0)], pair_stage,
                              "twin", family="unified_graph")
    assert {e[ST.STAGE_KEY] for e in out} == {ST.STAGE_A, ST.STAGE_B}
    assert all(e["family"] == "unified_graph" for e in out)
    assert sum(len(e["edges"]) for e in out) == 2


def test_unified_entries_drop_an_empty_side():
    from auto_patch.elevation_per_surface.route_profile import solve as SV
    out = SV._unified_entries([(0, 1, 1.0)],
                              {ST.pair_key(0, 1): ST.STAGE_A}, "twin")
    assert len(out) == 1 and out[0][ST.STAGE_KEY] == ST.STAGE_A
    assert "family" not in out[0], (
        "the solve-side entries carried no family before S1b; adding one "
        "would move every certificate row into a new bucket")
