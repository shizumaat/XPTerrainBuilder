"""Twins of the §53 (9) LAST STAGE's population (``pipeline/stage_one_map``):
the followers are the gap pieces and the mapped-road ribbons along them,
less every vertex a leader carries; the constants are the base map's levels
by the coordinate join; a vertex neither has is counted, never guessed."""
from __future__ import annotations

import types

from auto_patch_v2.classify.roles import Cell
from auto_patch_v2.pipeline import stage_one_map as som


def _pm(coords, faces):
    """A map whose face rings are cycles of EDGE ids, as ``PlanarMap``'s are
    (an edge = an unordered vertex pair, numbered as first met)."""
    eid: dict = {}
    ends: dict = {}

    def edge(a, b):
        k = frozenset((a, b))
        if k not in eid:
            eid[k] = 1000 + len(eid)
            ends[eid[k]] = (a, b)
        return eid[k]
    fs = {}
    for i, (role, ref, ring) in enumerate(faces):
        n = len(ring)
        fs[i] = types.SimpleNamespace(
            id=i, role=role, ref=ref, holes=(),
            ring=tuple(edge(ring[k], ring[(k + 1) % n]) for k in range(n)))
    return types.SimpleNamespace(
        vertices={i: types.SimpleNamespace(xy=xy) for i, xy in enumerate(coords)},
        faces=fs,
        ring_vertices=lambda cyc: tuple(v for e in cyc for v in ends[e]))


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


def test_a_row_with_no_unknown_is_not_the_last_stages():
    """A pin restated on the full map never moves an earlier stage's level,
    and a law row between two constants is the earlier stage's own."""
    from auto_patch_v2.model.constraints import ConstraintSet, Diff, Pin, Source
    src = Source("twin", "twin (2026-10-04)", ())
    rows = [Pin(v=1, z=99.0, source=src), Pin(v=7, z=50.0, source=src),
            Diff(a=1, b=2, cap=0.01, d=10.0, source=src),
            Diff(a=2, b=7, cap=0.01, d=10.0, source=src)]
    cs, dropped = som.late_constraints(ConstraintSet.from_rows(rows), {1: 10.0, 2: 11.0})
    kept = list(cs.rows())
    assert dropped == {"Pin": 1, "Diff": 1}
    assert sorted(som.row_vertices(r) for r in kept) == [(2, 7), (7,)]


def test_a_new_node_on_a_standing_edge_takes_the_edges_own_level():
    base = _pm([(0.0, 0.0), (10.0, 0.0), (10.0, 10.0)], [("parking_lot", "dsf:pol10", (0, 1, 2))])
    base.edges = {k: types.SimpleNamespace(a=a, b=b)
                  for k, (a, b) in enumerate([(0, 1), (1, 2), (2, 0)])}
    full = _pm([(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (2.5, 0.0), (50.0, 50.0)], [])
    z = {0: 100.0, 1: 104.0, 2: 90.0}
    fixed = {0: 100.0, 1: 104.0, 2: 90.0}
    rep = som.late_rim_levels(base, z, full, fixed, set(), 0.01)
    assert fixed[3] == 101.0 and 4 not in fixed
    assert rep == {"rim_nodes": 2, "on_a_base_edge": 1, "off_edge": 1}


def test_a_yielding_pin_on_a_follower_is_released():
    from auto_patch_v2.model.constraints import ConstraintSet, Pin, Source
    join = Source("road_coverage_join", "roads.coverage_edge join (27a (10))", ())
    other = Source("twin", "tunnel.bore_datum_m (x)", ())
    rows = [Pin(v=7, z=87.51, source=join), Pin(v=8, z=50.0, source=other)]
    cs, dropped = som.late_constraints(ConstraintSet.from_rows(rows), {1: 10.0},
                                       frozenset({"roads.coverage_edge join"}))
    assert [r.v for r in cs.rows()] == [8]
    assert dropped == {"Pin (yielding, on a follower)": 1}
    # without the register nothing is released
    assert len(list(som.late_constraints(ConstraintSet.from_rows(rows), {1: 10.0})[0].rows())) == 2


def test_a_follower_one_emitted_point_with_a_constant_keeps_its_base_level():
    """Spec §53 (18): the emitter merges two vertices closer than the
    identity spacing, and the survivor may be the follower — it is then the
    standing ring's emitted point and must not move."""
    coords = COORDS + [(3.4, 1.0)]                 # 0.4 m from lot vertex 3
    full = _pm(coords, FACES)
    k = len(coords) - 1
    base = _pm([coords[3], coords[k], coords[2]], [])
    z = [3.0, 3.4, 2.0]
    fixed, rep = som.late_fixed(base, z, full, {2, 7, k}, 0.5)
    assert fixed == {3: 3.0, k: 3.4} and rep["held_at_identity"] == 1
    # a follower further than the spacing stays an unknown (vertex 2, 1 m off)
    assert 2 not in fixed
    # without the spacing nothing is held
    fixed0, rep0 = som.late_fixed(base, z, full, {2, 7, k})
    assert fixed0 == {3: 3.0} and rep0["held_at_identity"] == 0


def test_a_ribbon_touching_a_piece_at_one_vertex_follows():
    """Spec §53 (18): pass C nodes a piece's corner into the ring of a
    ribbon it only touches — that ribbon is re-shaped by the piece, so it is
    a follower, never standing ground."""
    #   a second ribbon whose ring carries gap vertex 2 and no gap edge
    coords = COORDS + [(2.0, 2.0), (3.0, 2.0)]
    faces = FACES + [("service_road", "small_roads:-8", (2, 15, 14))]
    free, rep = som.late_followers(_pm(coords, faces))
    assert rep["follower_ribbon_refs"] == ["small_roads:-7", "small_roads:-8"]
    assert {14, 15} <= free


def test_a_ceiling_between_two_unknowns_is_re_tiered_and_one_on_a_constant_is_not():
    """Spec §55 (5): the two pavement ceilings on rows whose vertices are ALL
    last-stage unknowns rank with the stage's own rows; the law text stays."""
    from auto_patch_v2.constraints.ceiling import RULING as CEIL
    from auto_patch_v2.constraints.pavement_cap import RULING as FALLBACK
    from auto_patch_v2.law import Law
    from auto_patch_v2.model.constraints import ConstraintSet, Diff, Source
    from auto_patch_v2.solve.design_roles import hard_rulings, ruling_head
    from auto_patch_v2.solve.feasibility import tier_of
    rows = [Diff(a=7, b=8, cap=0.05, d=10.0, source=Source("pavement_ceiling", CEIL, ())),
            Diff(a=2, b=7, cap=0.05, d=10.0, source=Source("pavement_ceiling", CEIL, ())),
            Diff(a=7, b=8, cap=0.08, d=10.0, source=Source("pavement_road_cap", FALLBACK, ())),
            Diff(a=7, b=8, cap=0.08, d=10.0, source=Source("roads", "other law (x)", ()))]
    heads = frozenset(r.split("(")[0].strip() for r in (CEIL, FALLBACK))
    cs, rep = som.late_constraints(ConstraintSet.from_rows(rows), {2: 11.0}, retier_heads=heads)
    kept = list(cs.rows())
    assert rep == {"re-tiered (ceiling, all unknowns)": 2}
    got = sorted(ruling_head(r) for r in kept)
    assert got == sorted(["other law", CEIL.split("(")[0].strip(),
                          CEIL.split("(")[0].strip() + som.LAST_STAGE_SUFFIX,
                          FALLBACK.split("(")[0].strip() + som.LAST_STAGE_SUFFIX])
    law = Law.for_airport("HECA")
    tiers, hard = tier_of(law), hard_rulings(law)
    ground = max(tiers.values())
    for r in (CEIL, FALLBACK):
        new = ruling_head(types.SimpleNamespace(source=Source("g", som.last_stage_head(r), ())))
        assert new in hard and tiers[new] == ground          # groundside, hard
        assert tiers[r.split("(")[0].strip()] < ground       # the law's own rank stands
        assert som.last_stage_head(r).endswith(r[r.index("("):])   # the text is kept


def test_stations_are_standing_rings_within_reach_at_the_pieces_cap():
    """Spec §55 (1), (13): a ring within the follow reach of the piece is a
    station source at the PIECE's cap; a mapped-road ribbon welded to the
    piece is a follower and is none; one beside no piece is standing."""
    from shapely.geometry import box

    from auto_patch_v2.law import Law
    from auto_patch_v2.law.tables import role_cap
    from auto_patch_v2.pipeline.late_stage import late_stations
    law = Law.for_airport("HECA")
    coords = [(0.0, 0.0), (10.0, 0.0), (10.0, 40.0), (0.0, 40.0),        # apron, 1.45 m west
              (40.0, 0.0), (48.0, 0.0), (48.0, 40.0), (40.0, 40.0),      # ribbon welded east
              (11.45, 41.0), (40.0, 41.0), (40.0, 47.0), (11.45, 47.0),  # ribbon 1 m north
              (300.0, 0.0), (310.0, 0.0), (310.0, 40.0), (300.0, 40.0)]  # a pad far away
    faces = [("apron", "pav1", (0, 1, 2, 3)),
             ("service_road", "small_roads:-7", (4, 5, 6, 7)),
             ("service_road", "small_roads:-9", (8, 9, 10, 11)),
             ("building", "building1", (12, 13, 14, 15))]
    eid, ends = {}, {}

    def edge(a, b):
        k = frozenset((a, b))
        if k not in eid:
            eid[k] = 1000 + len(eid)
            ends[eid[k]] = types.SimpleNamespace(a=a, b=b)
        return eid[k]
    fs = {i: types.SimpleNamespace(id=i, role=role, ref=ref, holes=(),
                                   ring=tuple(edge(r[k], r[(k + 1) % 4]) for k in range(4)))
          for i, (role, ref, r) in enumerate(faces)}
    pm = types.SimpleNamespace(
        vertices={i: types.SimpleNamespace(xy=xy) for i, xy in enumerate(coords)},
        faces=fs, edges=ends,
        ring_vertices=lambda cyc: tuple(v for e in cyc for v in (ends[e].a, ends[e].b)))
    z = {i: 90.0 + (i // 4) for i in range(16)}
    (st,) = late_stations(pm, z, [box(11.45, 0.0, 40.0, 40.0)], law, "groundside_pavement")
    rings = {s.ring for s in st}
    assert rings == {"apron:pav1", "service_road:small_roads:-9"}
    cap = role_cap(law, "groundside_pavement").longitudinal
    assert {s.cap for s in st} == {cap}
    assert {s.cls for s in st if s.ring == "apron:pav1"} == {"apron"}
    assert {s.cls for s in st if s.ring.endswith("-9")} == {"road"}


def test_the_build_enters_the_last_stage_once_and_only_with_a_gap_piece():
    """Spec §55 (9) THE NO-OP IS STRUCTURAL: ``pipeline/build.build`` calls
    ``run_late_stage`` at ONE site, under the one condition that the
    classification carried a gap piece (``gap_free(cl)`` is not ``None``) —
    and ``gap_free`` of a classification without one is ``None``."""
    import ast
    import inspect

    import importlib
    _build = importlib.import_module("auto_patch_v2.pipeline.build")
    tree = ast.parse(inspect.getsource(_build))
    calls, guarded = [], []

    def walk(node, under):
        for child in ast.iter_child_nodes(node):
            u = under
            if isinstance(child, ast.If) and "cl_gaps is not None" in ast.unparse(child.test):
                u = True
            if isinstance(child, ast.Call) and getattr(child.func, "id", "") == "run_late_stage":
                calls.append(child)
                guarded.append(u)
            walk(child, u)
    walk(tree, False)
    assert len(calls) == 1 and guarded == [True]
    src = inspect.getsource(_build.build)
    assert "cl_gaps, _cl_base = None, gap_free(cl)" in src
    plain = types.SimpleNamespace(cells=(
        Cell(0, "apron", "pav1", ((0, 0), (1, 0), (1, 1)), (), None, None, "airside", "apron", {}),))
    assert som.gap_free(plain) is None
