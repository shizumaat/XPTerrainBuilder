"""#1971 twins (spec ``docs/specs/interchange-levels-20261113.md`` §7): a
pack interchange — a trench whose walls rise from its floor, a road deck
over it, another over that — read as ONE deck stack: one zero off the
decks' end lines, the floor at the walls' feet through under every deck,
the roads the decks carry mapped bridges between their end lines.

The base fixture is the spec's 3-level X: walls W 12 m apart along frame y
(y -100..100, 3.5 m high, a 6 m crest plate outside each, a pier to y 12),
a lower deck L (60 x 24 m, arched 4.0 at its ends, 5.0 at the crown) at 50
degrees to the corridor, an upper deck U (100 x 21 m, flat at 12.0) at 135
degrees; a rail in the corridor, a road along L, a bridge along U stopping
18 m short of U's ends.  The DEM: the trench 101, a plug 107 under the
decks, the ground 107.5, the road ends 108 (L) and 116 (U) — zero 104.
"""
from __future__ import annotations

import dataclasses as dc
import math
import types

import numpy as np
import pytest
from shapely import affinity
from shapely.geometry import LineString, Point, Polygon, box

from auto_patch_v2.airport import deck_carry as DC
from auto_patch_v2.airport import deck_stack as DS
from auto_patch_v2.airport import obj8 as O
from auto_patch_v2.airport.object_floor import FLOOR_REF, FLOOR_WALL_REF
from auto_patch_v2.airport.road_ways import road_ways
from auto_patch_v2.constraints.deck_stack import deck_stack_rows
from auto_patch_v2.geom.cluster_outline import pad_shade_extra
from auto_patch_v2.geom.lowest_face import floor_z_at
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import OsmWay
from auto_patch_v2.model.deck_stack import DeckStack, StackDeck
from auto_patch_v2.model.frame import Frame
from auto_patch_v2.planar.deck_stack_attach import attach_deck_stacks

LAW = Law.for_airport("")
THICK = LAW.tables.structures.basin.min_solid_thickness_m
FRAME = Frame("ZZZZ", origin=(36.0, -86.0), identity_dp=11)
L_XY, L_H = (1.0, 2.0), 50.0
U_XY, U_H = (-1.0, -3.0), 135.0


@dc.dataclass(frozen=True)
class _Airport:
    frame: object
    osm_ways: tuple
    dem: object
    pavements: tuple = ()
    runways: tuple = ()
    deck_stacks: tuple = ()
    stack_shade: object = None
    osm_ways_mapped: tuple | None = None
    sunken_ramps: object = None
    wall_shade: object = None
    entrance_shade: object = None


def _quad(a, b, c, d):
    return [(a, b, c), (a, c, d)]


def _write(path, solid, deck=()):
    """An OBJ8 of ``solid`` triangles (no hardness) and ``deck`` triangles
    (``ATTR_hard_deck``)."""
    verts = [p for tri in [*deck, *solid] for p in tri]
    out = ["A", "800", "OBJ", "", f"POINT_COUNTS {len(verts)} 0 0 {len(verts)}"]
    out += [f"VT {v[0]:.4f} {v[1]:.4f} {v[2]:.4f} 0 1 0 0 0" for v in verts]
    out += [f"IDX {i}" for i in range(len(verts))]
    if deck:
        out += ["ATTR_hard_deck concrete", f"TRIS 0 {3 * len(deck)}", "ATTR_no_hard"]
    if solid:
        out += [f"TRIS {3 * len(deck)} {3 * len(solid)}"]
    path.write_text("\n".join(out) + "\n", encoding="utf-8", newline="")
    return str(path)


def _walls(h=3.5, floor_plate=False, roof=False):
    """Two walls at authored x = +-6, their crest plates out to +-12, no
    floor face; a pier to y 12 on each plate."""
    tris = []
    for s in (1.0, -1.0):
        xi, xo = 6.0 * s, 12.0 * s
        tris += _quad((xi, 0, -100), (xi, 0, 100), (xi, h, 100), (xi, h, -100))
        tris += _quad((xo, 0, -100), (xo, 0, 100), (xo, h, 100), (xo, h, -100))
        tris += _quad((xi, h, -100), (xo, h, -100), (xo, h, 100), (xi, h, 100))
        for z in (-100.0, 100.0):
            tris += _quad((xi, 0, z), (xo, 0, z), (xo, h, z), (xi, h, z))
        px = 9.0 * s
        for (ax, az), (bx, bz) in (((px - .5, -1), (px + .5, -1)), ((px + .5, -1), (px + .5, 1)),
                                   ((px + .5, 1), (px - .5, 1)), ((px - .5, 1), (px - .5, -1))):
            tris += _quad((ax, h, az), (bx, h, bz), (bx, 12.0, bz), (ax, 12.0, az))
        tris += _quad((px - .5, 12, -1), (px + .5, 12, -1), (px + .5, 12, 1), (px - .5, 12, 1))
    if floor_plate:
        tris += _quad((-6, 0, -100), (6, 0, -100), (6, 0, 100), (-6, 0, 100))
    if roof:
        tris += _quad((-12, 6, -100), (12, 6, -100), (12, 6, 100), (-12, 6, 100))
    return tris


def _plate(w, length, y_of, n=6):
    """A plate ``w`` wide (x) and ``length`` long (z), its height ``y_of(z)``."""
    out = []
    zs = [-length / 2 + length * k / n for k in range(n + 1)]
    for a, b in zip(zs[:-1], zs[1:], strict=True):
        out += _quad((-w / 2, y_of(a), a), (w / 2, y_of(a), a), (w / 2, y_of(b), b),
                     (-w / 2, y_of(b), b))
    return out


def _placed(tmp_path, oid, xy, h, solid=(), deck=(), plan=None, deck_box=None, agl=0.0):
    aff = O.placement_affine(xy, h)
    hd = affinity.affine_transform(box(*deck_box), aff) if deck_box else None
    bbox = affinity.affine_transform(box(*plan), aff)
    return types.SimpleNamespace(
        id=oid, path=f"objects/{oid}.obj", resolved=_write(tmp_path / f"{oid}.obj", solid, deck),
        xy=xy, heading_deg=h, kind="OBJECT", anchor_z=104.0, agl_m=agl,
        deck_kind="flag" if deck else "", hard_deck=hd, deck_top_z=None, plan_bbox=bbox)


def _axis(h):
    r = math.radians(h)
    return (-math.sin(r), -math.cos(r))


def _at(xy, h, t):
    d = _axis(h)
    return (round(xy[0] + d[0] * t, 6), round(xy[1] + d[1] * t, 6))


class _Dem:
    def __init__(self, u_end=116.0):
        self.u_end = u_end

    def z(self, x, y):
        for xy, h, half, w, end in ((L_XY, L_H, 30.0, 12.5, 108.0),
                                    (U_XY, U_H, 50.0, 11.0, self.u_end)):
            d = _axis(h)
            a = (x - xy[0]) * d[0] + (y - xy[1]) * d[1]
            c = abs(-(x - xy[0]) * d[1] + (y - xy[1]) * d[0])
            if half <= abs(a) <= half + 15.0 and c <= w:
                return end
        if abs(x) < 6.0:
            return 107.0 if abs(y) < 25.0 else 101.0
        return 107.5


def _way(i, pts, **tags):
    return OsmWay(i, "big_roads", tuple(pts), False, dict(tags))


def _ways(rail=True, l_layer=None):
    out = []
    if rail:
        out += [_way(-1, [(0, -40), (0, 0), (0, 40)], railway="rail", tunnel="yes", layer="-1"),
                _way(-2, [(0, -500), (0, -40)], railway="rail"),
                _way(-3, [(0, 40), (0, 500)], railway="rail")]
    lt = {"layer": l_layer} if l_layer else {}
    out.append(_way(-10, [_at(L_XY, L_H, t) for t in (-150, -60, 0, 60, 150)],
                    highway="primary", **lt))
    out += [_way(-21, [_at(U_XY, U_H, t) for t in (-200, -32)], highway="primary"),
            _way(-20, [_at(U_XY, U_H, t) for t in (-32, 0, 32)], highway="primary",
                 bridge="yes", layer="1"),
            _way(-22, [_at(U_XY, U_H, t) for t in (32, 200)], highway="primary")]
    return tuple(out)


def _objects(tmp_path, upper=True, walls=None, l_xy=L_XY, l_h=L_H):
    ws = walls if walls is not None else _walls()
    out = [_placed(tmp_path, "W", (0.0, 0.0), 0.0, solid=ws, plan=(-12, -100, 12, 100))]
    out.append(_placed(tmp_path, "L", l_xy, l_h,
                       deck=_plate(24.0, 60.0, lambda z: 4.0 + (1.0 - (z / 30.0) ** 2)),
                       plan=(-12, -30, 12, 30), deck_box=(-12, -30, 12, 30)))
    if upper:
        out.append(_placed(tmp_path, "U", U_XY, U_H, deck=_plate(21.0, 100.0, lambda z: 12.0),
                           plan=(-10.5, -50, 10.5, 50), deck_box=(-10.5, -50, 10.5, 50)))
    return out


def _attach(tmp_path, objects=None, ways=None, dem=None, pavements=(), notes=None):
    objs = objects if objects is not None else _objects(tmp_path)
    a = _Airport(FRAME, ways if ways is not None else _ways(), dem or _Dem(),
                 pavements=pavements)
    cache = O.ResourceCache(THICK)
    return attach_deck_stacks(a, objs, cache, LAW, notes), objs, cache


# ── S1: the readers ──────────────────────────────────────────────────────

def test_t1_the_three_level_x_is_one_stack(tmp_path):
    a, _o, _c = _attach(tmp_path)
    (st,) = a.deck_stacks
    assert st.id == "stack:W" and {m for m, _r in st.members} == {"W", "L", "U"}
    assert abs(st.feet_y) < 1e-6 and abs(st.crest_y - 3.5) < 1e-6      # never the pier's 12
    by = {d.object_id: d for d in st.decks}
    assert by["L"].level == 1 and by["U"].level == 2
    assert by["L"].carried == (-10,) and -1 in by["L"].under
    assert set(by["U"].carried) == {-20, -21, -22} and -10 in by["U"].under
    assert -1 in st.under_ways and -10 not in st.under_ways


def test_t2_walls_and_one_deck_are_a_one_level_stack(tmp_path):
    a, _o, _c = _attach(tmp_path, objects=_objects(tmp_path, upper=False))
    (st,) = a.deck_stacks
    assert st.levels == 1 and {m for m, _r in st.members} == {"W", "L"}


def test_t3_two_decks_crossing_with_no_walls_are_no_stack(tmp_path):
    objs = _objects(tmp_path)[1:]
    a0 = _Airport(FRAME, _ways(), _Dem())
    a = attach_deck_stacks(a0, objs, O.ResourceCache(THICK), LAW)
    assert a is a0 and a.deck_stacks == ()


@pytest.mark.parametrize("case", ["low", "no_route", "floor_plate", "beside", "garage"])
def test_t4_nothing_below_grade_never_mints_a_stack(tmp_path, case):
    """#1961 / #1966 / #1950: walls too low, nothing running in them, a floor
    of their own, a deck beside them, a roofed garage with no hard deck."""
    objs, ways = _objects(tmp_path), _ways()
    if case == "low":
        objs = _objects(tmp_path, walls=_walls(h=1.0))
    elif case == "no_route":
        ways = _ways(rail=False)
    elif case == "floor_plate":
        objs = _objects(tmp_path, walls=_walls(floor_plate=True))
    elif case == "beside":
        objs = _objects(tmp_path, upper=False, l_xy=(60.0, 0.0))
    elif case == "garage":
        objs = _objects(tmp_path, walls=_walls(roof=True))[:1]
    a, _o, _c = _attach(tmp_path, objects=objs, ways=ways)
    assert a.deck_stacks == () and a.osm_ways == ways


def test_t5_a_spanning_deck_off_the_floor_is_no_member(tmp_path):
    notes: list[str] = []
    objs = _objects(tmp_path, upper=False, l_xy=(20.0, 0.0), l_h=90.0)
    a, _o, _c = _attach(tmp_path, objects=objs, notes=notes)
    assert a.deck_stacks == ()
    assert any("deck L spans the floor but is no member" in n for n in notes)


def test_t6_the_arched_decks_end_top_is_the_plate_on_its_end_edge(tmp_path):
    a, _o, _c = _attach(tmp_path)
    lo = next(d for d in a.deck_stacks[0].decks if d.object_id == "L")
    assert abs(lo.top_a - 4.0) < 0.01 and abs(lo.top_b - 4.0) < 0.01   # never the crown 5.0


def test_t7_across_is_side_to_side_and_end_to_side_is_a_note():
    piece = box(-12, -30, 12, 30)
    plate = np.array([[(-12, -30, 4), (12, -30, 4), (12, 30, 4)],
                      [(-12, -30, 4), (12, 30, 4), (-12, 30, 4)]], float)
    across = (_way(-5, [(-40, 0), (40, 0)], railway="rail"), LineString([(-40, 0), (40, 0)]))
    odd = (_way(-6, [(0, -60), (0, -10), (40, 0)], highway="service"),
           LineString([(0, -60), (0, -10), (40, 0)]))
    c = DC.carry_of(piece, plate, [across, odd], LAW)
    assert c.across == (-5,) and c.carried == ()
    assert any("way -6" in n and "unclassified" in n for n in c.notes)


def test_t8_layers_contradicting_the_levels_refuse_the_stack(tmp_path):
    notes: list[str] = []
    a, _o, _c = _attach(tmp_path, ways=_ways(l_layer="2"), notes=notes)
    assert a.deck_stacks == () and any("contradict the levels" in n for n in notes)


# ── S2: the derivation and the attach ────────────────────────────────────

def test_t9_one_zero_is_the_mean_over_the_end_lines(tmp_path):
    a, _o, _c = _attach(tmp_path)
    st = a.deck_stacks[0]
    zs = [g - t for _d, _k, _s, g, t in st.end_zeros]
    assert len(zs) == 4 and abs(st.zero_z - sum(zs) / len(zs)) < 1e-3
    assert abs(st.zero_z - 104.0) < 0.01 and abs(st.floor_z - 104.0) < 0.01
    notes: list[str] = []
    a, _o, _c = _attach(tmp_path, dem=_Dem(u_end=122.0), notes=notes)
    assert a.deck_stacks == () and any("clearance_m" in n for n in notes)


def test_t10_a_carried_stretch_is_a_mapped_bridge_and_no_ribbon(tmp_path):
    a, _o, _c = _attach(tmp_path)
    low = [w for w in a.osm_ways if w.id == -10]
    assert len(low) == 3
    mid = [w for w in low if w.tags.get(DC.DECK_TAG)]
    assert len(mid) == 1 and mid[0].tags["bridge"] == "yes" and "layer" not in mid[0].tags
    assert abs(LineString(mid[0].points).length - 60.0) < 0.5
    stubs = [w for w in a.osm_ways if w.id in (-21, -22) and w.tags.get(DC.DECK_TAG) == "U"]
    assert len(stubs) == 2 and all(abs(LineString(w.points).length - 18.0) < 0.5 for w in stubs)
    lines = [ln for w, ln in road_ways(a.osm_ways) if w.id == -10]
    assert lines and all(ln.distance(Point(L_XY)) > 25.0 for ln in lines)


def test_t11_the_attach_is_idempotent_and_leaves_no_stack_untouched(tmp_path):
    a, objs, cache = _attach(tmp_path)
    b = attach_deck_stacks(a, objs, cache, LAW)
    assert b.osm_ways == a.osm_ways and b.deck_stacks == a.deck_stacks
    assert b.osm_ways_mapped == _ways()
    a0 = _Airport(FRAME, _ways(rail=False), _Dem())
    assert attach_deck_stacks(a0, objs, cache, LAW) is a0


def test_t12_the_shade_takes_the_walls_out_of_every_pad(tmp_path):
    a, _o, _c = _attach(tmp_path)
    cap = Point(9.0, 50.0)
    assert a.stack_shade.contains(cap) and a.stack_shade.contains(Point(0.0, 0.0))
    assert pad_shade_extra(a).contains(cap)
    fl, _n = DS.stack_floors(a.deck_stacks)
    assert set(fl[0].covers) == {"L", "U"}


# ── S3: the floor and the rows ───────────────────────────────────────────

def test_t13_the_floor_is_between_the_walls_through_the_plug(tmp_path):
    pav = (types.SimpleNamespace(outer=((-30, 150), (30, 150), (30, 160), (-30, 160)),
                                 holes=()),)
    notes: list[str] = []
    a, _o, _c = _attach(tmp_path, pavements=pav, notes=notes)
    st = a.deck_stacks[0]
    (fl,), _n = DS.stack_floors(a.deck_stacks)
    assert fl.kind == "floor" and fl.decks == () and fl.id == FLOOR_REF + st.id
    assert {s[0] for s in fl.seats} == {"W", "L", "U"}
    assert all(abs(s[2] - st.zero_z) < 1e-9 for s in fl.seats)
    floor = Polygon(st.floor).buffer(0)
    assert abs(floor.bounds[0] + 6.0) < 0.3 and abs(floor.bounds[2] - 6.0) < 0.3   # not the hull
    assert abs(float(floor_z_at(fl.faces, [0.0], [0.0])[0]) - st.floor_z) < 1e-6   # the plug goes
    south = [r for r in st.runouts if min(p[1] for p in r[0]) < -150]
    assert south and abs(south[0][2] - 101.0) <= 0.06                               # meets ground
    run = -100.0 - min(p[1] for p in south[0][0])
    assert run >= (104.0 - 101.0) / LAW.tables.structures.tunnel.rail_ramp_max_grade - 1.0
    assert any("stops at airside pavement" in n for n in notes)


def _stub_map(stack):
    """A planar stub: the floor face, its void band, a road face at L's end
    line A, a ground face inside L's ring off the floor."""
    d = next(x for x in stack.decks if x.object_id == "L")
    faces, verts = {}, {}

    def face(role, ref, pts):
        ids = []
        for p in pts:
            verts[len(verts)] = types.SimpleNamespace(xy=tuple(p), incident_faces=[len(faces)])
            ids.append(len(verts) - 1)
        faces[len(faces)] = types.SimpleNamespace(role=role, ref=ref, ring=tuple(ids), holes=())
    face("tunnel_trench", FLOOR_REF + stack.id, [(-6, -10), (6, -10), (6, 10), (-6, 10)])
    face("retaining_wall", FLOOR_WALL_REF + stack.id, [(-7, -10), (-7, 10), (7, 10), (7, -10)])
    ea = np.mean(np.asarray(d.end_a), axis=0)
    face("service_road", "big_roads:-10", [tuple(ea + o) for o in ((-1, 0), (1, 0), (0, 1))])
    c = np.mean(np.asarray(d.ring), axis=0) + np.array([8.0, 0.0])
    face("grass", "ground", [tuple(c + o) for o in ((0, 0), (1, 0), (0, 1))])
    return types.SimpleNamespace(faces=faces, vertices=verts, ring_vertices=lambda r: list(r))


def test_t14_the_rows_end_lines_rim_and_ceilings(tmp_path):
    a, _o, _c = _attach(tmp_path)
    st = a.deck_stacks[0]
    rows = deck_stack_rows(_stub_map(st), LAW, a)
    flush = LAW.tables.structures.bridge.deck_flush_m
    z_end = st.zero_z + next(d for d in st.decks if d.object_id == "L").top_a
    ends = [r for r in rows if "end a" in r.source.inputs[2]]
    assert len(ends) == 3 and all(abs(r.lo - (z_end - flush)) < 1e-9
                                  and abs(r.hi - (z_end + flush)) < 1e-9 for r in ends)
    rim = [r for r in rows if r.source.inputs[2] == "the walls' top"]
    crest = st.zero_z + st.crest_y
    assert rim and all(abs(r.hi - crest) < 1e-9 and abs(r.lo - (crest - 0.5)) < 1e-9
                       for r in rim)
    ceil = [r for r in rows if "under the deck" in r.source.inputs[2]]
    assert ceil and all(r.lo is None for r in ceil)
    assert all(r.hi <= st.zero_z + 5.0 for r in ceil if r.source.inputs[1] == "L")
    assert all(r.source.ruling.startswith("structures.hard-deck bridge") for r in rows)
    # a vertex two end lines claim at different heights is refused by both
    lo = next(d for d in st.decks if d.object_id == "L")
    two = dc.replace(st, decks=(lo, dc.replace(lo, object_id="X", top_a=lo.top_a + 1.0)))
    rows2 = deck_stack_rows(_stub_map(two), LAW, dc.replace(a, deck_stacks=(two,)))
    assert not [r for r in rows2 if "end a" in r.source.inputs[2]]


def test_t15_no_stack_no_rows():
    a0 = _Airport(FRAME, _ways(), _Dem())
    assert deck_stack_rows(types.SimpleNamespace(faces={}, vertices={}), LAW, a0) == []


def test_the_model_record_holds_the_floor_rule():
    st = DeckStack("stack:W", "W", "w.obj", (("W", "w.obj"),), 1.0, 0.0, (), -0.05, 3.5,
                   ((0.0, 0.0),), (), (), (), (StackDeck("L", "l.obj", 0, (), 1, (), (), (), (),
                                                         4.0, 4.0),))
    assert st.floor_z == pytest.approx(0.95) and st.levels == 1


# ── S4: the sidecar ──────────────────────────────────────────────────────

def test_t16_the_sidecar_floor_record_carries_the_stack(tmp_path):
    from auto_patch_v2.pipeline.publication import object_floors
    a, _o, _c = _attach(tmp_path)
    fl, _n = DS.stack_floors(a.deck_stacks)
    (rec,) = object_floors(types.SimpleNamespace(object_floors=tuple(fl)), a)
    st = rec["stack"]
    assert rec["id"] == FLOOR_REF + "stack:W" and st["zero_m"] == pytest.approx(104.0, abs=0.01)
    assert {d["object"] for d in st["decks"]} == {"L", "U"} and st["levels"] == 2
    assert all(len(d["ends"]) == 2 and d["ends"][0]["stations"] for d in st["decks"])
    assert st["floor_line"] and len(st["rim"]) == 2
