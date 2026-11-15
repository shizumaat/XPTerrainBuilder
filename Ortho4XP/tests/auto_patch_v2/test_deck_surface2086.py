"""#2086 / #2065 R3: a deck authored on a grade is ONE plate when it is a
bridge of a deck and the structure riding it (``airport/deck_surface``,
``deck_riders.objects_ride``, ``deck_signature._rider_surfaces``).
Headless, synthetic: no pack, no mesh, no network."""
from __future__ import annotations

import types

import numpy as np
from auto_patch_v2.airport import deck_riders as DR
from auto_patch_v2.airport import deck_signature as DS
from auto_patch_v2.airport.deck_surface import grown_plate


def _quad(a, b, c, d):
    return [(a, b, c), (c, d, a)]


#: a 200 m deck in three quads falling 2.8 m end to end (LEMG's viaduct shape)
GRADED = np.array(
    _quad((0, 1.3, 0), (0, 1.3, 30), (20, 1.0, 30), (20, 1.0, 0))
    + _quad((20, 1.0, 0), (20, 1.0, 30), (180, 0.0, 30), (180, 0.0, 0))
    + _quad((180, 0.0, 0), (180, 0.0, 30), (200, -1.5, 30), (200, -1.5, 0)), float)


def test_a_graded_deck_grows_from_one_triangle_over_its_connected_surface():
    plane = np.zeros(len(GRADED), bool)
    plane[2] = True                                   # one half of the long quad
    got = grown_plate(GRADED, np.ones(len(GRADED), bool), plane, np.ones(len(GRADED), bool))
    assert got.all()


def test_a_surface_running_down_to_the_feet_is_a_ramp_and_nothing_grows():
    plane = np.zeros(len(GRADED), bool)
    plane[2] = True
    high = np.ones(len(GRADED), bool)
    high[-1] = False                                  # its last face stands on the feet
    got = grown_plate(GRADED, np.ones(len(GRADED), bool), plane, high)
    assert (got == plane).all()


def test_a_face_sharing_no_edge_does_not_join():
    far = np.array(_quad((0, 5, 0), (0, 5, 10), (10, 5, 10), (10, 5, 0))
                   + _quad((50, 5, 0), (50, 5, 10), (60, 5, 10), (60, 5, 0)), float)
    plane = np.array([True, True, False, False])
    got = grown_plate(far, np.ones(4, bool), plane, np.ones(4, bool))
    assert (got == plane).all()


# ── the rider witness on pack placements ─────────────────────────────────

def _geom(tris):
    v = np.asarray([p for t in tris for p in t], float)
    return types.SimpleNamespace(vertices=v, solid=np.arange(len(v)).reshape(-1, 3))


class _Cache:
    def __init__(self, geoms):
        self.g = geoms

    def geometry(self, path):
        return self.g.get(path)

    def genuine(self, path):
        g = self.g[path]
        return [types.SimpleNamespace(tris=g.solid[k:k + 2]) for k in range(0, len(g.solid), 2)]


def _o(path):
    return types.SimpleNamespace(resolved=path, xy=(0.0, 0.0), heading_deg=0.0)


DECK = [t for t in GRADED.tolist()]
#: a parapet box on the deck's north edge, and one 40 m beside it
ON = _quad((50, 2.0, 1), (50, 2.0, 2), (150, 2.0, 2), (150, 2.0, 1))
OFF = _quad((50, 2.0, 70), (50, 2.0, 71), (150, 2.0, 71), (150, 2.0, 70))


def test_a_structure_standing_on_its_deck_rides_it():
    cache = _Cache({"d": _geom(DECK), "s": _geom(ON)})
    assert DR.objects_ride([_o("d"), _o("s")], ["signature", DR.FAMILY_KIND], cache)


def test_a_structure_beside_the_deck_does_not_ride_and_a_building_member_refuses():
    cache = _Cache({"d": _geom(DECK), "s": _geom(ON), "x": _geom(OFF)})
    assert not DR.objects_ride([_o("d"), _o("x")], ["signature", DR.FAMILY_KIND], cache)
    assert not DR.objects_ride([_o("d"), _o("s"), _o("x")],
                               ["signature", DR.FAMILY_KIND, ""], cache)
    assert not DR.objects_ride([_o("d")], ["signature"], cache)


def _plate(tag, surface=None):
    return DS.DeckPlate(tag, tag, None, None, ((0, 0), (1, 0)), None, 0.0, 0.0, 0.0, 0.0,
                        1.0 if surface else 0.0, 0.0, (), (tag,), (), surface)


def test_only_a_riding_family_takes_the_surface_plate():
    cache = _Cache({"d": _geom(DECK), "s": _geom(ON), "x": _geom(OFF)})
    plane = _plate("plane", _plate("surface"))
    d, s, x = (types.SimpleNamespace(id=k, **vars(_o(k))) for k in "dsx")
    got = DS._rider_surfaces([d, s], {"d": plane}, cache)["d"]
    assert got.evidence == ("surface",) and got.plane_y == 1.0
    assert DS._rider_surfaces([d, x], {"d": plane}, cache)["d"] is plane
