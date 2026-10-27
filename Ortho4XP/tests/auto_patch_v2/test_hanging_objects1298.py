"""Owner RULINGS 2026-10-26p (Q164–Q168; #1298 EGLL/EGGW, #1138 KATL) and
2026-10-20am/an/ar/at: a HANGING pack object — solids hanging below its zero
with no floor at its walls' bottom — sets the cut.  With a flush hard deck it
is a COVER (the trench is cut under the deck; a co-placed floor object is read
with it as one tunnel; without one the depth is the walls' bottom); without a
hard deck at a bore end it is a PORTAL whose depth is its walls' bottom, read
from the ground beside the cover, and the cut takes in its whole plan.
"""
from __future__ import annotations

import types

import numpy as np
from shapely.geometry import LineString
from shapely.geometry import box as _sbox

from auto_patch_v2.airport import hanging_objects as HO
from auto_patch_v2.airport import obj8 as O
from auto_patch_v2.airport import portal_objects as P
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import OsmWay
from auto_patch_v2.planar import covered_ground as CG
from auto_patch_v2.planar import structure_mouth as SM

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


def _write(path, comps, hard=()):
    """An OBJ8 of ``comps``; the components indexed in ``hard`` are written
    under ``ATTR_hard_deck``."""
    verts = [p for comp in comps for tri in comp for p in tri]
    out = ["A", "800", "OBJ", "", f"POINT_COUNTS {len(verts)} 0 0 {len(verts)}"]
    out += [f"VT {v[0]:.4f} {v[1]:.4f} {v[2]:.4f} 0 1 0 0 0" for v in verts]
    out += [f"IDX {i}" for i in range(len(verts))]
    k = 0
    for i, comp in enumerate(comps):
        n = 3 * len(comp)
        if i in hard:
            out.append("ATTR_hard_deck concrete")
        out.append(f"TRIS {k} {n}")
        if i in hard:
            out.append("ATTR_no_hard")
        k += n
    path.write_text("\n".join(out) + "\n", encoding="utf-8", newline="")
    return str(path)


def _cover(tmp_path, name="cover.obj"):
    """A 20 x 80 m deck slab at y 0 (hard deck) on two side walls hanging to
    −5 m, open at both ends (z = 0 and z = 80): no floor."""
    comps = [_box(-10.0, 0.0, 20.0, 80.0, 0.3, y0=-0.3),
             _box(-10.0, 0.0, 0.5, 80.0, 5.0, y0=-5.0), _box(9.5, 0.0, 0.5, 80.0, 5.0, y0=-5.0)]
    return _write(tmp_path / name, comps, hard={0})


def _floor(tmp_path, name="floor.obj", y=-5.0):
    """The co-placed FLOOR object: a plate at ``y`` between the walls."""
    return _write(tmp_path / name, [_box(-9.5, 0.0, 19.0, 80.0, 0.5, y0=y)], hard={0})


def _placed(path, oid, xy=(0.0, 0.0)):
    return types.SimpleNamespace(id=oid, path=f"objects/{oid}.obj", resolved=path, xy=xy,
                                 heading_deg=0.0, kind="OBJECT", anchor_z=100.0, agl_m=0.0,
                                 plan_bbox=_sbox(-11.0, -81.0, 11.0, 1.0))


def test_the_walls_bottom_is_the_depth_of_an_object_with_no_floor(tmp_path):
    g = O.parse_obj8(_cover(tmp_path))
    assert abs(HO.hanging_bottom(g.vertices, g.solid, LAW) + 5.0) < 1e-6
    both = O.parse_obj8(_write(tmp_path / "shell.obj",
                               [_box(-10.0, 0.0, 0.5, 80.0, 5.0, y0=-5.0),
                                _box(-10.0, 0.0, 20.0, 80.0, 0.3, y0=-5.0)]))
    assert HO.hanging_bottom(both.vertices, both.solid, LAW) is None     # it has a floor


def test_a_hanging_cover_alone_is_a_shell_at_its_walls_bottom(tmp_path):
    """Q167: no floor object — the depth is the walls' bottom (−5 m)."""
    cache = O.ResourceCache(THICK)
    cuts, refused = HO.read_hanging_covers([_placed(_cover(tmp_path), "dsf:obj1")], cache,
                                           LAW, set(), {}, {})
    assert len(cuts) == 1, refused
    c = cuts[0]
    assert abs(c.floor_y + 5.0) < 0.31 and abs(c.floor_z - 95.0) < 0.31
    assert c.object_id == c.cover_object_id == "dsf:obj1"


def test_a_split_floor_and_cover_are_one_tunnel(tmp_path):
    """Q166 (EGLL ``Na.obj`` + ``N.obj``): the floor is the floor object's
    authored plate, both placements are the tunnel's."""
    cache = O.ResourceCache(THICK)
    objs = [_placed(_cover(tmp_path), "dsf:obj1"), _placed(_floor(tmp_path, y=-4.0), "dsf:obj2")]
    cuts, refused = HO.read_hanging_covers(objs, cache, LAW, set(), {}, {})
    assert len(cuts) == 1, refused
    c = cuts[0]
    assert c.object_id == "dsf:obj2" and c.cover_object_id == "dsf:obj1"
    assert abs(c.floor_y + 4.0) < 1e-6


def test_a_bare_face_at_a_bore_end_is_a_hanging_portal(tmp_path):
    """Q168 (EGGW ``eggw_tex14``): one vertical face to −8.33 m, its line
    the bore end's tolerance off on either side."""
    q = [(-20.0, 0.06, 0.0), (20.0, 0.06, 0.0), (20.0, -8.33, 0.0), (-20.0, -8.33, 0.0)]
    face = _write(tmp_path / "face.obj", [[(q[0], q[1], q[2]), (q[0], q[2], q[3])]])
    o = types.SimpleNamespace(id="dsf:obj3", path="objects/face.obj", resolved=face, xy=(0.0, 0.0),
                              heading_deg=0.0, plan_bbox=_sbox(-20.0, -1.0, 20.0, 1.0))
    bore = types.SimpleNamespace(id=-908, points=[(0.0, -8.0), (0.0, -80.0)])
    got, _r = P.read_portals([o], O.ResourceCache(THICK), LAW, [bore])
    assert len(got) == 1 and got[0].hanging and abs(got[0].depth_m - 8.39) < 1e-6
    deck = _write(tmp_path / "deckface.obj", [[(q[0], q[1], q[2]), (q[0], q[2], q[3])]], hard={0})
    o2 = types.SimpleNamespace(**{**vars(o), "resolved": deck})
    assert P.read_portals([o2], O.ResourceCache(THICK), LAW, [bore])[0] == []


def test_a_hanging_portals_cut_takes_in_its_plan():
    """20an / 20as: the mouth moves to the object's furthest point into the bore."""
    axis = LineString([(0.0, 0.0), (0.0, -100.0)])
    moved, d = SM.portal_mouth(axis, (0.0, 1.0), (0.0, 5.0), ((-10.0, 0.0), (10.0, 30.0)))
    assert abs(d - 30.0) < 1e-9 and moved.coords[0] == (0.0, 30.0)


class _Dem:
    """A bare-earth DEM's view of a covered road: a 20 m-deep cut, 40 m wide."""

    def z_many(self, xs, ys):
        return np.where(np.abs(np.asarray(xs, dtype=float)) < 20.0, 280.0, 300.0)

    def z(self, x, y):
        return float(self.z_many([x], [y])[0])


def test_the_portal_ground_is_the_ground_beside_the_cover():
    """KATL (#714): the DEM carries the road (280) under the lid; the
    portal's top is flush with the field beside it (300)."""
    from auto_patch_v2.planar.structure_approach import chains
    way = OsmWay(-1, "big_roads", ((0.0, -100.0), (0.0, 100.0)), False,
                 {"highway": "motorway", "tunnel": "yes", "lanes": "5"})
    bore = chains([way])[0]
    assert abs(CG.beside_ground(_Dem(), bore, LAW, (0.0, 0.0)) - 300.0) < 1e-6
