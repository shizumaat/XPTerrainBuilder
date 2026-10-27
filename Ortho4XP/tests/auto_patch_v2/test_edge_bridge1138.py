"""Round-5 twins for #1138 (owner RULINGS 2026-10-27l / 27r; 2026-10-28d
Q211-Q214): ONE derivation of where an edge bridge's cover ends
(``planar/bridge_span``), read by the structure pass, the covered ground,
the road deck rows (``constraints/edge_deck``) and both census readers of
the runway-edge tie (``verify/strips.runway_edge_tie`` with the declared
wall steps)."""
from __future__ import annotations

import types

import numpy as np
from auto_patch_v2.airport import obj8 as O
from auto_patch_v2.model.airport import OsmWay
from auto_patch_v2.planar import bridge_span as BS
from auto_patch_v2.planar import covered_ground as CG
from auto_patch_v2.planar.structure_approach import chains
from auto_patch_v2.verify.steps import WallSteps
from auto_patch_v2.verify.strips import runway_edge_tie
from shapely.geometry import LineString, Polygon
from shapely.geometry import box as _sbox
from test_hanging_objects1298 import LAW, THICK, _Dem, _edge_bridge, _placed

PAV = _sbox(-100.0, -80.0, 100.0, -40.0)


def _cut():
    """A covered motorway along x = 0 in a 40 m-wide, 20 m-deep cut."""
    way = OsmWay(-1, "big_roads", ((0.0, 60.0), (0.0, -200.0)), False,
                 {"highway": "motorway", "tunnel": "yes", "lanes": "5"})
    bore = chains([way])[0]
    secs = CG._sections(_Dem(), bore, LAW)
    return [(bore, secs, CG._ribbon(secs))]


def _bridge(tmp_path):
    """The miniature ``tunel_C`` (``test_hanging_objects1298._edge_bridge``):
    a slab over the cut side (frame y 0..−20), its headwall — the BACK —
    along y −20..−20.5, the span beyond it toward the pavement ``PAV``."""
    o = _placed(_edge_bridge(tmp_path), "dsf:obj7")
    o.plan_bbox = _sbox(-31.0, -21.0, 31.0, 1.0)
    (br,) = BS.edge_bridges([o], O.ResourceCache(THICK), _cut(), PAV, LAW)
    return br


def test_the_back_is_the_span_side_wall_face_and_the_cover_runs_to_the_pavement(tmp_path):
    """27l / 20ao / 20as: the trench takes in the object to its BACK (the
    headwall's span-side face, y −20.5); the cover is the span from the
    back to the airside pavement it edges (y −40), never the slab over the
    cut; the depth is the walls' bottom; the deck level the ground beside
    the cover (the field, 300, not the road under it)."""
    br = _bridge(tmp_path)
    assert abs(br.depth_m - 26.0) < 1e-6 and abs(br.deck_z - 300.0) < 1e-6
    assert br.toward == (0.0, -1.0)
    ys = [y for _x, y in br.back]
    assert max(ys) <= -20.4 and min(ys) >= -20.6
    _minx, miny, _maxx, maxy = br.cover.bounds
    assert abs(maxy + 20.5) < 0.1 and abs(miny + 40.0) < 0.6
    assert br.cover.intersection(_sbox(-30.0, -20.0, 30.0, 0.0)).area < 1.0
    assert br.bores == ("-1",)


def test_a_skewed_back_is_followed_lateral_line_by_line():
    """28d: the back is read per lateral line (``back_line``) — the face
    reaching furthest toward the span — so a skewed headwall with a pier in
    front of it is the skewed headwall."""
    walls = (((-60.0, -10.0), (60.0, -30.0)), ((3.0, -4.0), (5.0, -4.0)))
    back = BS.back_line(walls, (0.0, -1.0), 10.0)
    assert len(back) >= 12
    for x, y in back:
        assert abs(y - (-20.0 - x / 6.0)) < 1e-6


def test_a_mouth_is_pinned_by_crossing_the_back_not_by_its_ends_distance(tmp_path):
    """28d: a bore mapped short of the object (its end on the span side)
    still runs through the back — pinned; one running away from the span,
    or crossing far beyond the object's own run, is not."""
    br = _bridge(tmp_path)
    bore = types.SimpleNamespace(line=LineString([(0.0, -30.0), (0.0, -200.0)]))
    short = types.SimpleNamespace(bore=bore, xy=(0.0, -30.0), inward=(0.0, -1.0),
                                  approach=[(0.0, -30.0), (0.0, 60.0)])
    assert BS.bridge_crossed(short, [br], 5.0) is br
    away = types.SimpleNamespace(**{**vars(short), "inward": (0.0, 1.0)})
    assert BS.bridge_crossed(away, [br], 5.0) is None
    far = types.SimpleNamespace(bore=types.SimpleNamespace(
        line=LineString([(0.0, 200.0), (0.0, -200.0)])), xy=(0.0, 200.0),
        inward=(0.0, -1.0), approach=[(0.0, 200.0), (0.0, 300.0)])
    assert BS.bridge_crossed(far, [br], 5.0) is None


def test_the_cut_takes_in_the_object_and_stops_at_the_back(tmp_path):
    """28d Q213 / 20as: the corridor's ramp and footprint take in the
    object's whole plan, off the span side; the floor stands the rim
    stand-off off the back (the wall between is the step)."""
    br = _bridge(tmp_path)
    ramp = _sbox(-5.0, -60.0, 5.0, 80.0)          # a corridor reaching into the span
    outer = ramp.buffer(1.6, join_style="mitre")
    r2, o2 = BS.edge_cut(br, ramp, outer, 1.6, 500.0)
    assert r2.bounds[1] >= -20.5 + 1.6 - 0.01
    assert o2.intersection(_sbox(-29.0, -100.0, 29.0, -20.51)).area < 1e-6
    assert r2.bounds[0] <= -29.9 and r2.bounds[2] >= 29.9        # the whole object
    assert r2.intersection(br.cover).area < 1e-6


def test_a_trench_between_two_edge_bridges_is_level_back_to_back(tmp_path):
    """27r: a corridor that runs into ANOTHER bridge's back from its cut
    side stops there (``far_back_s``); met from its span side it is not
    that bridge's cut."""
    br = _bridge(tmp_path)
    other = types.SimpleNamespace(object_id="dsf:obj8", back=((-30.0, 120.0), (30.0, 120.0)),
                                  toward=(0.0, 1.0),
                                  back_line=LineString([(-30.0, 120.0), (30.0, 120.0)]))
    axis = LineString([(0.0, -20.0), (0.0, 300.0)])
    s, met = BS.far_back_s(br, axis, [br, other])
    assert abs(s - 140.0) < 1e-6 and met == (other,)
    facing = types.SimpleNamespace(**{**vars(other), "toward": (0.0, -1.0)})
    assert BS.far_back_s(br, axis, [facing]) is None


def test_the_cover_is_covered_ground_and_the_back_one_walled_mouth(tmp_path, monkeypatch):
    """27l / 28d Q212: inside the cover the ground is lifted to the ground
    beside the cover, outside the cut's ribbon too; the back is ONE walled
    mouth piece, the object's depth tall, taking in the object beyond it."""
    br = _bridge(tmp_path)
    cells = [types.SimpleNamespace(role="primary_parallel", ref="t1", kind="pavement")]
    monkeypatch.setattr(CG, "standing_cover", lambda _c: (cells, [], [PAV]))
    cl = types.SimpleNamespace(cells=tuple(cells))
    ap = types.SimpleNamespace(dem=_Dem(), osm_ways=list(_cut()[0][0].ways))
    xs = np.array([25.0, 0.0])          # outside the ribbon (|x| > 20) / inside
    ys = np.array([-30.0, -30.0])
    zs, rep = CG.covered_ground(ap, cl, LAW, xs, ys, np.array([290.0, 280.0]), (), (br,))
    assert abs(zs[0] - 300.0) < 1e-6 and abs(zs[1] - 300.0) < 1e-6
    pieces = [m for m in rep.mouth_walls if m[2] == br.resource]
    assert len(pieces) == 1 and abs(pieces[0][1] - 26.0) < 0.01
    plan = Polygon(br.plan).difference(br.cover).buffer(-0.5)
    assert Polygon(pieces[0][0]).buffer(0.01).contains(plan)


def test_the_tie_reads_the_excess_over_a_declared_wall_it_crosses():
    """28d / 15b: a vertex beyond a walled mouth, read against the runway
    edge, is forgiven up to the LARGEST declared step its chord crosses —
    never the sum — and the excess still reads (one core for verify and
    the census)."""
    edge = ((0.0, 0.0, 300.0), (200.0, 0.0, 300.0), "10/28", 4, "E")
    pt = [(1, 100.0, -40.0, 277.0, True, "tunnel_ramp")]
    q, tol = 0.01, 0.5
    assert runway_edge_tie(pt, [edge], {}, LAW, q, tol)
    rec = [{"kind": "wall_terrace", "step_m": 23.7, "shapes": ["tunel_A.obj#mouth"],
            "points": [[-20.0, 0.0], [-20.0, 200.0]]},
           {"kind": "wall_terrace", "step_m": 23.5, "shapes": ["tunel_A.obj#mouth"],
            "points": [[-21.0, 0.0], [-21.0, 200.0]]}]
    walls = WallSteps(rec, lambda la, lo: (lo, la))          # [lat, lon] -> (x, y)
    assert abs(walls.allowance(100.0, 0.0, 100.0, -40.0) - 23.7) < 1e-9
    assert not runway_edge_tie(pt, [edge], {}, LAW, q, tol, declared_walls=walls)
    deeper = [(1, 100.0, -40.0, 270.0, True, "tunnel_ramp")]
    (h,) = runway_edge_tie(deeper, [edge], {}, LAW, q, tol, declared_walls=walls)
    assert abs(h.dz + (30.0 - 23.7)) < 1e-9


def test_a_road_deck_over_an_edge_bridge_trench_follows_the_airside_abeam(monkeypatch):
    """28d Q211: each deck vertex is one-way equal to its nearest airside
    pavement vertex (the road follows, the airside leads), under a head
    ``[design] one_way_rulings`` names; a trench no edge bridge pinned
    mints nothing."""
    import auto_patch_v2.constraints.roads as R
    from auto_patch_v2.constraints import edge_deck as ED
    from auto_patch_v2.model.constraints import Linear
    from auto_patch_v2.model.structures import Deck
    v = {0: (0.0, 0.0), 1: (10.0, 0.0), 2: (0.0, 30.0), 3: (10.0, 30.0)}
    faces = {0: types.SimpleNamespace(id=0, role="taxiway", ref="tw", ring=(0, 1)),
             1: types.SimpleNamespace(id=1, role="service_road", ref="bridge_deck:-9",
                                      ring=(2, 3))}
    deck = Deck("bridge_deck:-9", -9, 0.0, 10.0, ())
    tn = types.SimpleNamespace(id="tunnel:-1@0", portal="dsf:obj7", decks=(deck,),
                               edge_back=((0.0, 10.0), (10.0, 10.0)))
    pm = types.SimpleNamespace(
        tunnels=(tn,), faces=faces,
        vertices={k: types.SimpleNamespace(xy=p) for k, p in v.items()},
        ring_vertices=lambda ring: ring)
    monkeypatch.setattr(R, "stage_one_vertices", lambda _pm, _law: frozenset({0, 1}))
    rows = ED.edge_deck_rows(pm, LAW, None)
    assert sorted((r.terms[0][0], r.terms[1][0]) for r in rows) == [(2, 0), (3, 1)]
    assert all(isinstance(r, Linear) and r.lo == r.hi == 0.0 and r.follows == (r.terms[0][0],)
               for r in rows)
    assert ED.RULING in LAW.tables.emit.design.one_way_rulings
    tn.edge_back = ()
    assert ED.edge_deck_rows(pm, LAW, None) == []
