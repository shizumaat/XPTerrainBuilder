"""#1252: an ``OBJECT_MSL`` row standing on a re-seated ``OBJECT_MSL``
frame's deck moves with the frame (``frame_riders.rider_seats``) — the airport pack's
own stock rows (``placement_write.dump_rows``) and a library-only sibling
pack's (``sibling_riders``).  Synthetic packs in ``tmp_path``; no airport,
no corpus, no DSFTool."""
from __future__ import annotations

import hashlib
import struct
import types

from auto_patch_v2.airport import dsf_commands
from auto_patch_v2.airport import frame_riders as DR
from auto_patch_v2.airport import placement_write as PW
from auto_patch_v2.airport import sibling_riders as SR
from auto_patch_v2.model.placement import (
    Anchor,
    Body,
    Conversion,
    PlacementPlan,
    PlacementRef,
    Provenance,
    Split,
)

LAT, LON = 32.9, -97.04
ZA = 184.36                      # the garage's authored zero (OBJECT_MSL)
DECK = 6.5                       # its upper deck, authored y
Z = 172.0                        # the design surface everywhere
M = 1.0 / 111_320.0              # one metre north, in degrees


def _garage(tmp_path, name="garage.obj"):
    """A 20 x 20 m garage: a ground slab at y 0 and a deck at y 6.5."""
    vt = [(-10, 0, -10), (10, 0, -10), (-10, 0, 10), (10, 0, 10),
          (-10, DECK, -10), (10, DECK, -10), (-10, DECK, 10), (10, DECK, 10)]
    idx = [0, 1, 2, 1, 3, 2, 4, 5, 6, 5, 7, 6]
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


def _conv(i, row):
    return Conversion(i, row.def_path, row.lon, row.lat, 0.0, row.kind, row.elevation)


def _frames(tmp_path, rows, splits=(), msl=(), conversions=None):
    dump = types.SimpleNamespace(placements=rows)
    if conversions is None:
        conversions = (_conv(0, rows[0]),)
    return DR.frame_moves(dump, str(tmp_path), splits, msl, conversions,
                          lambda la, lo: Z)


def test_a_car_on_the_deck_moves_with_the_garage(tmp_path):
    g = _garage(tmp_path)
    rows = [_row(g, ZA), _row("lib/cars/car.obj", ZA + DECK + 0.14, north=5),
            _row("lib/cars/car.obj", ZA + 0.1, north=-5),          # its floor
            _row("lib/cars/car.obj", ZA + DECK + 2.0, north=5),    # hovering
            _row("lib/cars/car.obj", ZA + DECK, north=40)]         # outside
    (f,) = _frames(tmp_path, rows)
    assert abs(f.whole - (Z - ZA)) < 1e-9 and not f.by_component
    counts: dict = {}
    seats = DR.rider_seats(rows, range(1, 5), [f], 0.5, counts)
    assert [s.index for s in seats] == [1, 2] and counts["deck_riders_moved"] == 2
    assert abs(seats[0].elevation - (Z + DECK + 0.14)) < 1e-6   # still on the deck
    assert abs(seats[1].elevation - (Z + 0.1)) < 1e-6
    assert {s.why for s in seats} == {DR.DECK_RIDER}


def test_a_cut_frame_moves_its_rider_by_the_body_it_stands_on(tmp_path):
    """The garage cut into its slab and its deck, seated 5 m apart: the car
    on the deck takes the deck's move, the car on the floor the slab's."""
    from auto_patch_v2.airport import obj8
    g = _garage(tmp_path)
    comps = obj8.solid_components(obj8.parse_obj8(str(tmp_path / g)))
    deck = next(k for k, c in enumerate(comps) if c.min_y == DECK)
    rows = [_row(g, ZA), _row("lib/cars/car.obj", ZA + DECK + 0.1, north=5),
            _row("lib/cars/car.obj", ZA + 0.1, north=5)]

    def body(bid, comp, z):
        return Body(bid, "building", (comp,), Anchor(LON, LAT, 0.0), "",
                    f"g__{bid}.obj", surface_z=z, y_zero=0.0)
    split = Split(PlacementRef(0, g, LON, LAT, 0.0),
                  (body("b0", 1 - deck, 170.0), body("b1", deck, 175.0)))
    (f,) = _frames(tmp_path, rows, splits=(split,), conversions=())
    seats = DR.rider_seats(rows, (1, 2), [f], 0.5)
    assert abs(seats[0].elevation - (175.0 + DECK + 0.1)) < 1e-6
    assert abs(seats[1].elevation - (170.0 + 0.1)) < 1e-6


def test_a_frame_that_stays_put_moves_nobody(tmp_path):
    g = _garage(tmp_path)
    rows = [_row(g, Z + 0.01)]
    assert _frames(tmp_path, rows) == []
    # an on-ground frame has no authored zero to move from
    rows = [_row(g, None, kind="OBJECT")]
    assert _frames(tmp_path, rows, conversions=()) == []


def test_the_pack_s_own_stock_row_on_a_deck_is_seated_not_converted(tmp_path):
    """The airport pack's stock car on its own garage: 11d converted it to
    on-ground (under the deck); it now moves with the garage.  A stock row
    on the open ground still converts, and ``elevated_m`` 0 disarms."""
    g = _garage(tmp_path)
    rows = [_row(g, ZA), _row("lib/cars/car.obj", ZA + DECK + 0.14, north=5),
            _row("lib/cars/car.obj", 190.0, north=40)]
    dump = types.SimpleNamespace(placements=rows)
    plan = types.SimpleNamespace(units=(), contacts=(), flat=None, authored_seats=())
    ss = types.SimpleNamespace(unit_seats=())
    conv, msl, _r, counts = PW.dump_rows(dump, plan, ss, (), lambda la, lo: Z,
                                         str(tmp_path), tol_m=0.02, elevated_m=0.5)
    (car,) = [m for m in msl if m.index == 1]
    assert car.why == DR.DECK_RIDER and abs(car.elevation - (Z + DECK + 0.14)) < 1e-6
    assert [c.index for c in conv if c.index == 2] == [2]
    assert counts["deck_riders_moved"] == 1
    conv, msl, _r, _c = PW.dump_rows(dump, plan, ss, (), lambda la, lo: Z,
                                     str(tmp_path), tol_m=0.02, elevated_m=0.0)
    assert 1 in {c.index for c in conv} and not any(m.index == 1 for m in msl)


def test_a_sibling_plan_carries_only_its_deck_riders(tmp_path):
    g = _garage(tmp_path)
    main_rows = [_row(g, ZA)]
    (f,) = _frames(tmp_path, main_rows)
    sib = types.SimpleNamespace(placements=[
        _row("lib/cars/car.obj", ZA + DECK + 0.14, north=5),
        _row("lib/cars/car.obj", 0.0, north=5, kind="OBJECT"),
        _row("lib/cars/car.obj", 191.1, north=60)])
    main = PlacementPlan("XXXX", "main", str(tmp_path), "m.dsf", "m.dsf.anchor_bak",
                         Provenance("", "1.0", "law"))
    sp = SR.sibling_plan(main, [f], str(tmp_path / "cars"), sib,
                         str(tmp_path / "cars" / "t.dsf"), 0.5)
    assert [m.index for m in sp.msl_seats] == [0]
    assert not sp.conversions and not sp.splits and sp.icao == "XXXX"
    assert sp.dsf_backup_path.endswith(".dsf.anchor_bak") and sp.pack_name == "cars"


# ── the cheap gate: an object placed from an elevation pool ─────────────

def _atom(name: bytes, payload: bytes) -> bytes:
    return struct.pack("<4sI", name[::-1], 8 + len(payload)) + payload


def _dsf(cmds: bytes, pools=((3, -98.0, 32.0), (4, -97.05, 32.88))) -> bytes:
    """Pools ``(planes, west, south)``, each 1/32 deg square (SCAL pairs
    ``(scale, offset)`` per plane)."""
    geod = b""
    for planes, w, s in pools:
        geod += _atom(b"POOL", struct.pack("<IB", 0, planes))
        sc = [1 / 32, w, 1 / 32, s] + [360.0, 0.0] * (planes - 2)
        geod += _atom(b"SCAL", struct.pack(f"<{len(sc)}f", *sc))
    body = (b"XPLNEDSF" + struct.pack("<I", 1)
            + _atom(b"HEAD", _atom(b"PROP", b"sim/west\0-98\0"))
            + _atom(b"GEOD", geod) + _atom(b"CMDS", cmds))
    return body + hashlib.md5(body).digest()


def test_the_gate_reads_the_pools_objects_are_placed_from():
    select = lambda k: struct.pack("<BH", 1, k)  # noqa: E731
    place = struct.pack("<BH", 7, 0)
    boxes = dsf_commands.object_pool_boxes
    assert boxes(_dsf(select(0) + place), 4) == []
    (box,) = boxes(_dsf(select(1) + place), 4)
    assert abs(box[0] + 97.05) < 1e-4 and abs(box[3] - (32.88 + 1 / 32)) < 1e-4
    assert len(boxes(_dsf(select(0) + place + select(1) + place))) == 2
    assert boxes(b"not a dsf") is None


def test_a_raw_lzma_tail_is_cut_off_the_dsf():
    """A 7z raw LZMA1 stream decodes a byte past the file (Global_Forests_v2):
    the footer is found by the atoms, not by the length."""
    from O4_DSF_Header import _whole
    buf = _dsf(struct.pack("<BH", 1, 1))
    assert _whole(buf + b"\x2d") == buf and _whole(buf) == buf
    assert dsf_commands.object_pool_boxes(_whole(buf + b"\x2d")) == []


def test_the_scan_dumps_only_packs_placing_objects_inside_the_airport(tmp_path, monkeypatch):
    from shapely.geometry import box
    scenery = tmp_path / "Custom Scenery"

    def pack(name, *, obj=False):
        root = scenery / name
        (root / "Earth nav data" / "+30-100").mkdir(parents=True)
        (root / "Earth nav data" / "+30-100" / "+32-098.dsf").write_bytes(b"x")
        if obj:
            (root / "a.obj").write_text("I\n", encoding="utf-8", newline="\n")
        return str(root)
    main, cars, own = pack("a_main", obj=True), pack("b_cars"), pack("c_own", obj=True)
    lights, forests = pack("d_lights"), pack("e_forests")
    near, far = [(-97.05, 32.88, -97.02, 32.91)], [(-97.6, 32.1, -97.5, 32.2)]
    table = {("b_cars", 4): near, ("b_cars", 0): near, ("c_own", 0): near,
             ("d_lights", 4): [], ("d_lights", 0): near,
             ("e_forests", 4): far, ("e_forests", 0): far}
    import O4_Scenery_Packs as SP
    monkeypatch.setattr(SP, "pack_enabled", lambda root, *a: True)
    monkeypatch.setattr(SR, "_boxes", lambda r, la, lo, m: table[(r.rsplit("/", 1)[-1], m)])
    region = box(-97.06, 32.87, -97.0, 32.92)
    assert SR.scan(main, 32, -98, region) == ([cars], [own, lights])
    assert main and forests


def _apt(tmp_path, d=0.01):
    """An airport pack whose apt.dat boundary is a square of +-``d`` deg."""
    nav = tmp_path / "Earth nav data"
    nav.mkdir(exist_ok=True)
    ring = [(LAT - d, LON - d), (LAT - d, LON + d), (LAT + d, LON + d), (LAT + d, LON - d)]
    lines = ["I", "1100 Version", "", "1 600 1 0 XXXX Test", "130 Airport Boundary"]
    lines += [f"111 {la:.8f} {lo:.8f}" for la, lo in ring[:-1]]
    lines += [f"113 {ring[-1][0]:.8f} {ring[-1][1]:.8f}", "", "99", ""]
    (nav / "apt.dat").write_text("\n".join(lines), encoding="utf-8", newline="\n")


def test_a_free_sibling_row_inside_the_airport_is_seated_on_the_new_ground(tmp_path):
    """Owner 2026-11-04: a secondary pack's object on top of / overlapping
    no other object is seated on the new ground; on a deck it rides; over
    an object it does not stand on, or outside the airport, it stays."""
    g = _garage(tmp_path)
    _apt(tmp_path)
    main_rows = [_row(g, ZA)]
    (f,) = _frames(tmp_path, main_rows)
    region = SR.airport_region(str(tmp_path), "XXXX")
    car = _garage(tmp_path, "car.obj")           # a 20 x 20 m "car", for its footprint
    index = {"lib/cars/car.obj": str(tmp_path / car)}
    sib = types.SimpleNamespace(placements=[
        _row("lib/cars/car.obj", ZA + DECK + 0.14, north=5),     # rides
        _row("lib/cars/car.obj", ZA + 3.0, north=5),            # over, not on
        _row("lib/cars/car.obj", 191.1, north=60),              # free: ground
        _row("lib/cars/car.obj", 191.1, north=5000),            # outside
        _row("lib/cars/car.obj", 0.0, north=60, kind="OBJECT"),  # same model
        _row("lib/cars/car.obj", 191.1, north=-60)])             # over a neighbour's
    other = types.SimpleNamespace(placements=[_row("lib/cars/car.obj", 0.0, north=-65,
                                                   kind="OBJECT")])
    cars = str(tmp_path / "cars")
    over = DR.over_objects([("", types.SimpleNamespace(placements=main_rows),
                             str(tmp_path), None),
                            (cars, sib, cars, index), ("lights", other, "x", index)],
                           box=region.bounds)
    assert over(LAT + 5 * M, LON) and not over(LAT + 200 * M, LON)
    assert over(LAT + 60 * M, LON) and not over(LAT + 60 * M, LON, (cars, LAT + 60 * M, LON))
    main = PlacementPlan("XXXX", "main", str(tmp_path), "m.dsf", "m.dsf.anchor_bak",
                         Provenance("", "1.0", "law"))
    sp = SR.sibling_plan(main, [f], cars, sib, str(tmp_path / "cars" / "t.dsf"),
                         0.5, region, over, key=cars)
    assert [m.index for m in sp.msl_seats] == [0]
    assert [c.index for c in sp.conversions] == [2]
    assert sp.provenance.counts["free_rows_on_ground"] == 1
    assert SR.airport_region(str(tmp_path), "YYYY") is None
