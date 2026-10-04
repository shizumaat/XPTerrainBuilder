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
    by = {r.v: r for r in rows}
    assert sorted(by) == [4, 7] and rep["rows"] == 2 and rep["conflicts"] == []
    assert by[4].lo == pytest.approx(96.0 - cap * 1.45) and by[4].hi == pytest.approx(96.0 + cap * 1.45)
    assert by[7].lo == pytest.approx(100.0 - cap * 1.45)
    assert ruling_head(rows[0]) in hard_rulings(LAW)
    # an UNFIXED ring binds nothing; a fixed piece vertex takes no row
    assert gf.gap_follow_rows(pm, LAW, {0: 96.0})[0] == []
    assert sorted(r.v for r in gf.gap_follow_rows(pm, LAW, {**fixed, 4: 96.0})[0]) == [7]


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
    r4 = next(r for r in rows if r.v == 4)
    assert 92.0 < r4.lo < r4.hi < 96.0
    c = rep["conflicts"][0]
    assert (c["upper"], c["lower"]) == ("service_road:route3", "parking_lot:dsf:pol10")
    assert (c["upper_m"], c["lower_m"]) == (96.0, 92.0) and c["gap_m"] > 3.0


def test_the_own_rim_and_a_follower_ribbon_bind_nothing():
    pm = _pm([(0.0, 0.0), (10.0, 0.0), (10.0, 40.0), (0.0, 40.0), (40.0, 0.0), (40.0, 40.0),
              (41.0, 0.0), (50.0, 0.0), (50.0, 40.0), (41.0, 40.0)],
             [("apron", "pav37", (0, 1, 2, 3)),
              ("groundside_pavement", "gap:7", (1, 4, 5, 2)),
              ("service_road", "small_roads:-7", (6, 7, 8, 9))])
    fixed = {0: 92.0, 1: 92.0, 2: 92.0, 3: 92.0, 6: 96.0, 7: 96.0, 8: 96.0, 9: 96.0}
    rows, _ = gf.gap_follow_rows(pm, LAW, fixed)
    assert rows == []
