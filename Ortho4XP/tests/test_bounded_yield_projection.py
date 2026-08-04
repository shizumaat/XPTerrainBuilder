"""Unit tests for the BOUNDED YIELD feasibility boxes in
``feasibility_project`` (owner ruling 2026-07-29: "Any yield absolutely
needs to stay within the feasibility box"; docs/specs/bounded-yield-spec.md).

Hermetic — no build, no fixtures.  Covers:
  (a) ``None`` bounds are byte-identical to omitting the parameters, on
      both sweep paths (chromatic ON and legacy scalar worklist);
  (b) a bounded free node clamps AT its box edge and the unsatisfiable
      edge stays visible in the returned over-cap tally;
  (c) a flat group's rigid level clamps at the group box edge and the
      group stays flat;
  (d) a BROKEN bounded node (reach-envelope anchor contradiction) has its
      blend clamped into the box instead of being quarantined outside it
      (the HECA south-terminal burial mechanism);
  (e) merged overlapping groups intersect their boxes.
"""
import pytest

import auto_patch.config as cfg
from auto_patch.elevation_per_surface.route_profile.one_solve import (
    feasibility_project)


@pytest.fixture(autouse=True)
def _zero_emit_margin(monkeypatch):
    monkeypatch.setattr(cfg, "EMIT_QUANTIZATION_MARGIN_M", 0.0)


@pytest.fixture(params=[True, False], ids=["chromatic", "scalar"])
def _sweep_path(request, monkeypatch):
    monkeypatch.setattr(cfg, "CHROMATIC_PROJECTION", request.param)
    return request.param


# ── (a) None bounds byte-identity ────────────────────────────────────────

def test_none_bounds_byte_identical(_sweep_path):
    edges = [(0, 1, 2.0), (1, 2, 1.0), (2, 3, 0.5), (0, 3, 10.0)]
    seed = [100.0, 90.0, 95.0, 100.5]
    base = list(seed)
    rem_a, bh_a = feasibility_project(base, [{"edges": edges}], {0},
                                      force_scalar=True)
    with_none = list(seed)
    rem_b, bh_b = feasibility_project(with_none, [{"edges": edges}], {0},
                                      force_scalar=True,
                                      group_bounds=None, node_bounds=None)
    assert with_none == base
    assert (rem_a, bh_a) == (rem_b, bh_b)


def test_none_group_bounds_with_flat_groups_byte_identical(_sweep_path):
    edges = [(0, 1, 1.0), (1, 2, 0.2), (2, 3, 0.2), (3, 4, 1.0)]
    seed = [100.0, 99.0, 96.0, 96.0, 100.0]
    groups = [{2, 3}]
    base = list(seed)
    feasibility_project(base, [{"edges": edges}], {0, 4},
                        force_scalar=True, flat_groups=[set(g) for g in groups])
    with_none = list(seed)
    feasibility_project(with_none, [{"edges": edges}], {0, 4},
                        force_scalar=True,
                        flat_groups=[set(g) for g in groups],
                        group_bounds=None, node_bounds=None)
    assert with_none == base


# ── (b) node box clamps at the edge; conflict stays reported ─────────────

def test_node_bound_clamps_at_box_edge(_sweep_path):
    # hard@80 pulls the free node down through a 5 m budget; its box floor
    # is 99, so it must stop exactly there and the edge stays over-cap.
    elev = [80.0, 100.0]
    rem, bh = feasibility_project(elev, [{"edges": [(0, 1, 5.0)]}], {0},
                                  force_scalar=True,
                                  node_bounds={1: (99.0, 101.0)})
    assert elev[0] == 80.0
    assert elev[1] == pytest.approx(99.0, abs=1e-9)
    assert rem == 1 and bh == 0


def test_node_bound_never_lifts_a_satisfied_node(_sweep_path):
    # Box present but nothing pushes the node out of it: no movement
    # beyond what the unbounded projection does (the clamp refines the
    # yield, it is not a new hold).
    elev = [100.0, 100.4]
    rem, _ = feasibility_project(elev, [{"edges": [(0, 1, 1.0)]}], {0},
                                 force_scalar=True,
                                 node_bounds={1: (99.0, 101.0)})
    assert elev[1] == pytest.approx(100.4)
    assert rem == 0


# ── (c) group box clamps the rigid level; group stays flat ───────────────

def test_group_bound_clamps_at_box_edge(_sweep_path):
    # Flat pad {1, 2} seeded at 100; hard@90 neighbours pull it down via
    # 1 m budgets; the group box floor 98 wins and the pad stays flat.
    elev = [90.0, 100.0, 100.0, 90.0]
    edges = [(0, 1, 1.0), (2, 3, 1.0)]
    rem, bh = feasibility_project(elev, [{"edges": edges}], {0, 3},
                                  force_scalar=True,
                                  flat_groups=[{1, 2}],
                                  group_bounds=[(98.0, 102.0)])
    assert elev[1] == elev[2] == pytest.approx(98.0, abs=1e-9)
    assert rem == 2 and bh == 0


def test_merged_groups_intersect_boxes(_sweep_path):
    # Two overlapping groups (shared node 2) act as one rigid unit whose
    # box is the intersection (99.5, 102) ∩ (98, 100.5) = (99.5, 100.5).
    elev = [90.0, 100.0, 100.0, 100.0, 90.0]
    edges = [(0, 1, 1.0), (3, 4, 1.0)]
    rem, _ = feasibility_project(elev, [{"edges": edges}], {0, 4},
                                 force_scalar=True,
                                 flat_groups=[{1, 2}, {2, 3}],
                                 group_bounds=[(99.5, 102.0), (98.0, 100.5)])
    assert elev[1] == elev[2] == elev[3] == pytest.approx(99.5, abs=1e-9)
    assert rem == 2


# ── (d) an inverted node takes its ceiling and stays movable ─────────────

def test_inverted_node_takes_the_ceiling_and_still_sweeps(_sweep_path):
    """REWRITTEN 2026-08-04 (spec ``docs/specs/kill-half-spec.md`` §2).

    This test pinned the BURIAL MECHANISM's repair: hard@100 and hard@0
    contradict through node 1 (floor 99 > ceiling 1), the envelope
    quarantined it at the distance-weighted blend (~50) and froze it, and
    the bounded-yield box existed to stop that blend parking a released
    seat outside the interval it was seated from.

    The blend and the freeze are DELETED, so there is no blend for a box
    to rescue: the node takes the ordinary clamp — the CEILING — and then
    sweeps.  The box still binds (it is the node's own law, not a
    quarantine), which is the half of this test that survives."""
    edges = [(0, 1, 1.0), (1, 2, 1.0)]
    unbounded = [100.0, 50.0, 0.0]
    feasibility_project(unbounded, [{"edges": edges}], {0, 2},
                        force_scalar=True)
    assert unbounded[1] == pytest.approx(1.0, abs=1e-9), (
        "the clamp's answer for an inverted interval is the ceiling "
        "(hard@0 + one 1.0 m budget)")
    bounded = [100.0, 50.0, 0.0]
    rem, _ = feasibility_project(bounded, [{"edges": edges}], {0, 2},
                                 force_scalar=True,
                                 node_bounds={1: (95.0, 100.0)})
    assert bounded[1] == pytest.approx(95.0, abs=1e-9), (
        "the box is the node's OWN law and still binds")
    assert rem >= 1                          # the contradiction stays visible


def test_contradictory_box_is_dropped(_sweep_path):
    # lo > hi is no box at all: behavior must equal the unbounded run.
    elev = [80.0, 100.0]
    feasibility_project(elev, [{"edges": [(0, 1, 5.0)]}], {0},
                        force_scalar=True,
                        node_bounds={1: (101.0, 99.0)})
    base = [80.0, 100.0]
    feasibility_project(base, [{"edges": [(0, 1, 5.0)]}], {0},
                        force_scalar=True)
    assert elev == base


# ── (f) REFERENCE RODS (owner ruling 2026-07-29 #2, spec §7) ─────────────

def test_reference_returns_slack_nodes_exactly(_sweep_path):
    # References are jointly feasible: both displaced nodes must end AT
    # their references EXACTLY (owner clarification 2026-07-29 — cap-lawful
    # sag below the string is a forbidden answer).
    elev = [100.0, 90.0, 92.0]
    edges = [(0, 1, 5.0), (1, 2, 5.0)]
    rem, _ = feasibility_project(elev, [{"edges": edges}], {0},
                                 force_scalar=True,
                                 node_refs={1: 99.0, 2: 100.0})
    assert rem == 0
    assert elev[1] == 99.0 and elev[2] == 100.0


def test_reference_conflicted_node_least_displacement(_sweep_path):
    # hard@80 through a 5 m budget: the reference 100 is unreachable; the
    # node must settle at the NEAREST lawful point (85), not anywhere else.
    elev = [80.0, 90.0]
    rem, _ = feasibility_project(elev, [{"edges": [(0, 1, 5.0)]}], {0},
                                 force_scalar=True, node_refs={1: 100.0})
    assert rem == 0
    assert elev[1] == pytest.approx(85.0, abs=1e-9)


def test_reference_with_binding_box(_sweep_path):
    # Box (99, 101) and a hard@80 5 m edge contradict; the box wins the
    # value (the clamp is law), the edge stays reported.
    elev = [80.0, 100.0]
    rem, _ = feasibility_project(elev, [{"edges": [(0, 1, 5.0)]}], {0},
                                 force_scalar=True,
                                 node_bounds={1: (99.0, 101.0)},
                                 node_refs={1: 100.5})
    assert elev[1] == pytest.approx(99.0, abs=1e-9)
    assert rem == 1


# ── (g) PAD ROD COUPLING (docs/specs/pad-rod-coupling-spec.md §2) ────────
# The reference of a soft-fabric vertex welded to a pad FACE is the pad's
# SEAT, not the fabric's yield-entry state.  These pin the projection-side
# semantics the coupling relies on; the contact-set side (which vertices
# are pad-face contacts, and which seat a two-pad contact takes) is pinned
# in tests/test_building_frontage_near_miss.py.

def _pad_face_arm(contact_ref, outward_refs):
    """One fp#8-shaped arm: rigid pad {0} at seat 100 welded to fabric
    node 1 (entry 92, the phase-A/B-shaped apron edge), which strings
    outward through node 2 to a hard anchor at 90.  ``contact_ref`` is
    node 1's reference — the entry state (pre-coupling) or the seat."""
    elev = [100.0, 92.0, 91.0, 90.0]
    edges = [(1, 2, 5.0), (2, 3, 5.0)]
    refs = {1: contact_ref}
    refs.update(outward_refs)
    rem, _ = feasibility_project(
        elev, [{"edges": edges}], {3}, force_scalar=True,
        flat_groups=[{0}], group_refs=[100.0], node_refs=refs)
    return elev, rem


def test_pad_face_contact_ends_at_the_seat(_sweep_path):
    """With nothing else referencing the outward fabric, the welded
    contact ends AT the seat (weld-tolerance class) and the fabric
    strings out at its own cap — graded, not stepped."""
    entry_arm, rem_entry = _pad_face_arm(92.0, {})
    assert rem_entry == 0
    assert entry_arm[1] == pytest.approx(92.0)          # 8 m wall at the face
    seat_arm, rem_seat = _pad_face_arm(100.0, {})
    assert rem_seat == 0
    assert seat_arm[0] == pytest.approx(100.0, abs=1e-9)   # pad never moved
    assert seat_arm[3] == 90.0                             # anchor never moved
    assert seat_arm[1] > entry_arm[1]                      # the step closes
    assert abs(seat_arm[1] - seat_arm[2]) <= 5.0 + 1e-9    # outward grade lawful
    assert abs(seat_arm[2] - seat_arm[3]) <= 5.0 + 1e-9
    if _sweep_path:
        # CHROMATIC sweeps (production default): the proximal pull carries
        # THROUGH the fabric, so the contact reaches the seat and the
        # transition emits as a cap-rate ramp outward.
        assert seat_arm[1] == pytest.approx(100.0, abs=0.02)
        assert seat_arm[2] == pytest.approx(95.0, abs=0.02)
    else:
        # LEGACY SCALAR worklist: no sweep structure, so the reference
        # semantics come from the exact-return polish alone — the contact
        # rises to the most its caps admit against the fabric's CURRENT
        # values (one cap hop above node 2), not to the seat.
        assert seat_arm[1] == pytest.approx(96.0, abs=1e-9)


def test_pad_face_contact_least_displacement_against_fabric_refs(
        _sweep_path):
    """MEASURED SEMANTICS (do not "fix" this to 100): the outward fabric
    carries its OWN §7 reference (its yield-entry state), so the coupled
    contact rises only as far as the cap web against those competing
    references admits — least displacement from the seat, not a hold at
    it.  The face step shrinks and the remainder emits as lawful outward
    grade; a frontage needing more than the caps allow stays a reported
    conflict rather than a silent lift."""
    entry_arm, _ = _pad_face_arm(92.0, {2: 91.0})
    seat_arm, rem = _pad_face_arm(100.0, {2: 91.0})
    assert rem == 0
    assert entry_arm[1] < seat_arm[1] < 100.0        # toward the seat, not to it
    assert abs(seat_arm[1] - seat_arm[2]) <= 5.0 + 1e-9
    expected = 97.996 if _sweep_path else 96.0
    assert seat_arm[1] == pytest.approx(expected, abs=1e-3)


def test_pad_face_contact_takes_least_displacement_when_capped(_sweep_path):
    """The seat reference is a REFERENCE, not a hold: where the caps
    cannot reach it the contact settles at the nearest lawful value
    (minimum displacement), never past it."""
    elev = [100.0, 92.0, 90.0]
    edges = [(1, 2, 1.0)]
    rem, _ = feasibility_project(
        elev, [{"edges": edges}], {2}, force_scalar=True,
        flat_groups=[{0}], group_refs=[100.0],
        node_refs={1: 100.0})
    assert rem == 0
    assert elev[1] == pytest.approx(91.0, abs=1e-9)      # 90 + cap, not 100


def test_group_reference_returns_exactly(_sweep_path):
    # Flat pad {1, 2} displaced to 95 with slack edges: the rigid group
    # must return to its reference level exactly and stay flat.
    elev = [90.0, 95.0, 95.0, 90.0]
    edges = [(0, 1, 10.0), (2, 3, 10.0)]
    rem, _ = feasibility_project(elev, [{"edges": edges}], {0, 3},
                                 force_scalar=True,
                                 flat_groups=[{1, 2}],
                                 group_refs=[98.0])
    assert rem == 0
    assert elev[1] == elev[2] == 98.0
