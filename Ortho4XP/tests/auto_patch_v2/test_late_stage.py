"""Twins of the §53 (9) LAST STAGE's population (``pipeline/stage_one_map``):
the followers are the gap pieces and the mapped-road ribbons along them,
less every vertex a leader carries; the constants are the base map's levels
by the coordinate join; a vertex neither has is counted, never guessed."""
from __future__ import annotations

import types

from auto_patch_v2.classify.roles import Cell
from auto_patch_v2.pipeline import stage_one_map as som


def _pm(coords, faces):
    return types.SimpleNamespace(
        vertices=[types.SimpleNamespace(xy=xy) for xy in coords],
        faces={i: types.SimpleNamespace(id=i, role=role, ref=ref, ring=tuple(ring), holes=())
               for i, (role, ref, ring) in enumerate(faces)})


#   0---1---2---3---4      apron | gap | ribbon | lot, a far ribbon beyond
#   |   |   |   |   |
#   5---6---7---8---9
COORDS = [(float(x), 1.0) for x in range(5)] + [(float(x), 0.0) for x in range(5)] \
    + [(10.0, 0.0), (11.0, 0.0), (11.0, 1.0), (10.0, 1.0)]
FACES = [("apron", "pav1", (0, 1, 6, 5)),
         ("groundside_pavement", "gap:0", (1, 2, 7, 6)),
         ("service_road", "small_roads:-7", (2, 3, 8, 7)),
         ("parking_lot", "dsf:pol10", (3, 4, 9, 8)),
         ("service_road", "small_roads:-9", (10, 11, 12, 13)),
         ("service_road", "route3", (4, 9, 10, 13))]


def test_followers_are_the_pieces_and_the_ribbons_along_them_less_the_leaders():
    free, rep = som.late_followers(_pm(COORDS, FACES))
    # the gap face and the ribbon sharing an edge with it; the apron's and the
    # lot's vertices are HELD; the far ribbon and the 1206 route never follow
    assert free == {2, 7}
    assert rep["gap_faces"] == 1 and rep["follower_ribbon_refs"] == ["small_roads:-7"]
    assert rep["held_on_a_leader"] == 4


def test_a_soft_role_does_not_hold_a_vertex():
    faces = FACES[:3] + [("graded_strip", "adjacent_ground:taxi:E:zone2#1", (3, 4, 9, 8))]
    free, _ = som.late_followers(_pm(COORDS, faces), frozenset({"graded_strip"}))
    assert free == {2, 3, 7, 8}
    free, _ = som.late_followers(_pm(COORDS, faces))
    assert free == {2, 7}


def test_no_gap_piece_no_follower():
    free, rep = som.late_followers(_pm(COORDS, [f for f in FACES if f[1] != "gap:0"]))
    assert free == set() and rep["follower_ribbons"] == 0


def test_the_constants_are_the_base_levels_by_coordinate():
    full = _pm(COORDS, FACES)
    base_coords = [COORDS[i] for i in (9, 0, 5, 1, 6, 2)] + [(99.0, 99.0)]
    base = _pm(base_coords, [])
    z = [9.0, 0.0, 5.0, 1.0, 6.0, 2.0, 77.0]
    fixed, rep = som.late_fixed(base, z, full, {2, 7})
    assert fixed == {9: 9.0, 0: 0.0, 5: 5.0, 1: 1.0, 6: 6.0}      # 2 is a follower
    assert rep["base_unmapped"] == 1 and rep["fixed"] == 5
    assert rep["unjoined"] == len(COORDS) - 5 - 2


def test_gap_free_drops_the_pieces_only():
    def cell(i, role, ref):
        return Cell(i, role, ref, ((0, 0), (1, 0), (1, 1)), (), None, None, "groundside", role, {})
    cl = types.SimpleNamespace(cells=(cell(0, "apron", "pav1"),
                                      cell(1, "groundside_pavement", "gap:0"),
                                      cell(2, "service_road", "small_roads:-7")))
    assert som.gap_free(types.SimpleNamespace(cells=cl.cells[:1])) is None
    import dataclasses as dc

    @dc.dataclass
    class CL:
        cells: tuple
    got = som.gap_free(CL(cl.cells))
    assert [c.ref for c in got.cells] == ["pav1", "small_roads:-7"]
