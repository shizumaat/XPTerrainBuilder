"""STOREY PADS (#2062, RULINGS 2026-11-13w; spec ``2062-storey-shell-spec``
Amendment A2): a split-level building stands on one held pad with one rigid
level per storey (``planar/storey_pad``); its levels' plans are read from
its wall feet alone, split at the corner bisector (``airport/split_level``);
outside its groundside runs at the lowest level the BACK CUT takes the
ground down to the block and a KERB declares the step to the higher lot;
every level's riser is a declared step (``constraints/riser``).
Synthetic: no pack, no airport."""
from __future__ import annotations

import dataclasses as _dc
import types

import numpy as np
import pytest
from auto_patch_v2.airport.split_level import SplitLevel, _covered_parts, _level_plans
from auto_patch_v2.law import Law
from auto_patch_v2.model.storey_shell import StoreyRun, StoreyShell
from auto_patch_v2.planar import storey_pad as SP
from shapely.geometry import LineString, Point, Polygon, box

LAW = Law.for_airport("SYNT")

#: a 40 x 30 box, its runs counter-clockwise in authored (x, z), outward normals
_RUNS = [((0, 0), (40, 0)), ((40, 0), (40, 30)), ((40, 30), (0, 30)), ((0, 30), (0, 0))]
_NORMALS = [(0, -1), (1, 0), (0, 1), (-1, 0)]


def test_a_wing_walled_at_its_lower_level_is_the_lower_level_inside():
    """A2 (1): floors are no witness of ground -- a wing whose long walls
    stand on level 0 and whose end wall stands on level 6 (an upper floor
    over it is a deck) is level 0 inside; only the end wall's strip is 6."""
    plan = box(0, 0, 40, 12)
    runs = [((0, 0), (40, 0)), ((40, 0), (40, 12)), ((40, 12), (0, 12)), ((0, 12), (0, 0))]
    p0, p1 = _level_plans(plan, (0.0, 6.0), runs, _NORMALS, [0, 1, 0, 0], 3.0, 3.0)
    assert p0.contains(box(3, 3, 36, 9)) and p1.within(box(37, 0, 40, 12).buffer(1e-6))


def test_the_corner_of_two_levels_is_split_by_its_bisector():
    """A2 (1): where the wall-foot strips of two outline-adjacent runs of
    different levels overlap, the bisector through their common vertex
    splits the overlap -- each keeps the half nearer its own wall."""
    plan = box(0, 0, 40, 30)
    p0, p1 = _level_plans(plan, (0.0, 6.0), _RUNS, _NORMALS, [0, 0, 1, 0], 3.0, 3.0)
    assert p1.area == pytest.approx(40 * 3 - 2 * 4.5)
    assert p1.contains(Point(38.0, 29.5)) and p0.contains(Point(39.5, 28.0))


def test_every_part_of_the_covered_plan_is_read_largest_first():
    """A2 (5): two parts of one family's plan are two records (the pit
    reads part 0, the largest)."""
    v = np.array([(0, 0, 0), (40, 0, 0), (40, 0, 30), (0, 0, 30),
                  (100, 0, 0), (110, 0, 0), (110, 0, 10), (100, 0, 10)], float)
    t = np.array([(0, 2, 1), (0, 3, 2), (4, 6, 5), (4, 7, 6)])
    parts = _covered_parts(v, t, 1.0, 10.0)
    assert [round(p.area) for p in parts] == [1200, 100]


#: the box's runs CLOCKWISE (the building on their right): S, W, N, E
_CW = [((40, 0), (0, 0)), ((0, 0), (0, 30)), ((0, 30), (40, 30)), ((40, 30), (40, 0))]
_FEET = [0.0, 6.0, 0.0, 0.0]


def _shell_level() -> SplitLevel:
    """A frame SplitLevel over the 40 x 30 box: S airside, W at 6, N and E
    groundside at 0."""
    runs = tuple((LineString(r), f) for r, f in zip(_CW, _FEET, strict=True))
    plan = box(0, 0, 40, 30)
    return SplitLevel("w", ("w",), ("objects/x.obj",), plan, 0.0, 6.0, (), (), 0.0, 0.0,
                      (20.0, 15.0), plan, runs, (0.0, 6.0), (0, 1, 0, 0), (),
                      (plan, Polygon()), 0)


def test_the_back_cut_is_chained_clipped_at_a_road_and_never_in_front_of_an_upper_run():
    """A2 (3): the back cut runs ``split_level_back_cut_m`` outside the
    groundside runs at the lowest level, chained (the corner between two
    of them is cut); a mapped road clips it (the road keeps its profile,
    the run says ``road``); the front of a run at another level is never
    cut."""
    sl = _shell_level()
    road = box(15, 32, 20, 40)
    yields = {"structure": None, "pit": None, "pad": None, "airside": box(-50, -50, 90, 0),
              "road": road}
    air = SP.prep(box(-50, -50, 90, 0))
    T, cuts = SP._back_cut(sl, sl.plan, 5.0, yields, air, 0.5)
    assert not T.intersects(road.buffer(-1e-6))
    assert T.contains(Point(42.5, 32.5))                 # the N-E corner, chained
    assert not T.contains(Point(-2.0, 15.0))             # the W run stands at 6
    assert T.area == pytest.approx(5 * 40 + 5 * 30 + 25 - 5 * 3, abs=1e-6)
    assert cuts[2][1] == ("road",) and cuts[3][1] == ()
    assert 0 not in cuts and 1 not in cuts               # airside, upper: no back cut


def _record(T, cut_runs) -> StoreyShell:
    plan = box(0, 0, 40, 30)
    runs = tuple(StoreyRun(r, f, 0 if f == 0.0 else 1, False, k == 0,
                           *((5.0, ()) if k in cut_runs else (None, ())))
                 for k, (r, f) in enumerate(zip(_CW, _FEET, strict=True)))
    return StoreyShell("w", ("w",), ("objects/x.obj",), "blk", (0.0, 6.0), 0, ("blk", "blk/p1"),
                       (box(3, 0, 40, 30), box(0, 0, 3, 30)), runs,
                       tuple(plan.exterior.coords)[:-1], (), (20.0, 15.0), back_cut=T)


def test_the_kerb_stands_on_the_back_cuts_outer_edge_only_beside_groundside_ground():
    """A2 (3): the kerb is the riser-wide band inside the pad along the back
    cut's outer edge where a groundside value face lies beyond it (none
    over the void, none within the airside's riser width); its wall record
    is ``planar/foot_kerb``'s shape, the high side the lot's, as high as
    the top level plus the visual bar."""
    T = box(40, 0, 45, 35).union(box(0, 30, 45, 35))
    P = box(0, 0, 40, 30).union(T)
    rec = _record(T, (2, 3))
    lot = box(45, 10, 60, 40).union(box(20, 35, 60, 40))      # E and N; void at N-W
    out = SP._with_kerb(rec, P, box(0, 0, 40, 30), 1.0, 0.5, lot, box(0, -20, 40, 0), [],
                        LAW)
    assert out.kerb is not None and out.kerb.within(P.buffer(1e-6))
    assert out.kerb.distance(Point(10, 34.5)) > 0.5             # no ground beyond: no kerb
    assert out.kerb.contains(Point(44.5, 20)) and out.kerb.contains(Point(30, 34.5))
    assert not out.kerb.intersects(box(0, -20, 45, 1.0))        # off the airside's riser
    for k in out.kerbs:
        assert set(k) == {"ring", "upper", "height_m"}
        assert k["height_m"] == pytest.approx(6.0 + float(LAW.tables.emit.cockpit.visual_m))
        for line in k["upper"]:
            assert all(abs(x - 45) < 1e-6 or abs(y - 35) < 1e-6 for x, y in line)


def test_the_kerb_is_carved_before_the_level_strips():
    """A2 (3): ``low_level._shell_split`` carves the kerb out of the pad
    first (``<pad>#kerb#strip``, its records on the held pad), then splits
    the rest at the storeys."""
    from auto_patch_v2.model.registries import Registries
    from auto_patch_v2.planar import low_level as LL
    from auto_patch_v2.planar.overlay import Region
    from shapely.strtree import STRtree
    P = box(0, 0, 45, 30)
    K = box(44, 0, 45, 30)
    shell = _dc.replace(_record(box(40, 0, 45, 30), (3,)), kerb=K, kerbs=(
        {"ring": list(K.exterior.coords), "upper": [[(45, 0), (45, 30)]], "height_m": 6.5},))
    reg = Registries()
    reg.held["blk"] = {"unit": "blk", "verdict": "storey_shell"}
    region = Region("building", "blk", P, None, None, "airside", "cell")
    air = [box(0, -20, 45, 0)]
    out = LL._shell_split("blk", [region], shell, air, STRtree(air), LAW, 0.5, reg, [region])
    kerb = [r.polygon for r in out if r.ref == "blk#kerb#strip"]
    assert sum(q.area for q in kerb) == pytest.approx(30.0)
    assert {r.ref for r in out} >= {"blk", "blk/p1", "blk/p1#strip"}
    assert all(not r.polygon.intersects(K.buffer(-1e-6)) for r in out
               if r.ref != "blk#kerb#strip")
    assert reg.held["blk"]["kerbs"][0]["height_m"] == 6.5
    assert reg.landings["blk/p1"]["shell"] == "w"


def test_a_shell_levels_riser_is_a_declared_step_and_a_plain_upper_level_is_not():
    """A2 (2): every level of a storey shell (its landing carries
    ``shell``), an UPPER level too, is spanned by its own landing rows only
    -- a lot ceiling across its riser is withdrawn; a non-shell upper level
    is untouched."""
    from auto_patch_v2.constraints import riser
    from auto_patch_v2.model.constraints import Diff, Linear, Source

    def face(i, ref, role, ring):
        return types.SimpleNamespace(id=i, ref=ref, role=role, ring=ring, holes=())
    faces = {0: face(0, "b", "building", (1, 2)), 1: face(1, "b/p1#strip", "building", (2, 3)),
             2: face(2, "b/p1", "building", (3, 4)), 3: face(3, "lot", "parking_lot", (4, 1))}
    src = Source("pavement_ceiling", "r")
    land = Source("landing_rows", "r", ("landing:b/p1", "b/p1", "platform:b"))
    rows = [Diff(4, 1, 0.01, 1.0, src),                    # the lot ring across the riser
            Diff(3, 4, 0.01, 1.0, src),                    # on the upper level: kept
            Linear(((3, 1.0), (1, -1.0)), 6.0, 6.0, land)]  # the landing row: kept
    for shell, kept in (("w", rows[1:]), (None, rows)):
        rec = {"block": "b", "kind": "upper_level", "y": 6.0}
        if shell:
            rec["shell"] = shell
        pm = types.SimpleNamespace(faces=faces, ring_vertices=lambda ring: ring,
                                   registries=types.SimpleNamespace(landings={"b/p1": rec}))
        assert riser.riser_exempt(list(rows), pm, {}) == kept
