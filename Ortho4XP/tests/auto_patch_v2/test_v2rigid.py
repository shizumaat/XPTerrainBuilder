"""ONE TOUCHING BODY, ONE DELTA (RULINGS 2026-09-10i, lane `v2rigid`;
spec ``othh-seat-artefacts-spec.md`` §14).

The LEMD read: the seat CUT contact edges inside one authored placement
(929 cuts, 13,979 of 23,371 edges intra-placement) and then gave each
measured ground component its OWN target, so one OBJ8 came out in
pieces metres apart — the T4 car park's walls +20.898 vs +19.668 with
the deck plates alternating, the old terminal's walls +5.5 against its
plates +8.3.  Four twins, hermetic and v2-pure:

1. two touching components of ONE placement whose feet read 1.2 m apart
   are ONE BODY at the median — no cut;
2. a body wider than ``body_feet_span_m`` carrying one foot SAMPLES the
   design surface under its ground-contact parts;
3. a plate touching a wall of body A takes A even when body B is nearer
   and touches it more often (no contact-count vote);
4. a component with no contact edge is its own body — a placement takes
   several deltas only across a physical separation.
"""
from __future__ import annotations

import pytest

from auto_patch_v2.emit import rebake as R
from auto_patch_v2.law import Law

from test_seat_clusters import _by_lat, _member, _plan_of  # noqa: E402


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


def test_two_touching_walls_of_one_placement_are_one_body(law):
    """10i (1)+(2): the T4 car park in miniature — two walls of ONE OBJ8
    whose feet stand 1.2 m apart (over ``cluster_seat_tolerance_m`` 0.5).
    The edge is NOT cut, the body takes ONE delta (the median), and the
    per-foot residuals are reported instead of being written."""
    wall = _member("Terminal4_yellow-LEMD13", [(0, 0.001, 0.0, 0.0), (1, 0.002, 0.0, 0.0)])
    pl = _plan_of([R.Unit("unit:25", (0.0, 0.0), 0.0, (wall,))], [(0, 1)])
    res = R.seat(pl, _by_lat({0.0: 700.0, 0.001: 720.9, 0.002: 719.7}), law)
    m = res.units[0].members[0]
    assert res.cut_edges == 0 and res.intra_placement_kept == 1
    assert res.counts()["clusters"] == 1
    assert m.delta_m == pytest.approx(20.3)                 # (20.9 + 19.7) / 2
    assert len({d for _c, _k, d in m.part_deltas}) == 1
    k = res.clusters[0]
    assert sorted(k.foot_residuals) == pytest.approx([-0.6, 0.6])
    assert k.foot_residual_max_m == pytest.approx(0.6)


def test_a_kilometre_body_with_one_foot_samples_the_surface(law):
    """10i (2): a body wider than ``body_feet_span_m`` carrying fewer than
    one measured foot per that span SAMPLES the design surface under every
    ground-contact part.  MEASURED LIMIT of the rule as ruled (reported,
    lane `v2rigid`): the sampling can only read the surface under the
    parts that TOUCH the ground, so a body whose single ground-contact
    part is one 265 m² slab (LEMD's T4 complex: 5,255 parts over 30
    resources, 1,204 m, authored with its floor 5.36 m above the pack's
    y = 0) gains exactly ONE extra foot, at that part's footprint
    centroid — the rule cannot manufacture feet a body does not have.
    Widening "ground-contact" to each placement's own lowest stratum was
    tried and REFUTED (LEMD pairs over 2 m 505 → 15,763, worst 46 m)."""
    span = law.tables.structures.rebake.body_feet_span_m
    assert span == pytest.approx(100.0)
    # one ground part and nine ELEVATED ones strung over ~1 km
    ps = [(0, 0.0002, 0.0, 0.0)] + [(i, 0.0002 + 0.001 * i, 0.0, 5.0) for i in range(1, 10)]
    big = _member("Terminal4SAT", ps)
    pl = _plan_of([R.Unit("u", (0.0, 0.0), 0.0, (big,))], [(i, i + 1) for i in range(9)])
    ground = {0.0: 595.0}                            # the anchor: the y = 0 plane
    ground.update({round(0.0002 + 0.001 * i, 6): 598.0 for i in range(10)})
    res = R.seat(pl, _by_lat(ground), law)
    k = res.clusters[0]
    assert k.diameter_m > span and k.n_measured == 1
    assert k.feet_sampled == 1                       # one ground-contact part, one sample
    assert k.ground_m == pytest.approx(598.0)
    assert res.units[0].members[0].delta_m == pytest.approx(3.0)
    # ...and with the law key at 0 the body is seated on whatever feet it has
    import dataclasses as dc
    off = dc.replace(law, tables=dc.replace(
        law.tables, structures=dc.replace(
            law.tables.structures, rebake=dc.replace(
                law.tables.structures.rebake, body_feet_span_m=0.0))))
    assert R.seat(pl, _by_lat(ground), off).clusters[0].feet_sampled == 0


def test_a_plate_takes_the_body_it_touches_not_the_nearest(law):
    """10i (3): a PLATE (elevated, no ground feet) touching a wall of body
    A takes A's delta — even though body B stands nearer and its parts
    outnumber A's in the contact count.  The carrier is the body it
    TOUCHES, resolved from the ground parts; never a vote."""
    a = _member("wallA", [(0, 0.001, 0.0, 0.0)])
    b = _member("wallB", [(1, 0.004, 0.0, 0.0), (2, 0.0041, 0.0, 0.0),
                          (3, 0.0042, 0.0, 0.0)])
    plate = _member("plate", [(4, 0.0011, 0.0, 3.0)])        # elevated: base_y > elevated_base_m
    pl = _plan_of([R.Unit("u", (0.0, 0.0), 0.0, (a, b, plate))],
                  [(0, 4), (1, 2), (2, 3)])
    res = R.seat(pl, _by_lat({0.0: 700.0, 0.001: 710.0, 0.0011: 710.0,
                              0.004: 720.0, 0.0041: 720.0, 0.0042: 720.0}), law)
    by = {m.resource: m for m in res.units[0].members}
    assert by["objects/wallA.obj"].delta_m == pytest.approx(10.0)
    assert by["objects/wallB.obj"].delta_m == pytest.approx(20.0)
    assert by["objects/plate.obj"].delta_m == pytest.approx(10.0)
    ka = {k for _c, k, _d in by["objects/wallA.obj"].part_deltas}
    assert {k for _c, k, _d in by["objects/plate.obj"].part_deltas} == ka


def test_a_separated_component_is_its_own_body(law):
    """10i (1): a placement carries several deltas ONLY across a physical
    separation — two components of one OBJ8 with no contact edge are two
    bodies, each on its own ground."""
    two = _member("depot", [(0, 0.001, 0.0, 0.0), (1, 0.010, 0.0, 0.0)])
    pl = _plan_of([R.Unit("u", (0.0, 0.0), 0.0, (two,))], [])
    res = R.seat(pl, _by_lat({0.0: 700.0, 0.001: 705.0, 0.010: 712.0}), law)
    m = res.units[0].members[0]
    assert res.counts()["clusters"] == 2 and res.cut_edges == 0
    assert m.delta_m is None                                 # several deltas: the separation
    assert sorted(d for _c, _k, d in m.part_deltas) == pytest.approx([5.0, 12.0])
