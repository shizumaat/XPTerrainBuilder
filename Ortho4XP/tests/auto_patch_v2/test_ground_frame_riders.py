"""#1837: a stock ``OBJECT_MSL`` row standing on an ``OBJECT`` /
``OBJECT_AGL`` frame of the airport pack moves with that frame by the
seat delta its riders witness (``ground_frame_riders``).  Synthetic packs
in ``tmp_path``; no airport, no corpus, no DSFTool."""
from __future__ import annotations

import types

from auto_patch_v2.airport import ground_frame_riders as GR
from auto_patch_v2.airport import placement_write as PW

LAT, LON = 32.9, -97.04
Z = 172.0                  # the build's surface everywhere
ZA = Z - 1.2               # the terrain the author saw under the frame
M = 1.0 / 111_320.0        # one metre north, in degrees
LAW = GR.Law(tol_m=2.0, fit_m=0.1, under_m=0.05)


def _obj(tmp_path, name, slabs):
    """A 20 x 20 m object of horizontal slabs at the authored ``y``s."""
    vt, idx = [], []
    for y in slabs:
        b = len(vt)
        vt += [(-10, y, -10), (10, y, -10), (-10, y, 10), (10, y, 10)]
        idx += [b, b + 1, b + 2, b + 1, b + 3, b + 2]
    body = ["I", "800", "OBJ", f"POINT_COUNTS {len(vt)} 0 0 {len(idx)}"]
    body += [f"VT {x} {y} {z} 0 1 0 0 0" for x, y, z in vt]
    body += [f"IDX {i}" for i in idx]
    body.append(f"TRIS 0 {len(idx)}")
    (tmp_path / "objects").mkdir(exist_ok=True)
    (tmp_path / "objects" / name).write_text("\n".join(body) + "\n",
                                             encoding="utf-8", newline="\n")
    return "objects/" + name


def _row(path, elevation, *, north=0.0, kind="OBJECT_MSL"):
    return types.SimpleNamespace(def_path=path, lat=LAT + north * M, lon=LON,
                                 heading_deg=0.0, kind=kind, elevation=elevation)


def _seats(tmp_path, rows, counts=None, zeros=None):
    return GR.ground_rider_seats(rows, range(1, len(rows)), str(tmp_path),
                                 zeros or {}, lambda la, lo: Z, 0.5, LAW, (), counts)


def test_cars_on_an_on_ground_garage_ride_it(tmp_path):
    """Garage floor slab (-0.2 / 0.11) and a deck (3.22 / 3.53): cars on
    the floor and the deck take the garage's seat delta, a car sitting in
    the slab is never read as standing on its underside."""
    g = _obj(tmp_path, "garage.obj", (-0.2, 0.11, 3.22, 3.53))
    rows = [_row(g, None, kind="OBJECT"), _row("lib/car.obj", ZA + 0.11, north=2),
            _row("lib/car.obj", ZA + 0.11, north=4), _row("lib/car.obj", ZA + 3.53, north=6)]
    counts: dict = {}
    seats = _seats(tmp_path, rows, counts)
    assert [s.index for s in seats] == [1, 2, 3]
    assert abs(seats[0].elevation - (Z + 0.11)) < 1e-6
    assert abs(seats[2].elevation - (Z + 3.53)) < 1e-6
    assert {s.why for s in seats} == {GR.GROUND_RIDER}
    assert counts["ground_riders_moved"] == 3 and counts["ground_rider_families"] == 1


def test_a_deck_only_population_reads_the_zero_near_the_build(tmp_path):
    """Every car on the deck: the floor reading (zero 3.42 m higher) is
    past the author's-terrain allowance, so the deck is what they stand on."""
    g = _obj(tmp_path, "garage.obj", (-0.2, 0.11, 3.22, 3.53))
    rows = [_row(g, None, kind="OBJECT"), _row("lib/car.obj", ZA + 3.53, north=2)]
    (s,) = _seats(tmp_path, rows)
    assert abs(s.elevation - (Z + 3.53)) < 1e-6


def test_a_lifted_frame_written_elsewhere_moves_its_riders_by_its_seat(tmp_path):
    """An ``OBJECT_AGL +8.5`` frame written at an absolute zero: the row on
    its deck moves by (written zero - the zero its riders witness), and a
    light hung between its floors moves with it (the zero is the one the
    most rows stand at: the light alone would read its own)."""
    t = _obj(tmp_path, "terminal.obj", (0.0, 3.5, 7.0))
    lift, written = 8.5, Z + 8.5 + 0.4
    za = ZA + lift
    rows = [_row(t, lift, kind="OBJECT_AGL"), _row("lib/car.obj", za + 7.0, north=2),
            _row("lib/car.obj", za + 7.0, north=4), _row("lib/flood.obj", za + 5.5, north=3)]
    seats = _seats(tmp_path, rows, zeros={0: (written, {})})
    assert [s.index for s in seats] == [1, 2, 3]
    assert abs(seats[0].elevation - (written + 7.0)) < 1e-6
    assert abs(seats[2].elevation - (written + 5.5)) < 1e-6


def test_rows_under_a_canopy_or_off_the_frame_do_not_ride(tmp_path):
    """A canopy at 3 m over a car on the ground, and a car beside the
    garage: neither stands on a frame surface near the build's zero."""
    c = _obj(tmp_path, "canopy.obj", (3.0, 3.2))
    rows = [_row(c, None, kind="OBJECT"), _row("lib/car.obj", ZA, north=2),
            _row("lib/car.obj", ZA + 0.11, north=40)]
    assert _seats(tmp_path, rows) == ()


def test_dump_rows_seats_the_pack_s_stock_row_on_its_garage(tmp_path):
    """Through ``placement_write.dump_rows``: the stock car on the garage is
    a ground rider, not a conversion; the one on open ground converts."""
    g = _obj(tmp_path, "garage.obj", (0.0, 3.5))
    rows = [_row(g, None, kind="OBJECT"), _row("lib/car.obj", ZA + 3.5, north=5),
            _row("lib/car.obj", 190.0, north=40)]
    dump = types.SimpleNamespace(placements=rows)
    plan = types.SimpleNamespace(units=(), contacts=(), flat=None, authored_seats=())
    ss = types.SimpleNamespace(unit_seats=())
    conv, msl, _r, counts = PW.dump_rows(dump, plan, ss, (), lambda la, lo: Z,
                                         str(tmp_path), tol_m=0.02, elevated_m=0.5,
                                         ground_rider_law=LAW)
    (car,) = [m for m in msl if m.index == 1]
    assert car.why == GR.GROUND_RIDER and abs(car.elevation - (Z + 3.5)) < 1e-6
    assert 2 in {c.index for c in conv} and 1 not in {c.index for c in conv}
    assert counts["ground_riders_moved"] == 1


def test_the_law_reads_the_placement_table_and_zero_disarms(tmp_path):
    """``[placement] ground_rider_*`` is the rule's law; tol 0 disarms."""
    from auto_patch_v2.law import Law
    law = GR.law_of(Law.load().tables.structures.placement)
    assert law.tol_m > 0.0 and law.fit_m > 0.0 and law.under_m > 0.0
    g = _obj(tmp_path, "garage.obj", (0.0, 3.5))
    rows = [_row(g, None, kind="OBJECT"), _row("lib/car.obj", ZA + 3.5, north=2)]
    assert GR.ground_rider_seats(rows, (1,), str(tmp_path), {}, lambda la, lo: Z,
                                 0.5, GR.Law(), ()) == ()
