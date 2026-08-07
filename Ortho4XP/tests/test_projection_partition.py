"""THE PROJECTION PARTITIONS — twins for the cycle-8 Q4 cure.

Spec: ``docs/specs/cycle8-one-graph-spec.md`` ADDENDUM ("THE FINAL
PROJECTION PARTITIONS"), deriving from RULINGS 2026-08-06 ("ONE graph"
clause 2, receiver-only) and the standing "airside is king".

The law under test, in one sentence: **a shared projection is a
coupling**, so airside projects FIRST with every groundside pair out of
its constraint set, and groundside projects AFTER against frozen airside
values.  The acceptance number that motivated it is the Q4 debt — a
groundside round moved airside rows (+6 SPJC / +5 HECA) purely by
co-projecting the two sides.

Each test is a KNOWN-ANSWER twin (RULINGS 2026-08-06, "Instrument truth
is law" clause 1): the byte-identity test carries its own POSITIVE
CONTROL — the same two runs through the un-partitioned projection, which
must DIFFER.  Without that control an assertion of "airside did not move"
would also pass if the projection had moved nothing at all.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from auto_patch.layout import (                              # noqa: E402
    GROUNDSIDE_ROLES, ROLE_APRON, ROLE_BUILDING,
    ROLE_GROUNDSIDE_PAVEMENT, ROLE_SERVICE_ROAD, ROLE_SERVICE_JUNCTION,
    ROLE_TUNNEL_RAMP,
)
from auto_patch.elevation_per_surface.route_profile.one_solve import (  # noqa: E402
    feasibility_project, feasibility_project_partitioned,
    partition_constraints_by_receiver,
)
from auto_patch.elevation_per_surface.route_profile.solve import (  # noqa: E402
    _receiver_nodes_from_roles,
)


# ── the fixture graph ────────────────────────────────────────────────
# 0 —1.0— 1 —1.0— 2   ‖   2 —0.5— 3 —0.5— 4
# ^hard                    ^^^^^^^^^^^^^^^^^ groundside (receivers 3, 4)
#
# Node 2 is the MOUTH-side airside vertex: it carries the coupling to the
# groundside chain.  Node 0 is the runway-class anchor.
AIRSIDE_EDGES = [(0, 1, 1.0), (1, 2, 1.0)]
MIXED_AND_GROUNDSIDE_EDGES = [(2, 3, 0.5), (3, 4, 0.5)]
RECEIVERS = {3, 4}


def _constraints():
    """A fresh constraint list (the projection may mutate entries)."""
    return [{"edges": list(AIRSIDE_EDGES) + list(MIXED_AND_GROUNDSIDE_EDGES),
             "family": "fixture"}]


def _run(seed, *, partitioned):
    """Project with the groundside chain seeded at ``seed``; return the
    full field."""
    elev = [0.0, 0.0, 0.0, float(seed), float(seed)]
    hard = {0}
    if partitioned:
        feasibility_project_partitioned(
            elev, _constraints(), hard,
            receiver_nodes=RECEIVERS, n_nodes=len(elev), force_scalar=True)
    else:
        feasibility_project(elev, _constraints(), hard, force_scalar=True)
    return elev


# ── 1. the partition itself ──────────────────────────────────────────

def test_partition_sends_every_receiver_touching_pair_to_the_receiver_side():
    givers, receivers = partition_constraints_by_receiver(
        _constraints(), RECEIVERS)
    g_edges = [e for entry in givers for e in entry["edges"]]
    r_edges = [e for entry in receivers for e in entry["edges"]]
    assert g_edges == AIRSIDE_EDGES
    # the MIXED pair (2, 3) is a receiver-side pair: it is the coupling.
    assert r_edges == MIXED_AND_GROUNDSIDE_EDGES
    # the two sides PARTITION the input — no edge lost, none enforced twice.
    assert len(g_edges) + len(r_edges) == len(_constraints()[0]["edges"])
    # other entry keys ride along, so family/envelope_skip semantics hold.
    assert all(entry.get("family") == "fixture" for entry in givers + receivers)


def test_a_lazy_entry_is_never_split_and_is_handed_over_by_identity():
    """``feasibility_project`` expands a flatness-certified entry IN
    PLACE so later passes see the expansion; a copy would silently lose
    that.  The entry goes whole to the side its shape belongs to."""
    lazy_gs = {"edges": [(3, 4, 0.5)], "lazy_expand": lambda: [],
               "lazy_nodes": [3, 4], "lazy_seed": [0.0, 0.0]}
    lazy_air = {"edges": [(0, 1, 1.0)], "lazy_expand": lambda: [],
                "lazy_nodes": [0, 1], "lazy_seed": [0.0, 0.0]}
    givers, receivers = partition_constraints_by_receiver(
        [lazy_gs, lazy_air], RECEIVERS)
    assert receivers == [lazy_gs] and receivers[0] is lazy_gs
    assert givers == [lazy_air] and givers[0] is lazy_air


def test_no_receivers_is_the_identical_list_object():
    """Byte-inertness: an airport with no groundside node must take the
    un-partitioned path with no copying at all."""
    sc = _constraints()
    givers, receivers = partition_constraints_by_receiver(sc, set())
    assert givers is sc and receivers == []


# ── 2. THE LAW: airside cannot see a groundside seat ─────────────────

# The seeds are chosen SUB-SATURATING on purpose: past a few metres the
# co-projected chain simply saturates at cap and two different seeds land
# airside in the same place, which would make the positive control below
# pass for the wrong reason.  (1.0, 1.6) is the real shape of the defect
# — a mouth dragging airside by centimetres.
@pytest.mark.parametrize("seed_a,seed_b", [(1.0, 1.6), (-30.0, 4.0)])
def test_airside_is_byte_identical_under_a_perturbed_groundside_seat(
        seed_a, seed_b):
    """The ruling, as an assertion: perturbing a groundside seat may not
    move ONE airside value by ONE bit."""
    air_a = _run(seed_a, partitioned=True)[:3]
    air_b = _run(seed_b, partitioned=True)[:3]
    assert air_a == air_b                       # bit-for-bit, not a tolerance
    assert air_a == [0.0, 0.0, 0.0]             # and it is the LAWFUL field

    # POSITIVE CONTROL — the same perturbation through ONE shared
    # projection moves airside.  This is the Q4 debt's mechanism in
    # miniature; if it ever stops differing, the twin above has gone
    # blind and this test says so.
    ctrl_a = _run(seed_a, partitioned=False)[:3]
    ctrl_b = _run(seed_b, partitioned=False)[:3]
    assert ctrl_a != ctrl_b


def test_the_receiver_pass_still_enforces_the_mixed_pair():
    """Receiver-only is a DIRECTION, not a deletion: the coupling law is
    enforced in the groundside pass, with the airside endpoint frozen."""
    elev = _run(20.0, partitioned=True)
    assert elev[2] == 0.0                                   # airside frozen
    assert abs(elev[3] - elev[2]) <= 0.5 + 1e-9             # law enforced
    assert abs(elev[4] - elev[3]) <= 0.5 + 1e-9


def test_the_partition_returns_the_whole_over_cap_tally():
    """The exit report counts every violated edge exactly once: the two
    passes' tallies sum over a partition of the same edge set."""
    elev = [0.0, 0.0, 0.0, 5.0, 5.0]
    rem_split, _ = feasibility_project_partitioned(
        elev, _constraints(), {0, 1, 2, 3, 4},
        receiver_nodes=RECEIVERS, n_nodes=len(elev), force_scalar=True)
    elev2 = [0.0, 0.0, 0.0, 5.0, 5.0]
    rem_joint, _ = feasibility_project(
        elev2, _constraints(), {0, 1, 2, 3, 4}, force_scalar=True)
    # everything hard ⇒ nothing moves ⇒ both report the same violation.
    assert rem_split == rem_joint == 1


# ── 3. WHO is a receiver ─────────────────────────────────────────────

def test_a_shared_mouth_vertex_is_airside_not_a_receiver():
    """RULINGS 2026-08-06: "the mouth of the service road has to function
    like an apron edge building, seated where it's feasible for the
    airside apron to meet it" — airside wins the seat, so the mouth is
    FROZEN DATA for the groundside pass, never one of its variables."""
    roles = {
        0: frozenset({ROLE_APRON}),                       # airside
        1: frozenset({ROLE_APRON, ROLE_SERVICE_ROAD}),    # THE MOUTH
        2: frozenset({ROLE_SERVICE_ROAD}),                # road interior
        3: frozenset({ROLE_GROUNDSIDE_PAVEMENT}),         # lot
        4: frozenset({ROLE_SERVICE_JUNCTION, ROLE_TUNNEL_RAMP}),
        5: frozenset({ROLE_BUILDING}),                    # pad: not gs here
        6: frozenset(),                                   # role-unmatched
    }
    assert _receiver_nodes_from_roles(roles) == {2, 3, 4}


def test_the_census_and_the_solver_share_one_groundside_partition():
    """LOCKSTEP.  ``row_side`` decides the campaign matrix's airside /
    groundside / mixed columns; the projection partition decides who may
    move in which pass.  Two literal sets would drift silently — the
    frontage-gap lesson — so the census reads the registry's."""
    sys.path.insert(0, str(ROOT / "tools"))
    import check_grade
    assert set(check_grade._GROUNDSIDE_ROLES) == set(GROUNDSIDE_ROLES)
