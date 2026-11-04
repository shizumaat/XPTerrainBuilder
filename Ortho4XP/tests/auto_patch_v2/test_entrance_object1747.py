"""Twin for #1747 (owner ruling 2026-11-03 "yes", LOWS; Q256 b, RULINGS
2026-10-28s (6)): a pack trench object standing at a mapped TUNNEL's end is
that bore's ENTRANCE — the mouth's floor is the object's bottom where it
stands (``trench_objects.mouth_portals``), the object stays put, and the
structure pass reads that floor (``structures``: ``Portal.floor_z``).
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
    assert p.floor_z == pytest.approx(base - 5.0, abs=0.01)
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
