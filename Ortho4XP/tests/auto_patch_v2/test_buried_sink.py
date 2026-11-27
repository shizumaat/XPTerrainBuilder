"""#2293: an ``OBJECT_AGL`` SINK that buries its building on every side,
with the hill it was sunk for beside it, converts and is seated on our
ground (``airport/buried_sink``); a sink whose low side meets the grade,
a sink on open ground (the height trick) and a pole keep the author's
row.  Synthetic packs in ``tmp_path``; no airport, no corpus."""
from __future__ import annotations

import math
import types

from auto_patch_v2.airport import buried_sink as BS
from auto_patch_v2.airport import placement_write as PW

Z = 100.0
LAT, LON = 17.9, -62.8
M_LAT = 110_000.0
#: the stock library index the tests resolve through (``lib/<name>``)
INDEX: dict[str, str] = {}


def _box_obj(tmp_path, name, x0, x1, z0, z1, y0=-0.5, y1=6.0):
    """An OBJ8 of one closed box ``x0..x1`` by ``z0..z1``, ``y0..y1``."""
    vt = [(x, y, z) for y in (y0, y1) for x, z in ((x0, z0), (x1, z0), (x1, z1), (x0, z1))]
    faces = ((0, 2, 1), (0, 3, 2), (4, 5, 6), (4, 6, 7), (0, 1, 5), (0, 5, 4),
             (1, 2, 6), (1, 6, 5), (2, 3, 7), (2, 7, 6), (3, 0, 4), (3, 4, 7))
    idx = [i for f in faces for i in f]
    body = ["I", "800", "OBJ", f"POINT_COUNTS {len(vt)} 0 0 {len(idx)}"]
    body += [f"VT {x} {y} {z} 0 1 0 0 0" for x, y, z in vt]
    body += [f"IDX {i}" for i in idx]
    body.append(f"TRIS 0 {len(idx)}")
    lib = tmp_path / "library"
    lib.mkdir(exist_ok=True)
    (lib / name).write_text("\n".join(body) + "\n", encoding="utf-8", newline="\n")
    INDEX["lib/" + name] = str(lib / name)
    return "lib/" + name


def _row(path, elevation, kind="OBJECT_AGL"):
    return types.SimpleNamespace(def_path=path, lat=LAT, lon=LON, heading_deg=0.0,
                                 kind=kind, elevation=elevation)


def _east_m(lon):
    return (lon - LON) * M_LAT * math.cos(math.radians(LAT))


def _pad_and_wall(wall_e=12.0, rise=6.0):
    """A level pad at ``Z`` with a retaining wall ``rise`` high from
    ``wall_e`` metres east of the row."""
    return lambda la, lo: Z + (rise if _east_m(lo) >= wall_e else 0.0)


def _flat(la, lo):
    return Z


def _sloped(la, lo):
    """3 m per 20 m rising east: a sink of 1.5 m puts the west side on grade."""
    return Z + 0.15 * _east_m(lo)


def _dump(*rows):
    return types.SimpleNamespace(placements=list(rows))


def test_a_sink_buried_on_every_side_with_its_hill_beside_converts(tmp_path):
    res = _box_obj(tmp_path, "hangar.obj", -10, 10, -13, 13)
    got = BS.buried_rows(_dump(_row(res, -3.5)), str(tmp_path), _pad_and_wall(),
                         bar_m=1.0, index=INDEX)
    assert got == {0}


def test_the_height_trick_on_open_ground_keeps_the_authored_row(tmp_path):
    res = _box_obj(tmp_path, "canopy.obj", -10, 10, -13, 13)
    assert BS.buried_rows(_dump(_row(res, -3.5)), str(tmp_path), _flat,
                          bar_m=1.0, index=INDEX) == frozenset()


def test_a_low_side_on_grade_keeps_the_authored_row(tmp_path):
    res = _box_obj(tmp_path, "slope.obj", -10, 10, -13, 13)
    # the drape at the row is Z; the west wall's ground is Z - 1.5: on grade
    assert BS.buried_rows(_dump(_row(res, -1.5)), str(tmp_path), _sloped,
                          bar_m=1.0, index=INDEX) == frozenset()


def test_a_pole_keeps_the_authored_row(tmp_path):
    res = _box_obj(tmp_path, "pole.obj", -0.2, 0.2, -0.2, 0.2, y0=0.0, y1=9.0)
    assert BS.buried_rows(_dump(_row(res, -3.5)), str(tmp_path), _pad_and_wall(1.0),
                          bar_m=1.0, index=INDEX) == frozenset()


def test_a_shallow_sink_a_lift_and_a_disarmed_bar_convert_nothing(tmp_path):
    res = _box_obj(tmp_path, "shed.obj", -10, 10, -13, 13)
    s = _pad_and_wall()
    assert BS.buried_rows(_dump(_row(res, -0.8)), str(tmp_path), s, bar_m=1.0,
                          index=INDEX) == frozenset()
    assert BS.buried_rows(_dump(_row(res, 3.0)), str(tmp_path), s, bar_m=1.0,
                          index=INDEX) == frozenset()
    assert BS.buried_rows(_dump(_row(res, -3.5)), str(tmp_path), s, bar_m=0.0,
                          index=INDEX) == frozenset()


def test_settled_rows_and_unreadable_resources_are_skipped(tmp_path):
    res = _box_obj(tmp_path, "hangar.obj", -10, 10, -13, 13)
    dump = _dump(_row(res, -3.5), _row("lib/not/installed.obj", -3.5))
    assert BS.buried_rows(dump, str(tmp_path), _pad_and_wall(), bar_m=1.0,
                          skip={0}, index=INDEX) == frozenset()


def test_outline_stations_walk_the_hull():
    import numpy as np
    v = np.array([(0, 0, 0), (4, 0, 0), (4, 0, 4), (0, 0, 4), (2, 5, 2)], float)
    st = BS.outline_stations(v, 2.0)
    assert len(st) == 8
    assert {(round(x), round(z)) for x, z in st} >= {(0, 0), (4, 0), (4, 4), (0, 4)}


def test_dump_rows_converts_the_buried_sink_on_ground(tmp_path, monkeypatch):
    res = _box_obj(tmp_path, "hangar.obj", -10, 10, -13, 13)
    monkeypatch.setattr(BS, "_library_index", lambda _root: INDEX)
    dump = _dump(_row(res, -3.5))
    plan = types.SimpleNamespace(units=(), contacts=(), flat=None, authored_seats=())
    ss = types.SimpleNamespace(unit_seats=())
    conv, msl, _r, counts = PW.dump_rows(dump, plan, ss, (), _pad_and_wall(), str(tmp_path),
                                         tol_m=0.02, sink_buried_m=1.0)
    assert [c.index for c in conv] + [m.index for m in msl] == [0]
    assert counts.get("buried_sinks_seated") == 1
    conv0, msl0, _r0, _c0 = PW.dump_rows(dump, plan, ss, (), _pad_and_wall(), str(tmp_path),
                                         tol_m=0.02)
    assert not conv0 and not msl0


def test_a_pack_object_is_the_splits_never_a_stock_sink(tmp_path):
    res = _box_obj(tmp_path, "deck.obj", -10, 10, -13, 13)
    (tmp_path / "pack" / "lib").mkdir(parents=True)
    deck = (tmp_path / "library" / "deck.obj").read_text(encoding="utf-8")
    (tmp_path / "pack" / res).write_text(deck, encoding="utf-8", newline="\n")
    assert BS.buried_rows(_dump(_row(res, -3.5)), str(tmp_path / "pack"), _pad_and_wall(),
                          bar_m=1.0, index=INDEX) == frozenset()
    assert BS.sinks_box(_dump(_row(res, -3.5)), 1.0, str(tmp_path / "pack")) is None
    assert BS.sinks_box(_dump(_row(res, -3.5)), 1.0, str(tmp_path)) is not None
