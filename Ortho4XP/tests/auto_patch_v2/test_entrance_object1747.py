"""Twin for #1747 (owner ruling 2026-11-03 "yes", LOWS; Q256 b, RULINGS
2026-10-28s (6)): a pack trench object standing at a mapped TUNNEL's end is
that bore's ENTRANCE — the mouth's floor is the object's bottom at the
portal with its face seated on the ground over it (Q-A 2026-11-05;
``trench_objects.mouth_portals``), the structure pass reads that floor
(``structures``: ``Portal.floor_z``) and the object stage seats the face
there (``airport/entrance_seat``).
Synthetic OBJ8 and ways; law values read from the tables."""
from __future__ import annotations

import pytest
from auto_patch_v2.airport import obj8
from auto_patch_v2.airport.trench_objects import mouth_portals, read_trench_objects
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import OsmWay
from auto_patch_v2.planar.basins import read_objects
from auto_patch_v2.planar.structure_mouth import portal_note
from test_tunnel_objects import _airport, _slab, _write

_T = {"highway": "primary", "lanes": "2", "tunnel": "yes", "layer": "-1"}


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


@pytest.fixture(scope="module")
def objs(tmp_path_factory):
    """A 12 m entrance FACE (a retaining wall over the bore's end): solids
    from 5 m under its zero to 2 m over it, no roof."""
    d = tmp_path_factory.mktemp("pack") / "objects"
    d.mkdir()
    (d.parent / "Earth nav data").mkdir()
    (d.parent / "Earth nav data" / "apt.dat").write_text("I\n1000 Version\n", encoding="utf-8",
                                                         newline="")
    vt: list = []
    tris: list = []
    _slab(vt, tris, -6.0, 6.0, -0.3, 0.3, -5.0, 2.0)
    return {"dir": d, "face": _write(d / "face.obj", vt, tris)}


def test_an_entrance_object_pins_the_mouth_at_its_bottom(objs, law):
    tunnel = OsmWay(-7, "big_roads", ((0.0, 3.0), (0.0, 300.0)), False, _T)
    airport = _airport(objs, law, [("face", (0.0, 0.0), 0.0, 0.0, "OBJECT")], (tunnel,))
    cache = obj8.ResourceCache(law.tables.structures.basin.min_solid_thickness_m)
    objects, _rep = read_objects(airport, law, cache)
    trenches, _notes = read_trench_objects(objects, cache, law, [tunnel])
    assert [t.object_id for t in trenches] == ["dsf:obj0"]
    pins = mouth_portals(trenches, objects, cache, law, [tunnel], airport.dem.z)
    # one pin, at the end the face stands at (the far end has no solid near)
    assert [(p.end_xy, p.way_id) for p in pins] == [((0.0, 3.0), -7)]
    p = pins[0]
    base = objects[0].anchor_z + objects[0].agl_m
    # Q-A (2026-11-05): the floor AT THE PORTAL is the face's bottom with the
    # face seated on the ground over it — the ground (flat, ``base``) less
    # the face's height (its top plate +2 over its bottom -5; the ground the
    # highest DEM over that plate), never its
    # bottom at the pack's own zero; ``bottom_y`` seats the face there
    assert p.floor_z == pytest.approx(airport.dem.z(6.0, 0.0) - 7.0, abs=0.01)
    assert p.bottom_y == pytest.approx(-5.0, abs=0.01)
    assert p.anchor_xy == p.end_xy               # the mouth does not move
    assert "entrance object" in portal_note(p, base, p.floor_z)
    # a road end the face does not stand at is no entrance: a covered or
    # untagged way's end is never pinned here
    assert mouth_portals(trenches, objects, cache, law, [], airport.dem.z) == []


def test_an_edge_wall_bridge_is_never_an_entrance(tmp_path):
    """KATL's ``tunel_A`` (#1138): an edge-wall bridge read as a trench
    object at a bore end pins by its back's crossing (``bridge_span``),
    never as an entrance — the first cut of this rule built two new I-285
    bores off it."""
    from auto_patch_v2.airport.trench_objects import TrenchObject
    from shapely.geometry import box
    from test_hanging_objects1298 import LAW, THICK, _edge_bridge, _placed
    o = _placed(_edge_bridge(tmp_path), "dsf:obj7")
    o.plan_bbox = box(-31.0, -21.0, 31.0, 1.0)
    way = OsmWay(-1, "big_roads", ((0.0, 0.0), (0.0, -200.0)), False, _T)
    t = TrenchObject(o.id, o.path, o.plan_bbox, 20.0, (((0.0, 0.0), -1),))
    assert mouth_portals([t], [o], obj8.ResourceCache(THICK), LAW, [way],
                         lambda x, y: 0.0) == []


def test_solids_standing_over_the_ground_are_no_entrance(objs, law):
    """LOWS bore -328's end under the house group's plates, 8.5 m over the
    ground: a building on the bore, never the mouth's road."""
    tunnel = OsmWay(-7, "big_roads", ((0.0, 3.0), (0.0, 300.0)), False, _T)
    airport = _airport(objs, law, [("face", (0.0, 0.0), 0.0, 10.0, "OBJECT_AGL")], (tunnel,))
    cache = obj8.ResourceCache(law.tables.structures.basin.min_solid_thickness_m)
    objects, _rep = read_objects(airport, law, cache)
    trenches, _notes = read_trench_objects(objects, cache, law, [tunnel])
    assert trenches, "the raised face is still read as a trench object"
    assert mouth_portals(trenches, objects, cache, law, [tunnel], airport.dem.z) == []


def test_the_entrances_own_pad_never_stops_its_ramp(law):
    """LOWS 1.0.464 (owner 2026-11-04, RULINGS 2026-11-03e (15) "the ramp
    grades to the entrance object's bottom"): once the pack's footprint
    cache vouched the entrance object, its walls minted building pads over
    both bore ends and both mouths were refused "the mouth stands against
    building pad".  A pad the pinned opening stands in is the entrance's
    own footprint; a pad beyond the opening still ends the ramp's top."""
    from auto_patch_v2.airport.portal_objects import Portal
    from auto_patch_v2.classify.roles import Cell, Classification
    from auto_patch_v2.planar.structures import build_structures
    from test_mouth_at_pavement971 import _airport as _bore_airport
    from test_mouth_at_pavement971 import _base_cells, _rect
    portals = [Portal(f"dsf:obj{i}", "objects/entrance.obj", (x, 0.0), -101, 6.0, 0.0,
                      (x, 0.0), floor_z=694.0) for i, x in ((1, -60.0), (2, 60.0))]

    def run(pads):
        cells = _base_cells() + [Cell(10 + k, "building", ref, _rect(*box), (), None, None,
                                      "groundside", "building", {})
                                 for k, (ref, box) in enumerate(pads)]
        return build_structures(_bore_airport(law), Classification(tuple(cells), (), {}, ()),
                                law, portals=portals)
    own = [("bW", (-75.0, -30.0, -45.0, 30.0)), ("bE", (45.0, -30.0, 75.0, 30.0))]
    _cl, tunnels, st = run(own)
    assert len(tunnels) == 2, st.refused
    assert not any("stands against building pad" in r for r in st.refused), st.refused
    # a house BEYOND the opening still stops the ramp short of it
    _cl, tunnels, st = run(own + [("house", (120.0, -30.0, 160.0, 30.0))])
    east = [t for t in tunnels if t.axis[0][0] > 0]
    assert east and max(x for x, _y in east[0].axis) < 120.0, (st.refused, east)


def test_the_entrance_face_is_seated_on_its_portals_floor_face_by_face():
    """#1747 (Q-A 2026-11-05; RULINGS 2026-11-03e (15) "the houses stay"):
    the structure pass publishes each entrance face's zero with its bore end
    (``Tunnel.portal_seat``), the seat record carries the end, and only the
    bodies standing within reach of that end take that zero — a house of
    the same object, and the other portal's face, keep theirs.  The row
    itself is never written as one seat (``row_seats``)."""
    import types

    from auto_patch_v2.airport.entrance_seat import entrance_zeros, seat_faces
    from auto_patch_v2.airport.terrain_shaped import ENTRANCE_SEAT, portal_seat_records, row_seats
    tn = types.SimpleNamespace(portal="dsf:obj7", portal_seat=("objects/e.obj", 430.95,
                                                               (100.0, 200.0), 10.0))
    recs = portal_seat_records([tn], lambda x, y: (47.0 + y * 1e-5, 13.0 + x * 1e-5))
    assert recs == [{"id": "dsf:obj7", "resource": "objects/e.obj", "datum": "portal",
                     "seat": ENTRANCE_SEAT, "elevation": 430.95,
                     "end": [47.002, 13.001], "reach_m": 10.0}]
    assert row_seats(types.SimpleNamespace(placements=[]), recs) == ()
    face = types.SimpleNamespace(geom_box=(47.00195, 13.0009, 47.0021, 13.00105))
    house = types.SimpleNamespace(geom_box=(47.01, 13.01, 47.011, 13.011))
    rec = types.SimpleNamespace(bodies=(face, house))
    took = []

    def at_zero(r, m, zero, take, why):
        took.extend((b, zero) for b in r.bodies if take(b))
        return r
    seat_faces(rec, types.SimpleNamespace(id="dsf:obj7"), entrance_zeros(recs), at_zero)
    assert took == [(face, 430.95)]
    took.clear()
    seat_faces(rec, types.SimpleNamespace(id="dsf:obj8"), entrance_zeros(recs), at_zero)
    assert took == []
