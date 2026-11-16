"""T4 (#2099 F2 P2, spec ``docs/specs/2099-F2.md`` §3): a walled trench's
floor stands on its walls' SECTION feet (``airport/wall_lines``, no clamp),
each corner at the zero plus the foot along the wall line it faces, linear
across two facing lines, never outside the walls' lowest and highest foot;
a plinth beside a wall never sets its floor.  Synthetic OBJ8 and ways; law
values read from the tables."""
from __future__ import annotations

import numpy as np
import pytest
from auto_patch_v2.airport import obj8
from auto_patch_v2.airport.trench_objects import mouth_portals, read_trench_objects
from auto_patch_v2.airport.walled_trench import walled_trench_floors
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import OsmWay
from auto_patch_v2.planar.basins import read_objects
from test_tunnel_objects import _airport, _slab, _write

_T = {"highway": "primary", "lanes": "2", "tunnel": "yes", "layer": "-1"}


def _sloped(vt, tris, x0, x1, z0, z1, ya, yb, top):
    """A wall slab ``x0..x1`` across, ``z0..z1`` along, its foot ``ya`` at
    ``z0`` falling linearly to ``yb`` at ``z1``, its top ``top``."""
    b = len(vt)
    for x, z, y in ((x0, z0, ya), (x1, z0, ya), (x1, z1, yb), (x0, z1, yb)):
        vt.append((x, y, z))
        vt.append((x, top, z))
    for k in range(4):
        i, j = b + 2 * k, b + 2 * ((k + 1) % 4)
        tris += [(i, i + 1, j + 1), (i, j + 1, j)]
    tris += [(b + 1, b + 3, b + 5), (b + 1, b + 5, b + 7)]
    tris += [(b, b + 4, b + 2), (b, b + 6, b + 4)]


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


@pytest.fixture(scope="module")
def floor(tmp_path_factory, law):
    d = tmp_path_factory.mktemp("pack") / "objects"
    d.mkdir()
    (d.parent / "Earth nav data").mkdir()
    (d.parent / "Earth nav data" / "apt.dat").write_text("I\n1000 Version\n", encoding="utf-8",
                                                         newline="")
    vt: list = []
    tris: list = []
    # the headwall across the bore, its foot broken at the bore line (a misread)
    for x0, x1 in ((-8.0, -0.2), (-0.2, 0.2), (0.2, 8.0)):
        _slab(vt, tris, x0, x1, -0.5, 0.5, -8.0, 1.0)
    # wall A: foot level -8; wall B: foot -8 -> -7 over its first 20 m, then
    # -7 (each its own wall line: they stand 0.5 m off the headwall)
    _slab(vt, tris, -8.0, -7.0, 1.0, 60.0, -8.0, -0.1)
    _sloped(vt, tris, 7.0, 8.0, 1.0, 20.5, -8.0 + 0.5 / 20.0, -7.0, -0.1)
    _slab(vt, tris, 7.0, 8.0, 20.5, 60.0, -7.0, -0.1)
    # a 0.1 m plinth at -7 on the floor beside wall A
    _slab(vt, tris, -7.0, -5.5, 10.0, 30.0, -7.1, -7.0)
    out = {"dir": d, "trench": _write(d / "trench.obj", vt, tris)}
    tunnel = OsmWay(-7, "big_roads", ((0.0, 0.6), (0.0, 300.0)), False, _T)
    airport = _airport(out, law, [("trench", (0.0, 0.0), 0.0, 0.0, "OBJECT")], (tunnel,))
    cache = obj8.ResourceCache(law.tables.structures.basin.min_solid_thickness_m)
    objects, _rep = read_objects(airport, law, cache)
    trenches, _notes = read_trench_objects(objects, cache, law, [tunnel])
    pins = mouth_portals(trenches, objects, cache, law, [tunnel], airport.dem.z)
    misread = {p.object_id for p in pins if p.opening_misread}
    floors, notes = walled_trench_floors(trenches, objects, cache, law, misread, airport.dem.z)
    assert len(floors) == 1, notes
    return floors[0]


def _z_at(faces: np.ndarray, x: float, y: float) -> float:
    """The floor's z at ``(x, y)`` (barycentric in the face holding it)."""
    for t in faces:
        (x1, y1, z1), (x2, y2, z2), (x3, y3, z3) = t
        det = (y2 - y3) * (x1 - x3) + (x3 - x2) * (y1 - y3)
        if abs(det) < 1e-12:
            continue
        a = ((y2 - y3) * (x - x3) + (x3 - x2) * (y - y3)) / det
        b = ((y3 - y1) * (x - x3) + (x1 - x3) * (y - y3)) / det
        c = 1.0 - a - b
        if min(a, b, c) >= -1e-9:
            return a * z1 + b * z2 + c * z3
    raise AssertionError(f"no floor face at {x:.2f},{y:.2f}")


def test_the_floor_stands_on_each_walls_section_foot(floor):
    zero, faces = floor.zero_z, floor.faces
    rel = faces[:, :, 2] - zero
    # none outside the walls' feet
    assert rel.min() >= -8.0 - 1e-6 and rel.max() <= -7.0 + 1e-6
    # across the floor at each station: its edges stand at each wall's foot
    # (the frame's y runs along the walls; the plinth beside wall A, stations
    # 10-30 m, leaves its edge 2 m off the wall: not read there)
    from shapely.geometry import LineString
    for st in (5.0, 15.0, 25.0, 45.0):
        hits = [g for y in (st, -st) for g in [floor.footprint.intersection(
            LineString([(-50.0, y), (50.0, y)]))] if not g.is_empty]
        assert hits, "the floor runs along the walls"
        x0, y0, x1, _y1 = hits[0].bounds
        foot_b = -8.0 + min(1.0, max(0.0, (st - 0.5) / 20.0))
        assert _z_at(faces, x1 - 0.05, y0) - zero == pytest.approx(foot_b, abs=0.05)
        if not 10.0 <= st <= 30.0:
            assert _z_at(faces, x0 + 0.05, y0) - zero == pytest.approx(-8.0, abs=0.05)
