"""#1707 D1: "Optimise pack" drops duplicate placements INSIDE
``dsf_write.write_pack``, from the pristine dump, on every write.

The recipe is a recorded decision (``pack_optimise``): a write with
``optimise=`` records it, a later write with none (a placement write, a
3D-trees write, an airport restore) re-applies it, ``{}`` writes without
it.  The tolerances are D1's (0.2 m, 1°, 1 mm of height); the exact
§15 (4) default of ``duplicate_rows`` is unchanged.  Headless: a
byte-copy DSFTool on a synthetic pack (``pack_optimise_fixture``).
"""
from __future__ import annotations

import math
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "src"))

import pack_optimise_fixture as FX  # noqa: E402
from auto_patch_v2.airport import dsf_write as W  # noqa: E402
from auto_patch_v2.airport import pack_forests as PF  # noqa: E402
from auto_patch_v2.airport import pack_optimise as PO  # noqa: E402
from auto_patch_v2.airport import unpatched_pack as UP  # noqa: E402
from auto_patch_v2.airport.pack_optimise import dedupe as DD  # noqa: E402
from auto_patch_v2.airport.pack_optimise import weight as WT  # noqa: E402
from auto_patch_v2.model.placement import Conversion  # noqa: E402

RECIPE = PO.default_recipe()
LINES = FX.DUMP.splitlines(keepends=True)


# ── D1, pure ────────────────────────────────────────────────────────────

def _two(dx_m=0.0, dhdg=0.0, dz=None, kind="OBJECT", d1=0):
    """A two-row dump: the second row ``dx_m`` east of the first."""
    lat = 25.5
    dlon = math.degrees(dx_m / (W._EARTH_R_M * math.cos(math.radians(lat))))
    def row(d, lon, hdg, z):
        mid = "" if z is None else f" {z:.6f}"
        return f"{kind} {d} {lon:.9f} {lat:.9f}{mid} {hdg % 360:.6f}\n"
    return ["OBJECT_DEF a.obj\n", "OBJECT_DEF b.obj\n",
            row(0, 51.5, 359.8, None if dz is None else 2.0),
            row(d1, 51.5 + dlon, 359.8 + dhdg, None if dz is None else 2.0 + dz)]


@pytest.mark.parametrize("rows, grouped", [
    (_two(0.19), True), (_two(0.21), False),
    (_two(dhdg=0.9), True), (_two(dhdg=1.1), False),       # across 0°/360°
    (_two(dz=0.0005, kind="OBJECT_AGL"), True),
    (_two(dz=0.01, kind="OBJECT_AGL"), False),
    (_two(d1=1), False),                                   # another object
])
def test_d1_tolerance_edges(rows, grouped):
    got = W.duplicate_rows(rows, tol_m=0.2, tol_deg=1.0, tol_h=0.001)
    assert got == ({0: [1]} if grouped else {})


def test_the_exact_default_of_section_15_4_is_unchanged():
    # token-equal def, position and heading; the height is not compared
    assert W.duplicate_rows(LINES) == {3: [4, 5]}
    assert W.duplicate_rows(LINES, {0}) == {}
    assert W.duplicate_rows(_two(0.01)) == {}, "exact means token-equal"


def test_the_recipe_drops_the_later_rows_of_each_group():
    drop, counts = PO.drop_ordinals(LINES, RECIPE, frozenset())
    assert drop == {1, 4} and counts == {"dropped": 2, "groups": 2}
    assert PO.drop_ordinals(LINES, {}, frozenset()) == (set(), {})


def test_a_plan_edited_duplicate_keeps_its_edit():
    drop, _ = DD.drop_set(LINES, DD.DEFAULTS, edited={4})
    assert drop == {1, 3}, "row 4 carries the seating; its unedited twin goes"


def test_the_record_reads_back_only_for_its_pristine_file():
    row = PO.record("abc", RECIPE, {"dropped": 2, "groups": 2}, "t")
    assert PO.recorded({PO.RECORD_KEY: row}, "abc") == RECIPE
    assert PO.recorded({PO.RECORD_KEY: row}, "other") == {}
    assert PO.recorded({PO.RECORD_KEY: {**row, "key": "x"}}, "abc") == {}
    assert PO.recorded({}, "abc") == {} and PO.recorded(None, "abc") == {}


def test_the_weight_counts_the_packs_own_objects(tmp_path, monkeypatch):
    rp = FX.make_pack(tmp_path, monkeypatch)
    assert WT._obj_triangles(str(rp.pack / "objects" / "car.obj")) == 1000
    assert WT._obj_triangles(str(tmp_path / "missing.obj")) == 0
    est = WT.estimate(str(rp.pack), LINES, {1, 4})
    assert est == {"tris_before": 3 * 1000 + 3 * 200,
                   "tris_after": 2 * 1000 + 2 * 200, "placements": 6}


# ── inside write_pack ───────────────────────────────────────────────────

@pytest.fixture
def rp(tmp_path, monkeypatch):
    return FX.make_pack(tmp_path, monkeypatch)


def test_optimise_writes_records_and_every_later_write_reapplies(rp):
    FX.write(rp, optimise=RECIPE)
    assert len(FX.rows(rp)) == 4
    row = FX.entry(rp)[PO.RECORD_KEY]
    assert row["dedupe"] == {"dropped": 2, "groups": 2}
    assert row["params"] == RECIPE and row["swaps"] == []
    # the re-apply twin: a placement write from the pristine backup with
    # no optimise argument keeps D1 (the 1.0.454 regression class)
    conv = Conversion(5, "objects/van.obj", 51.6, 25.6, 10.0, "OBJECT_AGL", 3.0)
    FX.write(rp, icao="OTST", conversions=(conv,))
    live = FX.rows(rp)
    assert len(live) == 4 and "OBJECT 1 51.600000000 25.600000000 10.000000" in live
    assert FX.entry(rp)[PO.RECORD_KEY]["dedupe"]["dropped"] == 2
    assert "OTST" in FX.entry(rp)["airports"]
    # ... and Undo is a write without it
    FX.write(rp, optimise={})
    assert len(FX.rows(rp)) == 6 and FX.entry(rp)[PO.RECORD_KEY] is None
    assert "OTST" in FX.entry(rp)["airports"]


def test_a_plan_edit_of_a_duplicate_survives_the_optimise(rp):
    conv = Conversion(4, "objects/van.obj", 51.6, 25.6, 10.0, "OBJECT_AGL", 2.0)
    FX.write(rp, icao="OTST", conversions=(conv,), optimise=RECIPE)
    live = FX.rows(rp)
    assert "OBJECT 1 51.600000000 25.600000000 10.000000" in live
    assert sum(r.startswith("OBJECT_AGL 1 51.6") for r in live) == 1, \
        "the unedited twin (row 3) is the one dropped; row 5 stays"


def test_forests_and_optimise_compose_and_undo_in_either_order(rp):
    original = rp.dsf.read_bytes()
    FX.write(rp, forests=FX.RENAMES)
    FX.write(rp, optimise=RECIPE)
    text = rp.dsf.read_text(encoding="utf-8")
    assert "broad_vhot_wet" in text and len(FX.rows(rp)) == 4
    FX.write(rp, forests={})                      # trees undone: optimise stays
    assert "wet_hot_flat" in rp.dsf.read_text(encoding="utf-8")
    assert len(FX.rows(rp)) == 4
    FX.write(rp, forests=FX.RENAMES)
    FX.write(rp, optimise={})                     # optimise undone: trees stay
    assert "broad_vhot_wet" in rp.dsf.read_text(encoding="utf-8")
    assert len(FX.rows(rp)) == 6
    assert PF.recorded(FX.entry(rp), FX.entry(rp)["backup_sha256"]) == FX.RENAMES
    assert (rp.dsf.parent / (rp.dsf.name + ".anchor_bak")).read_bytes() == original


def test_sibling_airports_keep_the_optimise(rp):
    FX.write(rp, icao="AAAA", optimise=RECIPE)
    FX.write(rp, icao="BBBB")
    e = FX.entry(rp)
    assert {"AAAA", "BBBB"} <= set(e["airports"]) and len(FX.rows(rp)) == 4
    assert e[PO.RECORD_KEY]["dedupe"]["dropped"] == 2


def test_an_airport_restore_keeps_the_optimise(rp):
    FX.write(rp, icao="OTST", optimise=RECIPE)
    out = UP.restore_airport(str(rp.pack), str(rp.dsf), "OTST", rp.tool,
                             allow_live_install=True, engine_version="1.0.test")
    assert out.state != UP.UNPROVEN
    assert len(FX.rows(rp)) == 4 and not FX.entry(rp).get("airports")
    assert FX.entry(rp)[PO.RECORD_KEY]["accepted"] is True


def test_the_pack_weight_tool_reads_what_the_offer_reads(tmp_path, monkeypatch, capsys):
    """``tools/pack_weight.py`` (the promoted packstat counter) on the
    synthetic pack's dump, no DSFTool."""
    import runpy
    rp = FX.make_pack(tmp_path, monkeypatch)
    tool = os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "tools", "pack_weight.py")
    main = runpy.run_path(tool)["main"]
    assert main([str(rp.pack), "--text", str(rp.dsf), "--json", "--top", "1"]) == 0
    row = __import__("json").loads(capsys.readouterr().out)[rp.dsf.name]
    assert (row["tris_before"], row["tris_after"], row["dropped"]) == (3600, 2400, 2)
    assert row["top"] == [[3000, 1000, 3, "objects/car.obj"]]
    assert row["offered"] is False, "6 placements are nowhere near 50 M"
