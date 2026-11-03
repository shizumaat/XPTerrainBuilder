"""#1707 D2: "Optimise pack" swaps heavy vehicles and ground equipment for
X-Plane's library equivalents — witnessed by the file name and the
footprint, never pointed at a name a library may draw as a blank, turned
by the head lights (else the profile, else the smallest turn), moved onto
the pack object's footprint centre, its lights kept in a lights-only copy
— and every write re-applies the recorded table from the pristine dump.
Headless: synthetic objects and a byte-copy DSFTool (``pack_optimise_fixture``).
"""
from __future__ import annotations

import math
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "src"))

import pack_optimise_fixture as FX  # noqa: E402
from auto_patch import agp_reader as AGP  # noqa: E402
from auto_patch_v2.airport import pack_optimise as PO  # noqa: E402
from auto_patch_v2.airport.pack_optimise import swap as SW  # noqa: E402


def obj(x, y, z, tris=12, lights=(), anim=False) -> str:
    """A box OBJ8 spanning ``x``/``y``/``z`` (min, max) drawing ``tris``
    triangles (its 12 faces, repeated)."""
    vt = [f"VT {a} {b} {c} 0 1 0 0 0" for a in x for b in y for c in z]
    faces = [0, 1, 3, 0, 3, 2, 4, 5, 7, 4, 7, 6, 0, 1, 5, 0, 5, 4,
             2, 3, 7, 2, 7, 6, 0, 2, 6, 0, 6, 4, 1, 3, 7, 1, 7, 5]
    idx = (faces * (tris // 12 + 1))[:tris * 3]
    rows = ["I", "800", "OBJ", "", "TEXTURE car.png",
            f"POINT_COUNTS {len(vt)} 0 0 {len(idx)}", *vt,
            *(f"IDX {i}" for i in idx)]
    if anim:
        rows += ["ANIM_begin"]
    rows += [f"TRIS 0 {len(idx)}"]
    if anim:
        rows += ["ANIM_end"]
    rows += list(lights)
    return "\n".join(rows) + "\n"


CART = obj((-0.3, 3.2), (0, 1.8), (-1.5, 0), tris=6000)       # x-long
LIB_CART = obj((-0.7, 0.7), (0, 1.8), (-3.8, 0.1))             # z-long
CAR = obj((0, 2.1), (0, 1.5), (-4.6, 0.1), tris=6000, lights=(
    "LIGHT_NAMED headlight 0.3 0.7 -0.2", "LIGHT_NAMED taillight 0.4 0.9 -4.4"))
LIB_CAR = obj((-0.9, 0.9), (0, 1.4), (-2.3, 2.2))
CART_LIB = "lib/airport/Ramp_Equipment/baggage/cart_8ft_1.obj"
CAR_LIB = "lib/cars/car_static_invar.obj"


@pytest.fixture
def lib(tmp_path):
    """A library: ``{virtual: [file, ...]}``, an adder and its ``exports_of``."""
    files: dict[str, list[str]] = {}

    def add(virtual, text, name=None):
        p = tmp_path / "lib" / (name or os.path.basename(virtual))
        p.parent.mkdir(exist_ok=True)
        p.write_text(text, encoding="utf-8", newline="")
        files.setdefault(virtual.lower(), []).append(str(p))
    return files, add, (lambda v: files.get(v.lower(), ()))


def put(root, rel, text):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8", newline="")


# ── the match ───────────────────────────────────────────────────────────


def _files_at(rows, lat, lon):
    """The files of ``weighted_files_at`` (test-only view)."""
    return [f for f, _r, _l in AGP.weighted_files_at(rows, lat, lon)]

def test_name_words_split_the_stem():
    assert SW.name_words("Ground Equipment/BaggageCar1.obj") == {"baggage", "car"}
    assert SW.name_words("x/T1BusRed.obj") == {"t", "bus", "red"}
    assert SW.name_words("x/GPU.obj") == {"gpu"}
    assert SW._class_of("a/BaggageCar1.obj")[0] == "baggage cart", \
        "the specific class is read before the general car"
    assert SW._class_of("a/Cargo_container.obj") is None, "cargo is not car"


def test_a_cart_is_swapped_turned_onto_the_library_axis(tmp_path, lib):
    _files, add, exports_of = lib
    add(CART_LIB, LIB_CART)
    put(tmp_path, "p/BaggageCar1.obj", CART)
    got = SW.plan_swaps(str(tmp_path / "p"), ["BaggageCar1.obj"], {0: 50}, exports_of)
    sw = got["BaggageCar1.obj"]
    assert sw["to"] == CART_LIB and sw["turn"] in (90, 270)
    assert sw["tris"] == [6000, 12] and sw["lights"] == ""


@pytest.mark.parametrize("case", ["blank", "missing", "empty", "animated",
                                  "misfit", "few", "variant"])
def test_no_swap_without_every_witness(tmp_path, lib, case):
    files, add, exports_of = lib
    add(CART_LIB, LIB_CART)
    if case == "blank":
        add(CART_LIB, obj((0, 1), (0, 1), (0, 1)), "Blank.obj")
    elif case == "missing":
        files[CART_LIB.lower()].append(str(tmp_path / "gone.obj"))
    elif case == "empty":
        add(CART_LIB, "I\n800\nOBJ\n\nPOINT_COUNTS 0 0 0 0\n", "nothing.obj")
    elif case == "variant":
        add(CART_LIB, obj((-1.5, 1.5), (0, 3), (-8, 8)), "bus.obj")
    text = {"animated": obj((-0.3, 3.2), (0, 1.8), (-1.5, 0), tris=6000, anim=True),
            "misfit": obj((-0.3, 9.2), (0, 1.8), (-1.5, 0), tris=6000)}.get(case, CART)
    put(tmp_path, "p/BaggageCar1.obj", text)
    n = 10 if case == "few" else 50
    assert SW.plan_swaps(str(tmp_path / "p"), ["BaggageCar1.obj"], {0: n},
                         exports_of) == {}


def test_the_head_lights_decide_the_turn_and_the_lights_are_kept(tmp_path, lib):
    _files, add, exports_of = lib
    add(CAR_LIB, LIB_CAR)
    put(tmp_path, "p/Car1Blue.obj", CAR)
    sw = SW.plan_swaps(str(tmp_path / "p"), ["Car1Blue.obj"], {0: 50},
                       exports_of)["Car1Blue.obj"]
    assert (sw["turn"], sw["why"]) == (180, "lights"), "its front is +z; X-Plane's is -z"
    assert sw["lights"] == "Car1Blue" + SW.LIGHTS_SUFFIX
    text = SW.lights_text(str(tmp_path / "p" / "Car1Blue.obj"))
    assert "POINT_COUNTS 0 0 0 0" in text and "LIGHT_NAMED headlight 0.3 0.7 -0.2" in text
    assert "TEXTURE car.png" in text and "VT" not in text


@pytest.mark.parametrize("blank_ratio, swapped", [
    (1.0, True), (5.0, True), (6.0, False), (200.0, False), (None, False)])
def test_a_minority_blank_ratio_variant_is_allowed(tmp_path, lib, blank_ratio, swapped):
    """Owner 2026-11-03: "Allow parked road cars to be swapped" — a pool
    whose blank is at most 5 % of its ratio is a target; a blank-majority
    or blank-only export is not (``None``: the blank alone)."""
    _files, add, _exports = lib
    add(CAR_LIB, LIB_CAR)
    real, blank = str(tmp_path / "lib" / "car_static_invar.obj"), str(tmp_path / "Blank.obj")
    (tmp_path / "Blank.obj").write_text("I\n800\nOBJ\n", encoding="utf-8", newline="")
    rows = ([] if blank_ratio is None else [(real, 95.0, "/aep")]) + [
        (blank, blank_ratio or 1.0, "/aep")]
    put(tmp_path, "p/Car1Blue.obj", CAR)
    got = SW.plan_swaps(str(tmp_path / "p"), ["Car1Blue.obj"], {0: 50},
                        lambda v: rows if v == CAR_LIB else [])
    assert bool(got) is swapped


def test_files_at_reads_regions_and_backups():
    rows = [("EXPORT", "/l/a.obj", None, 1.0, "/l"),
            ("EXPORT_BACKUP", "/x/empty.obj", None, 1.0, "/x"),
            ("EXPORT", "/h/hawaii.obj", (-160, 21, -160, 21), 1.0, "/h"),
            ("EXPORT_RATIO", "/e/euro.obj", "bitmap", 7.0, "/e")]
    assert AGP.weighted_files_at(rows, 29, -96) == [("/l/a.obj", 1.0, "/l"),
                                                    ("/e/euro.obj", 7.0, "/e")]
    assert _files_at(rows, 29, -96) == ["/l/a.obj", "/e/euro.obj"]
    assert _files_at(rows, 21, -160) == ["/l/a.obj", "/h/hawaii.obj", "/e/euro.obj"]
    assert _files_at(rows[1:2], 29, -96) == ["/x/empty.obj"], \
        "a backup alone is what X-Plane draws"


def test_export_files_reads_every_directive(tmp_path):
    root = tmp_path / "XP"
    lib_dir = root / "Resources" / "default scenery" / "lib1"
    lib_dir.mkdir(parents=True)
    (lib_dir / "library.txt").write_text(
        "A\n800\nLIBRARY\n"
        "REGION_DEFINE hi\nREGION_RECT -160 21 -160 21\nREGION hi\n"
        "EXPORT_BACKUP lib/v.obj objects/empty.obj\n"
        "REGION_DEFINE all\nREGION_ALL\nREGION all\n"
        "EXPORT_RATIO 3 lib/v.obj objects/a.obj\n"
        "EXPORT_EXCLUDE lib/v.obj objects/Blank.obj\n", encoding="utf-8", newline="")
    AGP._EXPORT_FILES_CACHE.clear()
    rows = AGP.export_files(str(root))["lib/v.obj"]
    assert [(r[0], os.path.basename(r[1]), r[2], r[3]) for r in rows] == [
        ("EXPORT_BACKUP", "empty.obj", (-160, 21, -160, 21), 1.0),
        ("EXPORT_RATIO", "a.obj", None, 3.0), ("EXPORT_EXCLUDE", "Blank.obj", None, 1.0)]
    assert {r[4] for r in rows} == {str(lib_dir)}


# ── the row ─────────────────────────────────────────────────────────────

def _centre(lon, lat, c, heading, lat0=25.5):
    """Metres east/north of the tile corner (one local scale, ``lat0``)."""
    e, n = SW._offset(c, heading)
    return ((lon - 51) * SW._M_DEG * math.cos(math.radians(lat0)) + e,
            (lat - 25) * SW._M_DEG + n)


@pytest.mark.parametrize("heading", [0.0, 37.5, 90.0, 211.0, 359.0])
@pytest.mark.parametrize("kind", ["OBJECT", "OBJECT_AGL"])
def test_the_library_object_stands_on_the_footprint_centre(heading, kind):
    sw = {"to": CART_LIB, "turn": 90, "from_c": [1.45, -0.75], "to_c": [0.0, -1.85],
          "dy": 0.25, "lights": ""}
    elev = " 2.000000" if kind == "OBJECT_AGL" else ""
    text = ("OBJECT_DEF a.obj\nOBJECT_DEF Cart.obj\n"
            f"{kind} 1 51.500000000 25.500000000{elev} {heading:.6f}\n"
            "OBJECT 0 51.6 25.6 0\n")
    out, counts = SW.apply(text, {"Cart.obj": sw})
    assert counts == {"Cart.obj": 1}
    lines = out.splitlines()
    assert lines[:2] == ["OBJECT_DEF a.obj", f"OBJECT_DEF {CART_LIB}"]
    toks = lines[2].split()
    assert toks[:2] == [kind, "1"] and lines[3] == "OBJECT 0 51.6 25.6 0"
    new_h = float(toks[-1])
    assert new_h == pytest.approx((heading + 90) % 360)
    if kind == "OBJECT_AGL":
        assert float(toks[4]) == pytest.approx(2.25), "the same base height"
    want = _centre(51.5, 25.5, sw["from_c"], heading)
    got = _centre(float(toks[2]), float(toks[3]), sw["to_c"], new_h)
    assert math.dist(want, got) < 0.01


def test_a_lights_copy_rides_on_the_same_row():
    sw = {"to": CAR_LIB, "turn": 180, "from_c": [1.0, -2.0], "to_c": [0, 0],
          "dy": 0.0, "lights": "Car1" + SW.LIGHTS_SUFFIX}
    text = ("OBJECT_DEF Car1.obj\nOBJECT_DEF Car2.obj\n"
            "OBJECT_AGL 0 51.5 25.5 1.0 10.0\nOBJECT 1 51.6 25.6 20.0\n")
    out, _ = SW.apply(text, {"Car1.obj": sw, "Car2.obj": dict(sw)})
    lines = out.splitlines()
    assert lines[:3] == [f"OBJECT_DEF {CAR_LIB}", f"OBJECT_DEF {CAR_LIB}",
                         f"OBJECT_DEF Car1{SW.LIGHTS_SUFFIX}"], "one copy, one definition"
    assert lines[4] == "OBJECT_AGL 2 51.5 25.5 1.0 10.0", "the vendor row, verbatim"
    assert lines[6] == "OBJECT 2 51.6 25.6 20.0"


# ── the recorded decision, written ──────────────────────────────────────

def _swap_pack(tmp_path, monkeypatch):
    rp = FX.make_pack(tmp_path, monkeypatch)
    (rp.pack / "objects" / "car.obj").write_text(CAR, encoding="utf-8", newline="")
    monkeypatch.setattr(SW, "MIN_SAVING", 1)
    lib_file = tmp_path / "libcar.obj"
    lib_file.write_text(LIB_CAR, encoding="utf-8", newline="")
    recipe = PO.build_recipe(str(rp.pack), FX.DUMP.splitlines(keepends=True),
                             lambda v: [str(lib_file)] if v == CAR_LIB else [])
    return rp, recipe


def test_write_swaps_and_every_later_write_reapplies(tmp_path, monkeypatch):
    rp, recipe = _swap_pack(tmp_path, monkeypatch)
    assert set(recipe["swap"]) == {"objects/car.obj"}
    FX.write(rp, optimise=recipe)
    text = rp.dsf.read_text(encoding="utf-8")
    copy = rp.pack / "objects" / ("car" + SW.LIGHTS_SUFFIX)
    assert f"OBJECT_DEF {CAR_LIB}" in text and copy.is_file()
    row = FX.entry(rp)[PO.RECORD_KEY]
    assert row["swaps"] == [{"path": "objects/car.obj", "to": CAR_LIB, "rows": 2}], \
        "the third car row is a duplicate D1 drops"
    assert row["generated"] == ["objects/car" + SW.LIGHTS_SUFFIX]
    first = rp.dsf.read_bytes()
    FX.write(rp)                                   # a later write: re-applied
    assert rp.dsf.read_bytes() == first, "the same recipe, the same bytes"
    FX.write(rp, optimise={})                      # Undo's write
    assert f"OBJECT_DEF {CAR_LIB}" not in rp.dsf.read_text(encoding="utf-8")


def test_undo_restores_the_bytes_and_removes_the_copy(tmp_path, monkeypatch):
    from auto_patch import optimise_stage as OS
    rp, recipe = _swap_pack(tmp_path, monkeypatch)
    original = rp.dsf.read_bytes()
    FX.write(rp, optimise=recipe)
    copy = rp.pack / "objects" / ("car" + SW.LIGHTS_SUFFIX)
    assert copy.is_file()
    assert OS.undo(str(rp.pack)) == ["Earth nav data/+20+050/+25+051.dsf"]
    assert rp.dsf.read_bytes() == original and not copy.exists()
    assert (rp.pack / "objects" / "car.obj").read_text(encoding="utf-8") == CAR, \
        "the vendor file is never written"


def test_revert_to_default_removes_the_copy(tmp_path, monkeypatch):
    from auto_patch import object_rebake as OR
    rp, recipe = _swap_pack(tmp_path, monkeypatch)
    original = rp.dsf.read_bytes()
    FX.write(rp, optimise=recipe)
    OR.restore_detail(str(rp.pack))
    assert rp.dsf.read_bytes() == original
    assert not (rp.pack / "objects" / ("car" + SW.LIGHTS_SUFFIX)).exists()


def test_remove_generated_never_touches_a_vendor_file(tmp_path):
    put(tmp_path, "p/a.obj", "x")
    put(tmp_path, "p/a.o4opt-lights.obj", "x")
    assert PO.remove_generated(str(tmp_path / "p"), [
        "a.obj", "a.o4opt-lights.obj", "../p/a.obj"]) == ["a.o4opt-lights.obj"]
    assert (tmp_path / "p" / "a.obj").is_file()


def test_a_light_pack_is_weighed_without_reading_its_objects(tmp_path, monkeypatch):
    """The check reads every object file (the whole recipe) only for a pack
    heavy enough to be offered, or when the user said Optimise."""
    from auto_patch import object_stage as OST
    from auto_patch import optimise_stage as OS
    rp = FX.make_pack(tmp_path, monkeypatch)
    dump = tmp_path / "dump.txt"
    dump.write_text(FX.DUMP, encoding="utf-8", newline="")
    monkeypatch.setattr(OST, "pack_dump", lambda *a, **k: OST._PackDump(
        rp.pack.name, str(rp.dsf), str(rp.dsf), str(dump), str(tmp_path)))
    built = []
    real = PO.build_recipe
    monkeypatch.setattr(PO, "build_recipe", lambda *a: built.append(1) or real(*a))
    pw = OS.check(str(rp.pack), 25, 51, read_only=False)
    assert built == [] and pw.wanted == PO.default_recipe()
    OS.check(str(rp.pack), 25, 51, read_only=False, full=True)
    assert built == [1]
