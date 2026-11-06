"""Twin for #1747 (owner RULINGS 2026-11-06b (6)): no building pad is minted
from a tunnel-mouth (entrance) object's footprint or walls — the ground meets
the mouth face (``airport/entrance_shade``).  A real building beside the mouth
still gets its pad.  Synthetic OBJ8 and ways; law values read from the tables."""
from __future__ import annotations

import pytest
from auto_patch_v2.airport import obj8
from auto_patch_v2.airport.entrance_shade import entrance_shade
from auto_patch_v2.geom import pad_shade_extra
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import OsmWay
from auto_patch_v2.planar.basins import read_objects
from shapely.geometry import Point, Polygon, box
from test_tunnel_objects import _airport, _slab, _write

_T = {"highway": "primary", "lanes": "2", "tunnel": "yes", "layer": "-1"}


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


@pytest.fixture(scope="module")
def objs(tmp_path_factory):
    """An entrance FACE (a wall 5 m under its zero over the bore's end) with
    a low HOUSE in the same file 30 m off (its own component, standing on its
    zero), and a separate house object."""
    d = tmp_path_factory.mktemp("pack") / "objects"
    d.mkdir()
    (d.parent / "Earth nav data").mkdir()
    (d.parent / "Earth nav data" / "apt.dat").write_text("I\n1000 Version\n", encoding="utf-8",
                                                         newline="")
    vt: list = []
    tris: list = []
    _slab(vt, tris, -6.0, 6.0, -0.3, 0.3, -5.0, 0.5)
    _slab(vt, tris, 24.0, 36.0, -4.0, 4.0, 0.0, 3.0)
    face = _write(d / "face.obj", vt, tris)
    vt, tris = [], []
    _slab(vt, tris, -6.0, 6.0, -4.0, 4.0, 0.0, 6.0)
    return {"dir": d, "face": face, "house": _write(d / "house.obj", vt, tris)}


def _shade(objs, law):
    tunnel = OsmWay(-7, "big_roads", ((0.0, 3.0), (0.0, 300.0)), False, _T)
    airport = _airport(objs, law, [("face", (0.0, 0.0), 0.0, 0.0, "OBJECT"),
                                   ("house", (-20.0, 0.0), 0.0, 0.0, "OBJECT")], (tunnel,))
    cache = obj8.ResourceCache(law.tables.structures.basin.min_solid_thickness_m)
    objects, _rep = read_objects(airport, law, cache)
    return airport, entrance_shade(airport, objects, cache, law)


def test_the_mouths_walls_are_shaded_and_a_house_is_not(objs, law):
    airport, sh = _shade(objs, law)
    assert sh is not None
    assert sh.contains(Point(0.0, 0.0))            # the face's wall
    assert not sh.intersects(box(23.0, -5.0, 37.0, 5.0))   # the same file's house
    assert not sh.intersects(box(-27.0, -5.0, -13.0, 5.0))  # the house beside it
    # with no tunnel the face is no mouth and nothing is shaded
    airport = _airport(objs, law, [("face", (0.0, 0.0), 0.0, 0.0, "OBJECT")], ())
    cache = obj8.ResourceCache(law.tables.structures.basin.min_solid_thickness_m)
    objects, _rep = read_objects(airport, law, cache)
    assert entrance_shade(airport, objects, cache, law) is None


class _B:
    def __init__(self, outer):
        self.source, self.outer, self.holes = "dsf:object:object", outer, ()


def _pads(buildings, shade, law):
    from auto_patch_v2.classify.evidence import PAD_REFUSED, _pads
    from test_v2padcluster import _AP

    class _R:
        class buildings:
            sources = ("dsf:object",)

    ap = _AP((), buildings=tuple(buildings))
    ap.entrance_shade = shade
    gate = Polygon([(-500.0, -500.0), (-500.0, 500.0), (500.0, 500.0), (500.0, -500.0)])
    pads, _d, _s = _pads(ap, _R, 10.0, gate, Polygon(), Polygon(), law=law)
    return [g for _r, g in pads], dict(PAD_REFUSED)


def test_the_mouths_walls_mint_no_pad_and_the_house_beside_it_does(objs, law):
    """The footprint cache's ring welded from the mouth's walls mints no pad;
    the house's ring beside it does, and a pad that merely touches the
    mouth keeps all its ground but the walls'."""
    _ap, sh = _shade(objs, law)
    weld = tuple(box(-8.0, -2.0, 8.0, 2.0).exterior.coords)[:-1]
    house = tuple(box(-26.0, -4.0, -14.0, 4.0).exterior.coords)[:-1]
    pads, _ref = _pads([_B(weld), _B(house)], None, law)
    assert len(pads) == 2                           # the control: both minted
    pads, ref = _pads([_B(weld), _B(house)], sh, law)
    assert len(pads) == 1 and pads[0].contains(Point(-20.0, 0.0))
    assert ref["fallback_tunnel_mouth"] == 1
    # a ring that only touches the wall's plan (within the touch tolerance)
    # is no weld of it: it keeps its pad, less the wall
    beside = tuple(box(-20.0, 0.2, 20.0, 20.0).exterior.coords)[:-1]
    pads, ref = _pads([_B(beside)], sh, law)
    assert len(pads) == 1 and ref["fallback_tunnel_mouth"] == 0
    assert pads[0].intersection(sh).area < 1e-6


def test_the_shade_is_on_the_one_pad_shade_path(objs, law):
    class _A:
        sunken_ramps = wall_shade = None
    a = _A()
    _ap, a.entrance_shade = _shade(objs, law)
    assert pad_shade_extra(a) is a.entrance_shade
