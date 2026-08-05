"""Reference honesty — spec ``docs/specs/reference-honesty-and-terracing-
spec.md`` Track 1.

The defect these pin: every reference surface built AFTER
``one_solve.feasibility_project``'s quarantine blend was sampling that
blend.  A quarantined value is by definition one the law REFUSED to admit,
so anchoring on it drags the whole free interior toward it.

Covered here:

(The ``solve._rod_string_values`` rod-held string and the ``_BandView``
band adapter that used to be covered here were DELETED with the §7
reference channel in the build-complete-then-debug round.)

* the RIGID BRANCH VERTEX placement in ``one_solve``'s chain-rigid blend
  (Track 1 step 3), including the ★ hard-neighbour clamp that guards the
  05C runway kink.
"""
import os

import pytest

from auto_patch.elevation_per_surface.route_profile.one_solve import (
    feasibility_project)


# ── the anchor ladder is GONE with its module ────────────────────────────
# ``apron_reference.apron_reference_values`` (the apron reference surface
# R) and ``reference_field.build_reference_field`` (the R1 one-field
# assembly) existed ONLY to produce ``z_ref`` for the §7 proximal pull.
# With the pull retired they had zero production importers, so both
# modules — and the ladder tests that lived here — were deleted in the
# build-complete-then-debug round.  Aprons are graded by the law edges
# and the reach band alone now: ONE authority.


# ── rigid branch vertices (Track 1 step 3) ───────────────────────────────
# ★ These three tests are xfail(strict) since 2026-08-04 — see the marker's
# reason.  The blend they refine no longer exists; the STOP is reported to
# the spec author rather than resolved by deleting the feature.

def _branch_case(env_value):
    """Three rod chains meeting at a junction, every node quarantined by a
    pair of contradictory hard anchors, so the whole rod graph lands in the
    broken branch.  Node 3 is the junction (rod degree 3)."""
    # nodes: 0,1 = hard contradiction pair;  2..8 = fabric.
    # rod legs: 3-4-5, 3-6-7, 3-8  (3 has degree 3 → branch vertex).
    n = 9
    elev = [200.0, 100.0] + [150.0] * 7
    # A tight symmetric web between the two contradictory anchors makes
    # every fabric node broken (floor from 0, ceiling from 1).
    edges = []
    for i in range(2, n):
        edges.append((0, i, 0.5))
        edges.append((1, i, 0.5))
    rod_edges = [(4, 3, 0.98, 1.02), (5, 4, 0.98, 1.02),
                 (6, 3, 1.98, 2.02), (7, 6, 1.98, 2.02),
                 (8, 3, -1.02, -0.98)]
    constraints = [{"edges": edges},
                   {"edges": rod_edges, "envelope_skip": True}]
    old = os.environ.get("O4_BRANCH_RIGID_BLEND")
    os.environ["O4_BRANCH_RIGID_BLEND"] = env_value
    try:
        broken = set()
        feasibility_project(elev, constraints, {0, 1}, max_iters=200,
                            broken_out=broken)
    finally:
        if old is None:
            os.environ.pop("O4_BRANCH_RIGID_BLEND", None)
        else:
            os.environ["O4_BRANCH_RIGID_BLEND"] = old
    return elev, broken


def _worst_mouth_step(elev):
    """The largest rod-slab violation AT THE JUNCTION — the ~1.2 m
    corridor-mouth step memory ``rod-chains-split-at-branches`` names as
    the chain-rigid pass's known residual."""
    return max(abs((elev[leg] - elev[3]) - delta)
               for (leg, delta) in ((4, 1.0), (6, 2.0), (8, -1.0)))


@pytest.mark.xfail(strict=True, reason=(
    "EXPOSED CONSUMER, kill-half §2 (2026-08-04): the chain/branch-rigid "
    "pass is a MODE of the deleted break blend — it recomputed that blend "
    "per rod chain — so with the pointwise blend gone its `broken` input is "
    "empty and the pass is inert.  O4_CHAIN_RIGID_BLEND / "
    "O4_BRANCH_RIGID_BLEND are not this spec's to retire; reported instead "
    "of deleted."))
def test_branch_vertex_lands_on_the_string_when_the_gate_is_on():
    elev, broken = _branch_case("1")
    assert {3, 4, 5, 6, 7, 8} <= broken, broken
    # The junction takes the LEAST-DISPLACEMENT point among the levels its
    # rod slabs to the (now rigidly placed) legs imply.  It cannot satisfy
    # three mutually disagreeing legs exactly — that residual is honest —
    # but it is on the string, not on the pointwise blend.
    implied = [elev[4] - 1.0, elev[6] - 2.0, elev[8] + 1.0]
    assert elev[3] == pytest.approx(sum(implied) / len(implied))


@pytest.mark.xfail(strict=True, reason=(
    "EXPOSED CONSUMER, kill-half §2 (2026-08-04): the chain/branch-rigid "
    "pass is a MODE of the deleted break blend — it recomputed that blend "
    "per rod chain — so with the pointwise blend gone its `broken` input is "
    "empty and the pass is inert.  O4_CHAIN_RIGID_BLEND / "
    "O4_BRANCH_RIGID_BLEND are not this spec's to retire; reported instead "
    "of deleted."))
def test_branch_rigid_shrinks_the_mouth_step_and_leaves_the_chains_alone():
    off, _ = _branch_case("0")
    on, _ = _branch_case("1")
    for leg in (4, 5, 6, 7):
        assert off[leg] == pytest.approx(on[leg]), \
            "the CHAINS are placed identically — only the junction moves"
    assert _worst_mouth_step(on) < _worst_mouth_step(off)


@pytest.mark.xfail(strict=True, reason=(
    "EXPOSED CONSUMER, kill-half §2 (2026-08-04): the chain/branch-rigid "
    "pass is a MODE of the deleted break blend — it recomputed that blend "
    "per rod chain — so with the pointwise blend gone its `broken` input is "
    "empty and the pass is inert.  O4_CHAIN_RIGID_BLEND / "
    "O4_BRANCH_RIGID_BLEND are not this spec's to retire; reported instead "
    "of deleted."))
def test_branch_rigid_gate_off_is_the_landed_pointwise_behaviour():
    """Gate-off must leave the junction on its blend value exactly (the
    byte-identity arm of the gate)."""
    off, _ = _branch_case("0")
    # the pointwise blend of a node midway between two contradictory
    # anchors 0.5 m-reachable from each: hi + (lo − hi)·t.
    assert off[3] == pytest.approx(off[2]), \
        "an unstrung broken node and the junction share the blend"


# ── THE STRING BACK DOOR IS GONE ─────────────────────────────────────────
# ``O4_CORRIDOR_REF_STRING`` promoted rod-held string values into
# ``z_ref``, i.e. the PAUSED string acting as a surface authority.  It was
# defaulted off on 2026-08-04 (owner: "No degradation-shield interims;
# retire the string back door") and DELETED, together with the proximal
# pull and the whole refs channel, in the build-complete-then-debug round.


def test_the_corridor_ref_string_path_is_gone():
    import auto_patch.elevation_per_surface.route_profile.solve as SV
    src = open(SV.__file__).read()
    assert 'environ.get("O4_CORRIDOR_REF_STRING"' not in src
    assert not hasattr(SV, "_rod_string_values")


def test_the_reference_channel_is_gone_from_the_projection():
    import inspect
    params = inspect.signature(feasibility_project).parameters
    assert "node_refs" not in params and "group_refs" not in params
