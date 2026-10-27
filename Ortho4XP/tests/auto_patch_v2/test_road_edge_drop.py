"""Issues #712 / #1003 twin (owner RULINGS 2026-10-20d, 2026-10-27i, 27j;
spec ``docs/specs/fill-step-at-road-kerb-spec.md``): where a pad fill
cannot bank down, the step goes along a road edge — R1 a page a network
road runs through is that road only where it is welded to a pad (§3), R2
the fill runs to the road (or the lot between, 27i) as a lens, R3 the road
comes down off the fill by §37 (6) alone, and the fill's RISER at the
road's far kerb (§2 (3)-(5)) is minted with the fill and declared as one
wall.  Hermetic: a metre frame."""
from __future__ import annotations

import types

import pytest
from auto_patch_v2.airport import riser_wall as RW
from auto_patch_v2.classify import sources as S
from auto_patch_v2.classify.rules import load_rules
from auto_patch_v2.planar import fill_riser as FR
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


def test_r1_network_road_through_a_page_is_evidence_and_a_candidate():
    page = box(0, 0, 1000, 18)                       # an 18 m carriageway
    road = [LineString([(-10, 9), (1010, 9)])]       # the mapped secondary
    got, cand = S._network_evidence(_rec(page), page, _tree(road), road, RULES)
    assert cand and got.cls == "lot" and got.network_through_m == pytest.approx(1000.0)


def test_r1_a_lot_wider_than_a_road_or_with_no_road_through_is_no_candidate():
    lot = box(0, 0, 200, 120)                        # 120 m: a car park
    road = [LineString([(-10, 60), (210, 60)])]
    got, cand = S._network_evidence(_rec(lot), lot, _tree(road), road, RULES)
    assert not cand and got.network_through_m > 0.0  # evidence on every page
    page = box(0, 0, 1000, 18)
    stub = [LineString([(-10, 9), (100, 9)])]        # ends inside: no through road
    assert not S._network_evidence(_rec(page), page, _tree(stub), stub, RULES)[1]
    # taxi evidence keeps a page off the road rung
    assert not S._network_evidence(_rec(page, taxi_m=50.0), page, _tree(road), road,
                                   RULES)[1]


def test_r1_a_candidate_is_a_road_only_where_it_is_welded_to_a_pad():
    """§3 (owner RULINGS 2026-10-27i): the witness is the classifier's own
    touch witness — a page sharing a pad's rim is that road, a page held off
    a pad as a hillside terrace or gapped from one keeps its verdict."""
    from auto_patch_v2.law import Law
    law = Law.for_airport("HECA")
    page = box(0, 0, 1000, 18)
    rec, _c = S._network_evidence(_rec(page), page, _tree([LineString([(-10, 9), (1010, 9)])]),
                                  [LineString([(-10, 9), (1010, 9)])], RULES)
    polys = {rec.id: page}

    def run(pads, dem):
        ev = types.SimpleNamespace(pads=pads, runway_polys=[])
        ap = types.SimpleNamespace(dem=dem)
        return S._network_strips([rec], [0], polys, ev, ap, law)[0]
    flat = _Dem(lambda x, y: 90.0)
    got = run([("building1", box(400, 18, 500, 80))], flat)
    assert got.cls == "strip" and got.network_strip and "building1" in got.reason
    assert run([("building1", box(400, 30, 500, 80))], flat).cls == "lot"     # gapped
    hill = _Dem(lambda x, y: 90.0 if y < 18.0 else 100.0)
    assert run([("building1", box(400, 18, 500, 80))], hill).cls == "lot"     # held
    assert S._network_strips([rec], [0], polys, types.SimpleNamespace(pads=[]),
                             types.SimpleNamespace(dem=flat), law)[0].cls == "lot"


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


# THE RISER TWIN (spec §2 (3)-(5)): a block's fill (south), an 18 m road
# whose south kerb is the fill's edge, the fill's riser along the far
# (north) kerb, and a gap piece beyond it, all over ground at 90 m; the
# fill at D + y = 100 m
GROUND = 90.0
LEVEL = 100.0
LENS = box(0, -40, 100, 0)
ROAD = box(-50, 0, 150, 18)


def _law():
    from auto_patch_v2.law import Law
    return Law.for_airport("HECA")


def _risers(dem, law=None, grid=0.5):
    law = law or _law()
    return FR.fill_risers(LENS, LEVEL, [ROAD], ROAD, dem, law, grid, 100.0), law


def test_the_riser_stands_along_the_far_kerb_within_the_lens_span():
    (r,), law = _risers(_Dem(lambda x, y: GROUND))
    w = FR.riser_width(law, 0.5)
    x0, y0, x1, y1 = r["polygon"].bounds
    assert y0 == pytest.approx(18.0) and y1 == pytest.approx(18.0 + w)
    assert x0 >= -1e-6 and x1 <= 100.0 + 1e-6 and x1 - x0 > 95.0   # the lens's span
    assert r["polygon"].intersection(ROAD).area < 1e-6               # the road is never cut
    assert r["upper"].distance(LineString([(0, 18), (100, 18)])) < 1e-6
    g = float(law.tables.emit.road_contact.ramp_grade)
    assert r["height_m"] == pytest.approx(LEVEL - g * (18.0 + w) - GROUND, abs=0.05)


def test_no_riser_where_the_kerb_stands_within_visual_of_the_ground():
    law = _law()
    g = float(law.tables.emit.road_contact.ramp_grade)
    near = LEVEL - g * 19.0 - 0.2                     # 0.2 m under the kerb: drapes
    assert _risers(_Dem(lambda x, y: near), law)[0] == []
    # half the span over high ground: the riser stands only over the low half
    (r,), _l = _risers(_Dem(lambda x, y: near if x < 50.0 else GROUND), law)
    x0, _y0, x1, _y1 = r["polygon"].bounds
    assert x0 > 40.0 and x1 == pytest.approx(100.0)
    assert _risers(_Dem(lambda x, y: GROUND), law)[0] and \
        FR.fill_risers(LENS, LEVEL, [ROAD], ROAD, None, law, 0.5, 100.0) == []


W = 2.0                                               # the twin's riser width
_RINGS = {
    "fill": ("building", "b/landing0", [(0, -40), (100, -40), (100, 0), (0, 0)]),
    "road": ("service_road", "dsf:pol10", [(-50, 0), (0, 0), (100, 0), (150, 0),
                                           (150, 18), (100, 18), (50, 18), (0, 18),
                                           (-50, 18)]),
    "riser": ("building", "b/landing0#strip", [(0, 18), (50, 18), (100, 18),
                                               (100, 18 + W), (50, 18 + W), (0, 18 + W)]),
    "gap": ("groundside_pavement", "gap:0", [(-50, 18 + W), (0, 18 + W), (50, 18 + W),
                                             (100, 18 + W), (150, 18 + W), (150, 60),
                                             (-50, 60)]),
}


def _riser_map():
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
    ring = _RINGS["riser"][2]
    reg = types.SimpleNamespace(
        landings={"b/landing0": {"block": "b", "y": 0.0, "kind": "plate", "risers": [
            {"ring": ring + ring[:1], "upper": [[(0, 18), (100, 18)]], "height_m": 9.5}]}},
        held={"b": {"datum_pred": LEVEL, "samples_reach": [0.0]}})
    pm = types.SimpleNamespace(vertices=V, faces=faces, edges=ends, registries=reg,
                               ring_vertices=lambda c: list(cyc_v[c]), road_terrace={})
    return pm, at


def _z(pm, at, grade=0.05):
    """The road falls at ``grade`` off the fill's kerb; the riser's outer
    line and the gap stand on the ground."""
    z = {}
    for xy, v in at.items():
        fs = pm.vertices[v].incident_faces
        if 1 in fs:
            z[v] = LEVEL - grade * xy[1]
        elif 0 in fs:
            z[v] = LEVEL
        else:
            z[v] = GROUND
    return z


@pytest.fixture(scope="module")
def riser():
    law = _law()
    pm, at = _riser_map()
    counts: dict = {}
    walls = RW.riser_walls(pm, law, counts)
    pm.road_terrace = {"wall": dict(enumerate(walls))}
    return law, pm, at, walls, counts


def test_each_riser_is_one_declared_wall_and_one_joint(riser):
    from auto_patch_v2.pipeline.publication import wall_terrace_joints
    law, pm, at, walls, counts = riser
    assert counts["fill_riser_walls"] == len(walls) == 1
    rec = walls[0]
    assert rec["retains"] and rec["road_edge"] and rec["height_m"] == 9.5
    assert {pm.vertices[v].xy for v in rec["upper"]} == {(0.0, 18.0), (50.0, 18.0),
                                                         (100.0, 18.0)}
    assert {pm.vertices[v].xy[1] for v in rec["lower"]} == {18.0 + W}
    z = _z(pm, at)
    (j,) = wall_terrace_joints(pm, law, [z[v] for v in sorted(pm.vertices)])
    assert j["kind"] == "wall_terrace" and j["step_m"] == pytest.approx(9.5, abs=0.01)


def test_no_station_lies_on_the_far_kerb(riser):
    from auto_patch_v2.model.planar import drop_edges
    from auto_patch_v2.pipeline.late_stage import late_stations
    law, pm, at, _walls, _c = riser
    kerb = drop_edges(pm)
    assert kerb == {frozenset((at[(0, 18)], at[(50, 18)])),
                    frozenset((at[(50, 18)], at[(100, 18)]))}
    z = _z(pm, at)
    base = types.SimpleNamespace(**{**vars(pm), "faces": {k: f for k, f in pm.faces.items()
                                                          if k != 3}})
    line = LineString([(0, 18), (100, 18)])
    (st,) = late_stations(base, z, [box(-50, 17.5, 150, 60)], law, "groundside_pavement")
    assert all(line.distance(Point(s.xy)) > 1e-6 for s in st if 0 < s.xy[0] < 100)
    pm2 = types.SimpleNamespace(**{**vars(base), "road_terrace": {}})
    (st2,) = late_stations(pm2, z, [box(-50, 17.5, 150, 60)], law, "groundside_pavement")
    assert any(line.distance(Point(s.xy)) <= 1e-6 for s in st2)   # the control


def test_the_low_side_keeps_its_ground_across_the_riser(riser):
    """The wall's step floor admits the DEM on the riser's outer line, the
    pair rows across it are released and its bending is cut."""
    import inspect

    from auto_patch_v2.constraints.road_ramp import _wall_step_rows, wall_release
    from auto_patch_v2.model.constraints import ConstraintSet, Diff, Source
    from auto_patch_v2.pipeline import late_stage
    from auto_patch_v2.solve.wall_cut import wall_cut_edges
    law, pm, at, walls, _c = riser
    z = _z(pm, at)
    rows = _wall_step_rows(pm, dict(enumerate(walls)))
    assert len(rows) == 3
    for r in rows:
        (lv, _c1), (uv, _c2) = r.terms
        assert z[lv] - z[uv] >= r.lo - 1e-9
    up, lo = at[(50, 18)], at[(50, 18 + W)]
    across = Diff(lo, up, 0.1, 1.0, Source("roads", "x", ()))
    along = Diff(at[(0, 18)], up, 0.1, 50.0, Source("roads", "x", ()))
    cs, rep = wall_release(pm, law, ConstraintSet.from_rows([across, along]))
    assert rep["released"] == 1 and list(cs.diffs) == [along]
    cut = wall_cut_edges(pm, [(up, lo, at[(0, 18 + W)]), (up, at[(0, 18)], at[(0, 0)])])
    assert (min(up, lo), max(up, lo)) in cut
    assert (min(up, at[(0, 18)]), max(up, at[(0, 18)])) not in cut
    assert "wall_release(pm, law, cs)" in inspect.getsource(late_stage.late_solve)


def test_the_riser_takes_no_bank_and_no_landing_row(riser):
    from auto_patch_v2.constraints import platform as P
    law, pm, _at, _w, _c = riser
    assert set(P.landing_vertices(pm)) == {"b/landing0"}
    assert not any("#strip" in str(q[0]) for q in
                   [q for q in P.collar_faces(pm, law, P.is_strip_ref)
                    if q[0] not in pm.registries.landings])


def test_a_block_carrying_a_fill_gets_a_stage_two_datum_column():
    """Round 3 D5 (``model.platform.datum_vertices`` ``fills``): a held
    block that welds nothing and carries a pad fill gets its own column —
    the readers that ask for it, never the stage split."""
    from auto_patch_v2.model.platform import datum_vertices
    law = _law()
    pm, _at = _riser_map()
    pm.registries.held = {"b/landing0": {}}       # the fill's own ref as a held block
    pm.registries.landings = {"x/landing0": {"block": "b/landing0", "y": 0.0,
                                             "kind": "plate"}}
    assert datum_vertices(pm, law, air=set()) == {}
    got = datum_vertices(pm, law, air=set(), fills=True)
    assert set(got) == {"b/landing0"}
    assert 0 in pm.vertices[got["b/landing0"]].incident_faces
    pm.registries.landings["x/landing0"]["kind"] = "deck"
    assert datum_vertices(pm, law, air=set(), fills=True) == {}
