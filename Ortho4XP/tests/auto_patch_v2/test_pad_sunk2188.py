"""#2188 item 2: a pad below the airside it touches is a HELD terrace —
read from its area DEM or from its objects' authored height, never from
the rim DEM alone (``classify/pad_sunk``)."""
from __future__ import annotations

import types

import pytest
from shapely.geometry import Polygon

from auto_patch_v2.classify.pad_sunk import SUNK_KEY, _authored_top_m, hold_sunk_cells
from auto_patch_v2.classify.roles import Cell
from auto_patch_v2.law import Law


def _rect(x0, y0, x1, y1):
    return ((x0, y0), (x1, y0), (x1, y1), (x0, y1))


class _Dem:
    """Apron ground at ``hi`` for y >= 99, the pad's ground ``lo`` below."""

    def __init__(self, hi: float, lo: float):
        self.hi, self.lo = hi, lo

    def z(self, x: float, y: float) -> float:
        return self.hi if y >= 99.0 else self.lo


def _frame():
    # (lon, lat) -> (x, y): identity, so a cluster ring (lat, lon) is (y, x)
    return types.SimpleNamespace(entry=lambda: (lambda lon, lat: (lon, lat)))


def _cluster(x0, y0, x1, y1, tops, areas):
    rows = tuple(("o.obj", 1.0, 0.0, a) for a in areas)
    ev = types.SimpleNamespace(tops=tuple(tops), rows=rows)
    ring = [(y0, x0), (y0, x1), (y1, x1), (y1, x0)]
    return types.SimpleNamespace(rings=(ring,), evidence=ev)


def _airport(dem, clusters=()):
    return types.SimpleNamespace(dem=dem, frame=_frame(), clusters=tuple(clusters))


def _apron():
    return [Cell(0, "apron", "pav1", _rect(0.0, 100.0, 200.0, 200.0), (), None, None,
                 "airside", "apron", {})]


PAD = Polygon(_rect(50.0, 40.0, 150.0, 100.0))      # its north rim ON the apron


def _hold(dem, law, clusters=()):
    pad = Cell(1, "building", "b1", tuple(PAD.exterior.coords)[:-1], (), None, None,
               "airside", "building", {})
    cells, n = hold_sunk_cells(_apron() + [pad], _airport(dem, clusters), law)
    return [(c.ref, Polygon(c.ring, c.holes), c.evidence) for c in cells
            if c.role == "building"], n


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


def test_a_pad_on_the_apron_level_stays_welded(law):
    out, n = _hold(_Dem(375.0, 374.0), law)
    assert n == 0 and out[0][2] == {} and out[0][1].equals(PAD)


def test_a_pad_whose_own_ground_stands_a_terrace_below_is_held(law):
    out, n = _hold(_Dem(375.0, 360.0), law)
    assert n == 1
    (ref, q, ev), = out
    gap = float(law.tables.emit.design.pad_frontage_m)
    assert ref == "b1" and q.bounds[3] < 100.0 - gap        # yielded, beyond the radius
    assert ev[SUNK_KEY]["airside_m"] == 375.0 and ev[SUNK_KEY]["dem_m"] < 375.0


def test_a_pad_above_the_apron_is_not_this_rule(law):
    _out, n = _hold(_Dem(360.0, 375.0), law)
    assert n == 0


def test_the_authored_height_alone_holds_a_pad(law):
    # flat ground (the DEM shows no step), objects authored 15 m under their zero
    deep = _cluster(60.0, 50.0, 140.0, 90.0, (-15.5, -16.0), (300.0, 100.0))
    out, n = _hold(_Dem(375.0, 375.0), law, [deep])
    assert n == 1 and out[0][2][SUNK_KEY]["authored_top_m"] == pytest.approx(-15.625)


def test_an_at_grade_object_keeps_the_weld(law):
    slab = _cluster(60.0, 50.0, 140.0, 90.0, (0.03, -1.0), (300.0, 100.0))
    _out, n = _hold(_Dem(375.0, 375.0), law, [slab])
    assert n == 0


def test_a_cluster_mostly_outside_the_pad_is_not_its_witness():
    outside = _cluster(140.0, 50.0, 300.0, 90.0, (-20.0,), (100.0,))
    assert _authored_top_m(PAD, [outside], _frame().entry()) is None


def test_the_held_levels_ride_the_cells():
    from auto_patch_v2.classify.pad_sunk import sunk_levels
    held = Cell(0, "building", "b1", _rect(0, 0, 1, 1), (), None, None, "airside", "building",
                {SUNK_KEY: {"airside_m": 375.0, "dem_m": 360.4, "authored_top_m": -15.0}})
    plain = Cell(1, "building", "b2", _rect(0, 0, 1, 1), (), None, None, "airside", "building", {})
    assert sunk_levels([held, plain]) == {"b1": 360.4}


def test_a_held_pad_leaves_its_cluster_plane():
    from auto_patch_v2.constraints.cluster_pad import _split_blocks
    faces = {1: types.SimpleNamespace(ref="b48"), 2: types.SimpleNamespace(ref="b49"),
             3: types.SimpleNamespace(ref="b49#s1")}
    groups = [(1, "b48", [10, 11]), (2, "b49", [20, 21]), (3, "b49#s1", [30])]
    one = [(1, "cluster:u/0", [10, 11, 20, 21, 30], (1, 2, 3))]
    plain = types.SimpleNamespace(faces=faces, sunk_pads={})
    assert _split_blocks(plain, one, groups) == one
    held = types.SimpleNamespace(faces=faces, sunk_pads={"b49": 360.0, "b49#s1": 360.0})
    got = sorted(e[3] for e in _split_blocks(held, one, groups))
    assert got == [(1,), (2, 3)]


def test_the_held_level_row_holds_the_pad_mean(law):
    from auto_patch_v2.constraints import pad_sunk_level as mod
    pm = types.SimpleNamespace(sunk_pads={"b49": 360.0})
    real = mod._pad_groups
    try:
        mod._pad_groups = lambda planar, law: [(7, "b49", [1, 2, 3, 4]), (8, "b48", [5, 6])]
        rows = mod.pad_sunk_level(pm, law, None)
    finally:
        mod._pad_groups = real
    assert len(rows) == 2
    up, down = rows
    assert up.hi == 360.0 and down.hi == -360.0 and set(up.follows) == {1, 2, 3, 4}
    assert all(c == 0.25 for _v, c in up.terms)


# #2195: a pad below the pads of its own unit (no airside near it)

class _UnitDem:
    """The upper pad's ground at ``hi`` for y >= 300, the pit ``lo`` below."""

    def __init__(self, hi: float, lo: float):
        self.hi, self.lo = hi, lo

    def z(self, x: float, y: float) -> float:
        return self.hi if y >= 300.0 else self.lo


def _unit_hold(dem, law, pit_tops):
    """An apron far away (the airside witness never reads), an upper pad
    b47 (y 300..360) and a pit pad b49 (y 240..300) touching it, both
    under pieces of ONE unit ``u``."""
    upper = Cell(1, "building", "b47", _rect(500.0, 300.0, 600.0, 360.0), (), None, None,
                 "airside", "building", {})
    pit = Cell(2, "building", "b49", _rect(500.0, 240.0, 600.0, 300.0), (), None, None,
               "airside", "building", {})
    top = _cluster(510.0, 310.0, 590.0, 350.0, (0.03,), (400.0,))
    low = _cluster(510.0, 245.0, 590.0, 295.0, pit_tops, (400.0,) * len(pit_tops))
    for c, k in ((top, "u#0"), (low, "u#1")):
        c.unit, c.id = "u", k
    cells, n = hold_sunk_cells(_apron() + [upper, pit], _airport(dem, [top, low]), law)
    return {c.ref: (Polygon(c.ring, c.holes), c.evidence) for c in cells
            if c.role == "building"}, n


def test_a_pit_pad_below_its_unit_is_held_at_its_own_ground(law):
    out, n = _unit_hold(_UnitDem(376.0, 360.0), law, (-16.0,))
    assert n == 1
    q, ev = out["b49"]
    gap = float(law.tables.emit.design.pad_frontage_m)
    assert q.bounds[3] < 300.0 - gap                      # yielded to b47
    assert ev[SUNK_KEY]["dem_m"] == 360.0 and ev[SUNK_KEY]["unit_m"] == 376.0
    assert out["b47"][1] == {}                            # the upper pad is not moved


def test_a_unit_on_a_hillside_with_one_authored_floor_stays_one_plane(law):
    # the ground steps, the author drew one floor: never held (both witnesses)
    _out, n = _unit_hold(_UnitDem(376.0, 360.0), law, (0.03,))
    assert n == 0


def test_a_unit_authored_low_on_level_ground_stays_one_plane(law):
    _out, n = _unit_hold(_UnitDem(376.0, 375.0), law, (-16.0,))
    assert n == 0
