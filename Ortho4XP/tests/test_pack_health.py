"""#1978 THE PACK HEALTH CHECK: known vendor defects repaired in our
output of an airport pack, the vendor original kept, every repair
reported.

* #1954 — a malformed ``LIGHT_*`` record (wrong arity per the OBJ8
  specification) is completed or dropped in OUR copy of the object
  (``<stem>.o4fix.obj``, which the written DSF names), in an "Optimise
  pack" copy and in a split body; the vendor ``.obj`` is never written.
  The two hand repairs the owner confirmed in the sim (LFKC, 2026-11-07)
  are reproduced.
* #1975 — exact duplicate line / draped-polygon placements and sliver
  lines stacked in a pile (CYYC, 2026-11-09) leave the written DSF; a
  dense LEGITIMATE spot (the census's densest: 90 starts of one line in
  ~10 m) and short lines away from a pile stay.

Headless: synthetic objects and dumps, and the "Optimise pack" twins'
byte-copy DSFTool pack (``pack_optimise_fixture``).
"""
from __future__ import annotations

import os
import sys
import types

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "src"))

import pack_optimise_fixture as FX  # noqa: E402
from auto_patch_v2.airport import pack_health as PH  # noqa: E402
from auto_patch_v2.airport.pack_health import light_records as LR  # noqa: E402
from auto_patch_v2.airport.pack_health import objects as OB  # noqa: E402
from auto_patch_v2.airport.pack_health import stacked_polygons as SP  # noqa: E402

DREF = "sim/graphics/animation/lights/normal"


# ── #1954: the arity per LIGHT_* keyword ────────────────────────────────

@pytest.mark.parametrize("line", [
    "LIGHT_NAMED airplane_beacon 0 10 0",
    "LIGHT_NAMED\tamb_street_light2\t0.000000\t9.536036\t0.898227",
    "LIGHT_PARAM spot_params_sp 1.3 7.2 -18.9",
    "LIGHT_PARAM spot_params_sp 1.3 7.2 -18.9 1 1 1 0.5 30 0 -1 0 0.5",
    "LIGHT_CUSTOM 0 1 0 1 1 1 1 0.5 0 0 1 1 " + DREF,
    "LIGHT_SPILL_CUSTOM 0 1 0 1 1 1 1 20 0 -1 0 0.5 " + DREF,
    "LIGHT_SPILL_CUSTOM 0 1 0 1 1 1 1 20 0 -1 0 0.5 " + DREF + "  # a comment",
    "LIGHTS 0 4",
    "VLIGHT 0 1 0 1 1 1",                 # a table row, not a record
    # extra tokens X-Plane does not read, a dataref left out, an odd
    # number: shipping packs carry thousands, lit as their authors saw
    "LIGHT_NAMED full_custom_halo_night 0 10 0 1 0 0",
    "LIGHT_NAMED airplane_beacon 0 ten 0",
    "LIGHT_SPILL_CUSTOM 0 1 0 1 1 1 1 75 -0.3 -0.95 -0 0.5",
    "LIGHT_CUSTOM 0 1 0 1 1 1 1 3 0.87 0.01 0.99 0.1",
    "LIGHT_PARAM full_custom_halo_night 2,15 2,23 2,66 1 0,85 0,3 1 100",
])
def test_a_well_formed_record_is_left_alone(line):
    lines = ["I", "800", "OBJ", line]
    assert LR.check_lines(lines) == []
    assert LR.repair_lines(lines) == (lines, [])


@pytest.mark.parametrize("line, action", [
    ("LIGHT_NAMED airplane_beacon 0 10", "dropped"),
    ("LIGHT_NAMED Rmp10Deg1_var11.90096617 6.29 -0.0043", "dropped"),
    ("LIGHT_PARAM spot_params_sp 1.3 7.2", "dropped"),
    ("LIGHT_CUSTOM 0 1 0 1 1 1 1 0.5 0 0 " + DREF, "dropped"),
    ("LIGHT_SPILL_CUSTOM 0 1 0 1 1 1 1 " + DREF, "completed"),        # 7
    ("LIGHT_SPILL_CUSTOM 0 1 0 1 1 1 1 20 " + DREF, "completed"),     # 8
    ("LIGHT_SPILL_CUSTOM 0 1 0 1 1 1 1 20 0 -1 " + DREF, "dropped"),  # 10
    ("LIGHT_SPILL_CUSTOM 0 1 0 1 1 1 0.9 20 0 -1 0.34", "dropped"),   # 11
    ("LIGHT_SPILL_CUSTOM 16.9 6.5 10.3", "dropped"),
    ("LIGHTS 0", "dropped"),
])
def test_a_malformed_record_is_completed_or_dropped(line, action):
    lines = ["I", "800", "OBJ", line, "ATTR_LOD 0 100"]
    found = LR.check_lines(lines)
    assert [(f.line, f.action) for f in found] == [(3, action)]
    out, _ = LR.repair_lines(lines)
    if action == "dropped":
        assert out == ["I", "800", "OBJ", "ATTR_LOD 0 100"]
    else:
        assert LR.check_lines(out) == [] and len(out) == 5


# The owner's two hand repairs (LFKC, confirmed in the sim 2026-11-07):
# the vendor rows, and what the repaired objects carry.
FEUERWEHR = [
    "LIGHT_SPILL_CUSTOM -6.8574 3.1920 4.7750 0.996078 1.0 0.72549 0.3 20.0 "
    "-0.8589 -0.512121 0.00472213 0.5 " + DREF,
    "LIGHT_SPILL_CUSTOM 32.3389 6.1674 24.4508 1.0 1.0 0.843137 0.5 40.0 "
    "0.0255766 -0.408907 0.912217 0.819152 " + DREF,
    "LIGHT_SPILL_CUSTOM 41.8403 3.3314 23.6910 0.996078 1.0 0.72549 0.2  " + DREF,
]
FEUERWEHR_FIXED = ("LIGHT_SPILL_CUSTOM 41.8403 3.3314 23.6910 0.996078 1.0 "
                   "0.72549 0.2 20.0 0.0 -1.0 0.0 0.5 " + DREF)
LAMPE = "LIGHT_SPILL_CUSTOM 0.1947 4.0637 0.0086 1.0 1.0 1.0 0.5  " + DREF
LAMPE_FIXED = ("LIGHT_SPILL_CUSTOM 0.1947 4.0637 0.0086 1.0 1.0 1.0 0.5 "
               "15.0 0.0 -1.0 0.0 0.5 " + DREF)


def _numbers(line):
    return [float(t) for t in line.split()[1:-1]]


def test_the_owners_two_confirmed_repairs_are_what_it_writes():
    out, found = LR.repair_lines(FEUERWEHR + ["ATTR_LOD 0 900\r"])
    assert [f.action for f in found] == ["completed"]
    # the size of the same-colour sibling (20), not of the others (40)
    assert _numbers(out[2]) == _numbers(FEUERWEHR_FIXED)
    assert out[:2] == FEUERWEHR[:2] and out[3] == "ATTR_LOD 0 900\r"
    out, _ = LR.repair_lines([LAMPE + "\r"])
    assert _numbers(out[0]) == _numbers(LAMPE_FIXED) and out[0].endswith("\r")


# ── #1954: our copy of the object, never the vendor's ───────────────────

OBJ = ("I\r\n800\r\nOBJ\r\n\r\nTEXTURE t.png\r\nPOINT_COUNTS 3 0 0 3\r\n"
       "VT 0 0 0 0 1 0 0 0\r\nVT 1 0 0 0 1 0 1 0\r\nVT 0 0 1 0 1 0 0 1\r\n"
       "IDX10 0 1 2\r\nTRIS 0 3\r\n" + LAMPE + "\r\n")


@pytest.fixture
def lit_pack(tmp_path):
    pack = tmp_path / "Pack"
    (pack / "objects").mkdir(parents=True)
    (pack / "objects" / "lampe.obj").write_bytes(OBJ.encode("latin-1"))
    (pack / "objects" / "good.obj").write_bytes(
        OBJ.replace(LAMPE, LAMPE_FIXED).encode("latin-1"))
    return pack


def test_a_placed_object_gets_a_repaired_copy_the_dsf_names(lit_pack):
    vendor = (lit_pack / "objects" / "lampe.obj").read_bytes()
    text = ("OBJECT_DEF objects/lampe.obj\nOBJECT_DEF objects/good.obj\n"
            "OBJECT_DEF lib/airport/lights/x.obj\nOBJECT 0 1 2 0\n")
    out, broken, files = PH.repair_objects(text, str(lit_pack))
    assert list(broken) == ["objects/lampe.obj"]
    assert files == ["objects/lampe.o4fix.obj"]
    assert out.splitlines()[:3] == ["OBJECT_DEF objects/lampe.o4fix.obj",
                                    "OBJECT_DEF objects/good.obj",
                                    "OBJECT_DEF lib/airport/lights/x.obj"]
    assert (lit_pack / "objects" / "lampe.obj").read_bytes() == vendor
    copy = (lit_pack / "objects" / "lampe.o4fix.obj").read_bytes().decode("latin-1")
    rows = copy.split("\r\n")
    assert rows[3].startswith("# o4fix ")
    assert LR.check_lines(rows) == []
    assert _numbers(rows[-2]) == _numbers(LAMPE_FIXED)
    # a second write leaves a current copy alone, and only our copies go
    mtime = os.stat(lit_pack / "objects" / "lampe.o4fix.obj").st_mtime_ns
    assert OB.write_copies(str(lit_pack), ["objects/lampe.obj"]) == files
    assert os.stat(lit_pack / "objects" / "lampe.o4fix.obj").st_mtime_ns == mtime
    assert OB.remove(str(lit_pack), files + ["objects/lampe.obj"]) == files
    assert (lit_pack / "objects" / "lampe.obj").is_file()


def test_the_optimise_copy_and_the_lights_copy_carry_the_repair(lit_pack):
    from auto_patch_v2.airport.pack_optimise import objcopy as OC
    from auto_patch_v2.airport.pack_optimise import swap as SW
    phys = str(lit_pack / "objects" / "lampe.obj")
    assert LR.check_lines(OC.copy_text(phys, {"lod": 400}).split("\r\n")) == []
    lights = SW.lights_text(phys)
    assert lights is not None and LR.check_lines(lights.split("\n")) == []


def test_a_split_body_is_written_from_the_repaired_text(lit_pack):
    from auto_patch_v2.airport import obj8_split as S
    src = S._read(str(lit_pack / "objects" / "lampe.obj"))
    spill = [c for c in src.commands if c.startswith("LIGHT_SPILL_CUSTOM")]
    assert [_numbers(c) for c in spill] == [_numbers(LAMPE_FIXED)]


# ── #1975: duplicate and stacked draped placements ──────────────────────

def _block(d, pts, param=0, depth=2):
    rows = "".join("POLYGON_POINT " + " ".join(f"{v:.9f}" for v in p) + "\n"
                   for p in pts)
    return (f"BEGIN_POLYGON {d} {param} {depth}\nBEGIN_WINDING\n{rows}"
            "END_WINDING\nEND_POLYGON\n")


DEFS = ("POLYGON_DEF lines/hold.lin\nPOLYGON_DEF ground/asphalt.pol\n"
        "POLYGON_DEF trees/pine.for\nPOLYGON_DEF lines/border.lin\n")
LAT, LON = 51.12870, -114.00000
REAL = _block(0, [(LON - 0.001, LAT - 0.001), (LON - 0.0012, LAT - 0.001)])


def _sliver(k):
    """A 0.2-0.3 m two-point line in the pile's ~10 m spot (21 distinct
    shapes, every other one a repeat)."""
    lon = LON + 0.0000001 * (k % 7)
    return _block(0, [(lon, LAT), (lon + 0.000003 + 0.0000001 * (k % 3), LAT)])


def test_the_pile_goes_and_the_real_lines_stay():
    pile = "".join(_sliver(k) for k in range(SP.STACK_MIN + 200))
    text = DEFS + REAL + pile + REAL
    out, rep = SP.repair_text(text)
    assert rep.dropped == SP.STACK_MIN + 200 + 1      # + the repeated REAL
    assert rep.stacked == 21 and rep.duplicates == SP.STACK_MIN + 180
    assert out == DEFS + REAL
    assert rep.site[2] == SP.STACK_MIN + 200 and abs(rep.site[0] - LAT) < 1e-3
    assert rep.by_def == {"lines/hold.lin": SP.STACK_MIN + 201}


def test_a_dense_legitimate_spot_and_a_short_dash_stay():
    # the census's densest legitimate spot: 90 starts of one line in ~10 m
    dense = "".join(_block(3, [(LON + 0.0000001 * k, LAT),
                               (LON + 0.0000001 * k + 0.000004, LAT)])
                    for k in range(90))
    dash = _block(0, [(LON + 0.01, LAT), (LON + 0.010002, LAT)])   # 0.14 m
    text = DEFS + dense + dash
    out, rep = SP.repair_text(text)
    assert out == text and rep.dropped == 0


def test_only_draped_repeats_go():
    pol = _block(1, [(LON, LAT), (LON + 0.001, LAT), (LON, LAT + 0.001)])
    forest = _block(2, [(LON, LAT), (LON + 0.001, LAT), (LON, LAT + 0.001)], 255)
    text = DEFS + pol + pol + forest + forest
    out, rep = SP.repair_text(text)
    assert rep.duplicates == 1 and out == DEFS + pol + forest + forest
    # another parameter is another placement
    other = pol.replace("BEGIN_POLYGON 1 0 2", "BEGIN_POLYGON 1 1 2")
    assert SP.scan((DEFS + pol + other).splitlines()).dropped == 0


def test_a_bezier_line_with_long_handles_is_not_a_sliver():
    pile = "".join(_sliver(k) for k in range(SP.STACK_MIN))
    curve = _block(0, [(LON, LAT, LON + 0.0005, LAT),
                       (LON + 0.000001, LAT, LON, LAT + 0.0005)], depth=4)
    _out, rep = SP.repair_text(DEFS + curve + pile)
    assert 0 not in rep.drop and 1 in rep.drop


# ── the record, the log and the write ───────────────────────────────────

def test_the_record_reads_back_only_for_its_pristine_file_and_rules():
    rep = SP.scan((DEFS + REAL + REAL).splitlines())
    found = LR.check_lines([LAMPE])
    row = PH.record("abc", PH.Health(rep, {"objects/lampe.obj": tuple(found)}),
                    ["objects/lampe.o4fix.obj"], "t")
    assert PH.count(row) == 2
    assert PH.recorded({PH.RECORD_KEY: row}, "abc") == row
    assert PH.recorded({PH.RECORD_KEY: row}, "other") == {}
    assert PH.recorded({PH.RECORD_KEY: {**row, "version": 0}}, "abc") == {}
    assert PH.generated_of({PH.RECORD_KEY: row}) == ["objects/lampe.o4fix.obj"]
    assert PH.record("abc", PH.Health(SP.scan([]), {}), [], "t") is None
    lines = PH.log_lines("Pack", "+51-115.dsf", row)
    assert len(lines) == 2 and "1 exact repeats" in lines[0]
    assert "objects/lampe.o4fix.obj" in lines[1]


HEALTH_DUMP = FX.DUMP.replace(
    "OBJECT_DEF objects/van.obj\n",
    "OBJECT_DEF objects/van.obj\nOBJECT_DEF objects/lampe.obj\n").replace(
    "POLYGON_DEF lib/g8/terrain/wet_hot_flat.for\n",
    "POLYGON_DEF lib/g8/terrain/wet_hot_flat.for\nPOLYGON_DEF lines/hold.lin\n"
) + "OBJECT 2 51.700000000 25.700000000 0.000000\n" + "".join(
    _block(1, [(51.5, 25.5), (51.5000031, 25.5)]) for _ in range(3))


@pytest.fixture
def rp(tmp_path, monkeypatch):
    rp = FX.make_pack(tmp_path, monkeypatch)
    rp.dsf.write_bytes(HEALTH_DUMP.encode("utf-8"))
    (rp.pack / "objects" / "lampe.obj").write_bytes(OBJ.encode("latin-1"))
    return rp


def _recipe():
    from auto_patch_v2.airport import pack_optimise as PO
    return PO.default_recipe()


def test_every_write_repairs_and_restore_puts_the_vendor_back(rp):
    from auto_patch import object_rebake as OR
    vendor = rp.dsf.read_bytes()
    FX.write(rp)
    live = rp.dsf.read_text(encoding="utf-8")
    assert live.count("BEGIN_POLYGON 1 ") == 1, "two exact repeats dropped"
    assert "OBJECT_DEF objects/lampe.o4fix.obj" in live
    row = FX.entry(rp)[PH.RECORD_KEY]
    assert row["polygons"]["duplicates"] == 2
    assert row["lights"] == {"objects/lampe.obj": {"completed": 1, "dropped": 0}}
    assert (rp.pack / "objects" / "lampe.o4fix.obj").is_file()
    # a later write with a choice keeps the repair (it is not a choice)
    FX.write(rp, optimise=_recipe())
    assert rp.dsf.read_text(encoding="utf-8").count("BEGIN_POLYGON 1 ") == 1
    assert FX.entry(rp)[PH.RECORD_KEY]["polygons"]["dropped"] == 2
    # the pack row counts it, and Restore originals undoes all of it
    packs = OR.modified_packs(str(rp.pack.parent))
    assert packs and packs[0]["repaired"] == 3
    OR.restore_detail(str(rp.pack))
    assert rp.dsf.read_bytes() == vendor
    assert not (rp.pack / "objects" / "lampe.o4fix.obj").exists()
    assert (rp.pack / "objects" / "lampe.obj").read_bytes() == OBJ.encode("latin-1")


def test_the_stage_writes_once_then_finds_it_current(rp, monkeypatch):
    from auto_patch import health_stage as HS
    from auto_patch import object_stage as OS
    from auto_patch_v2.airport.dsf_write import pristine_dsf_path
    dump = rp.pack.parent / "dump.txt"
    dump.write_text(HEALTH_DUMP, encoding="utf-8", newline="\n")

    def pack_dump(pack_root, lat, lon, *, read_only):
        return OS._PackDump(rp.pack.name, str(rp.dsf),
                            pristine_dsf_path(str(rp.dsf)), str(dump), "")
    monkeypatch.setattr(OS, "pack_dump", pack_dump)
    plan_ = types.SimpleNamespace(pack_root=str(rp.pack))
    tile = types.SimpleNamespace(lat=25, lon=51)
    assert HS.health_stage(plan_, tile, writes=False) == "found"
    assert not (rp.pack / "objects" / "lampe.o4fix.obj").exists()
    assert HS.health_stage(plan_, tile, writes=True) == "repaired"
    assert HS.health_stage(plan_, tile, writes=True) == "current"
    assert rp.dsf.read_text(encoding="utf-8").count("BEGIN_POLYGON 1 ") == 1
