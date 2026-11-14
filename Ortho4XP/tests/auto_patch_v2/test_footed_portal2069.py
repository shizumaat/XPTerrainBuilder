"""#2069 (NZWN ``Tunnel.obj``; owner RULINGS 2026-10-26p Q167, #971): a
roofed pack portal whose walls hang under its zero, with no floor plate and
no hard deck, stands on its walls' FEET -- the mouth's floor is its zero plus
that foot.  A part pins a bore end its roof stands over, or one whose mapped
road runs under its roof within the shortest lawful ramp; its mouth stands
at the back of its roof.  Before: refused as "walls under its zero", the
bore then refused as entering a pack building -- no ramp, no cut, no seat.
"""
from __future__ import annotations

import types

from auto_patch_v2.airport import obj8 as O
from auto_patch_v2.airport import portal_objects as P
from auto_patch_v2.airport.footed_portal import footed_parts
from auto_patch_v2.law import Law
from shapely.geometry import LineString
from shapely.geometry import box as _sbox

LAW = Law.for_airport("")
THICK = LAW.tables.structures.basin.min_solid_thickness_m
GROUND, ZERO, FOOT, ROOF = 4.0, 3.4, -4.0, 7.0


def _box(x, z, w, d, y0, y1):
    x1, z1 = x + w, z + d
    v = [(x, y0, z), (x1, y0, z), (x1, y0, z1), (x, y0, z1),
         (x, y1, z), (x1, y1, z), (x1, y1, z1), (x, y1, z1)]
    faces = [(4, 5, 6), (4, 6, 7), (0, 1, 5), (0, 5, 4), (1, 2, 6), (1, 6, 5),
             (2, 3, 7), (2, 7, 6), (3, 0, 4), (3, 4, 7)]      # no floor face
    return [(v[a], v[b], v[c]) for a, b, c in faces]


def _write(path, comps, hard=False):
    verts = [p for comp in comps for tri in comp for p in tri]
    out = ["A", "800", "OBJ", "", f"POINT_COUNTS {len(verts)} 0 0 {len(verts)}"]
    out += [f"VT {v[0]:.4f} {v[1]:.4f} {v[2]:.4f} 0 1 0 0 0" for v in verts]
    out += [f"IDX {i}" for i in range(len(verts))]
    if hard:
        out.append("ATTR_hard_deck concrete")
    out.append(f"TRIS 0 {len(verts)}")
    path.write_text("\n".join(out) + "\n", encoding="utf-8", newline="")
    return str(path)


def _portal(tmp_path, z0=0.0, name="footed.obj", hard=False, extra=()):
    """A 16 x 20 m roofed box hanging FOOT under its zero, z0..z0+20 south
    of its anchor (+z is south)."""
    return _write(tmp_path / name, [_box(-8.0, z0, 16.0, 20.0, FOOT, ROOF), *extra], hard)


def _placed(path, extent):
    return types.SimpleNamespace(id="dsf:obj1", path="objects/footed.obj", resolved=path,
                                 xy=(0.0, 0.0), heading_deg=0.0, plan_bbox=_sbox(*extent),
                                 kind="OBJECT", anchor_z=ZERO, agl_m=0.0)


#: the bore: its END at (0, 0.5), running north away from the portals
BORE = types.SimpleNamespace(id=-199, points=[(0.0, 0.5), (0.0, 80.0)], tags={"tunnel": "yes"})
#: the open road leaving the end, south
ROAD = types.SimpleNamespace(id=-200, points=[(0.0, -200.0), (0.0, 0.5)],
                             tags={"highway": "secondary"})


def _read(objs, roads=(ROAD,)):
    return P.read_portals(objs, O.ResourceCache(THICK), LAW, [BORE], dem_z=lambda x, y: GROUND,
                          roads=roads)


def test_a_portal_on_its_walls_feet_over_the_end_is_read_at_its_foot(tmp_path):
    got, refused = _read([_placed(_portal(tmp_path), (-8.0, -21.0, 8.0, 1.0))])
    assert len(got) == 1, refused
    p = got[0]
    assert p.footed and p.way_id == -199 and p.end_xy == (0.0, 0.5)
    assert abs(p.floor_z - (ZERO + FOOT)) < 1e-6 and abs(p.bottom_y - FOOT) < 1e-6
    assert abs(p.depth_m - (GROUND - ZERO - FOOT)) < 1e-6
    # its body is seated at its own roof, not at the end (the seat's anchor)
    assert -20.0 < p.anchor_xy[1] < 0.0 and p.face_plan.area > 100.0


def test_a_portal_up_the_open_road_pins_the_end_its_road_leaves(tmp_path):
    """NZWN west: the portal stands 40 m up the open road from the mapped end."""
    objs = [_placed(_portal(tmp_path, z0=40.0), (-8.0, -61.0, 8.0, 1.0))]
    got, _r = _read(objs)
    assert len(got) == 1 and got[0].end_xy == (0.0, 0.5)
    got, refused = _read(objs, roads=())
    assert got == [] and "no part pins a mapped bore end" in refused[0]


def test_a_portal_past_the_shortest_lawful_ramp_pins_nothing(tmp_path):
    tn = LAW.tables.structures.tunnel
    z0 = tn.mouth_depth_m / tn.ramp_max_grade + 5.0
    got, _r = _read([_placed(_portal(tmp_path, z0=z0), (-8.0, -z0 - 21.0, 8.0, 1.0))])
    assert got == []


def test_one_object_with_two_portals_pins_both_ends_of_its_bore(tmp_path):
    """NZWN ``Tunnel.obj``: both portals of bore -199 in one OBJ8, one per
    genuine component."""
    far = _box(-8.0, -100.0, 16.0, 20.0, FOOT + 1.0, ROOF + 1.0)     # north, over the far end
    bore = types.SimpleNamespace(id=-199, points=[(0.0, 0.5), (0.0, 79.5)], tags={})
    o = _placed(_portal(tmp_path, extra=[far]), (-8.0, -21.0, 8.0, 101.0))
    got, _r = P.read_portals([o], O.ResourceCache(THICK), LAW, [bore],
                             dem_z=lambda x, y: GROUND, roads=())
    assert sorted(p.end_xy for p in got) == [(0.0, 0.5), (0.0, 79.5)]
    assert sorted(round(p.bottom_y, 6) for p in got) == [FOOT, FOOT + 1.0]


def test_a_hard_deck_or_a_floor_is_never_a_footed_portal(tmp_path):
    """EGLL's covers are hard decks (#1298); a shell carries a floor."""
    got, _r = _read([_placed(_portal(tmp_path, hard=True), (-8.0, -21.0, 8.0, 1.0))])
    assert got == []
    floor = _box(-8.0, 0.0, 16.0, 20.0, FOOT - 0.3, FOOT)
    cache = O.ResourceCache(THICK)
    path = _portal(tmp_path, name="shell.obj", extra=[floor])
    g = cache.geometry(path)
    assert isinstance(footed_parts(g, cache.genuine(path), LAW), str)


def test_the_mouth_stands_at_the_back_of_the_roof():
    from auto_patch_v2.planar import structure_mouth as SM
    axis = LineString([(0.0, 0.0), (0.0, -100.0)])        # the ramp runs south
    inward = (0.0, 1.0)                                    # the bore runs north
    up_road = _sbox(-8.0, -60.0, 8.0, -40.0)
    moved, d = SM.roof_back_mouth(axis, inward, up_road)
    assert abs(d + 40.0) < 1e-9 and moved.coords[0] == (0.0, -40.0)
    over = _sbox(-8.0, -10.0, 8.0, 6.0)                  # reaches over the bore
    moved, d = SM.roof_back_mouth(axis, inward, over)
    assert abs(d - 6.0) < 1e-9 and moved.coords[0] == (0.0, 6.0)
