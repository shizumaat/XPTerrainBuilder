"""Owner RULINGS 2026-10-26p (Q164–Q168; #1298 EGLL/EGGW, #1138 KATL) and
2026-10-20am/an/ar/at: a HANGING pack object — solids hanging below its zero
with no floor at its walls' bottom — sets the cut.  With a flush hard deck it
is a COVER (the trench is cut under the deck; a co-placed floor object is read
with it as one tunnel; without one the depth is the walls' bottom); without a
hard deck at a bore end it is a PORTAL whose depth is its walls' bottom, read
from the ground beside the cover, and the cut takes in its whole plan.  With a
deck slab but still no hard deck it is an EDGE-WALL BRIDGE (2026-10-27l): the
trench stops at its walls' back and every deck over it keeps its deck level.
"""
from __future__ import annotations

import types

import numpy as np
from auto_patch_v2.airport import hanging_objects as HO
from auto_patch_v2.airport import obj8 as O
from auto_patch_v2.airport import portal_objects as P
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import OsmWay
from auto_patch_v2.planar import covered_ground as CG
from auto_patch_v2.planar import structure_mouth as SM
from shapely.geometry import LineString
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


def _edge_bridge(tmp_path):
    """KATL ``tunel_C`` in miniature (#1138): a 60 x 20 m deck slab at y 0
    (plates at 0 and −2.1, NO hard deck) over the trench side z 0..20, a
    headwall along z = 20 hanging to −24 m (the span stands behind it,
    z > 20) and two piers to −26 m under the slab's front."""
    comps = [_box(-30.0, 0.0, 60.0, 20.0, 2.1, y0=-2.1),
             _box(-30.0, 20.0, 60.0, 0.5, 21.9, y0=-24.0),
             _box(-12.0, 3.0, 2.0, 2.0, 24.0, y0=-26.0), _box(10.0, 3.0, 2.0, 2.0, 24.0, y0=-26.0)]
    return _write(tmp_path / "edge.obj", comps)


def test_bridge_edge_walls_with_a_deck_plate_are_an_edge_wall_bridge(tmp_path):
    """27l (#1138 KATL ``tunel_*``): a deck slab on walls hanging to −26 m,
    no hard deck, is no bare face (Q168) but an EDGE-WALL BRIDGE: its depth
    is its walls' bottom, its walls' plan segments are read in the frame."""
    o = _placed(_edge_bridge(tmp_path), "dsf:obj9")
    g = O.parse_obj8(o.resolved)
    assert P.hanging_reading(o, g, LAW) is None
    depth, hull, walls = HO.edge_wall_reading(o, g, LAW)
    assert abs(depth - 26.0) < 1e-6 and len(hull) >= 4
    # heading 0: authored z runs to frame −y; the headwall stands at y −20..−20.5
    assert any(min(p[1] for p in w) <= -20.0 and max(abs(p[0]) for p in w) >= 29.0
               for w in walls)
    bore = types.SimpleNamespace(id=-2191, points=[(0.0, -2.0), (0.0, -120.0)])
    got, _r = P.read_portals([o], O.ResourceCache(THICK), LAW, [bore])
    assert len(got) == 1 and got[0].hanging and got[0].edge_walls


def test_an_edge_wall_bridges_trench_stops_at_its_walls_back(tmp_path):
    """27l / 20ao: the mouth moves into the bore to the headwall's back
    across the corridor's width — not to the far corner of a skewed plan,
    and a wall beside the corridor does not reach it."""
    axis = LineString([(0.0, 0.0), (0.0, 100.0)])          # the ramp runs +y
    inward = (0.0, -1.0)                                     # the bore runs −y
    skewed = ((-60.0, -10.0), (60.0, -30.0))                 # a 120 m skewed headwall
    pier = ((3.0, -4.0), (5.0, -4.0))
    beside = ((40.0, -80.0), (45.0, -80.0))                  # outside |x| <= 8
    moved, d = SM.edge_wall_mouth(axis, inward, (skewed, pier, beside), 8.0)
    # across x −8..8 the headwall stands at y −18.67..−21.33: its back is 21.33 in
    assert abs(d - (20.0 + 8.0 / 6.0)) < 1e-6 and abs(moved.coords[0][1] + d) < 1e-9
    kept, d0 = SM.edge_wall_mouth(axis, inward, (((-5.0, 4.0), (5.0, 4.0)),), 8.0)
    assert d0 == 0.0 and kept is axis                        # a wall on the ramp side


def test_a_deck_over_an_edge_wall_trench_keeps_the_deck_level():
    """27l: over an edge-wall bridge's trench a terrain deck never stands
    under the deck level its walls' tops give (KATL: the service road level
    with the taxiway); elsewhere the floor + clearance alone."""
    from auto_patch_v2.constraints.structures import deck_floor
    tn = types.SimpleNamespace(mouth_z=276.5, span_deck_z=302.4)
    assert deck_floor(tn, 5.0) == 302.4
    assert deck_floor(types.SimpleNamespace(mouth_z=285.5, span_deck_z=None), 5.0) == 290.5


def test_the_deck_over_an_edge_wall_trench_is_held_hard_at_the_deck_level():
    """27l / 27r: every deck vertex at or above the recorded deck level, under
    a head ``[design] hard_rulings`` names (a law, never a target)."""
    from auto_patch_v2.constraints.structures import SPAN_DECK_RULING, _span_deck_rows
    from auto_patch_v2.model.constraints import Band
    from auto_patch_v2.solve.design_roles import hard_rulings, is_hard
    rows = _span_deck_rows(types.SimpleNamespace(span_deck_z=303.1), [3, 4], ())
    assert all(isinstance(r, Band) and r.lo == 303.1 and r.hi is None for r in rows)
    assert all(r.source.ruling.startswith(SPAN_DECK_RULING) for r in rows)
    assert all(is_hard(hard_rulings(LAW), r) for r in rows)


def test_the_span_between_two_edge_wall_bridges_is_cover(tmp_path):
    """27l / 27r: over a covered bore the span between two pack bridge edges
    — from one's walls' back to the other's — is clipped in as cover, so
    the ground there takes the ground beside the cover (not the lidar road);
    the open cut beyond the walls is not."""
    from auto_patch_v2.planar.covered_span import edge_spans
    path = _edge_bridge(tmp_path)
    a = _placed(path, "dsf:obj1")
    b = types.SimpleNamespace(**{**vars(_placed(path, "dsf:obj2", xy=(0.0, -100.0))),
                                 "heading_deg": 180.0,
                                 "plan_bbox": _sbox(-31.0, -101.0, 31.0, -79.0)})
    a.plan_bbox = _sbox(-31.0, -21.0, 31.0, 1.0)
    bore = types.SimpleNamespace(line=LineString([(0.0, 10.0), (0.0, -110.0)]))
    rib = _sbox(-40.0, -110.0, 40.0, 10.0)
    secs = [types.SimpleNamespace(dl=30.0, dr=30.0)]
    spans = edge_spans([(bore, secs, rib)], [a, b], O.ResourceCache(THICK), LAW)
    assert len(spans) == 1
    lo, hi = spans[0].bounds[1], spans[0].bounds[3]
    # from the second edge's headwall back (its 0.5 m wall at y −80..−79.5)
    # to the first's (y −20..−20.5): never the slabs or piers beyond them
    assert abs(hi + 20.5) < 1e-6 and abs(lo + 79.5) < 1e-6
    assert edge_spans([(bore, secs, rib)], [a], O.ResourceCache(THICK), LAW) == []
