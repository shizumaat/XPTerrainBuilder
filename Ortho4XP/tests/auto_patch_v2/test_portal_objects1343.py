"""#1343 (KBUF) / owner 2026-10-19 #971 ("Tunnel mouths should always stop
at the pavement (or object if one is provided)"): a ROOFED pack object over
a mapped bore's END is the tunnel's PORTAL — the mouth stays AT it and its
floor is the ground less the portal's ROOF TOP (the road is the object's
zero), never the bore law's ``mouth_depth_m``.  A roof taller than the bore
law, a roof that does not stand over the end, and a shell with a floor are
no portal.
"""
from __future__ import annotations

import types

from auto_patch_v2.airport import obj8 as O
from auto_patch_v2.airport import portal_objects as P
from auto_patch_v2.law import Law
from shapely.geometry import box as _sbox

LAW = Law.for_airport("")
THICK = LAW.tables.structures.basin.min_solid_thickness_m


def _box(x, z, w, d, h, y0=0.0):
    x1, z1, y1 = x + w, z + d, y0 + h
    v = [(x, y0, z), (x1, y0, z), (x1, y0, z1), (x, y0, z1),
         (x, y1, z), (x1, y1, z), (x1, y1, z1), (x, y1, z1)]
    faces = [(0, 1, 2), (0, 2, 3), (4, 5, 6), (4, 6, 7),
             (0, 1, 5), (0, 5, 4), (1, 2, 6), (1, 6, 5),
             (2, 3, 7), (2, 7, 6), (3, 0, 4), (3, 4, 7)]
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


def _portal(tmp_path, roof_y=6.0, name="portal.obj", roof_x=-7.0, floor=False):
    """Two side walls (y 0..roof) and a 14 x 20 m roof slab over them,
    running SOUTH from its anchor (z 0..20): the bore runs out of it at
    the anchor."""
    y0 = -4.0 if floor else 0.0          # a shell's walls stand on its floor
    comps = [_box(-7.0, 0.0, 0.5, 20.0, roof_y - y0, y0=y0),
             _box(6.5, 0.0, 0.5, 20.0, roof_y - y0, y0=y0),
             _box(roof_x, 0.0, 14.0, 20.0, 0.3, y0=roof_y - 0.3)]
    if floor:
        comps.append(_box(-6.5, 0.0, 13.0, 20.0, 0.3, y0=-4.0))
    return _write(tmp_path / name, comps)


def _placed(path, oid="dsf:obj1", xy=(0.0, 0.0), extent=(-8.0, -21.0, 8.0, 1.0)):
    return types.SimpleNamespace(id=oid, path=f"objects/{oid}.obj", resolved=path, xy=xy,
                                 heading_deg=0.0, plan_bbox=_sbox(*extent))


#: the bore: its END at the portal's anchor, running north away from it
BORE = types.SimpleNamespace(id=-756, points=[(0.0, 0.5), (0.0, 60.0)])


def _read(objs):
    return P.read_portals(objs, O.ResourceCache(THICK), LAW, [BORE])


def test_a_roofed_object_over_a_bore_end_is_its_portal(tmp_path):
    got, refused = _read([_placed(_portal(tmp_path))])
    assert len(got) == 1 and not refused
    p = got[0]
    assert abs(p.depth_m - 6.0) < 1e-6 and p.way_id == -756 and p.end_xy == (0.0, 0.5)
    assert P.portal_of((0.0, 0.6), got, 5.0) is p
    assert P.portal_of((0.0, 30.0), got, 5.0) is None


def test_a_roof_taller_than_the_bore_law_is_a_building(tmp_path):
    tall = LAW.tables.structures.tunnel.mouth_depth_m + 2.0
    got, refused = _read([_placed(_portal(tmp_path, roof_y=tall))])
    assert got == [] and "a building on the bore, not a portal" in refused[0]


def test_a_roof_that_does_not_stand_over_the_end_is_no_portal(tmp_path):
    """EGGW ``eggw_cabins.obj``: the plan BOX holds the bore end; the roof
    stands 40 m away."""
    got, _r = _read([_placed(_portal(tmp_path, roof_x=40.0), extent=(-8.0, -21.0, 60.0, 1.0))])
    assert got == []


def test_a_shell_with_a_floor_is_not_a_portal(tmp_path):
    got, _r = _read([_placed(_portal(tmp_path, floor=True))])
    assert got == []


def test_a_corridor_object_is_never_read_again(tmp_path):
    got, _r = P.read_portals([_placed(_portal(tmp_path))], O.ResourceCache(THICK), LAW,
                             [BORE], taken={"dsf:obj1"})
    assert got == []


def test_a_low_roof_is_a_deck_and_a_cover_over_a_cut_is_no_portal(tmp_path):
    """EGLL: hard-deck covers at ~0.9 m over bore ends (a deck, not a
    portal); a cover whose walls run below its zero is #1298's class."""
    got, refused = _read([_placed(_portal(tmp_path, roof_y=1.0))])
    assert got == [] and "clears no road" in refused[0]
    comps = [_box(-7.0, 0.0, 0.5, 20.0, 11.0, y0=-5.0), _box(6.5, 0.0, 0.5, 20.0, 11.0, y0=-5.0),
             _box(-7.0, 0.0, 14.0, 20.0, 0.3, y0=5.7)]
    got, _r = _read([_placed(_write(tmp_path / "cover.obj", comps))])
    assert got == []


def test_a_hard_deck_bridge_over_a_bore_end_is_no_portal(tmp_path):
    """LFPG ``H13.obj``: a taxiway bridge over a mapped road is class A's
    (22n), and the trench under it is #1138's (held) — never a portal."""
    comps = [_box(-7.0, 0.0, 0.5, 20.0, 6.0), _box(6.5, 0.0, 0.5, 20.0, 6.0),
             _box(-7.0, 0.0, 14.0, 20.0, 0.3, y0=5.7)]
    got, _r = _read([_placed(_write(tmp_path / "bridge.obj", comps, hard=True))])
    assert got == []


def _pin(role):
    """``structure_mouth._pinned`` at a mouth whose opening stands in one
    face of ``role``; the bore runs north of the mouth, the ramp south."""
    from auto_patch_v2.planar import structure_mouth as SM
    from shapely.geometry import LineString
    axis = LineString([(0.0, 0.0), (0.0, -120.0)])
    group = types.SimpleNamespace(mouth=(0.0, 0.0), inward=(0.0, 1.0))
    face = _sbox(-30.0, -4.0, 30.0, 30.0)
    cells = [types.SimpleNamespace(kind="governed", role=role, ref="pav1")]
    ring = _sbox(-5.0, -6.0, 5.0, 2.0)
    return SM._pinned(group, axis, cells, [face], [], LAW, (), 3.5, 3.6, (), 0.5, (), ring)


def test_a_pinned_mouth_keeps_the_portals_opening_but_never_cuts_a_taxiway():
    """#971 "or object if one is provided": the pavement the portal's
    opening stands in is the portal's — but clause 1 stands: a taxiway at
    the opening is never cut, and the mouth slides as any mapped one."""
    got = _pin("parking_lot")
    assert isinstance(got, tuple) and got[1] == (0.0, 0.0)
    assert all(r != "pav1" for _p, r in got[2])
    assert _pin("cross_connector") == "pav1"


def test_26k_a_portal_cut_may_stand_in_the_runway_strip_and_nothing_else():
    """Owner RULINGS 2026-10-26k (Q155, KBUF site 1): the keep-out refuses a
    wall in the runway strip unless a pack portal pins the mouth."""
    from auto_patch_v2.planar import structure_mouth as SM
    strip = _sbox(0.0, 0.0, 100.0, 50.0)
    inside, clear = _sbox(10.0, 10.0, 30.0, 30.0), _sbox(200.0, 0.0, 220.0, 20.0)
    pin = types.SimpleNamespace(object_id="dsf:obj1")
    assert SM.strip_keepout(inside, strip, None) == SM.STRIP_REFUSED
    assert SM.strip_keepout(inside, strip, pin) == SM.STRIP_PORTAL
    assert SM.strip_keepout(clear, strip, pin) == SM.strip_keepout(clear, strip, None) == ""
    assert SM.strip_keepout(inside, None, None) == ""


def test_a_pinned_mouth_stands_under_its_portals_anchor():
    """KBUF site 1 (``Road_Tunnel.obj`` dsf:obj6856): the portal is drawn on
    the mesh at its ANCHOR, 10.4 m inside the mapped bore end — the mouth
    moves into the bore to it; an anchor on the ramp side keeps the end."""
    from auto_patch_v2.planar import structure_mouth as SM
    from shapely.geometry import LineString
    axis = LineString([(0.0, 0.0), (0.0, -100.0)])        # the ramp runs south
    inward = (0.0, 1.0)                                    # the bore runs north
    moved, d = SM.portal_mouth(axis, inward, (0.2, 10.4))
    assert abs(d - 10.4) < 1e-9 and moved.coords[0] == (0.0, 10.4)
    assert list(moved.coords)[1:] == list(axis.coords)
    same, d0 = SM.portal_mouth(axis, inward, (0.0, -1.5))
    assert same is axis and d0 == 0.0
