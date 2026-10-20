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


def _boxes(tmp_path, name, boxes):
    """An OBJ8 of closed boxes ``(x0, y0, x1, y1)`` (2 m deep in z), one
    genuine component each."""
    vt, idx = [], []
    faces = ((0, 2, 1), (0, 3, 2), (4, 5, 6), (4, 6, 7), (0, 1, 5), (0, 5, 4),
             (1, 2, 6), (1, 6, 5), (2, 3, 7), (2, 7, 6), (3, 0, 4), (3, 4, 7))
    for x0, y0, x1, y1 in boxes:
        k = len(vt)
        vt += [(x0, y0, 0), (x1, y0, 0), (x1, y0, 2), (x0, y0, 2),
               (x0, y1, 0), (x1, y1, 0), (x1, y1, 2), (x0, y1, 2)]
        idx += [k + i for f in faces for i in f]
    body = ["I", "800", "OBJ", f"POINT_COUNTS {len(vt)} 0 0 {len(idx)}"]
    body += [f"VT {x} {y} {z} 0 1 0 0 0" for x, y, z in vt]
    body += [f"IDX {i}" for i in idx]
    body.append(f"TRIS 0 {len(idx)}")
    (tmp_path / "objects").mkdir(exist_ok=True)
    (tmp_path / "objects" / name).write_text("\n".join(body) + "\n", encoding="utf-8",
                                             newline="\n")
    return "objects/" + name


def _read(tmp_path, rows, dem=lambda x, y: Z):
    """``obj8.read_placed_objects`` over synthetic rows ``(id, path, xy,
    kind)`` — the one site ``zero_y`` / ``origin_built`` are set."""
    from auto_patch_v2.airport import obj8 as O8
    cache = O8.ResourceCache(0.05)
    objs, _rep = O8.read_placed_objects(
        [(i, p, xy, 0.0, 40.0 if k == "OBJECT_MSL" else None, k) for i, p, xy, k in rows],
        str(tmp_path), None, dem, 0.5, 0.05, 0.3, cache,
        floor_plate_normal_y_min=0.9, msl_tol_m=0.3)
    return objs, cache


def _partition(objs, cache, elevated_base_m=0.5):
    from auto_patch_v2.airport import contact as C
    members = [(o, cache.geometry(o.resolved), list(enumerate(cache.components(o.resolved))))
               for o in objs]
    return C.partition(members, 0.01, 1.0, 10**9, 0.5, 50_000,
                       elevated_base_m=elevated_base_m)


def test_two_bodies_of_one_lifted_msl_row_each_stand_on_their_own_feet(tmp_path):
    """#1102 (owner Q54): two boxes authored 6 m up under ONE ``OBJECT_MSL``
    row, over ground 3 m apart.  The zero moves in the AUTHORED frame, so
    both are ground parts with feet at authored y 0 (pre-fix: both
    "elevated", footless, at y_zero 0.0), and the unit stays keyed at
    ``agl_m`` 0."""
    path = _boxes(tmp_path, "pair.obj", [(0.0, 6.0, 4.0, 10.0), (30.0, 6.0, 34.0, 9.0)])
    objs, cache = _read(tmp_path, [("dsf:obj0", path, (0.0, 0.0), "OBJECT_MSL")],
                        dem=lambda x, y: Z if x < 15.0 else Z + 3.0)
    (o,) = objs
    assert o.zero_y == 6.0 and not o.origin_built and o.agl_m == 0.0
    part = _partition(objs, cache)
    assert part.structures == 2 and len(part.parts) == 2
    for p in part.parts:
        assert p.base_y == 0.0 and p.feet.shape[0] > 0
        assert abs(float(p.feet[:, 2].max())) < 1e-9          # authored y of the feet
        assert abs(float(p.pts[:, 1].min()) - Z) < 1e-9        # rendered on the origin's zero
    xs = sorted(float(p.feet[:, 0].mean()) for p in part.parts)
    assert xs[0] < 15.0 < xs[1]                                  # over each its own ground


def test_the_elevated_screen_is_relative_to_the_zero(tmp_path):
    """``[rebake] elevated_base_m`` 0.5 reads ``base_y − zero_y``: a part
    at 6.4 over a zero of 6.0 is ground, one at 7.0 is elevated."""
    path = _boxes(tmp_path, "three.obj", [(0.0, 6.0, 4.0, 9.0), (20.0, 6.4, 24.0, 9.0),
                                          (40.0, 7.0, 44.0, 9.0)])
    objs, cache = _read(tmp_path, [("dsf:obj0", path, (0.0, 0.0), "OBJECT_MSL")])
    part = _partition(objs, cache)
    by_x = sorted(part.parts, key=lambda p: float(p.pts[:, 0].min()))
    assert [round(p.base_y, 3) for p in by_x] == [0.0, 0.4, 1.0]
    assert [p.feet.shape[0] > 0 for p in by_x] == [True, True, False]


def test_a_one_body_member_read_against_its_zero_is_written_never_kept(tmp_path):
    """The writer restores the pristine frame (``BodyCut`` offset ``oy +
    zero_y``): the one body is WRITTEN (its authored row would float it
    6 m) and its vertices' y_min is 0.000."""
    from auto_patch_v2.airport import placement_file as PF
    from auto_patch_v2.airport.placement_record import Split
    path = str(tmp_path / _boxes(tmp_path, "tower.obj", [(0.0, 6.0, 4.0, 30.0)]))
    body = types.SimpleNamespace(body_id=0, cut_components=(0,), tris=(), seat=None,
                                 anchor=types.SimpleNamespace(offset=(2.0, 0.0, 1.0)),
                                 new_resource="objects/tower__b0.obj", merged_into="")
    rec = Split(1, "dsf:obj1", "objects/tower.obj", "", 40.0, -3.0, 0.0, (body,))

    def run(zero_y, landed):
        m = types.SimpleNamespace(id="dsf:obj1", resource="objects/tower.obj", tilted=(),
                                  live_path=path, authored_path=path, zero_y=zero_y)
        counts = {"kept": 0, "one_body": 0, "split": 0, "files": 0, "write_error": 0}
        splits, kept, whole = [], [], []
        PF._cut_and_file(rec, m, True, counts, splits, kept, whole,
                         always_write=False, tilted_whole=[], landed=landed)
        return splits, kept
    for landed in (False, True):
        splits, kept = run(0.0, landed)                       # the control: kept whole
        assert not splits and kept
        splits, kept = run(6.0, landed)
        assert len(splits) == 1 and not kept
    (f,) = splits[0].files
    ys = [float(ln.split()[2]) for ln in f.text.splitlines() if ln.split()[:1] == ["VT"]]
    assert min(ys) == 0.0 and max(ys) == 24.0


def test_the_partition_guard_keeps_a_set_built_around_its_origin(tmp_path):
    """Owner Q54: MSL rows are split like any on-ground row, except an
    origin set with a member reaching below its origin (a hillside wing,
    an approach-light pole) — the whole set — or one that cannot be read.
    The verdict is ``PlacedObject.origin_built``, set where the row is
    read; a lifted member's ``zero_y`` is its lowest static y."""
    deep = _boxes(tmp_path, "wing_low.obj", [(0.0, -11.5, 4.0, 4.0)])
    high = _boxes(tmp_path, "wing_high.obj", [(0.0, 2.5, 4.0, 9.0)])
    car = _boxes(tmp_path, "car.obj", [(0.0, 6.0, 4.0, 7.5)])
    objs, _c = _read(tmp_path, [("a", deep, (0.0, 0.0), "OBJECT_MSL"),
                                ("b", high, (0.0, 0.0), "OBJECT_MSL"),
                                ("c", car, (50.0, 0.0), "OBJECT_MSL"),
                                ("d", deep, (90.0, 0.0), "OBJECT"),
                                ("e", "objects/missing.obj", (120.0, 0.0), "OBJECT_MSL")])
    got = {o.id: (o.origin_built, o.zero_y) for o in objs}
    assert got == {"a": (True, 0.0), "b": (True, 0.0), "c": (False, 6.0),
                   "d": (False, 0.0), "e": (True, 0.0)}
