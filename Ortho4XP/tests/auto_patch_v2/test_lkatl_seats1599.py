"""#1599 / #1597 (KATL, owner sim read of 1.0.441): four general rules.

* an OPEN frame's one zero is taken per CONNECTED SET of its bodies, and a
  set holding a body its building carries rests on that building
  (``open_frame_seat.rigid_open`` / ``open_sets``; 22c with 22o);
* a FOOTLESS member resting on a terrain-adapted one stays with it
  (``adapted_riders``);
* a unit standing wholly a storey under its pad's plane takes its own
  ground (``footprint_unit._below_its_pad``; 28p (2): never float);
* the terrain-edge breakline runs over the vertices ON its line only
  (``emit/terrain_edge``)."""
from __future__ import annotations

import types

import pytest

from auto_patch_v2.airport import anchor_rule as AR
from auto_patch_v2.airport import open_frame_seat as OFS
from auto_patch_v2.airport.adapted_riders import riders_of_adapted
from auto_patch_v2.airport.placement_record import Body, Split
from auto_patch_v2.law import Law

_M = types.SimpleNamespace(resource="objects/roofs.obj", zero_y=0.0)


def _body(i, zero, box, carried=""):
    a = AR.Anchor(AR.OTHER, box[0], box[1], 100.0 - zero, "own", 100.0,
                  offset=(1.0, 100.0 - zero, 2.0))
    return Body(i, AR.OTHER, (i,), a, f"objects/roofs__b{i}.obj",
                merged_into=carried, geom_box=box, plan_box=box)


def _split(*bodies):
    return Split(0, "dsf:obj0", _M.resource, "/x/" + _M.resource,
                 40.0, -3.0, 0.0, tuple(bodies))


def _zeros(rec):
    return [round(b.anchor.surface_z - b.anchor.y_zero, 2) for b in rec.bodies]


def test_an_open_frame_of_separate_roofs_seats_each_roof_on_its_own():
    """KATL ``techo1.obj``: 51 roofs over 600 m in one placement were ONE
    rigid structure at the lowest zero (287.76), up to 12.8 m into their
    halls.  Roofs 500 m apart are separate sets; two touching ones are one."""
    near = (40.0, -3.0, 40.0001, -2.9999)
    touch = (40.0001, -2.9999, 40.0002, -2.9998)
    far = (40.0045, -3.0, 40.0046, -2.9999)
    out = OFS.rigid_open(_split(_body(0, 300.0, near), _body(1, 302.0, touch),
                                _body(2, 310.0, far)), _M, True)
    assert _zeros(out) == [300.0, 300.0, 310.0]
    assert len(OFS.open_sets(out.bodies)) == 2


def test_a_set_its_building_carries_rests_on_that_building():
    """A roof set holding a body carried by its hall's unit takes that
    body's zero (KATL b50: 291.03, the hall's pad), not the set's lowest."""
    a = (40.0, -3.0, 40.0001, -2.9999)
    b = (40.0001, -2.9999, 40.0002, -2.9998)
    out = OFS.rigid_open(_split(_body(0, 289.96, a), _body(1, 291.03, b, "fu:5:69/host")),
                         _M, True)
    assert _zeros(out) == [291.03, 291.03]


def test_bodies_with_no_box_stay_one_set():
    a = AR.Anchor(AR.OTHER, 40.0, -3.0, 0.0, "own", 100.0, offset=(1.0, 0.0, 2.0))
    bs = [Body(i, AR.OTHER, (i,), a, f"b{i}.obj") for i in range(3)]
    assert len(OFS.open_sets(bs)) == 1


def _member(mid, feet):
    part = types.SimpleNamespace(pid=hash(mid) % 1000, feet=((0, 0, 0),) if feet else ())
    return types.SimpleNamespace(id=mid, resource=mid + ".obj", parts=(part,))


def test_a_footless_member_on_a_terrain_adapted_one_stays_with_it():
    """KATL ``techo1.obj`` (0 feet) touches ``pared1.obj`` (a wall corridor
    the terrain adapts to) at 89 contacts: it keeps its row with the walls."""
    walls, roofs, hall = _member("w", True), _member("r", False), _member("h", True)
    u = types.SimpleNamespace(members=(walls, roofs, hall))
    pw, pr, ph = (m.parts[0].pid for m in (walls, roofs, hall))
    got = riders_of_adapted((u,), {}, ((pw, pr), (pr, ph)), frozenset({"w"}))
    assert got == frozenset({"r"})
    assert riders_of_adapted((u,), {}, ((pw, ph),), frozenset({"w"})) == frozenset()
    assert riders_of_adapted((u,), {}, ((pw, pr),), frozenset()) == frozenset()


def test_a_unit_wholly_a_storey_under_its_pads_plane_takes_its_ground():
    """KATL: a small building on a pad's lower level (291.10) was seated on
    the pad's plane (300.80) and floated 9.70 m."""
    from auto_patch_v2.airport.footprint_unit import _below_its_pad
    pad = AR.PadRing("building47", ((0, 0), (0, 1), (1, 1)), (300.8, 300.8, 300.8))
    low = [(0, 0, 0.0, 291.1), (0, 0, 0.0, 291.2)]
    assert _below_its_pad(low, pad, 3.0)
    assert not _below_its_pad(low + [(0, 0, 0.0, 300.7)], pad, 3.0)   # spans both
    assert not _below_its_pad(low, pad, 0.0)                          # disarmed
    # the surface must read the pad's own plane over its rings
    assert _below_its_pad(low, pad, 3.0, lambda la, lo: 300.8, {})
    assert not _below_its_pad(low, pad, 3.0, lambda la, lo: 291.1, {})


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


def test_the_terrain_edge_runs_only_over_vertices_on_its_line(law):
    """KATL ``terrain_edge:23``: a staircase edge's bounding box took a road
    node and a taxiway node into its chain, a 64 m chord across the
    shoulder whose ramp the mesher stamped on the ring (a 5.4 m dip)."""
    from auto_patch_v2.emit.surface import GradedSurface, SurfaceVertex
    from auto_patch_v2.emit.terrain_edge import EDGE_KIND, with_terrain_edges
    from auto_patch_v2.model.planar import PlanarMap, Vertex

    xs = [(0.0, 0.0), (20.0, 0.0), (20.0, 20.0), (5.0, 15.0)]
    verts = {i: Vertex(i, p, (60.0 + i * 1e-7, -135.0), 700.0, ())
             for i, p in enumerate(xs)}
    pm = PlanarMap("ZZZZ", verts, {}, {}, {},
                   terrain_edges=(((0.0, 0.0), (20.0, 0.0), (20.0, 20.0)),))
    surf = GradedSurface("ZZZZ", law.ruleset_key, (60.0, -135.0), "EPSG:3857",
                         11, tuple(SurfaceVertex(i, verts[i].key, 700.0)
                                   for i in verts), (), (), {})
    bl = [b for b in with_terrain_edges(surf, pm, law).breaklines if b.kind == EDGE_KIND]
    assert [b.vertices for b in bl] == [(0, 1, 2)]       # never the off-line #3
