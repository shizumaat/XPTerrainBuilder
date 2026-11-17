"""Twin for #2120 R2 Part P (spec ``sim-review/2120-R2.md`` §3): a PORTAL IN
A CUT -- a pack frame whose walls stand from a mapped road's floor up to
the cover over its bore, nothing under its zero -- is read by one witness
(``airport/cut_portal``) and its readers: the entrance shade (no pad), the
covered ground's walled mouths (the cut's depth, capped by the solid) and
its seat (its top on the cover beside the cut, ``airport/cut_portal_seat``).

Synthetic: a plane at 300 m with a 20 m-deep cut 80 m wide along the y
axis (a bare-earth DEM of a covered motorway), a bore mapped
``tunnel=yes`` along it, and a frame of walls y 0..20 with a roof at y 20
standing across the cut.  Law values read from the tables."""
from __future__ import annotations

import dataclasses as _dc
import types

import numpy as np
import pytest
from auto_patch_v2.airport import obj8
from auto_patch_v2.airport.anchor_rule import datum_of
from auto_patch_v2.airport.cut_portal import CutPortal, attach_cut_portals
from auto_patch_v2.airport.cut_portal_seat import PORTAL_PLATE, portal_seats
from auto_patch_v2.airport.entrance_shade import entrance_shade
from auto_patch_v2.classify.roles import Cell, Classification
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import OsmWay, Runway, RunwayEnd
from auto_patch_v2.planar.basins import read_objects
from auto_patch_v2.planar.covered_ground import covered_ground
from shapely.geometry import Point, box
from test_tunnel_objects import _airport, _slab, _write

_BORE = {"highway": "motorway", "tunnel": "yes", "lanes": "5", "layer": "-1", "covered": "yes"}


class _CutDem:
    """A plane at 300 m with a cut ``depth`` deep and 80 m wide along y."""

    provenance = {"synthetic": "a cut along the y axis"}

    def __init__(self, depth: float = 20.0):
        self.depth = depth

    def z_many(self, xs, ys):
        xs = np.asarray(xs, dtype=float)
        return np.where(np.abs(xs) < 40.0, 300.0 - self.depth, 300.0)

    def z(self, x, y):
        return float(self.z_many([x], [y])[0])

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


@pytest.fixture(scope="module")
def objs(tmp_path_factory):
    """A PORTAL frame (walls and roof y 0..20, a 0.5 m parapet) 120 m wide
    across the cut, and a SHORT frame of the same plan standing 5 m tall."""
    d = tmp_path_factory.mktemp("pack") / "objects"
    d.mkdir()
    (d.parent / "Earth nav data").mkdir()
    (d.parent / "Earth nav data" / "apt.dat").write_text("I\n1000 Version\n", encoding="utf-8",
                                                         newline="")
    vt: list = []
    tris: list = []
    _slab(vt, tris, -60.0, 60.0, -10.0, 10.0, 0.0, 20.0)     # walls and roof, one solid
    _slab(vt, tris, -60.0, 60.0, -10.0, -9.5, 19.5, 20.5)    # the parapet
    portal = _write(d / "portal.obj", vt, tris)
    vt, tris = [], []
    _slab(vt, tris, -60.0, 60.0, -10.0, 10.0, 0.0, 5.0)
    short = _write(d / "short.obj", vt, tris)
    vt, tris = [], []                                        # side walls, no roof
    _slab(vt, tris, -60.0, -58.0, -10.0, 10.0, 0.0, 20.0)
    _slab(vt, tris, 58.0, 60.0, -10.0, 10.0, 0.0, 20.0)
    walls = _write(d / "walls.obj", vt, tris)
    vt, tris = [], []                                        # a shell under its zero
    _slab(vt, tris, -60.0, 60.0, -10.0, 10.0, -8.0, 12.0)
    return {"dir": d, "portal": portal, "short": short, "walls": walls,
            "shell": _write(d / "shell.obj", vt, tris)}


def cut_portals(ap, objects, cache, law):
    return attach_cut_portals(ap, objects, cache, law).cut_portals


def _read(objs, law, name="portal", depth=20.0, runways=None):
    bore = OsmWay(-2192, "big_roads", ((0.0, -150.0), (0.0, 150.0)), False, _BORE)
    ap = _airport(objs, law, [(name, (0.0, 0.0), 0.0, 280.0, "OBJECT")], (bore,))
    ap = _dc.replace(ap, dem=_CutDem(depth))
    if runways is not None:
        ap = _dc.replace(ap, runways=runways)
    cache = obj8.ResourceCache(law.tables.structures.basin.min_solid_thickness_m)
    objects, _rep = read_objects(ap, law, cache)
    return ap, objects, cache


def test_a_frame_standing_in_a_cut_over_a_bore_is_a_portal(objs, law):
    ap, objects, cache = _read(objs, law)
    got = cut_portals(ap, objects, cache, law)
    assert len(got) == 1
    p = got[0]
    assert p.bores == (-2192,)
    assert abs(p.floor_z - 280.0) < 1e-6 and abs(p.cover_z - 300.0) < 1e-6
    assert p.top_y == pytest.approx(20.0) and p.solid_top_y == pytest.approx(20.5)
    assert p.depth_m == pytest.approx(20.0)
    assert p.plan.contains(Point(0.0, 0.0))


def test_walls_without_a_roof_or_under_the_zero_are_no_portal(objs, law):
    """Trench walls with no roof over the bore (a train trench's sides) and a
    frame with geometry under its zero (the trench / shell readers') are
    not read here."""
    for name in ("walls", "shell"):
        ap, objects, cache = _read(objs, law, name=name)
        assert cut_portals(ap, objects, cache, law) == (), name


def test_no_cut_no_short_frame_no_paved_frame_is_a_portal(objs, law):
    # a DEM that sees no cut (a coarse DEM, a true bored tunnel): nothing
    ap, objects, cache = _read(objs, law, depth=0.0)
    assert cut_portals(ap, objects, cache, law) == ()
    # a frame shorter than the mouth depth
    ap, objects, cache = _read(objs, law, name="short")
    assert cut_portals(ap, objects, cache, law) == ()
    # a frame more than half over the airport's paved surfaces (a runway
    # 60 m wide laid over it): a structure an aircraft uses is no portal
    ends = (RunwayEnd("09", (-600.0, 0.0), (60.5, -135.5), 0.0, 0.0, 300.0, "fixture"),
            RunwayEnd("27", (600.0, 0.0), (60.5, -135.5), 0.0, 0.0, 300.0, "fixture"))
    ap, objects, cache = _read(objs, law, runways=(Runway("09/27", 60.0, 1, ends, 3, "D"),))
    assert cut_portals(ap, objects, cache, law) == ()


def test_a_portal_in_a_cut_is_shaded_from_every_pad(objs, law):
    ap, objects, cache = _read(objs, law)
    assert entrance_shade(ap, objects, cache, law) is None      # not derived: nothing
    ap = attach_cut_portals(ap, objects, cache, law)
    sh = entrance_shade(ap, objects, cache, law)
    assert sh is not None and sh.contains(Point(0.0, 0.0)) and sh.contains(Point(55.0, 5.0))


def _portal(top=20.0, bottom=0.0):
    return CutPortal("dsf:obj1", "objects/portal.obj", box(-60.0, 25.0, 60.0, 45.0), top,
                     bottom, top + 0.5, (-1,), 280.0, 300.0)


def _mouths(portals, rep_out=None):
    ring = ((-500.0, -25.0), (500.0, -25.0), (500.0, 25.0), (-500.0, 25.0))
    cls = Classification((Cell(1, "runway", "10/28", ring, (), 4, "E", "airside", "runway",
                               {}),), (), {}, ())
    bore = OsmWay(-1, "big_roads", ((0.0, -100.0), (0.0, 100.0)), False, _BORE)
    ap = types.SimpleNamespace(dem=_CutDem(), osm_ways=(bore,))
    xs = np.array([0.0])
    _z, rep = covered_ground(ap, cls, Law.for_airport("ZZZZ"), xs, xs, np.array([280.0]),
                             portals=portals)
    if rep_out is not None:
        rep_out.append(rep)
    return rep.mouth_walls


def test_a_portal_walls_its_mouth_with_the_cuts_depth_capped_by_its_solid():
    assert _mouths(()) == []                       # the control: no wall object, no wall
    walls = _mouths((_portal(),))
    assert len(walls) == 1                          # the mouth it stands at (y = +25)
    ring, depth, path = walls[0]
    assert depth == pytest.approx(20.0) and path == "objects/portal.obj"
    assert max(y for _x, y in ring) > 25.0          # the open cut beyond the mouth
    _r, depth, _p = _mouths((_portal(top=12.0),))[0]
    assert depth == pytest.approx(12.0)             # capped by the portal's own solid


def test_a_walled_mouth_is_published_as_the_portals_claimed_mouth():
    """#2120 R2 item 1: the mouth a portal walls is CLAIMED -- the bore's
    ways and the point its axis meets the walled edge (y = +25)."""
    reps: list = []
    _mouths((_portal(),), reps)
    (ways, (x, y), portal), = reps[0].portal_mouths
    assert ways == (-1,) and portal == "dsf:obj1"
    assert x == pytest.approx(0.0, abs=0.01) and y == pytest.approx(25.0, abs=1.0)
    reps.clear()
    _mouths((), reps)
    assert reps[0].portal_mouths == []


def test_the_seat_stands_the_top_on_the_cover_beside_the_cut():
    p = _portal()
    ap = types.SimpleNamespace(dem=_CutDem(), cut_portals=(p,))
    got = portal_seats(ap, 0.5, 5.0)
    assert len(got) == 1 and got[0].top_y == 20.0
    st = got[0].stations
    assert st and all(abs(x) >= 40.0 for x, _y in st)   # never in the cut
    assert portal_seats(ap, 0.5, 5.0, taken={"dsf:obj1"}) == ()
    m = types.SimpleNamespace(plate_y=20.0, plate_kind=PORTAL_PLATE,
                              plate_stations=((1.0, 2.0),))
    d = datum_of(m)
    assert d is not None and d.y == 20.0 and d.stations == ((1.0, 2.0),)
