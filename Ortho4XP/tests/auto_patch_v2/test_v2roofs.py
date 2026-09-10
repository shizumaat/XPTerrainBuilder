"""THE PLATE FOLLOWS THE WALL IT TOUCHES, AND THE WALL UNDER ITS EAVE
(RULINGS 2026-09-10u, lane `v2roofs`; spec ``othh-seat-artefacts-spec.md``
§15).

The owner's LEMD read after 10i: roof planes still floating over their
walls — 440 plate-above-wall pairs over 0.5 m, 257 plates, 5 resources
(``tools/v2_rebake_replay.py pairs --class plate-vs-wall``).  Two rules:

1. a TOUCHING SET of one placement is ONE BODY, elevated parts included
   — the BFS assigns a cohesion group, never a part, and where a group
   touches several bodies the tie resolves to the wall it rests on (the
   largest plan-footprint overlap), never to the lowest body id;
2. THE EAVE GAP: a free component with no carrier within
   ``contact_tol_m`` takes the wall it OVERLAPS IN PLAN whose top lies
   within ``[rebake] plate_gap_max_m`` of its own bottom, before falling
   to nearest.

Hermetic and v2-pure: no pack, no mesh, no network.
"""
from __future__ import annotations

import pytest

from auto_patch_v2.airport import rigid as RG
from auto_patch_v2.emit import rebake as R
from auto_patch_v2.law import Law

from test_seat_clusters import _by_lat, _member, _plan_of  # noqa: E402
from test_v2planes import _comps, _plane_index, _strip_plane, _wall  # noqa: E402

#: ``emit.identity.min_distinct_spacing_m`` (asserted in ``test_v2planes``)
SPACING = 0.5


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


# ── rule 1: one placement, one touching body ────────────────────────────

def test_a_ground_wall_touching_an_elevated_plate_is_one_body(law):
    """10u (1): `Terminal4SAT_Yellow-LEMD11` in miniature — a wall and the
    plate resting on it, ONE placement, one contact edge.  Before 10u the
    edge was discarded (the plate is elevated, so neither the cut nor the
    ground union saw it) and the plate was assigned independently by the
    BFS; now the two are one body with one delta."""
    one = _member("Terminal4SAT_Yellow-LEMD11",
                  [(0, 0.0010, 0.0, 0.0),        # the wall: ground, feet at y = 0
                   (1, 0.0011, 0.0, 15.0)])      # the plate: elevated (base_y > 0.5)
    pl = _plan_of([R.Unit("u", (0.0, 0.0), 0.0, (one,))], [(0, 1)])
    res = R.seat(pl, _by_lat({0.0: 700.0, 0.0010: 705.0, 0.0011: 705.0}), law)
    m = res.units[0].members[0]
    assert res.counts()["clusters"] == 1 and res.cut_edges == 0
    assert res.elevated_groups == 0                # nothing left free to assign
    assert m.delta_m == pytest.approx(5.0)         # ONE delta over both parts
    assert len({k for _c, k, _d in m.part_deltas}) == 1


def test_a_plate_takes_the_wall_it_overlaps_not_the_lower_body_id(law):
    """10u (1): the plate is a DIFFERENT placement touching two bodies —
    the lower-id body by an edge with no plan overlap, the higher-id one
    by the wall it actually rests on (their plan footprints overlap).
    The pre-10u tie-break took the lowest body id; the tie now resolves
    to the touching wall."""
    stub = _member("stub", [(0, 0.0040, 0.0, 0.0)])       # body 0: no plan overlap
    wall = _member("wall", [(1, 0.0010, 0.0, 0.0)])       # body 1: the wall it rests on
    plate = _member("plate", [(2, 0.0010, 0.0, 15.0)])    # elevated, over `wall`
    pl = _plan_of([R.Unit("u", (0.0, 0.0), 0.0, (stub, wall, plate))],
                  [(0, 2), (1, 2)])
    res = R.seat(pl, _by_lat({0.0: 700.0, 0.0010: 710.0, 0.0040: 720.0}), law)
    by = {m.resource: m for m in res.units[0].members}
    assert by["objects/stub.obj"].delta_m == pytest.approx(20.0)
    assert by["objects/wall.obj"].delta_m == pytest.approx(10.0)
    # the wall it rests on, not body 0
    assert by["objects/plate.obj"].delta_m == pytest.approx(10.0)
    assert {k for _c, k, _d in by["objects/plate.obj"].part_deltas} == \
        {k for _c, k, _d in by["objects/wall.obj"].part_deltas}
    assert res.elevated_groups == 1 and res.group_ties == 0


# ── rule 2: the eave gap ────────────────────────────────────────────────

def _roof_over_a_wall(tmp_path, name, y, stub_top):
    """A wall 0..4 m high at z = 0 whose PLAN footprint the roof plane at
    ``y`` covers, plus a STUB panel just outside the roof's footprint
    (z = 2.0, top ``stub_top``) that stands NEARER in 3-D — the carrier
    the pure-nearest rule picks."""
    v: list = []
    t: list = []
    _wall(v, t, 0.0, 10.0, 0.0)                  # the wall under the roof, top y = 4
    _wall(v, t, 0.0, 10.0, 2.0, 0.0, stub_top)   # the stub: nearer in 3-D, no overlap
    _strip_plane(v, t, 0.0, 10.0, -1.0, 1.0, y, 4)
    geom, comps = _comps(tmp_path, name, v, t)
    plane = _plane_index(comps)
    wall = next(i for i, c in enumerate(comps)
                if i != plane and abs(c.cz) < 0.5)
    stub = next(i for i, c in enumerate(comps) if i not in (plane, wall))
    return geom, comps, plane, wall, stub


def test_a_roof_two_metres_over_its_wall_top_joins_that_wall(tmp_path, law):
    """10u (2): a roof authored 2 m clear of the wall top it covers
    touches nothing, and the pure-nearest rule handed it to whatever was
    closest in 3-D.  Its plan footprint OVERLAPS the wall and the gap is
    under ``plate_gap_max_m``, so it joins that wall's body as if
    touching."""
    gap = law.tables.structures.rebake.plate_gap_max_m
    assert gap == pytest.approx(4.0)
    geom, comps, plane, wall, stub = _roof_over_a_wall(tmp_path, "eave.obj", 6.0, 6.0)
    seat = {wall: +2.0, stub: -1.5}
    # the pre-10u rule: nothing touches, the stub is nearest in 3-D
    assert RG.complete_component_deltas(geom, comps, seat,
                                        contact_tol_m=SPACING)[plane] == -1.5
    stats: dict = {}
    done = RG.complete_component_deltas(geom, comps, seat, contact_tol_m=SPACING,
                                        plate_gap_max_m=gap, stats=stats)
    assert done[plane] == +2.0                    # the wall under the eave
    assert stats["eave"] == 1 and stats["nearest"] == 0


def test_a_roof_six_metres_over_its_wall_falls_back_to_nearest(tmp_path, law):
    """Beyond ``plate_gap_max_m`` the rule does NOT fire: a plane 6 m over
    the wall top is not a parapet gap, and the carrier is the nearest as
    before — reported, not fixed (``stats['nearest']``)."""
    gap = law.tables.structures.rebake.plate_gap_max_m
    geom, comps, plane, wall, stub = _roof_over_a_wall(tmp_path, "far.obj", 10.0, 6.0)
    seat = {wall: +2.0, stub: -1.5}
    stats: dict = {}
    done = RG.complete_component_deltas(geom, comps, seat, contact_tol_m=SPACING,
                                        plate_gap_max_m=gap, stats=stats)
    assert done[plane] == -1.5
    assert stats["eave"] == 0 and stats["nearest"] == 1


def test_the_eave_gap_is_the_callers_law_value(law):
    """``rigid`` holds no number of its own: ``plate_gap_max_m`` defaults
    to 0.0 (the pre-10u pure-nearest fallback) and the value is the
    caller's."""
    import inspect
    assert "plate_gap_max_m" in law.tables.structures.rebake.__dataclass_fields__
    src = inspect.getsource(RG)
    assert "plate_gap_max_m" in src and "4.0" not in src
