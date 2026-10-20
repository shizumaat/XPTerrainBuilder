"""Owner answer 48 (2026-10-20, #1102): a converted ``OBJECT_MSL`` row is
seated by its geometry's FEET on the design surface under them
(``surface − y``), not by its origin.  Synthetic packs in ``tmp_path``;
no airport, no corpus."""
from __future__ import annotations

import types

from auto_patch_v2.airport import msl_feet as MF
from auto_patch_v2.airport import placement_write as PW

Z = 100.0


def _obj(tmp_path, name, y0, y1, *, anim_y=None, dx=0.0):
    """An OBJ8 whose static solid spans ``y0..y1`` (and, with ``anim_y``,
    an animated triangle reaching down to it)."""
    vt = [(dx, y0, 0), (dx + 5, y0, 0), (dx, y1, 5), (dx + 5, y1, 5)]
    idx = [0, 1, 2, 1, 3, 2]
    if anim_y is not None:
        vt += [(0, anim_y, 0), (1, anim_y, 0), (0, anim_y, 1)]
        idx += [4, 5, 6]
    body = ["I", "800", "OBJ", f"POINT_COUNTS {len(vt)} 0 0 {len(idx)}"]
    body += [f"VT {x} {y} {z} 0 1 0 0 0" for x, y, z in vt]
    body += [f"IDX {i}" for i in idx]
    body.append("TRIS 0 6")
    if anim_y is not None:
        body += ["ANIM_begin", "TRIS 6 3", "ANIM_end"]
    (tmp_path / "objects").mkdir(exist_ok=True)
    (tmp_path / "objects" / name).write_text("\n".join(body) + "\n", encoding="utf-8", newline="\n")
    return "objects/" + name


def _row(path, kind="OBJECT_MSL", elevation=40.0, lat=38.5, lon=-28.7):
    return types.SimpleNamespace(def_path=path, lat=lat, lon=lon, heading_deg=12.0,
                                 kind=kind, elevation=elevation)


def _rows(dump, tmp_path, unit_seats=(), surface=lambda la, lo: Z):
    plan = types.SimpleNamespace(units=(), contacts=(), flat=None, authored_seats=())
    ss = types.SimpleNamespace(unit_seats=unit_seats)
    return PW.dump_rows(dump, plan, ss, (), surface, str(tmp_path), tol_m=0.02)


def test_lowest_feet_ignore_animated_parts(tmp_path):
    p = _obj(tmp_path, "a.obj", 6.0, 12.0, anim_y=-3.0)
    f = MF.lowest_feet(str(tmp_path / p), 0.3)
    assert f.shape == (2, 3) and float(f[:, 1].min()) == 6.0
    assert MF.lowest_feet(str(tmp_path / "missing.obj"), 0.3) is None


def test_a_lifted_msl_object_is_seated_by_its_feet(tmp_path):
    """The LPHR class: the whole model 6 m above its origin.  Converted
    on-ground it floats 6 m; seated by its row its feet meet the surface."""
    tower = _obj(tmp_path, "tower.obj", 6.0, 30.0)
    dump = types.SimpleNamespace(placements=[_row(tower)])
    conv, msl, _r, counts = _rows(dump, tmp_path)
    assert not conv
    (s,) = msl
    assert s.index == 0 and s.why == "geometry_feet"
    assert abs(s.elevation + 6.0 - Z) < 1e-9          # feet on the surface
    assert counts["msl_feet_seated"] == 1


def test_the_surface_is_read_under_the_feet_not_at_the_origin(tmp_path):
    """An origin metres from its geometry, on higher ground: the feet are
    seated on the ground under THEM (LPHR's apron vehicles)."""
    car = _obj(tmp_path, "car.obj", 0.0, 1.5, dx=40.0)     # 40 m from its origin
    # the origin's ground 31.5, everywhere else (under the feet) 27.5
    origin = (38.5, -28.7)
    surf = lambda la, lo: 31.5 if (la, lo) == origin else 27.5  # noqa: E731
    dump = types.SimpleNamespace(placements=[_row(car)])
    _c, msl, _r, _n = _rows(dump, tmp_path, surface=surf)
    assert abs(msl[0].elevation - 27.5) < 1e-9


def test_rows_sharing_one_origin_are_one_rigid_set(tmp_path):
    """One model split into files at one origin (bodies and wheels): every
    piece takes ONE elevation, so the model is never pulled apart."""
    body = _obj(tmp_path, "body.obj", 6.2, 7.5)
    wheels = _obj(tmp_path, "wheels.obj", 5.9, 6.4)
    dump = types.SimpleNamespace(placements=[_row(body), _row(wheels)])
    _c, msl, _r, _n = _rows(dump, tmp_path)
    assert sorted(m.index for m in msl) == [0, 1]
    assert len({round(m.elevation, 9) for m in msl}) == 1
    # the minimax: wheels need Z - 5.9, the body's feet Z - 6.2
    assert abs(msl[0].elevation - (Z - 6.05)) < 1e-9


def test_geometry_reaching_below_its_origin_keeps_the_conversion(tmp_path):
    """A hillside piece or a mast pole reaching under its origin is not
    lifted onto its lowest vertex; nor is any row sharing its origin."""
    deep = _obj(tmp_path, "wing_low.obj", -11.5, 4.0)
    high = _obj(tmp_path, "wing_high.obj", 2.5, 9.0)
    dump = types.SimpleNamespace(placements=[_row(deep), _row(high)])
    conv, msl, _r, n = _rows(dump, tmp_path)
    assert not msl and sorted(c.index for c in conv) == [0, 1]
    assert n["msl_feet_below_origin"] == 2


def test_left_converted_where_it_cannot_be_read_or_the_unit_seats_it(tmp_path):
    tower = _obj(tmp_path, "tower.obj", 6.0, 30.0)
    dump = types.SimpleNamespace(placements=[_row(tower)])
    # no graded face: X-Plane drapes, nothing is guessed
    conv, msl, _r, n = _rows(dump, tmp_path, surface=lambda la, lo: None)
    assert [c.index for c in conv] == [0] and n["msl_feet_off_sheet"] == 1
    # on a unit's pad: the unit's to seat
    box = (38.4, -28.8, 38.6, -28.6, Z, "pad")
    conv, msl, _r, n = _rows(dump, tmp_path, unit_seats=(box,))
    assert [c.index for c in conv] == [0] and n["msl_feet_on_unit_pad"] == 1
    # an unresolvable (stock) resource and a plain row: untouched
    dump = types.SimpleNamespace(placements=[
        _row("lib/airport/tower.obj"), _row(tower, kind="OBJECT", elevation=None)])
    conv, msl, _r, n = _rows(dump, tmp_path)
    assert [c.index for c in conv] == [0] and not msl
    assert n["msl_feet_unresolved"] == 1


def test_a_seat_equal_to_the_drape_is_left_to_the_drape(tmp_path):
    shed = _obj(tmp_path, "shed.obj", 0.0, 3.0)
    dump = types.SimpleNamespace(placements=[_row(shed)])
    conv, msl, _r, n = _rows(dump, tmp_path)
    assert [c.index for c in conv] == [0] and not msl
    assert n["msl_feet_left_to_the_drape"] == 1


def test_the_partition_guard_keeps_a_set_built_around_its_origin(tmp_path):
    """Owner Q54: MSL rows are split like any on-ground row, except an
    origin set with a member reaching below its origin (a hillside wing,
    an approach-light pole) — the whole set — or one that cannot be read."""
    from auto_patch_v2.airport import obj8 as O8
    deep = str(tmp_path / _obj(tmp_path, "wing_low.obj", -11.5, 4.0))
    high = str(tmp_path / _obj(tmp_path, "wing_high.obj", 2.5, 9.0))
    car = str(tmp_path / _obj(tmp_path, "car.obj", 6.0, 7.5))

    def po(i, path, xy, kind="OBJECT_MSL"):
        return types.SimpleNamespace(id=i, resolved=path, xy=xy, heading_deg=0.0,
                                     kind=kind)
    objs = [po("a", deep, (0.0, 0.0)), po("b", high, (0.0, 0.0)),
            po("c", car, (50.0, 0.0)), po("d", deep, (90.0, 0.0), kind="OBJECT"),
            po("e", None, (120.0, 0.0))]
    got = MF.below_origin_ids(objs, O8.parse_obj8, 0.3)
    assert got == {"a", "b", "e"}
