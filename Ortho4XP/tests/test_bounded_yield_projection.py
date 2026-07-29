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


# ── (d) broken-node blend clamps into the box ────────────────────────────

def test_broken_blend_clamped_into_box(_sweep_path):
    # hard@100 and hard@0 contradict through node 1 (floor 99 > ceil 1),
    # so the envelope quarantines it at the distance-weighted blend (~50)
    # — the burial mechanism.  With a box the blend clamps to the floor.
    edges = [(0, 1, 1.0), (1, 2, 1.0)]
    unbounded = [100.0, 50.0, 0.0]
    feasibility_project(unbounded, [{"edges": edges}], {0, 2},
                        force_scalar=True)
    assert 1.0 < unbounded[1] < 99.0        # blended between the anchors
    bounded = [100.0, 50.0, 0.0]
    rem, _ = feasibility_project(bounded, [{"edges": edges}], {0, 2},
                                 force_scalar=True,
                                 node_bounds={1: (95.0, 100.0)})
    assert bounded[1] == pytest.approx(95.0, abs=1e-9)
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
