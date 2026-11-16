"""#2077 rule A: a shared-origin set holding a RELIEF SKIN (a cliff or a
slope modelled as one surface, a town standing on it in the same frame)
is one rigid terrain composite -- recognised by its geometry only, seated
at its origin's ground, never split; its walls' zero footprint is where
the tile build conforms the ground to the frame zero.  Synthetic OBJ8s,
no corpus."""
from __future__ import annotations

import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from auto_patch_v2.airport import relief_skin as RS  # noqa: E402
from auto_patch_v2.airport import terrain_model as TM  # noqa: E402
from auto_patch_v2.airport.obj8 import parse_obj8  # noqa: E402
from auto_patch_v2.model.frame import Frame  # noqa: E402
from test_v2objsplit import _box, _write_obj  # noqa: E402

STEP = 10.0


def _sheet(path, height, x0=-300.0, x1=300.0, z0=0.0, z1=100.0):
    """A single-surface grid skin of ``height(x, z)``."""
    xs = np.arange(x0, x1 + 1e-6, STEP)
    zs = np.arange(z0, z1 + 1e-6, STEP)
    verts = [(float(x), float(height(x, z)), float(z)) for x in xs for z in zs]
    nz = len(zs)
    tris = []
    for i in range(len(xs) - 1):
        for j in range(nz - 1):
            a, b, c, d = i * nz + j, (i + 1) * nz + j, i * nz + j + 1, (i + 1) * nz + j + 1
            tris += [(a, b, c), (b, d, c)]
    return _write_obj(path, verts, [("", tris)])


def _cliff(x, z):
    """A 45 m cliff over 100 m: the old town's skin, in a sketch."""
    return 0.45 * z


def _shape(tmp_path, height, name="skin.obj", **kw):
    p = _sheet(tmp_path / name, height, **kw)
    return p, RS.shape_of(p, parse_obj8(p))


def test_a_steep_single_surface_skin_is_a_relief_skin(tmp_path):
    p, s = _shape(tmp_path, _cliff)
    assert s is not None
    m = RS._measures(s.grid)
    assert m["share"] >= RS.MIN_SHARE and m["extent_m"] >= TM.MIN_PLAN_M
    assert m["relief_m"] >= RS.MIN_RELIEF_M and m["skin"] >= RS.MIN_SKIN
    assert m["floor"] <= RS.MAX_FLOOR_SHARE and m["steep"] >= RS.MIN_STEEP


@pytest.mark.parametrize("height, why", [
    (lambda x, z: 0.1 * z, "too little relief (a roofscape's slope)"),
    (lambda x, z: 0.25 * z + 15.0 * (abs(x) < 100), "a floor: a flat plate"),
])
def test_what_is_not_a_relief_skin(tmp_path, height, why):
    assert _shape(tmp_path, height)[1] is None, why


def test_too_short_is_not(tmp_path):
    assert _shape(tmp_path, _cliff, x0=-200.0, x1=200.0)[1] is None


def test_a_building_stack_is_not_a_single_surface(tmp_path):
    """A roof over a floor everywhere is a building's stack, not a skin."""
    xs = np.arange(-300.0, 301.0, STEP)
    zs = np.arange(0.0, 101.0, STEP)
    verts, tris = [], []
    for lift in (0.0, 8.0):
        base = len(verts)
        verts += [(float(x), 0.45 * z + lift, float(z)) for x in xs for z in zs]
        nz = len(zs)
        for i in range(len(xs) - 1):
            for j in range(nz - 1):
                a, b = base + i * nz + j, base + (i + 1) * nz + j
                tris += [(a, b, a + 1), (b, b + 1, a + 1)]
    p = _write_obj(tmp_path / "stack.obj", verts, [("", tris)])
    assert RS.shape_of(p, parse_obj8(p)) is None


def _rows():
    return [("dsf:obj0", "skin.obj", (0.0, 0.0), 30.0, None, "OBJECT"),
            ("dsf:obj1", "walls.obj", (0.0, 0.0), 30.0, None, "OBJECT"),
            ("dsf:obj2", "far.obj", (900.0, 0.0), 30.0, None, "OBJECT")]


def test_the_skin_is_seated_at_its_origins_ground(tmp_path):
    """2.2: ``z0`` is our ground under the set's origin; an ``OBJECT_MSL``
    skin or one another reading holds is not read."""
    p, _s = _shape(tmp_path, _cliff)
    paths = {"skin.obj": p}
    got = RS.placement_skins(_rows(), paths.get,
                             lambda d: parse_obj8(paths[d]) if d in paths else None,
                             lambda x, y: 428.5)
    assert set(got) == {"dsf:obj0"}
    m = got["dsf:obj0"]
    assert m.z0 == pytest.approx(428.5) and m.skin and m.fill and not m.ground
    assert m.seat_by == ""
    rows = [("dsf:obj0", "skin.obj", (0.0, 0.0), 30.0, 430.0, "OBJECT_MSL")]
    assert not RS.placement_skins(rows, paths.get, lambda d: parse_obj8(paths[d]),
                                  lambda x, y: 428.5)
    assert not RS.placement_skins(_rows(), paths.get, lambda d: parse_obj8(paths[d])
                                  if d in paths else None, lambda x, y: 428.5,
                                  skip={"dsf:obj0"})
    hid = RS.placement_skins(_rows(), paths.get, lambda d: parse_obj8(paths[d])
                             if d in paths else None, lambda x, y: 428.5,
                             hidden={"skin.obj"})
    assert hid["dsf:obj0"].ground == "hidden" and hid["dsf:obj0"].hideable


def _walls(path, y0):
    """A block of 4 x 2 houses, 6 x 6 m on a 10 m pitch, standing at ``y0``
    below the skin (z < 0)."""
    verts, tris = [], []
    for k in range(8):
        v, t = _box(-60.0 + 10.0 * (k % 4), -40.0 + 10.0 * (k // 4), side=6.0, h=9.0)
        tris += [(a + len(verts), b + len(verts), c + len(verts)) for a, b, c in t]
        verts += [(x, y + y0, z) for x, y, z in v]
    return _write_obj(path, verts, [("", tris)])


def test_the_zero_footprint_holds_the_walls_on_the_frame_zero(tmp_path):
    """2.5: walls whose bottom stands within ``SKIRT_M`` of the frame zero
    make zero-level cells; their 30 m closing is the footprint, less the
    skin's own plan; walls authored high are not on the author's ground."""
    p, s = _shape(tmp_path, _cliff)
    w = _walls(tmp_path / "walls.obj", 0.5)
    rings = RS._zero_footprint([(TM._solid(parse_obj8(w)), 0.0)], [s.grid])
    assert rings
    from shapely.geometry import Point, Polygon
    poly = Polygon(rings[0])
    # the houses (x -60 .. -24, z -40 .. -24) and the streets between them
    assert len(rings) == 1
    assert poly.contains(Point(-57.0, -37.0)) and poly.contains(Point(-52.0, -37.0))
    assert poly.contains(Point(-52.0, -32.0))
    assert not poly.contains(Point(0.0, 50.0))          # the skin's plan
    assert 400.0 < poly.area < 1200.0
    # a lift moves the walls off the zero; walls 10 m up stand on nothing
    assert not RS._zero_footprint([(TM._solid(parse_obj8(w)), 10.0)], [s.grid])
    hi = _walls(tmp_path / "high.obj", 12.0)
    assert not RS._zero_footprint([(TM._solid(parse_obj8(hi)), 0.0)], [s.grid])


def test_the_frame_carries_its_plane_and_writes_it(tmp_path):
    """``set_members`` + ``with_planes``: every row of the frame rides the
    skin (OBJECT_MSL at the zero plus its lift), the far row does not, and
    the skin's own record carries ``cut`` with ``fill`` and the plane in
    lon/lat at the zero less UNDER_M."""
    p, _s = _shape(tmp_path, _cliff)
    w = _walls(tmp_path / "walls.obj", 0.0)
    paths = {"skin.obj": p, "walls.obj": w}
    geom = lambda d: parse_obj8(paths[d]) if d in paths else None  # noqa: E731
    skins = RS.placement_skins(_rows(), paths.get, geom, lambda x, y: 428.5)
    members = RS.with_planes(TM.set_members(_rows(), skins), _rows(), geom)
    assert set(members) == {"dsf:obj0", "dsf:obj1"}
    assert members["dsf:obj1"].plane and members["dsf:obj1"].plane == members["dsf:obj0"].plane

    class _A:
        terrain_models = (("dsf:obj0", "skin.obj", members["dsf:obj0"], 0.0),
                          ("dsf:obj1", "walls.obj", members["dsf:obj1"], 0.0))
        frame = Frame("TEST", (47.8, 13.04), 11)
    recs = TM.seat_records(_A())
    assert [r["elevation"] for r in recs] == [428.5, 428.5]
    cut = recs[0]["cut"]
    assert cut["fill"] is True and cut["plane"]["z"] == pytest.approx(428.4)
    ring = np.asarray(cut["plane"]["rings"][0])
    assert abs(ring[:, 1].mean() - 47.8) < 0.01 and abs(ring[:, 0].mean() - 13.04) < 0.01
    assert "cut" not in recs[1]
    assert "relief skins:" in RS.log_line("TEST", [m for _o, _d, m, _l in _A.terrain_models])
    # the terrain model's own line leaves a skin out
    assert TM.log_line("TEST", [members["dsf:obj0"]]).endswith("none")
