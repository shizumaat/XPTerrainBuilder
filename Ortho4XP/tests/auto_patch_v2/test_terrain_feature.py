"""Owner RULINGS 2026-10-20aq (#1169): a pack object that represents a
terrain feature (a whole mountain, a rocky point) keeps the author's
placement — its origin set is never converted, re-seated or read as
ground.  The rule is geometry only.  Synthetic packs in ``tmp_path``; no
airport, no corpus."""
from __future__ import annotations

import types

from auto_patch_v2.airport import obj8 as O
from auto_patch_v2.airport import placement_write as PW
from auto_patch_v2.airport import terrain_feature as TF


def _grid(n, step, height):
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
    body.append(f"TRIS 0 {len(idx)}")
    (tmp_path / "objects").mkdir(exist_ok=True)
    (tmp_path / "objects" / name).write_text("\n".join(body) + "\n", encoding="utf-8", newline="\n")
    return "objects/" + name


def _mountain(tmp_path):
    """1.2 km square, its surface rising 0.25 m per m: no floor plane."""
    return _write(tmp_path, "hill.obj", *_grid(81, 15.0, lambda x, z: 0.25 * x))


def _terminal(tmp_path):
    """A 600 m terminal: a flat floor and a 30 m roof."""
    floor, fi = _grid(31, 20.0, lambda x, z: 0.0)
    roof, ri = _grid(31, 20.0, lambda x, z: 30.0)
    return _write(tmp_path, "terminal.obj", floor + roof, fi + [i + len(floor) for i in ri])


def _row(path, lat=36.13, lon=-5.35, elevation=0.0, kind="OBJECT_MSL"):
    return types.SimpleNamespace(def_path=path, lat=lat, lon=lon, heading_deg=2.0,
                                 kind=kind, elevation=elevation)


def test_the_rule_selects_terrain_never_a_building(tmp_path):
    hill = O.parse_obj8(str(tmp_path / _mountain(tmp_path)))
    terminal = O.parse_obj8(str(tmp_path / _terminal(tmp_path)))
    area, span, floor = TF.underside(hill)
    assert area >= TF.MIN_AREA_M2 and span >= TF.MIN_UNDERSIDE_SPAN_M
    assert floor <= TF.MAX_FLOOR_SHARE and TF.is_terrain_feature(hill)
    assert not TF.is_terrain_feature(terminal)       # a floor plane
    small = O.parse_obj8(str(tmp_path / _write(
        tmp_path, "ramp.obj", *_grid(6, 20.0, lambda x, z: x))))
    assert not TF.is_terrain_feature(small)          # slope, but a building's size


def test_the_origin_set_keeps_its_authored_rows(tmp_path):
    """The rock and the guns placed in its frame stay OBJECT_MSL as
    authored; an unrelated building row elsewhere still converts."""
    hill, guns, shed = _mountain(tmp_path), _terminal(tmp_path), _terminal(tmp_path)
    dump = types.SimpleNamespace(placements=[
        _row(hill), _row(guns), _row(shed, lat=36.14, elevation=3.0)])
    assert TF.feature_rows(dump, str(tmp_path)) == frozenset({0, 1})
    plan = types.SimpleNamespace(units=(), contacts=(), flat=None, authored_seats=())
    ss = types.SimpleNamespace(unit_seats=())
    conv, msl, _r, counts = PW.dump_rows(dump, plan, ss, (), lambda la, lo: 100.0,
                                         str(tmp_path), tol_m=0.02)
    touched = {c.index for c in conv} | {m.index for m in msl}
    assert 0 not in touched and 1 not in touched and 2 in touched
    assert counts["terrain_feature_rows_kept"] == 2


def test_the_reader_marks_the_set_and_reads_nothing(tmp_path):
    hill, guns = _mountain(tmp_path), _terminal(tmp_path)
    cache = O.ResourceCache(0.5)
    placements = [("a", hill, (0.0, 0.0), 2.0, 0.0, "OBJECT_MSL"),
                  ("b", guns, (0.0, 0.0), 2.0, 0.0, "OBJECT_MSL"),
                  ("c", guns, (900.0, 0.0), 2.0, 0.0, "OBJECT_MSL")]
    got = TF.feature_ids(placements, lambda d: cache.geometry(str(tmp_path / d)))
    assert got == frozenset({"a", "b"})
