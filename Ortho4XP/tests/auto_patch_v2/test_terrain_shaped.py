"""Issue #1730: a TERRAIN-SHAPED hard deck (a hill with its highway modelled
as one ``ATTR_hard_deck`` skin) is one rigid body seated at its fit to the
DEM -- never split, never a pit, never a bridge -- and the patch under it is
drawn to its surface.  Geometry and the DEM only; synthetic packs in
``tmp_path``, no airport, no corpus."""
from __future__ import annotations

import math
import types

import numpy as np

from auto_patch_v2.airport import obj8 as O
from auto_patch_v2.airport import terrain_shaped as TS
from auto_patch_v2.geom import terrain_deck as TD


def _sheet(n, step, height):
    vt, idx = [], []
    for i in range(n):
        for j in range(n):
            vt.append((i * step, height(i * step, j * step), j * step))
    for i in range(n - 1):
        for j in range(n - 1):
            a, b, c, d = i * n + j, (i + 1) * n + j, i * n + j + 1, (i + 1) * n + j + 1
            idx += [a, b, c, b, d, c]
    return vt, idx


def _write(tmp_path, name, vt, idx):
    body = ["I", "800", "OBJ", f"POINT_COUNTS {len(vt)} 0 0 {len(idx)}"]
    body += [f"VT {x} {y} {z} 0 1 0 0 0" for x, y, z in vt]
    body += [f"IDX {i}" for i in idx]
    body += ["ATTR_hard_deck concrete", f"TRIS 0 {len(idx)}"]
    (tmp_path / "objects").mkdir(exist_ok=True)
    path = tmp_path / "objects" / name
    path.write_text("\n".join(body) + "\n", encoding="utf-8", newline="\n")
    return "objects/" + name


def _grid(tmp_path, name, vt, idx):
    return TS.grid_of_resource(_write(tmp_path, name, vt, idx), str(tmp_path), None)


def _hill(x, z):
    """A 20 m hill over a 300 m square (authored y)."""
    return 20.0 * math.sin(math.pi * x / 300.0) * math.sin(math.pi * z / 300.0) - 20.0


def _dem(offset):
    """The ground the hill was modelled on, ``offset`` higher."""
    def many(xs, ys):
        xs, ys = np.asarray(xs, float), np.asarray(ys, float)
        # heading 0: authored (x, z) -> frame (x, -z)
        return 20.0 * np.sin(np.pi * xs / 300.0) * np.sin(np.pi * -ys / 300.0) - 20.0 + offset
    return many


def test_a_hill_skin_is_terrain_shaped_and_fitted(tmp_path):
    grid = _grid(tmp_path, "hill.obj", *_sheet(31, 10.0, _hill))
    assert grid is not None and grid.area_m2 >= TS.MIN_AREA_M2
    assert grid.relief_m >= TS.MIN_RELIEF_M
    fits = TS.placement_fits([("dsf:obj0", "objects/hill.obj", (0.0, 0.0), 0.0)],
                             lambda d: grid, _dem(37.3))
    f = fits["dsf:obj0"]
    assert abs(f.z0 - 37.3) < 0.2 and f.follow > 0.95


def test_a_deck_is_never_terrain_shaped(tmp_path):
    """A flat deck fails the relief gate however large; a bridge's size
    fails the area gate; a skin over a gap fails the follow gate."""
    flat = _write(tmp_path, "flat.obj", *_sheet(31, 10.0, lambda x, z: 0.02 * x))
    assert TS.grid_of_resource(flat, str(tmp_path), None) is None
    small = _write(tmp_path, "small.obj", *_sheet(11, 10.0, _hill))
    assert TS.grid_of_resource(small, str(tmp_path), None) is None
    grid = _grid(tmp_path, "span.obj", *_sheet(31, 10.0, _hill))
    ground = _dem(37.3)

    def gap(xs, ys):                     # a flat river 30 m down under its span
        xs = np.asarray(xs, float)
        return np.where((xs > 60.0) & (xs < 240.0), 7.3, ground(xs, ys))
    assert not TS.placement_fits([("dsf:obj0", "objects/span.obj", (0.0, 0.0), 0.0)],
                                 lambda d: grid, gap)


def test_a_deck_in_a_shared_frame_is_the_frames(tmp_path):
    grid = _grid(tmp_path, "hill.obj", *_sheet(31, 10.0, _hill))
    rows = [("dsf:obj0", "objects/hill.obj", (0.0, 0.0), 0.0),
            ("dsf:obj1", "objects/terminal.obj", (0.0, 0.0), 0.0)]
    assert not TS.placement_fits(rows, lambda d: grid if d.endswith("hill.obj") else None,
                                 _dem(37.3))


def test_the_patch_target_is_the_deck_surface_nearest_the_ground(tmp_path):
    """Cut to the top, fill to the underside, the ground kept inside the
    span; a point off the deck is not under it."""
    grid = _grid(tmp_path, "hill.obj", *_sheet(31, 10.0, _hill))
    f = TS.placement_fits([("dsf:obj0", "objects/hill.obj", (0.0, 0.0), 0.0)],
                          lambda d: grid, _dem(37.3))["dsf:obj0"]
    xs, ys = np.array([150.0, 150.0, 900.0]), np.array([-150.0, -150.0, -150.0])
    surface = f.z0 + _hill(150.0, 150.0) - TD.UNDER_M
    t, under = TD.target_at(f, xs, ys, np.array([surface + 5.0, surface - 5.0, 10.0]))
    assert under.tolist() == [True, True, False]
    assert abs(t[0] - surface) < 0.3 and abs(t[1] - surface) < 0.3 and t[2] == 10.0


def test_the_seat_is_written_on_the_row(tmp_path):
    rows = [types.SimpleNamespace(def_path="objects/x.obj", lat=39.18, lon=-76.68,
                                  heading_deg=0.4, kind="OBJECT", elevation=None),
            types.SimpleNamespace(def_path="objects/hill.obj", lat=39.19, lon=-76.68,
                                  heading_deg=0.4, kind="OBJECT", elevation=None)]
    dump = types.SimpleNamespace(placements=rows)
    rec = [{"id": "dsf:obj1", "resource": "objects/hill.obj", "seat": TS.SEAT,
            "elevation": 37.21},
           {"id": "dsf:obj0", "resource": "objects/hill.obj", "seat": TS.SEAT,
            "elevation": 1.0},                       # names another resource: ignored
           {"id": "dsf:obj0", "resource": "objects/x.obj", "seat": "re-seated"}]
    seats = TS.row_seats(dump, rec)
    assert [(m.index, m.elevation, m.why) for m in seats] == [(1, 37.21, "terrain_fit")]


def test_the_object_read_reads_nothing_of_a_terrain_shaped_deck(tmp_path):
    """No witness, no hard deck for the bridge readers, the fit recorded."""
    _write(tmp_path, "hill.obj", *_sheet(31, 10.0, _hill))
    dem = _dem(37.3)
    objs, _rep = O.read_placed_objects(
        [("dsf:obj0", "objects/hill.obj", (0.0, 0.0), 0.0, None, "OBJECT")],
        str(tmp_path), None, lambda x, y: float(dem([x], [y])[0]), 2.5, 0.2, 1.0,
        floor_plate_normal_y_min=0.9, dem_many=dem)
    o = objs[0]
    assert o.terrain_fit is not None and abs(o.terrain_fit.z0 - 37.3) < 0.2
    assert o.hard_deck is None and not o.witnesses and not o.terrain_feature


def test_the_groundside_patch_under_the_deck_takes_its_surface(tmp_path):
    """One soft target per groundside vertex under the deck; an airside
    vertex (airside is king) and a vertex off the deck take none."""
    from auto_patch_v2.constraints import terrain_shaped as CT
    from auto_patch_v2.law.tables import load_default
    grid = _grid(tmp_path, "hill.obj", *_sheet(31, 10.0, _hill))
    f = TS.placement_fits([("dsf:obj0", "objects/hill.obj", (0.0, 0.0), 0.0)],
                          lambda d: grid, _dem(37.3))["dsf:obj0"]
    roles = {0: "service_road", 1: "stub", 2: "service_road"}
    xy = {0: (150.0, -150.0), 1: (150.0, -140.0), 2: (900.0, -150.0)}
    planar = types.SimpleNamespace(
        vertices={v: types.SimpleNamespace(xy=xy[v], incident_faces=(v,)) for v in xy},
        roles_at=lambda v: (roles[v],))
    ground = _dem(37.3 + 4.0)                        # the ground 4 m over the deck
    airport = types.SimpleNamespace(
        terrain_decks=(f,), dem=types.SimpleNamespace(z_many=ground))
    rows = CT.deck_surface_rows(planar, load_default(), airport)
    assert [r.terms[0][0] for r in rows] == [0]
    surface = f.z0 + _hill(150.0, 150.0) - TD.UNDER_M
    assert abs(rows[0].lo - surface) < 0.3 and rows[0].lo == rows[0].hi
    assert TS.seat_records(airport)[0]["elevation"] == round(f.z0, 3)
