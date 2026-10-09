"""Twins of ``constraints/gap_follow`` (spec §53 (13)): a gap-piece vertex
within reach of a FIXED standing ring is bound to that ring's level at the
tighter cap; beside a pad the distance counts from the set-back; two fixed
neighbours that disagree bind the vertex BETWEEN them and are reported; the
piece's own rim, a follower ribbon and an unfixed ring bind nothing."""
from __future__ import annotations

import types

import pytest

from auto_patch_v2.constraints import gap_follow as gf
from auto_patch_v2.law import Law
from auto_patch_v2.law.tables import role_cap, snap_margin_m
from auto_patch_v2.solve.design_roles import hard_rulings, ruling_head

LAW = Law.for_airport("HECA")


def _pm(coords, faces):
    eid, ends = {}, {}

    def edge(a, b):
        k = frozenset((a, b))
        if k not in eid:
            eid[k] = 1000 + len(eid)
            ends[eid[k]] = types.SimpleNamespace(a=a, b=b)
        return eid[k]
    fs = {}
    for i, (role, ref, ring) in enumerate(faces):
        n = len(ring)
        fs[i] = types.SimpleNamespace(id=i, role=role, ref=ref, holes=(),
                                      ring=tuple(edge(ring[k], ring[(k + 1) % n]) for k in range(n)))
    return types.SimpleNamespace(
        vertices={i: types.SimpleNamespace(xy=xy) for i, xy in enumerate(coords)},
        faces=fs, edges=ends,
        ring_vertices=lambda cyc: tuple(v for e in cyc for v in (ends[e].a, ends[e].b)))


# a piece (4..7) 1.45 m east of a road (0..3)
COORDS = [(0.0, 0.0), (10.0, 0.0), (10.0, 40.0), (0.0, 40.0),
          (11.45, 0.0), (40.0, 0.0), (40.0, 40.0), (11.45, 40.0)]


def test_a_piece_vertex_is_bound_to_the_fixed_ring_at_the_tighter_cap():
    pm = _pm(COORDS, [("service_road", "route3", (0, 1, 2, 3)),
                      ("groundside_pavement", "gap:7", (4, 5, 6, 7))])
    fixed = {0: 96.0, 1: 96.0, 2: 100.0, 3: 100.0}
    rows, rep = gf.gap_follow_rows(pm, LAW, fixed)
    cap = role_cap(LAW, "service_road").longitudinal
    by = {r.terms[0][0]: r for r in rows}
    assert sorted(by) == [4, 7] and rep["rows"] == 2 and rep["conflicts"] == []
    assert by[4].lo == pytest.approx(96.0 - cap * 1.45) and by[4].hi == pytest.approx(96.0 + cap * 1.45)
    assert by[7].lo == pytest.approx(100.0 - cap * 1.45)
    assert ruling_head(rows[0]) in hard_rulings(LAW)
    # an UNFIXED ring binds nothing; an edge with ONE fixed end binds at that
    # end; a fixed piece vertex takes no row
    assert gf.gap_follow_rows(pm, LAW, {})[0] == []
    assert [r.terms[0][0] for r in gf.gap_follow_rows(pm, LAW, {1: 96.0})[0]] == [4]
    assert sorted(r.terms[0][0] for r in gf.gap_follow_rows(pm, LAW, {**fixed, 4: 96.0})[0]) == [7]


def test_beside_a_pad_the_distance_counts_from_the_set_back():
    pm = _pm(COORDS, [("building", "building26", (0, 1, 2, 3)),
                      ("groundside_pavement", "gap:0", (4, 5, 6, 7))])
    rows, _ = gf.gap_follow_rows(pm, LAW, {0: 90.79, 1: 90.79, 2: 90.79, 3: 90.79})
    knife = LAW.tables.structures.building_pad.groundside_cutback_m + snap_margin_m(LAW)
    # the TIGHTER of the two faces' caps: the pad's own (the apron class's)
    cap = min(role_cap(LAW, "groundside_pavement").longitudinal,
              role_cap(LAW, "building").longitudinal)
    assert rows[0].hi - 90.79 == pytest.approx(cap * (1.45 - knife))
    assert rows[0].hi - 90.79 < 0.05


def test_two_fixed_neighbours_that_disagree_bind_the_vertex_between_them():
    coords = COORDS + [(11.45, -5.0), (20.0, -5.0), (20.0, -1.45), (11.45, -1.45)]
    pm = _pm(coords, [("service_road", "route3", (0, 1, 2, 3)),
                      ("groundside_pavement", "gap:7", (4, 5, 6, 7)),
                      ("parking_lot", "dsf:pol10", (8, 9, 10, 11))])
    fixed = {0: 96.0, 1: 96.0, 2: 96.0, 3: 96.0, 8: 92.0, 9: 92.0, 10: 92.0, 11: 92.0}
    rows, rep = gf.gap_follow_rows(pm, LAW, fixed)
    r4 = next(r for r in rows if r.terms[0][0] == 4)
    assert 92.0 < r4.lo < r4.hi < 96.0
    c = rep["conflicts"][0]
    assert (c["upper"], c["lower"]) == ("service_road:route3", "parking_lot:dsf:pol10")
    assert (c["upper_m"], c["lower_m"]) == (96.0, 92.0) and c["gap_m"] > 3.0


def test_the_own_rim_binds_nothing_and_a_ribbon_beside_no_piece_is_a_standing_ring():
    pm = _pm([(0.0, 0.0), (10.0, 0.0), (10.0, 40.0), (0.0, 40.0), (40.0, 0.0), (40.0, 40.0),
              (41.0, 0.0), (50.0, 0.0), (50.0, 40.0), (41.0, 40.0)],
             [("apron", "pav37", (0, 1, 2, 3)),
              ("groundside_pavement", "gap:7", (1, 4, 5, 2)),
              ("service_road", "small_roads:-7", (6, 7, 8, 9))])
    fixed = {0: 92.0, 1: 92.0, 2: 92.0, 3: 92.0, 6: 96.0, 7: 96.0, 8: 96.0, 9: 96.0}
    rows, _ = gf.gap_follow_rows(pm, LAW, fixed)
    # the own rim (the apron the piece welds to) binds nothing; the ribbon
    # shares no vertex with the piece, so it is no follower — it is STANDING
    # ground and binds the piece's vertices 4, 5 one metre from it (spec
    # §55 (13): a ribbon beside no piece is a ring like any other)
    assert sorted(r.terms[0][0] for r in rows) == [4, 5]
    assert {r.source.inputs for r in rows} == {("service_road:small_roads:-7",) * 2}
    assert rows[0].hi == pytest.approx(96.0 + role_cap(LAW, "service_road").longitudinal * 1.0)


def test_a_follower_ribbon_takes_the_same_rows():
    pm = _pm([(0.0, 0.0), (10.0, 0.0), (10.0, 40.0), (0.0, 40.0),
              (11.45, 0.0), (20.0, 0.0), (20.0, 40.0), (11.45, 40.0),
              (40.0, 0.0), (40.0, 40.0)],
             [("parking_lot", "dsf:pol10", (0, 1, 2, 3)),
              ("service_road", "small_roads:-7", (4, 5, 6, 7)),
              ("groundside_pavement", "gap:0", (5, 8, 9, 6))])
    rows, _ = gf.gap_follow_rows(pm, LAW, {0: 90.0, 1: 90.0, 2: 90.0, 3: 90.0})
    cap = role_cap(LAW, "parking_lot").longitudinal
    assert sorted(r.terms[0][0] for r in rows) == [4, 7]          # the RIBBON's vertices
    assert rows[0].hi == pytest.approx(90.0 + cap * 1.45)


def test_a_lot_vertex_holds_the_roads_level_within_the_lateral_window():
    """Spec §55 (3) 4 (owner RULINGS 2026-10-06d): a lot vertex 60 m from the
    road is within 0.02 x 60 = 1.2 m of the road's level there, and that
    level is its published target; a ramp part takes no lot row."""
    coords = [(0.0, 0.0), (10.0, 0.0), (10.0, 40.0), (0.0, 40.0),          # the road
              (11.45, 0.0), (70.0, 0.0), (70.0, 40.0), (11.45, 40.0),     # the lot
              (130.0, 0.0), (130.0, 40.0)]                                # the ramp beyond
    pm = _pm(coords, [("service_road", "route3", (0, 1, 2, 3)),
                      ("groundside_pavement", "gap:7/lot", (4, 5, 6, 7)),
                      ("groundside_pavement", "gap:7/ramp0", (5, 8, 9, 6))])
    fixed = {0: 96.0, 1: 96.0, 2: 100.0, 3: 100.0}
    rows, rep = gf.gap_follow_rows(pm, LAW, fixed)
    lot = {r.terms[0][0]: r for r in rows if r.source.ruling == gf.LOT_RULING}
    c_t = role_cap(LAW, "groundside_pavement").transverse
    assert sorted(lot) == [4, 5, 6, 7] and rep["lot_rows"] == 4
    assert (lot[5].lo, lot[5].hi) == (pytest.approx(96.0 - c_t * 60.0), pytest.approx(96.0 + c_t * 60.0))
    assert c_t * 60.0 == pytest.approx(1.2)
    assert rep["lot_targets"] == {4: 96.0, 5: 96.0, 6: 100.0, 7: 100.0}
    assert lot[5].source.inputs == ("service_road:route3",)
    assert ruling_head(lot[5]) in hard_rulings(LAW)
    # the follow rows are still there, on the two vertices within reach
    assert sorted(r.terms[0][0] for r in rows if r.source.ruling == gf.RULING) == [4, 7]
    # an uncut piece, a step part and a ramp take none
    for ref in ("gap:7", "gap:7/s0", "gap:7/ramp0"):
        pm2 = _pm(coords[:8], [("service_road", "route3", (0, 1, 2, 3)),
                               ("groundside_pavement", ref, (4, 5, 6, 7))])
        assert gf.gap_follow_rows(pm2, LAW, fixed)[1]["lot_rows"] == 0


def _st(xy, z, cls, ring):
    return types.SimpleNamespace(xy=xy, z=z, cls=cls, ring=ring)


def test_a_part_beside_a_knife_takes_no_bound_from_the_other_groups_ring():
    """Spec §55 (2) 5 (§55 (14) Q-E): the road west of the part is its own
    group's ring; the lot south of it stands within reach too, but the
    nearest station OF THAT RING is the other group's — its bound is
    refused and reported, and the vertex is not bound between the two."""
    coords = COORDS + [(11.45, -5.0), (20.0, -5.0), (20.0, -1.45), (11.45, -1.45)]
    pm = _pm(coords, [("service_road", "route3", (0, 1, 2, 3)),
                      ("groundside_pavement", "gap:7/s0", (4, 5, 6, 7)),
                      ("parking_lot", "dsf:pol10", (8, 9, 10, 11))])
    fixed = {0: 96.0, 1: 96.0, 2: 96.0, 3: 96.0, 8: 92.0, 9: 92.0, 10: 92.0, 11: 92.0}
    st = [_st((10.0, 0.0), 96.0, "road", "service_road:route3"),
          _st((10.0, 40.0), 96.0, "road", "service_road:route3"),
          _st((11.45, -1.45), 92.0, "lot", "parking_lot:dsf:pol10")]
    mine = gf.PartStations(st, frozenset({0, 1}), False)
    rows, rep = gf.gap_follow_rows(pm, LAW, fixed, {"gap:7/s0": mine})
    r4 = next(r for r in rows if r.terms[0][0] == 4)
    cap = role_cap(LAW, "service_road").longitudinal
    assert (r4.lo, r4.hi) == (pytest.approx(96.0 - cap * 1.45), pytest.approx(96.0 + cap * 1.45))
    assert rep["conflicts"] == []
    assert [(d["v"], d["ring"], d["z"]) for d in rep["declared"]] == [(4, "parking_lot:dsf:pol10", 92.0)]
    # one of its own group: bound between the two, as an uncut piece is
    own = gf.PartStations(st, frozenset({0, 1, 2}), False)
    rows3, rep3 = gf.gap_follow_rows(pm, LAW, fixed, {"gap:7/s0": own})
    assert rep3["declared"] == [] and len(rep3["conflicts"]) == 1
    # a part the cut handed no stations for, and no cut at all: unchanged
    assert len(gf.gap_follow_rows(pm, LAW, fixed, {"gap:9": own})[1]["conflicts"]) == 1
    assert len(gf.gap_follow_rows(pm, LAW, fixed)[1]["conflicts"]) == 1


def test_a_lot_that_meets_a_pad_takes_no_lot_row():
    """Spec §55 (3) 4 (§55 (14) Q-G): lot rows and targets only on a lot
    part whose own stations are roads and aprons alone."""
    coords = [(0.0, 0.0), (10.0, 0.0), (10.0, 40.0), (0.0, 40.0),
              (11.45, 0.0), (70.0, 0.0), (70.0, 40.0), (11.45, 40.0)]
    pm = _pm(coords, [("service_road", "route3", (0, 1, 2, 3)),
                      ("groundside_pavement", "gap:7/lot", (4, 5, 6, 7))])
    fixed = {0: 96.0, 1: 96.0, 2: 100.0, 3: 100.0}
    road = [_st((10.0, 0.0), 96.0, "road", "service_road:route3"),
            _st((10.0, 40.0), 100.0, "road", "service_road:route3")]
    for takes, n in ((True, 4), (False, 0)):
        ps = gf.PartStations(road, frozenset({0, 1}), takes)
        rep = gf.gap_follow_rows(pm, LAW, fixed, {"gap:7/lot": ps})[1]
        assert (rep["lot_rows"], len(rep["lot_targets"])) == (n, n), takes
    # a lot part the cut handed nothing for takes none
    assert gf.gap_follow_rows(pm, LAW, fixed, {"gap:8/lot": ps})[1]["lot_rows"] == 0


def test_a_piece_beside_a_basin_follows_the_rim_never_the_floor_or_the_wall_foot():
    """Spec §60 (9) R1: the cells behind a declared step (the floor / ramp
    roles and the wall void) are never follow neighbours; the wall void's rim
    edge at ground binds.  A floor 13 m down, 1.9 m from the piece."""
    from auto_patch_v2.emit import graded
    from auto_patch_v2.pipeline.late_stage import BEHIND_STEP
    from auto_patch_v2.planar import basins
    FLOOR_ROLES = graded.FLOOR_ROLES
    # the stage reads the two existing sets, no list of its own
    assert BEHIND_STEP == (frozenset(FLOOR_ROLES), basins.WALL_ROLE)
    assert basins.WALL_ROLE == graded.VOID_ROLE
    # floor 0..3 | wall void 1,8,9,2 (two parts, split at 12,13) | piece 4..7
    # stands 1.2 m off the rim 8-9 and 1.7 m off the foot 1-2
    coords = [(0.0, 0.0), (10.0, 0.0), (10.0, 40.0), (0.0, 40.0),
              (11.7, 0.0), (40.0, 0.0), (40.0, 40.0), (11.7, 40.0),
              (10.5, 0.0), (10.5, 40.0), (10.0, 20.0), (10.5, 20.0)]
    faces = [("tunnel_trench", "basin_floor:4", (0, 1, 10, 2, 3)),
             ("retaining_wall", "basin_wall:4", (1, 8, 11, 10)),
             ("retaining_wall", "basin_wall:4#1", (10, 11, 9, 2)),
             ("groundside_pavement", "gap:1/s3", (4, 5, 6, 7))]
    floor, ground = -9.68, 3.96
    fixed = {0: floor, 1: floor, 2: floor, 3: floor, 10: floor,
             8: ground, 9: ground, 11: ground}
    rows, rep = gf.gap_follow_rows(_pm(coords, faces), LAW, fixed,
                                   behind_step=BEHIND_STEP)
    by = {r.terms[0][0]: r for r in rows}
    assert sorted(by) == [4, 7] and rep["conflicts"] == []
    cap = role_cap(LAW, "groundside_pavement").longitudinal
    for v in (4, 7):                       # the rim's level, the rim's ring alone
        assert by[v].lo == pytest.approx(ground - cap * 1.2)
        assert by[v].hi == pytest.approx(ground + cap * 1.2)
        assert set(by[v].source.inputs) == {"retaining_wall:basin_wall:4"}
    # every floor role is behind the step: a piece beside a ramp alone takes no row
    for role in FLOOR_ROLES:
        pm = _pm(COORDS, [(role, "ramp:0", (0, 1, 2, 3)),
                          ("groundside_pavement", "gap:7", (4, 5, 6, 7))])
        assert gf.gap_follow_rows(pm, LAW, {0: -3.0, 1: -3.0, 2: 0.0, 3: 0.0},
                                  behind_step=BEHIND_STEP)[0] == []


def test_a_pad_rings_reach_covers_the_stand_off_and_a_roads_does_not():
    """Spec §62 (3) R-D rule 1 (owner RULINGS 2026-10-09d (1) / 09f): a part
    vertex 2.6 m off a PAD's rim — past the plain reach, inside the piece's
    stand-off plus its noding margin — is bound to the pad's level; the same
    vertex 2.6 m off a ROAD takes no row."""
    from auto_patch_v2.law.tables import gap_standoff_m
    plain, pad = gf.reach_m(LAW), gf.reach_m(LAW, pad=True)
    ident = LAW.tables.emit.identity.min_distinct_spacing_m
    assert pad == pytest.approx(gap_standoff_m(LAW) + snap_margin_m(LAW) + 2 * ident)
    assert plain < 2.6 < pad
    coords = COORDS[:4] + [(12.6, 0.0), (40.0, 0.0), (40.0, 40.0), (12.6, 40.0)]
    fixed = {0: 90.0, 1: 90.0, 2: 90.0, 3: 90.0}
    piece = ("groundside_pavement", "gap:0", (4, 5, 6, 7))
    rows, rep = gf.gap_follow_rows(_pm(coords, [("building", "building5", (0, 1, 2, 3)), piece]),
                                   LAW, fixed)
    knife = LAW.tables.structures.building_pad.groundside_cutback_m + snap_margin_m(LAW)
    cap = min(role_cap(LAW, "groundside_pavement").longitudinal,
              role_cap(LAW, "building").longitudinal)
    assert sorted(r.terms[0][0] for r in rows) == [4, 7]
    assert rows[0].hi - 90.0 == pytest.approx(cap * (2.6 - knife))
    rows_r, _ = gf.gap_follow_rows(_pm(coords, [("service_road", "route3", (0, 1, 2, 3)), piece]),
                                   LAW, fixed)
    assert rows_r == []
