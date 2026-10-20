"""Issue #711 (owner RULINGS 2026-10-14c (5) at a 10-03e landing): a viaduct
ramp landing on a LANDING runs out at road grade along its direction of
travel to raw DEM — the strip cuts the lot it crosses, yields to every
other standing region, is held relative to its block's datum, and the
landing's 1:3 collar banks its sides.  Hermetic."""
from __future__ import annotations

import types

import pytest
from shapely.geometry import Point, box
from shapely.ops import unary_union

from auto_patch_v2.airport import ramp_feet as RF
from auto_patch_v2.geom.ramp_profile import ramp_delta, runout_profile
from auto_patch_v2.law import Law
from auto_patch_v2.model import platform as MP
from auto_patch_v2.model.registries import Registries


@pytest.fixture
def law():
    return Law.load()


def _g_cap(law):
    from auto_patch_v2.law.tables import role_cap
    return (float(law.tables.emit.road_contact.ramp_grade),
            float(role_cap(law, "service_road").longitudinal))


# ── the long section ──────────────────────────────────────────────────────

def test_on_level_ground_the_runout_closes_its_offset_at_the_design_grade(law):
    g, cap = _g_cap(law)
    prof = runout_profile(106.0, lambda s: 100.0, g, cap, 400.0)
    s_end, z_end = prof[-1]
    assert z_end == pytest.approx(100.0, abs=0.06)
    assert s_end == pytest.approx(6.0 / g, abs=1.5)
    # the design profile is the shared ramp law's
    assert prof[20][1] == pytest.approx(106.0 + ramp_delta(100.0, 106.0, 100.0, g, 20.0))


def test_where_the_ground_falls_away_the_runout_never_passes_the_road_cap(law):
    g, cap = _g_cap(law)
    fall = 0.06                              # the terrain falls 6 % ahead
    prof = runout_profile(101.6, lambda s: 95.5 - fall * s, g, cap, 400.0)
    steps = [(z0 - z1) / (s1 - s0) for (s0, z0), (s1, z1) in zip(prof, prof[1:])]
    assert max(steps) <= cap + 1e-9
    s_end, z_end = prof[-1]
    assert z_end == pytest.approx(95.5 - fall * s_end, abs=0.06)
    assert s_end == pytest.approx(6.1 / (cap - fall), abs=2.0)


# ── the strip ─────────────────────────────────────────────────────────────

class _Dem:
    def __init__(self, z=100.0):
        self._z = z

    def z(self, x, y):
        return self._z


def _airport(feet, dem=100.0):
    frame = types.SimpleNamespace(entry=lambda: (lambda lo, la: (lo, la)),
                                  transformers=lambda: (None, lambda x, y: (y, x)))
    return types.SimpleNamespace(frame=frame, dem=_Dem(dem), ramp_feet=tuple(feet))


def _foot():
    # the ramp comes down eastward to its lip at x = 10, 8 m wide
    return RF.RampFoot("u", "deck", (10.0, 5.0), (1.0, 0.0), 8.0, 0.0, 4.0)


def _plats():
    return [("u/landing0", [box(0, 0, 10, 10)], box(0, 0, 10, 10), 0.0, "deck",
             "u", 3, "u", None)]


def test_a_landing_foot_runs_out_ahead_at_road_grade(law):
    from auto_patch_v2.planar.landing_runout import landing_runouts
    g, _cap = _g_cap(law)
    counts: dict = {}
    got = landing_runouts(_plats(), {"u": {"datum_pred": 106.0}}, _airport([_foot()]),
                          law, box(0, 0, 10, 10), 1.0, 0.5, counts)
    assert list(got) == ["runout:u/landing0"]
    rec = got["runout:u/landing0"]
    (q,) = rec["polys"]
    # from the landing's edge, along the direction of travel, |6 m| / 5 %
    assert q.bounds[0] == pytest.approx(10.0, abs=0.01)
    assert q.bounds[2] == pytest.approx(10.0 + 6.0 / g, abs=1.5)
    assert q.bounds[3] - q.bounds[1] == pytest.approx(8.0)
    assert rec["ground"][0] == (0.0, 0.0) and rec["run_m"] == pytest.approx(6.0 / g, abs=1.5)
    assert counts["landing_runouts"] == 1


def test_a_pad_in_the_run_stops_the_runout(law):
    from auto_patch_v2.planar.landing_runout import landing_runouts
    counts: dict = {}
    taken = box(0, 0, 10, 10).union(box(60, -20, 90, 30))   # a pad 50 m ahead
    got = landing_runouts(_plats(), {"u": {"datum_pred": 106.0}}, _airport([_foot()]),
                          law, taken, 1.0, 0.5, counts)
    assert got == {} and counts["landing_runout_feet"]["held_ahead"] == 1


def test_two_ramps_landing_side_by_side_both_run_out(law):
    # issue #711 (HECA T3): a steep ramp and a gentle one land side by side
    # and their runs converge — the sibling's strip is no pad in the run;
    # the later foot runs out on the ground the earlier strip left
    from auto_patch_v2.planar.landing_runout import landing_runouts
    plats = _plats() + [("u/landing1", [box(0, 12, 10, 22)], box(0, 12, 10, 22), 0.0,
                         "deck", "u", 3, "u", None)]
    a = RF.RampFoot("u", "deck", (10.0, 5.0), (1.0, 0.0), 8.0, 0.0, 4.0)
    b = RF.RampFoot("u", "deck", (10.0, 17.0), (0.96, -0.28), 8.0, 0.0, 4.0)
    counts: dict = {}
    taken = box(0, 0, 10, 10).union(box(0, 12, 10, 22))
    got = landing_runouts(plats, {"u": {"datum_pred": 106.0}}, _airport([a, b]),
                          law, taken, 1.0, 0.5, counts)
    assert sorted(got) == ["runout:u/landing0", "runout:u/landing1"]
    assert counts["landing_runout_feet"]["held_ahead"] == 0
    p0, p1 = (unary_union(got[r]["polys"]) for r in sorted(got))
    assert p0.intersection(p1).area < 1e-6


def test_no_predicted_datum_or_ground_at_grade_asks_nothing(law):
    from auto_patch_v2.planar.landing_runout import landing_runouts
    counts: dict = {}
    assert landing_runouts(_plats(), {"u": {"datum_pred": None}}, _airport([_foot()]),
                           law, box(0, 0, 10, 10), 1.0, 0.5, counts) == {}
    assert counts["landing_runout_feet"]["no_datum"] == 1
    counts = {}
    assert landing_runouts(_plats(), {"u": {"datum_pred": 100.1}}, _airport([_foot()]),
                           law, box(0, 0, 10, 10), 1.0, 0.5, counts) == {}
    assert counts["landing_runout_feet"]["at_grade"] == 1


def test_the_strip_cuts_the_lot_and_yields_to_a_road(law):
    from auto_patch_v2.planar import landing as LD
    from auto_patch_v2.planar.overlay import Region
    land = Region("building", "u/landing0", box(0, 0, 10, 10), None, None, "airside", "cell")
    lot = Region("parking_lot", "lot", box(10, -20, 200, 30), None, None, "groundside", "cell")
    road = Region("service_road", "rd", box(40, -20, 46, 30), None, None, "groundside", "cell")
    reg = Registries()
    reg.landings["u/landing0"] = {"block": "u", "y": 0.0}
    reg.landing_runouts["runout:u/landing0"] = {"landing": "u/landing0",
                                                "polys": [box(10, 1, 130, 9)]}
    out = LD.landing_cut([lot, road], [land], law, reg=reg)
    strips = [r for r in out if r.ref == "runout:u/landing0"]
    assert {r.role for r in strips} == {"service_road"}
    # the road keeps its ground: the strip is cut in two at it
    assert sum(r.polygon.area for r in strips) == pytest.approx(120 * 8 - 6 * 8)
    assert [r for r in out if r.ref == "rd"][0] is road
    lots = [r for r in out if r.role == "parking_lot"]
    assert not any(r.polygon.intersects(Point(80, 5)) for r in lots)
    assert sum(r.polygon.area for r in lots) == pytest.approx(190 * 50 - 120 * 8)


# ── the rows ──────────────────────────────────────────────────────────────

class _Planar:
    """The strip as one face (four corners), the datum column vertex 9."""

    def __init__(self):
        self.registries = Registries()
        xy = {0: (10, 1), 1: (130, 1), 2: (130, 9), 3: (10, 9), 9: (-50, 0)}
        self.vertices = {k: types.SimpleNamespace(xy=p, incident_faces=(0,), dem_z=100.0)
                         for k, p in xy.items()}
        self.faces = {0: types.SimpleNamespace(id=0, ref="runout:u/landing0",
                                               role="service_road", ring=(0, 1, 2, 3),
                                               holes=())}

    def ring_vertices(self, cycle):
        return tuple(cycle)


def test_the_strip_is_held_relative_to_its_blocks_datum(law, monkeypatch):
    from auto_patch_v2.constraints.ramp_runout import (LANDING_RUNOUT_RULING,
                                                       landing_runout_rows)
    monkeypatch.setattr(MP, "datum_vertices", lambda _p, _l: {"u": 9})
    planar = _Planar()
    rec = {"landing": "u/landing0", "block": "u", "y": -0.2, "lip": (10.0, 5.0),
           "dir": (1.0, 0.0), "g": 0.05, "cap": 0.10, "z0_pred": 105.8, "reach_m": 0.5,
           "dem0": 100.0}
    ceilings: dict = {}
    try:
        def bounds(ground):
            planar.registries.landing_runouts["runout:u/landing0"] = {**rec, "ground": ground}
            rows = landing_runout_rows(planar, law)
            assert all(r.source.ruling == LANDING_RUNOUT_RULING for r in rows)
            # the strip's own chords: along each side at the road cap, across
            # at each paired station at the cross-fall cap
            chords = sorted((tuple(sorted((r.a, r.b))), r.cap) for r in rows if hasattr(r, "cap"))
            assert chords == [((0, 1), 0.1), ((0, 3), 0.02), ((1, 2), 0.02), ((2, 3), 0.1)]
            rows = [r for r in rows if not hasattr(r, "cap")]
            assert len(rows) == 8
            out, cap = {}, {}
            for r in rows:
                if hasattr(r, "terms"):
                    (v, a), (d, b) = r.terms
                    assert d == 9 and (a, b) == (1.0, -1.0)
                    out[v] = (r.lo, r.hi)
                else:
                    cap[r.v] = r.hi
            ceilings.update(cap)
            return out
        level = bounds([(0.0, 0.0), (120.0, 0.0)])
        # at the lip the landing's own level; never above it anywhere
        assert level[0] == pytest.approx((-0.2, -0.2))
        assert all(hi == pytest.approx(-0.2) for _lo, hi in level.values())
        # 120 m on over level ground: no lower than the 5 % design ramp
        assert level[1][0] == pytest.approx(-0.2 - 6.0)
        # the ceiling: the profile off the highest level the block may hold
        # (105.8 + 0.5), or the ground once that has met it, + visual_m
        vis = float(law.tables.emit.cockpit.visual_m)
        assert ceilings[0] == pytest.approx(106.3 + vis)
        assert ceilings[1] == pytest.approx(100.3 + vis)
        # the ground falling 8 % beside it: closing the offset would be 13 %,
        # the road cap (10 %) holds it
        falling = bounds([(0.0, 0.0), (120.0, -9.6)])
        assert falling[1][0] == pytest.approx(-0.2 - 12.0)
    finally:
        planar.registries.landing_runouts.clear()


def test_the_collar_banks_the_strips_sides(monkeypatch):
    from auto_patch_v2.constraints import platform as CP
    pm = types.SimpleNamespace(faces={
        1: types.SimpleNamespace(ref="u/landing0"),
        2: types.SimpleNamespace(ref="u/landing0#collar"),
        3: types.SimpleNamespace(ref="runout:u/landing0"),
        4: types.SimpleNamespace(ref="runout:u/landing0#collar")},
        registries=Registries())
    pm.registries.landing_runouts["runout:u/landing0"] = {"landing": "u/landing0"}
    got = CP._with_runouts(pm, [("u/landing0", (2,), (1,)), ("v/b0", (7,), (8,))])
    # the landing's collar banks off the strip's first metres; the strip's
    # own side bank (its own ref, never folded into the landing by the
    # object stage) banks off the strip
    assert got == [("u/landing0", (2,), (1, 3)), ("v/b0", (7,), (8,)),
                   ("runout:u/landing0", (4,), (3,))]


def test_a_bank_between_two_strips_banks_off_both():
    # #711 (HECA T3): two ramps land side by side and run out on two strips;
    # the first landing's bank borders the sibling's strip and banks off it
    # too (off its own alone a seam vertex 1.1 m from the sibling strip had
    # no row to it and stood 3 m under it)
    from auto_patch_v2.constraints import platform as CP
    F = types.SimpleNamespace
    pm = F(faces={1: F(ref="u/landing0", ring=(1, 2, 3)),
                  2: F(ref="u/landing0#collar", ring=(3, 4, 5)),
                  3: F(ref="runout:u/landing0", ring=(6, 7, 8)),
                  5: F(ref="u/landing1", ring=(20, 21, 22)),
                  6: F(ref="runout:u/landing1", ring=(5, 9, 10))},
           registries=Registries(), ring_vertices=lambda ring: ring)
    pm.registries.landings.update({"u/landing0": {}, "u/landing1": {}})
    pm.registries.landing_runouts.update({"runout:u/landing0": {"landing": "u/landing0"},
                                          "runout:u/landing1": {"landing": "u/landing1"}})
    got = CP._with_runouts(pm, [("u/landing0", (2,), (1,)), ("v/b0", (7,), (8,))])
    assert got[0] == ("u/landing0", (2,), (1, 3, 6))
    assert got[1] == ("v/b0", (7,), (8,))


def test_a_mapped_road_on_the_strip_rides_it():
    from auto_patch_v2.constraints import ramp_runout as RR
    from auto_patch_v2.constraints.road_ramp import GEN as ROAD_RAMP
    from auto_patch_v2.model.constraints import Band, Source
    planar = _Planar()
    planar.registries.landing_runouts["runout:u/landing0"] = {"landing": "u/landing0"}
    on = Band(1, None, 95.0, Source(ROAD_RAMP, "roads.groundside_road ramp ceiling"))
    off = Band(9, None, 95.0, Source(ROAD_RAMP, "roads.groundside_road ramp ceiling"))
    other = Band(1, None, 99.0, Source("roads", "road_cross_section"))
    rows, n = RR.runout_exempt([on, off, other], planar)
    assert n == 1 and rows == [off, other]
