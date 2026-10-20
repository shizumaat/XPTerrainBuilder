"""Owner 2026-10-20 (#798): a sloping building's pad welded into the apron
is ONE level, its door line keeps the apron cap, and the apron's hard cap
rows elsewhere round it blend at up to the tunnel-ramp cap
(``constraints/door_pad``)."""
from __future__ import annotations

import dataclasses as dc
import types

from auto_patch_v2.constraints import door_pad as DP
from auto_patch_v2.constraints.apron import GEN as APRON_GEN
from auto_patch_v2.law import Law
from auto_patch_v2.law.tables import design as design_law
from auto_patch_v2.model.constraints import Band, ConstraintSet, Diff, Flat, Pin, Source
from shapely.geometry import Polygon

#: pad 1-2-3 (x 0..10, y 0..10), its door wall the top edge, the taxi point
#: 20 m north of the door's centre: the corridor is the triangle of the
#: wall's middle half and that point
_TRI = Polygon([(2.5, 10.0), (7.5, 10.0), (5.0, 30.0)])


def _pad(**kw):
    base = dict(ref="building1", group=(1, 2, 3), corridor=_TRI,
                door=(5.0, 10.0), door_v=1, taxi_v=9, door_m=20.0, door_cap=0.0202)
    base.update(kw)
    return DP.DoorPad(**base)


def _map(xy: dict):
    """A stand-in map: only the vertices' positions are read."""
    return types.SimpleNamespace(vertices={v: types.SimpleNamespace(xy=p)
                                           for v, p in xy.items()})


def test_the_pad_is_one_level_and_its_door_line_keeps_the_cap(monkeypatch):
    monkeypatch.setattr(DP, "door_pads", lambda *a: [_pad()])
    rows = DP.door_pad_level(None, Law.for_airport("KASE"), None)
    flats = [r for r in rows if isinstance(r, Flat)]
    doors = [r for r in rows if isinstance(r, Diff)]
    assert [f.group for f in flats] == [(1, 2, 3)]
    assert [(d.a, d.b, d.cap, d.d) for d in doors] == [(1, 9, 0.0202, 20.0)]
    # the door line is ONE HARD ROW of its own head; the Flat another head
    assert doors[0].source.ruling.split(" (")[0] == DP.DOOR_HEAD
    assert flats[0].source.ruling.split(" (")[0] != DP.DOOR_HEAD


def test_the_blend_is_read_by_chord_geometry_against_the_triangle(monkeypatch):
    """Round-3 spec D1: an apron cap row with one end on the pad is raised
    to the ramp cap unless its other end lies inside the corridor triangle;
    a row between two pads' vertices is raised either way."""
    law = Law.for_airport("KASE")
    top = float(law.tables.structures.tunnel.ramp_max_grade)
    other = _pad(ref="building2", group=(11, 12), corridor=Polygon(
        [(40, 0), (41, 0), (40.5, 1)]))
    monkeypatch.setattr(DP, "door_pads", lambda *a: [_pad(), other])
    pm = _map({1: (5.0, 10.0), 2: (0.0, 0.0), 3: (10.0, 10.0), 4: (5.0, 20.0),
               5: (20.0, 20.0), 6: (30.0, 30.0), 11: (14.0, 10.0), 12: (14.0, 0.0)})
    apron = Source(APRON_GEN, "common.roles.apron ring edge", ())
    taxi = Source("taxi_box", "taxi", ())
    rows = [Diff(1, 4, 0.0202, 10.0, apron),                 # into the triangle: kept
            Diff(1, 5, 0.0202, 18.0, apron),                 # the door vertex out of it: raised
            Diff(3, 5, 0.0202, 14.0, apron),                 # a rim corner out of it: raised
            Diff(3, 11, 0.0202, 4.0, apron),                 # pad to pad: raised
            Diff(5, 6, 0.0202, 14.0, apron),                 # off the pad: kept
            Diff(3, 6, 0.01, 20.0, apron, soft="apron:1:0"),  # preference: kept
            Diff(3, 5, 0.0202, 14.0, taxi)]                  # taxi row: kept
    counts: dict = {}
    got = DP.relax_apron_caps(rows, pm, law, None, counts)
    assert [r.cap for r in got] == [0.0202, top, top, top, 0.0202, 0.01, 0.0202]
    assert counts[f"{DP.GEN}.apron_rows_relaxed"] == 3


def test_the_corridor_is_the_door_share_and_the_taxi_point():
    from shapely.geometry import LineString, Point
    tri = DP._corridor(LineString([(0, 10), (10, 10)]), Point(5, 30), 0.5)
    assert sorted(set(tri.exterior.coords)) == [(2.5, 10.0), (5.0, 30.0), (7.5, 10.0)]


def test_the_law_carries_the_door_corridor_and_the_ramp_cap():
    st = Law.for_airport("KASE").tables.structures
    assert st.placement.door_corridor_share == 0.5
    assert st.tunnel.ramp_max_grade == 0.1


def test_the_law_makes_the_door_line_and_the_give_hard():
    """Round-3 spec D1 / D2 (owner RULINGS 2026-10-19ac): the door line is a
    HARD apron-tier law, the give's Band a HARD taxi-tier law, 0.5 m."""
    law = Law.for_airport("KASE")
    d = design_law(law)
    assert {DP.DOOR_HEAD, DP.GIVE_HEAD} <= set(d.hard_rulings)
    tier = {h: d.hard_conflict_tiers[k] for k, heads in enumerate(d.hard_conflict_ranks)
            for h in heads}
    assert tier[DP.DOOR_HEAD] == "apron" and tier[DP.GIVE_HEAD] == "taxi"
    assert law.tables.structures.placement.door_airside_give_m == 0.5


def test_no_door_pad_on_stage_ones_map(monkeypatch):
    """Pads follow the solved airside (master 2026-10-20): while stage 1's
    map is derived no door-line pad exists, so it adds no row there."""
    monkeypatch.setattr(DP, "_derive", lambda *a: [_pad()])
    DP._MEMO.clear()
    with DP.stage_one():
        assert DP.door_pads(object(), None, None) == []
    DP._MEMO.clear()
    assert DP.door_pads(object(), None, None) == [_pad()]
    DP._MEMO.clear()


def test_stage_one_carries_mains_pads():
    """``stage_one_map.base_pad_map``: the classification's pad cells are
    replaced by main's (``Classification.base_pads``); nothing else moves."""
    import dataclasses as dc

    from auto_patch_v2.classify.roles import Cell, Classification
    from auto_patch_v2.pipeline.stage_one_map import base_pad_map

    def cell(i, role, ref, kind):
        return Cell(i, role, ref, ((0, 0), (1, 0), (1, 1)), (), None, None,
                    "airside", kind, {})
    apron, pad = cell(0, "apron", "pav1", "apron"), cell(1, "building", "building1", "building")
    main = cell(9, "building", "building1", "building")
    cl = Classification((apron, pad), (), {}, ())
    assert base_pad_map(cl) is None
    got = base_pad_map(dc.replace(cl, base_pads=(main,)))
    assert got.cells == (apron, main) and got.base_pads is None


def test_the_law_carries_the_blend_reach():
    assert Law.for_airport("KASE").tables.structures.placement.door_blend_reach_m == 60.0


# ── THE TOY MAP (round-3 spec step 5): two pads 8 m apart on a frozen apron ──
#
# Pad A (x 10..20) stands in the apron, its door at (15, 22) and the taxi
# point 8 m north at (15, 30); pad B (x 28..38) touches the junction along
# y = 30, so its level IS the junction's.  Stage 1 left the taxi point at
# 101.2 and the junction at 100.0; the pads' rims are 8 m apart under the
# 10 % pavement ceiling.  The door line needs A >= 101.2 - 0.16; the
# ceiling allows A <= 100.0 + 0.8: infeasible by 0.24 m with the airside
# frozen, feasible with 0.3 m of give.

_A = ((10, 10), (20, 10), (20, 22), (15, 22), (10, 22))
_B = ((28, 15), (38, 15), (38, 30), (28, 30), (28, 22))
_APRON = ((0, 0), (50, 0), (50, 30), (38, 30), (38, 15), (28, 15), (28, 22),
          (28, 30), (15, 30), (0, 30))
_TAXI = ((0, 30), (15, 30), (28, 30), (38, 30), (50, 30), (50, 45), (0, 45))


class _FlatDem:
    provenance = {"synthetic": "flat 100"}

    def z(self, x: float, y: float) -> float:
        return 100.0

    def bounds(self):
        return (-9000.0, -9000.0, 9000.0, 9000.0)


def _law(give: float):
    """KASE's law with the give at ``give`` and the single solve (the toy
    states stage 2's problem itself: the frozen airside as pins)."""
    law = Law.for_airport("ZZZZ")
    st, em = law.tables.structures, law.tables.emit
    return dc.replace(law, tables=dc.replace(
        law.tables,
        structures=dc.replace(st, placement=dc.replace(
            st.placement, door_airside_give_m=give)),
        emit=dc.replace(em, design=dc.replace(em.design, staged_solve=False))))


def _toy(monkeypatch, give: float):
    from auto_patch_v2.classify.roles import Cell, Classification
    from auto_patch_v2.model.airport import Airport, SceneryPack
    from auto_patch_v2.model.frame import Frame
    from auto_patch_v2.planar.build import build
    law = _law(give)
    ap = Airport("ZZZZ", "Synthetic", Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11),
                 100.0, (), (), (), {}, (), (), (), (), (), (), (),
                 SceneryPack("fixture", "apt.dat", "0", (), ()), _FlatDem(), law.ruleset_key)
    cells = (Cell(0, "apron", "pav1", _APRON, (_A,), None, None, "airside", "apron", {}),
             Cell(1, "building", "bA", _A, (), None, None, "airside", "building", {}),
             Cell(2, "building", "bB", _B, (), None, None, "airside", "building", {}),
             Cell(3, "junction", "j1", _TAXI, (), None, "B", "airside", "taxiway", {}))
    pm, _st = build(ap, Classification(cells, (), {}, ()), law)
    at = {pm.vertices[v].xy: v for v in pm.vertices}

    def v(x, y):
        return at[(float(x), float(y))]
    ga = tuple(sorted(v(*p) for p in _A))
    gb = tuple(sorted(v(*p) for p in _B))
    pads = [DP.DoorPad("bA", ga, Polygon([(12.5, 22), (17.5, 22), (15, 30)]),
                       (15.0, 22.0), v(15, 22), v(15, 30), 8.0, 0.0202),
            DP.DoorPad("bB", gb, Polygon([(30.5, 30), (35.5, 30), (33, 30.5)]),
                       (33.0, 30.0))]
    monkeypatch.setattr(DP, "door_pads", lambda *a: pads)
    rows = DP.door_pad_level(pm, law, ap)
    rows.append(Diff(v(20, 22), v(28, 22), 0.10, 8.0, Source(
        "pavement_cap", "rulesets.common.pavement_max_grade ceiling", ())))
    cs = ConstraintSet.from_rows(DP.relax_apron_caps(rows, pm, law, ap))
    airside = {u for u in pm.vertices
               if any(pm.faces[f].role in ("apron", "junction")
                      for f in pm.vertices[u].incident_faces)}
    levels = {u: 100.0 for u in airside if u not in ga}
    levels[v(15, 30)] = 101.2
    return law, ap, pm, cs, levels, v, ga, gb


def test_the_give_set_its_bands_and_the_levels_it_releases(monkeypatch):
    """Round-3 spec D2: the pad's taxi-shared vertices and the far end of
    every hard row touching a pad leave the levels, each Banded within the
    give of its stage-1 level (a hard head) and preferring it."""
    law, ap, pm, cs, levels, v, ga, gb = _toy(monkeypatch, 0.3)
    z1 = dict(levels)
    rep, bands, pref = DP.blend_release(pm, law, ap, levels, cs)
    give = {v(28, 30), v(38, 30), v(15, 30)}     # B on the junction; the taxi point
    assert {b.v for b in bands} == give and rep["give"] == 3
    assert all(isinstance(b, Band) and b.source.ruling.split(" (")[0] == DP.GIVE_HEAD
               and abs(b.lo - (z1[b.v] - 0.3)) < 1e-9 and abs(b.hi - (z1[b.v] + 0.3)) < 1e-9
               for b in bands)
    assert pref == {u: z1[u] for u in give}
    assert not give & set(levels) and not set(gb) & set(levels)
    # disarmed: no give, the taxi-shared vertices stay stage 1's
    law0, ap, pm, cs, levels, v, ga, gb = _toy(monkeypatch, 0.0)
    _rep, bands0, pref0 = DP.blend_release(pm, law0, ap, levels, cs)
    assert bands0 == [] and pref0 == {} and v(15, 30) in levels


def _solve(monkeypatch, give: float):
    from auto_patch_v2.solve import solve_design
    law, ap, pm, cs, levels, v, ga, gb = _toy(monkeypatch, give)
    z1 = dict(levels)
    _rep, bands, pref = DP.blend_release(pm, law, ap, levels, cs)
    frozen = [Pin(u, z, Source("stage_one", "stage 1 level", ())) for u, z in levels.items()]
    cs2 = ConstraintSet.from_rows([*cs.rows(), *bands, *frozen])
    sol, rep = solve_design(dc.replace(pm, preferred_z={**pm.preferred_z, **pref}), cs2, law)
    z = sol.z
    door = abs(z[v(15, 22)] - z[v(15, 30)])
    spread = max(max(z[u] for u in g) - min(z[u] for u in g) for g in (ga, gb))
    moved = max((abs(z[b.v] - z1[b.v]) for b in bands), default=0.0)
    return door, spread, moved, rep.hard_conflict


def test_the_toy_door_line_is_infeasible_frozen_and_named(monkeypatch):
    """With no give the door line cannot hold: §5a relaxes IT (the apron
    tier, under the taxi-tier ceiling), and the named failure reads it —
    the record the sidecar's ``hard_conflict`` ships (round-3 spec D3)."""
    _door, spread, _moved, conf = _solve(monkeypatch, 0.0)
    assert spread < 1e-6
    assert [c["row"] for c in conf] == [DP.DOOR_HEAD]
    line, = DP.door_line_failures(conf, 0.0)
    assert line.startswith("DOOR LINE bA at ") and "with 0 m airside give" in line
    assert "INFEASIBLE by 0.2" in line


def test_the_toy_door_line_holds_with_the_give(monkeypatch):
    """0.3 m of give: the door line within its cap, the airside within the
    give of stage 1, each pad one level, nothing relaxed."""
    door, spread, moved, conf = _solve(monkeypatch, 0.3)
    assert conf == []
    assert door <= 0.0202 * 8.0 + 1e-3
    assert moved <= 0.3 + 1e-3
    assert spread < 1e-6


def test_the_door_line_read_reads_the_toy(monkeypatch):
    """``tools/door_line_read.py`` on the toy's solve: the door line, the
    spread, the rim edges and the give as the twins above state them."""
    import importlib.util
    from pathlib import Path

    from auto_patch_v2.solve import solve_design
    spec = importlib.util.spec_from_file_location(
        "door_line_read_twin", Path(__file__).resolve().parents[2] / "tools" / "door_line_read.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    law, ap, pm, cs, levels, v, ga, gb = _toy(monkeypatch, 0.3)
    _rep, bands, pref = DP.blend_release(pm, law, ap, levels, cs)
    frozen = [Pin(u, z, Source("stage_one", "stage 1 level", ())) for u, z in levels.items()]
    sol, rep = solve_design(dc.replace(pm, preferred_z={**pm.preferred_z, **pref}),
                            ConstraintSet.from_rows([*cs.rows(), *bands, *frozen]), law)
    monkeypatch.setattr(mod, "_law_of", lambda sv: law)
    got = mod.read({"icao": "ZZZZ", "pm": pm, "z": sol.z, "airport": ap,
                    "stage2_bands": bands, "hard_conflict": rep.hard_conflict})
    a, b = got["pads"]
    assert a["ref"] == "bA" and a["door_line_pct"] <= 2.02 + 0.02 and a["spread_m"] < 1e-4
    # the toy's apron carries no cap row of its own: the rim edges are read,
    # not governed (KASE's apron caps them at the ramp cap, 10 %)
    assert b["spread_m"] < 1e-4 and a["rim_edge_pct"] > 0.0 and a["rim_edge_at"]
    assert got["give"]["vertices"] == 3 and got["give"]["over_give"] == 0
    assert got["give"]["worst_m"] <= 0.3 + 1e-3 and got["failures"] == []
