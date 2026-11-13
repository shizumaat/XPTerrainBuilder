"""#1921 / #1936 (owner RULINGS 2026-11-06d (4)(5)): a floored trench object's
cut stands BENEATH its floor by ``[tunnel.object] floor_clearance_m`` (the
floor drawn, never z-fighting or covered), and the rim of the cut -- where
the ground and the pavement meet the object -- stands at the frame's top
edge, never above its zero (``airport/floor_rim``)."""
from __future__ import annotations

import types

import numpy as np
from auto_patch_v2.airport import obj8 as O
from auto_patch_v2.airport import object_floor as OF
from test_hanging_objects1298 import LAW, THICK, _box, _placed, _write
from test_object_floor1903 import _ramped_floor


def _cover(tmp_path, top=0.0, parapet=0.0):
    """A 20 x 80 m roof slab topping out at ``top`` on two side walls
    hanging to -5 m (their crest ``parapet`` over the slab)."""
    comps = [_box(-10.0, 0.0, 20.0, 80.0, 0.3, y0=top - 0.3),
             _box(-10.0, 0.0, 0.5, 80.0, 5.0 + top + parapet, y0=-5.0),
             _box(9.5, 0.0, 0.5, 80.0, 5.0 + top + parapet, y0=-5.0)]
    return _write(tmp_path / f"cover{top}{parapet}.obj", comps, hard={0})


def _floor(tmp_path, top=0.0, parapet=0.0):
    cache = O.ResourceCache(THICK)
    objs = [_placed(_cover(tmp_path, top, parapet), "dsf:obj1"),
            _placed(_ramped_floor(tmp_path), "dsf:obj2")]
    floors, notes = OF.read_object_floors(objs, cache, LAW, {})
    assert len(floors) == 1, notes
    return floors[0]


def test_the_rim_reads_the_frames_top_never_over_its_zero(tmp_path):
    f = _floor(tmp_path)
    dz = np.array([t[2] for t in f.rim_tops])
    assert len(dz) > 40 and np.all(np.abs(dz) <= 0.01)
    # walls standing 0.8 m over the roof are furniture on the ground
    dz = np.array([t[2] for t in _floor(tmp_path, parapet=0.8).rim_tops])
    assert np.all(np.abs(dz) <= 0.01)
    # a frame sunk 0.4 m under its zero: the ground meets its top
    dz = np.array([t[2] for t in _floor(tmp_path, top=-0.4).rim_tops])
    sides = dz[dz < -0.2]
    # (a corner sample also reaches the ramp's lip rising to the zero)
    assert len(sides) > 20 and abs(np.median(sides) + 0.4) <= 0.01
    assert np.all(np.abs(sides + 0.4) <= 0.1)


def _planar(floor):
    """The map ``planar/object_floor_cells`` cuts from ``floor``, every
    ring vertex its own (with the faces it touches)."""
    from auto_patch_v2.planar.object_floor_cells import add_object_floor_cells
    cells: list = []
    add_object_floor_cells([floor], LAW, cells, [], [], [], [], [], [])
    faces, verts = {}, {}
    for k, (role, ref, poly, _owner) in enumerate(cells):
        ids = []
        for x, y in poly.exterior.coords[:-1]:
            verts[len(verts)] = types.SimpleNamespace(xy=(x, y), incident_faces=(k,))
            ids.append(len(verts) - 1)
        faces[k] = types.SimpleNamespace(role=role, ref=ref, ring=tuple(ids), holes=())
    # the apron the rim meets (a band vertex no surface shares is left alone)
    apron = len(faces)
    faces[apron] = types.SimpleNamespace(role="apron", ref="apron", ring=(), holes=())
    for k, f in list(faces.items()):
        if f.role == "retaining_wall":
            for v in f.ring:
                verts[v].incident_faces = (k, apron)
    return types.SimpleNamespace(object_floors=(floor,), faces=faces, vertices=verts,
                                 ring_vertices=lambda ring: list(ring))


def _role(planar, p):
    return planar.faces[planar.vertices[p.v].incident_faces[0]].role


def test_the_cut_stands_beneath_the_floor_and_the_rim_at_the_top(tmp_path):
    from auto_patch_v2.constraints.object_floor import object_floor_pins
    f = _floor(tmp_path)
    planar = _planar(f)
    pins = object_floor_pins(planar, LAW, None)
    clear = LAW.tables.structures.tunnel.object.floor_clearance_m
    assert clear > 0.2
    cut = [p for p in pins if _role(planar, p) == "tunnel_trench"]
    rim = [p for p in pins if _role(planar, p) == "retaining_wall"]
    assert cut and rim
    for p in cut:
        x, y = planar.vertices[p.v].xy
        z = OF.floor_z_at(f.faces, [x], [y], edge_m=1.0)[0]
        assert abs(p.z - (z - clear)) < 1e-9          # beneath the floor, by the law
    assert all(abs(p.z - 100.0) <= 0.01 for p in rim)  # the frame's top: its zero


def test_a_rim_vertex_a_road_carries_keeps_the_roads_law(tmp_path):
    from auto_patch_v2.constraints.object_floor import object_floor_pins
    f = _floor(tmp_path)
    planar = _planar(f)
    rim = [p.v for p in object_floor_pins(planar, LAW, None)
           if _role(planar, p) == "retaining_wall"]
    road = len(planar.faces)
    planar.faces[road] = types.SimpleNamespace(role="service_road", ref="road", ring=(), holes=())
    planar.vertices[rim[0]].incident_faces = (planar.vertices[rim[0]].incident_faces[0], road)
    alone = planar.vertices[rim[1]]
    alone.incident_faces = alone.incident_faces[:1]           # the patch ends there
    again = {p.v for p in object_floor_pins(planar, LAW, None)}
    assert rim[0] not in again and rim[1] not in again and set(rim[2:]) <= again
