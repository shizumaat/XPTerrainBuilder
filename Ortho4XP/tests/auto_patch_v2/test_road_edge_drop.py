"""Issues #712 / #1003 twin (owner RULINGS 2026-10-20d; spec
``docs/specs/road-edge-drop-spec.md``): where a pad fill cannot bank down,
the drop goes along a road edge — R1 a page a network road runs through is
that road, R2 the fill runs to the road, R3 the road comes down off the
fill by §37 (6) alone (round 3 D3: no second road profile), R4 the road's
low side is a DROP the gap sheet never follows, declared as a wall where a
gap piece stands across it (round 3 D4).  Hermetic: a metre frame."""
from __future__ import annotations

import types

import pytest
from auto_patch_v2.airport import road_edge_wall as RW
from auto_patch_v2.classify import sources as S
from auto_patch_v2.classify.rules import load_rules
from auto_patch_v2.planar import fill_road as PF
from shapely.geometry import LineString, Point, box

RULES = load_rules()


def _rec(poly, cls="lot", **kw):
    half = poly.length / 2.0
    base = dict(id="dsf:pol1", description="", area_m2=poly.area,
                width_m=poly.area / half, road_m=0.0, osm_road_m=0.0,
                through_m=0.0, dead_ends=0, road_pieces=0, road_reach=2,
                aisle_m=0.0, taxi_m=0.0, startups=0, parking_cover=0.0,
                apron_cover=0.0, cls=cls, reason="2 road(s) reach it")
    base.update(kw)
    return S.SourceRecord(**base)


def _tree(lines):
    from shapely.strtree import STRtree
    return STRtree(lines)


def test_r1_a_page_a_network_road_runs_through_is_that_road():
    page = box(0, 0, 1000, 18)                       # an 18 m carriageway
    road = [LineString([(-10, 9), (1010, 9)])]       # the mapped secondary
    got = S._network_strip(_rec(page), page, _tree(road), road, RULES)
    assert got.cls == "strip" and got.network_through_m == pytest.approx(1000.0)


def test_r1_a_lot_wider_than_a_road_or_with_no_road_through_stays():
    lot = box(0, 0, 200, 120)                        # 120 m: a car park
    road = [LineString([(-10, 60), (210, 60)])]
    assert S._network_strip(_rec(lot), lot, _tree(road), road, RULES).cls == "lot"
    page = box(0, 0, 1000, 18)
    stub = [LineString([(-10, 9), (100, 9)])]        # ends inside: no through road
    assert S._network_strip(_rec(page), page, _tree(stub), stub, RULES).cls == "lot"
    # taxi evidence keeps a page off the road rung
    assert S._network_strip(_rec(page, taxi_m=50.0), page, _tree(road), road,
                            RULES).cls == "lot"


class _Dem:
    def __init__(self, z):
        self.z = z


def test_r2_a_fill_that_cannot_bank_down_runs_to_the_road_kerb_as_a_lens():
    fill = box(0, 0, 100, 60)
    road = box(-50, 120, 150, 138)                   # 60 m off, 18 m wide
    low = _Dem(lambda x, y: 88.0)
    assert PF.cannot_bank(fill, 96.6, low, 15.0, 0.33)
    assert not PF.cannot_bank(fill, 96.6, _Dem(lambda x, y: 94.0), 15.0, 0.33)
    E = PF.extend_to_roads(fill, [road], 100.0)
    assert E.contains(fill) and E.bounds[3] == pytest.approx(120.0)
    assert E.intersection(road).area < 1e-6          # the road is never taken
    assert PF.extend_to_roads(fill, [road], 40.0) is None   # beyond reach
    # never a hull: the ground beside the fill, off the road's line, stays
    assert not E.contains(Point(140.0, 30.0))
    # what is held is never taken, and a piece cut off the fill by it goes
    held = box(-60, 80, 160, 90)
    E2 = PF.extend_to_roads(fill, [road], 100.0, held)
    assert E2.bounds[3] <= 80.0 + 1e-6


def test_r2_the_lens_never_returns_ground_across_the_road():
    """A short strip whose ends are within reach of the fill: the ground
    beyond its far kerb, within reach of both, is never the fill's."""
    fill = box(0, 0, 100, 60)
    road = box(20, 120, 80, 138)                     # 60 m long, 18 m wide
    E = PF.extend_to_roads(fill, [road], 100.0)
    assert E is not None and E.intersection(road).area < 1e-6
    assert E.intersection(box(-200, 138, 300, 400)).area < 1e-6


def test_r3_no_second_road_profile():
    """Round 3 D3: the road climbs to the fill by §37 (6) alone — no
    ``fill_road`` generator, no ruling."""
    from auto_patch_v2.constraints import GENERATORS
    assert "fill_road" not in {name for name, _g in GENERATORS}
    from auto_patch_v2.law import Law
    law = Law.for_airport("HECA")
    from auto_patch_v2.solve.design_roles import hard_rulings
    assert not any("fill_road" in r for r in hard_rulings(law))


def test_r4_runs_are_cyclic_and_need_two_vertices():
    ring = [1, 2, 3, 4, 5, 6]
    assert RW._runs(ring, {2, 3, 5, 6, 1}.__contains__) == [[5, 6, 1, 2, 3]]
    assert RW._runs(ring, {2, 3, 5, 6}.__contains__) == [[2, 3], [5, 6]]
    assert RW._runs(ring, {4}.__contains__) == []


# THE DROP TWIN (round 3 step 5): a block's fill (south), an 18 m road strip
# whose south kerb is the fill's edge, and a gap piece 1 m off its far
# (north) kerb, all over ground at 90 m; the fill at D + y = 100 m
GROUND = 90.0
LEVEL = 100.0
_RINGS = {
    "fill": ("building", "b/landing0", [(0, -40), (100, -40), (100, 0), (0, 0)]),
    "road": ("service_road", "dsf:pol10", [(-50, 0), (0, 0), (100, 0), (150, 0),
                                           (150, 18), (100, 18), (50, 18), (0, 18),
                                           (-50, 18)]),
    "gap": ("groundside_pavement", "gap:0", [(-50, 19), (0, 19), (50, 19), (100, 19),
                                             (150, 19), (150, 60), (-50, 60)]),
}


def _drop_map():
    V: dict = {}
    at: dict = {}
    eid, ends, cyc_v = {}, {}, {}

    def vid(xy):
        if xy not in at:
            at[xy] = len(at)
            V[at[xy]] = types.SimpleNamespace(
                xy=(float(xy[0]), float(xy[1])), dem_z=GROUND, incident_faces=[],
                key=(30.0 + xy[1] * 1e-5, 31.0 + xy[0] * 1e-5))
        return at[xy]

    def edge(a, b):
        k = frozenset((a, b))
        if k not in eid:
            eid[k] = 1000 + len(eid)
            ends[eid[k]] = types.SimpleNamespace(a=a, b=b)
        return eid[k]
    faces = {}
    for fid, (role, ref, pts) in enumerate(_RINGS.values()):
        ring = [vid(p) for p in pts]
        cyc = tuple(edge(ring[k], ring[(k + 1) % len(ring)]) for k in range(len(ring)))
        cyc_v[cyc] = ring
        faces[fid] = types.SimpleNamespace(id=fid, role=role, ref=ref, ring=cyc, holes=())
        for v in ring:
            V[v].incident_faces.append(fid)
    reg = types.SimpleNamespace(
        landings={"b/landing0": {"block": "b", "y": 0.0, "kind": "plate"}},
        held={"b": {"datum_pred": LEVEL, "samples_reach": [0.0]}})
    pm = types.SimpleNamespace(vertices=V, faces=faces, edges=ends, registries=reg,
                               ring_vertices=lambda c: list(cyc_v[c]), road_terrace={})
    return pm, at


def _road_targets(pm, at, grade=0.05):
    """§37 (6) off the fill's kerb mouths: the road falls at ``grade`` from
    LEVEL along its distance to the fill's kerb."""
    out = {}
    for xy, v in at.items():
        if pm.faces[1].id in pm.vertices[v].incident_faces:
            x, y = xy
            d = y + max(0.0, -x, x - 100.0)
            out[v] = LEVEL - grade * d
    return out


@pytest.fixture(scope="module")
def drop():
    from auto_patch_v2.law import Law
    law = Law.for_airport("HECA")
    pm, at = _drop_map()
    targets = _road_targets(pm, at)
    counts: dict = {}
    runs = RW.drop_runs(pm, law, targets, counts)
    walls = RW.road_edge_walls(pm, law, runs, targets, 8.0, counts)
    pm.road_terrace = {"drop": runs, "wall": dict(enumerate(walls))}
    return law, pm, at, targets, runs, walls


def test_the_drop_is_the_far_kerb_never_the_fill(drop):
    _law, pm, at, _t, runs, _w = drop
    assert len(runs) == 1
    run = {pm.vertices[v].xy for v in runs[0]["run"]}
    assert (0.0, 18.0) in run and (100.0, 18.0) in run
    assert not run & {(0.0, 0.0), (100.0, 0.0)}      # the fill's kerb is no drop


def test_no_station_lies_on_a_drop_edge(drop):
    from shapely.geometry import LineString as L
    from auto_patch_v2.pipeline.late_stage import late_stations
    law, pm, _at, targets, runs, _w = drop
    z = {v: targets.get(v, LEVEL if 0 in pm.vertices[v].incident_faces else GROUND)
         for v in pm.vertices}
    base = types.SimpleNamespace(**{**vars(pm), "faces": {k: f for k, f in pm.faces.items()
                                                          if k != 2}})
    (st,) = late_stations(base, z, [box(-50, 19, 150, 60)], law, "groundside_pavement")
    kerb = L([pm.vertices[v].xy for v in runs[0]["run"]])
    assert all(kerb.distance(Point(s.xy)) > 1e-6 for s in st)
    pm2 = types.SimpleNamespace(**{**vars(base), "road_terrace": {}})
    (st2,) = late_stations(pm2, z, [box(-50, 19, 150, 60)], law, "groundside_pavement")
    assert any(kerb.distance(Point(s.xy)) <= 1e-6 for s in st2)   # the control


def test_the_drop_is_one_declared_wall_of_about_the_step(drop):
    from auto_patch_v2.pipeline.publication import wall_terrace_joints
    law, pm, at, targets, runs, walls = drop
    assert len(walls) == 1
    rec = walls[0]
    assert rec["retains"] and rec["upper"] == runs[0]["run"]
    assert {pm.vertices[v].xy[1] for v in rec["lower"]} == {19.0}
    top = max(targets[v] for v in rec["upper"])
    assert rec["height_m"] == pytest.approx(top - GROUND, abs=1e-3)
    z = [0.0] * len(pm.vertices)
    for v in pm.vertices:
        z[v] = targets.get(v, LEVEL if 0 in pm.vertices[v].incident_faces else GROUND)
    (j,) = wall_terrace_joints(pm, law, z)
    assert j["kind"] == "wall_terrace" and 8.5 <= j["step_m"] <= 10.5


def test_the_gap_piece_keeps_its_own_ground_beside_the_drop(drop):
    """No follow row and no lot row binds the piece to the raised road; the
    wall's own step floor admits its DEM."""
    from auto_patch_v2.constraints import gap_follow as gf
    from auto_patch_v2.constraints.road_ramp import _wall_step_rows
    law, pm, at, targets, _runs, walls = drop
    fixed = {v: targets.get(v, LEVEL) for v in pm.vertices
             if 2 not in pm.vertices[v].incident_faces}
    rows, rep = gf.gap_follow_rows(pm, law, fixed)
    near = {v for xy, v in at.items() if xy[1] == 19.0}
    assert not [r for r in rows if r.terms[0][0] in near], rep
    z = {v: GROUND for v in near}
    for r in _wall_step_rows(pm, dict(enumerate(walls))):
        (lv, _c), (uv, _c2) = r.terms
        assert z[lv] - targets[uv] >= r.lo - 1e-9
    # the control: without the drop the piece follows the road
    pm2 = types.SimpleNamespace(**{**vars(pm), "road_terrace": {}})
    rows2, _rep2 = gf.gap_follow_rows(pm2, law, fixed)
    assert [r for r in rows2 if r.terms[0][0] in near]


def test_the_wall_machinery_reaches_the_last_stage(drop):
    """Round 3 step 4: the drop's record is one the last stage reads — the
    pair rows across its line are released (``wall_release``, which the
    last stage applies, ``pipeline/late_stage.late_solve``) and the bending
    across the stand-off is cut (``solve/wall_cut``)."""
    import inspect

    from auto_patch_v2.constraints.road_ramp import wall_release
    from auto_patch_v2.model.constraints import ConstraintSet, Diff, Source
    from auto_patch_v2.pipeline import late_stage
    from auto_patch_v2.solve.wall_cut import wall_cut_edges
    law, pm, at, _t, _runs, walls = drop
    up, lo = at[(50, 18)], at[(50, 19)]
    across = Diff(lo, up, 0.1, 1.0, Source("gap_follow", "x", ()))
    along = Diff(at[(0, 18)], up, 0.1, 50.0, Source("roads", "x", ()))
    cs, rep = wall_release(pm, law, ConstraintSet.from_rows([across, along]))
    assert rep["released"] == 1 and list(cs.diffs) == [along]
    cut = wall_cut_edges(pm, [(up, lo, at[(0, 19)]), (up, at[(0, 18)], at[(0, 0)])])
    assert (min(up, lo), max(up, lo)) in cut
    assert (min(up, at[(0, 18)]), max(up, at[(0, 18)])) not in cut
    assert "wall_release(pm, law, cs)" in inspect.getsource(late_stage.late_solve)


def test_a_block_carrying_a_fill_gets_a_stage_two_datum_column():
    """Round 3 D5 (``model.platform.datum_vertices`` ``fills``): a held
    block that welds nothing and carries a pad fill gets its own column —
    the readers that ask for it, never the stage split."""
    from auto_patch_v2.law import Law
    from auto_patch_v2.model.platform import datum_vertices
    law = Law.for_airport("HECA")
    pm, at = _drop_map()
    pm.registries.held = {"b/landing0": {}}       # the fill's own ref as a held block
    pm.registries.landings = {"x/landing0": {"block": "b/landing0", "y": 0.0,
                                             "kind": "plate"}}
    assert datum_vertices(pm, law, air=set()) == {}
    got = datum_vertices(pm, law, air=set(), fills=True)
    assert set(got) == {"b/landing0"}
    assert 0 in pm.vertices[got["b/landing0"]].incident_faces
    pm.registries.landings["x/landing0"]["kind"] = "deck"
    assert datum_vertices(pm, law, air=set(), fills=True) == {}


def test_a_lot_below_the_drop_takes_no_level_from_the_road_beyond_it(drop):
    """The lot rows never bind a vertex whose nearest road edge is a drop to
    the next road edge along (``constraints/gap_follow._lot_rows``)."""
    from auto_patch_v2.constraints import gap_follow as gf
    law, pm, at, targets, _runs, _walls = drop
    pm2 = types.SimpleNamespace(**{**vars(pm), "faces": dict(pm.faces)})
    g = pm.faces[2]
    pm2.faces[2] = types.SimpleNamespace(**{**vars(g), "ref": "gap:0/lot"})
    fixed = {v: targets.get(v, LEVEL) for v in pm.vertices
             if 2 not in pm.vertices[v].incident_faces}
    rows, rep = gf.gap_follow_rows(pm2, law, fixed)
    near = {v for xy, v in at.items() if xy[1] == 19.0}
    assert not set(rep["lot_targets"]) & near, rep["lot_targets"]
    pm3 = types.SimpleNamespace(**{**vars(pm2), "road_terrace": {}})
    _rows3, rep3 = gf.gap_follow_rows(pm3, law, fixed)
    assert set(rep3["lot_targets"]) & near                         # the control
