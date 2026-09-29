"""OWNER RULINGS 2026-09-29x (Q-97 (b), issue #97, HECA 30.126819,
31.4099299): a groundside road between two airside pavements at different
levels takes the LOWER pavement's level, and ONE 1:3 bank rises from the
road's far kerb to the higher pavement; the taxiways do not move.

Twin of ``airport/road_ramp.between_levels`` (the pre-solve publication,
read off a real planar build) and ``constraints/road_ramp.
between_levels_rewrite`` (applied between §20b's stages against stage 1's
solved levels, which are constants there)."""
from __future__ import annotations

import pytest

from auto_patch_v2.classify.roles import Cell
from auto_patch_v2.constraints.road_ramp import (BANK_RULING, GEN, RULING,
                                                 RULING_CEILING,
                                                 between_levels_rewrite,
                                                 reach_seed_rewrite)
from auto_patch_v2.law import Law
from auto_patch_v2.model.constraints import ConstraintSet
from auto_patch_v2.solve.design_roles import one_way_rulings
from tests.auto_patch_v2.test_crown import _rect
from tests.auto_patch_v2.test_v2roadramp import (HALF_WIDTH, RUN_LEN,
                                                 _airport, _map)

DEM_Z = 701.0
LOW_Z = 700.0            # taxiway A: CUT 1 m under the DEM
HIGH_Z = 702.0           # taxiway B: FILLED 1 m over it
A_TOP, ROAD_Y0, ROAD_Y1, B_BOT = 170.0, 176.0, 184.0, 192.0


class _Flat:
    provenance = {"synthetic": "flat"}

    def z(self, x: float, y: float) -> float:
        return DEM_Z

    def bounds(self):
        return (-9000.0, -9000.0, 9000.0, 9000.0)


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


@pytest.fixture(scope="module")
def built(law):
    airport, r = _airport(law, _Flat())
    cells = (
        Cell(0, "runway", "09/27", _rect(r, -RUN_LEN / 2, -HALF_WIDTH,
                                         RUN_LEN / 2, HALF_WIDTH), (), 3, "D",
             "airside", "runway", {}),
        Cell(1, "junction", "twyA", _rect(r, -200.0, 140.0, 200.0, A_TOP), (),
             None, "D", "airside", "junction", {}),
        Cell(2, "junction", "twyB", _rect(r, -200.0, B_BOT, 200.0, 222.0), (),
             None, "D", "airside", "junction", {}),
        Cell(3, "service_road", "roadA",
             _rect(r, -150.0, ROAD_Y0, 150.0, ROAD_Y1), (), None, "D",
             "groundside", "service_road", {}),
    )
    pm, rep = _map(law, airport, cells)
    # stage 1's solved levels: A cut, B filled (the taxiways are constants)
    levels = {}
    for f in pm.faces.values():
        if f.role == "junction":
            z = LOW_Z if f.ref.startswith("twyA") else HIGH_Z
            for cyc in (f.ring, *f.holes):
                for v in pm.ring_vertices(cyc):
                    levels[v] = z
    return pm, rep, levels


def _y(pm, v):
    """The lateral coordinate ``_rect`` laid out (``_rot(0)`` maps it to -x)."""
    return -pm.vertices[v].xy[0]


def test_the_road_between_two_bands_is_published_with_both_feet(law, built):
    pm, rep, _lv = built
    bl = pm.road_between_levels
    assert rep["between_levels_road"] == len(bl["road"]) > 0
    for r, (fa, fb) in bl["road"].items():
        assert {fa[3], fb[3]} == {"twyA", "twyB"}
        assert ROAD_Y0 - 0.01 <= _y(pm, r) <= ROAD_Y1 + 0.01
    # the strip vertices published stand BETWEEN the road and their foot
    assert bl["strip"]
    for s_, (r, foot, w, d) in bl["strip"].items():
        y = _y(pm, s_)
        assert A_TOP - 0.01 <= y <= ROAD_Y0 + 0.01 or ROAD_Y1 - 0.01 <= y <= B_BOT + 0.01


def _cs(pm, law):
    from auto_patch_v2.constraints.road_ramp import road_ramp_rows
    rows = road_ramp_rows(pm, law, None)
    from auto_patch_v2.model.constraints import Band, Linear
    return ConstraintSet(linears=tuple(r for r in rows if isinstance(r, Linear)),
                         bands=tuple(r for r in rows if isinstance(r, Band)))


def test_the_road_reads_at_the_lower_level_with_one_bank_under_1_in_3(law, built):
    pm, _rep, levels = built
    cs = _cs(pm, law)
    # the road vertices the §37 (6) ramp governs (a route-frame vertex)
    road = set(pm.road_between_levels["road"]) & {
        int(r.source.inputs[0][7:]) for r in cs.linears
        if r.source.ruling == RULING}
    assert road
    out, rep = between_levels_rewrite(pm, law, cs, levels)
    vis = float(law.tables.emit.cockpit.visual_m)
    tgt = {int(r.source.inputs[0][7:]): r.hi for r in out.linears
           if r.source.generator == GEN and r.source.ruling == RULING}
    ceil = {r.v: r.hi for r in out.bands
            if r.source.generator == GEN and r.source.ruling == RULING_CEILING}
    assert rep["applied"] == len(pm.road_between_levels["road"])
    for r in road:
        assert tgt[r] == pytest.approx(LOW_Z)               # the LOWER pavement
        assert ceil[r] == pytest.approx(LOW_Z + vis)
    # ONE bank on the HIGH side only, one-way, never steeper than 1:3 here
    rows = [r for r in out.linears if r.source.ruling == BANK_RULING]
    banks = [r for r in rows if r.lo is not None]
    lows = [r for r in rows if r.lo is None]
    assert banks and rep["strip_high"] == len(banks)
    # the LOW side: a mandatory-down CEILING at the road-to-pavement plane
    assert rep["strip_low"] == len(lows)
    for b in lows:
        assert b.hi == 0.0 and _y(pm, b.follows) <= ROAD_Y0 + 0.01
    for b in banks:
        s_ = b.follows
        assert _y(pm, s_) >= ROAD_Y1 - 0.01                  # the twyB side
        assert b.lo == b.hi == 0.0
        assert sum(c for _v, c in b.terms) == pytest.approx(0.0)  # a plane
    assert rep["bank_over_slope"] == 0
    assert rep["max_bank_slope"] <= float(law.tables.emit.design.bank_slope)
    assert "zones.adjacent_ground between-levels bank" in one_way_rulings(law)
    # the stage-2 rewrite the pipeline binds carries it
    _o2, rep2 = reach_seed_rewrite(pm, law, cs, levels)
    assert rep2["between_levels"]["applied"] == rep["applied"]


def test_two_pavements_at_one_level_change_nothing(law, built):
    pm, _rep, levels = built
    cs = _cs(pm, law)
    flat = {v: LOW_Z for v in levels}
    out, rep = between_levels_rewrite(pm, law, cs, flat)
    assert rep["applied"] == 0 and out is cs


def test_no_airside_vertex_is_governed(law, built):
    pm, _rep, levels = built
    bl = pm.road_between_levels
    assert not (set(bl["road"]) | set(bl["strip"])) & set(levels)


def test_the_lower_pavement_may_be_an_apron(law):
    """RULINGS 2026-09-29ad: the feet are every airside pavement carrying a
    level (``contact_roles``) — at HECA the lower side is ``objpav115``'s
    APRON piece; an apron has no zone class and reaches the taxi class's
    default half width."""
    airport, r = _airport(law, _Flat())
    cells = (
        Cell(0, "runway", "09/27", _rect(r, -RUN_LEN / 2, -HALF_WIDTH,
                                         RUN_LEN / 2, HALF_WIDTH), (), 3, "D",
             "airside", "runway", {}),
        Cell(1, "apron", "apronA", _rect(r, -200.0, 140.0, 200.0, A_TOP), (),
             None, "D", "airside", "apron", {}),
        Cell(2, "junction", "twyB", _rect(r, -200.0, B_BOT, 200.0, 222.0), (),
             None, "D", "airside", "junction", {}),
        Cell(3, "service_road", "roadA",
             _rect(r, -150.0, ROAD_Y0, 150.0, ROAD_Y1), (), None, "D",
             "groundside", "service_road", {}),
    )
    pm, _rep = _map(law, airport, cells)
    bl = pm.road_between_levels
    assert bl["road"]
    assert all({fa[3], fb[3]} == {"apronA", "twyB"} for fa, fb in bl["road"].values())
    levels = {}
    for f in pm.faces.values():
        if f.role in ("apron", "junction"):
            z = LOW_Z if f.ref.startswith("apronA") else HIGH_Z
            for cyc in (f.ring, *f.holes):
                for v in pm.ring_vertices(cyc):
                    levels[v] = z
    out, rep = between_levels_rewrite(pm, law, _cs(pm, law), levels)
    assert rep["applied"] == len(bl["road"])
    tgt = [row.hi for row in out.linears
           if row.source.generator == GEN and row.source.ruling == RULING
           and int(row.source.inputs[0][7:]) in bl["road"]]
    assert tgt and all(t == pytest.approx(LOW_Z) for t in tgt)
