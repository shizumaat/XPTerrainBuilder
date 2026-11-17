"""#1939 (owner RULINGS 2026-11-06c (5), "the mouth object sets the ramp"):
a road piece that enters a structure's mouth is not terraced to the
pavement over the structure.  ``airport/road_ramp._mouth_floors`` names the
road vertices of every piece sharing a vertex with a structure FLOOR (a
value-carrying structure role: a tunnel ramp), never a wall's;
``_nearer_floor`` is the test ``road_terrace`` applies against the vertex's
stage-1 foot distance (ESSA ``small_roads:-291#3``: floor 4.5 m, taxiway
foot 13.2 m, the approach had been held 4.8 m over lidar)."""
from __future__ import annotations

import dataclasses as _dc

from auto_patch_v2.airport.road_ramp import _mouth_floors, _nearer_floor
from auto_patch_v2.law.tables import load_default


@_dc.dataclass
class _V:
    xy: tuple


@_dc.dataclass
class _F:
    role: str
    ref: str
    ring: tuple
    holes: tuple = ()


class _Pm:
    def __init__(self, vertices, faces):
        self.vertices = {k: _V(p) for k, p in vertices.items()}
        self.faces = dict(enumerate(faces))

    @staticmethod
    def ring_vertices(ring):
        return tuple(ring)


def _map(floor_role: str):
    # the floor 0..10 x 0..10; the mouth piece shares its edge (vertices 2, 3)
    # and reaches 30 m out; a second road piece 50 m away touches nothing
    v = {0: (0, 0), 1: (10, 0), 2: (10, 10), 3: (0, 10),
         4: (0, 40), 5: (10, 40),
         6: (60, 0), 7: (70, 0), 8: (70, 10), 9: (60, 10)}
    return _Pm(v, [_F(floor_role, "tunnel_ramp", (0, 1, 2, 3)),
                   _F("service_road", "small_roads:-1", (3, 2, 5, 4)),
                   _F("service_road", "small_roads:-2", (6, 7, 8, 9))])


def test_the_piece_entering_a_floor_is_at_the_mouth_and_its_neighbour_is_not():
    law = load_default()
    pm = _map("tunnel_ramp")
    mv, floors = _mouth_floors(pm, law, {"service_road"}, frozenset())
    assert mv == {2, 3, 4, 5}
    # vertex 4 stands 30 m from the floor: nearer than a foot 31 m away,
    # not nearer than one 20 m away
    assert _nearer_floor(pm, 4, 31.0, floors)
    assert not _nearer_floor(pm, 4, 20.0, floors)


def test_a_wall_is_no_floor_and_a_deck_piece_is_no_road():
    law = load_default()
    mv, floors = _mouth_floors(_map("retaining_wall"), law, {"service_road"}, frozenset())
    assert mv == set() and floors[1] is None
    mv, _f = _mouth_floors(_map("tunnel_ramp"), law, {"service_road"},
                           frozenset({"small_roads:-1"}))
    assert mv == set()
