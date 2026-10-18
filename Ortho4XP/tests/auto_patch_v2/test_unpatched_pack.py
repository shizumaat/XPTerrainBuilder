"""An airport left without a patch gets its ORIGINAL pack back (owner
RULINGS 2026-10-12d, issue #564).

Synthetic ``tmp_path`` packs written through the real ``apply_plan`` /
``write_pack`` with the byte-copy DSFTool stand-in of
``test_backup_state`` (the live DSF IS the edited dump text):

1. one airport seated the DSF, and is now unpatched -> the DSF is the
   pristine file again, its split bodies are gone, the record is gone;
2. two airports in one DSF, one unpatched -> its rows are as authored,
   the OTHER airport's seating and bodies are kept, and a later write of
   the other does not bring the unpatched one's edits back;
3. an airport that never re-seated the pack -> nothing is touched;
4. a restore that cannot be proven -> nothing is written and the reason
   lands on the airport's unpatched record;
5. the object stage's hook: found from the records alone, before any
   plan; the lane stand-down writes nothing and says so.
"""
from __future__ import annotations

import os
import types

import pytest

import O4_UI_Utils as UI
import O4_Unpatched_Airports as UNPATCHED
from auto_patch import object_stage as ENGINE
from auto_patch_v2.airport import backup_state as B
from auto_patch_v2.airport import placement_write as PW
from auto_patch_v2.airport import unpatched_pack as UP

from test_backup_state import (DUMP4, _objs, _pack, _record_doc,  # noqa: E402
                               _snapshot, _stand_in_dsftool, _tffg, _tncm)

DSF = "+18-064.dsf"


@pytest.fixture(autouse=True)
def _clean_memo():
    B.invalidate_memo()
    yield
    B.invalidate_memo()


@pytest.fixture
def seated(tmp_path, monkeypatch):
    """A pack whose one DSF both TNCM and TFFG re-seated."""
    pack, dsf = _pack(tmp_path, dsf_text=DUMP4, name=DSF)
    tool = _stand_in_dsftool(tmp_path, monkeypatch)
    patch = str(tmp_path / "patch")
    world = types.SimpleNamespace(pack=pack, dsf=dsf, tool=tool, patch=patch,
                                  tmp=tmp_path)

    def write(make, tag):
        plan, files = make(pack, dsf)
        PW.apply_plan(plan, files, tool, patch_dir=patch,
                      work_dir=str(tmp_path / tag))
    world.write = write
    return world


def _restore(world, icao):
    return UP.restore_airport(str(world.pack), str(world.dsf), icao,
                              world.tool, work_dir=str(world.tmp / "wr"))


# ── 1 ───────────────────────────────────────────────────────────────────


def test_the_only_seated_airport_gets_the_pristine_pack_back(seated):
    seated.write(_tncm, "w1")
    assert _objs(seated.pack) == ["b__b0.obj", "b__b1.obj"]
    assert seated.dsf.read_text(encoding="utf-8") != DUMP4

    out = _restore(seated, "TNCM")

    assert out.state == UP.RESTORED and out.kept == ()
    assert seated.dsf.read_text(encoding="utf-8") == DUMP4
    assert _objs(seated.pack) == []
    assert len(out.bodies_removed) == 2
    assert not (seated.dsf.parent / "o4_placement_provenance.json").exists()
    assert B.classify_dsf(str(seated.dsf)).state is B.State.PRISTINE
    # idempotent: the mesh step may be run again on the same record
    assert _restore(seated, "TNCM").state == UP.NONE


# ── 2 ───────────────────────────────────────────────────────────────────


def test_the_other_airports_seating_is_kept(seated):
    seated.write(_tncm, "w1")
    seated.write(_tffg, "w2")

    out = _restore(seated, "TNCM")

    assert out.state == UP.RECOMPOSED and out.kept == ("TFFG",)
    text = seated.dsf.read_text(encoding="utf-8")
    # TNCM's two placements are as authored …
    assert "OBJECT_MSL 0 -63.1 18.04 5.0 10.0\n" in text
    assert "OBJECT_MSL 1 -63.11 18.041 6.0 20.0\n" in text
    assert "objects/b__b" not in text
    # … and TFFG's conversion and split body are still there
    assert "OBJECT 2 -63.15 18.1 30.0\n" in text
    assert "OBJECT_DEF objects/d__b0.obj\n" in text
    assert _objs(seated.pack) == ["d__b0.obj"]
    entry = _record_doc(seated.dsf)["dsfs"][DSF]
    assert set(entry["airports"]) == {"TFFG"}
    assert entry["body_files"] == ["objects/d__b0.obj"]
    assert (seated.dsf.parent / (DSF + ".anchor_bak")).read_text(
        encoding="utf-8") == DUMP4


def test_a_later_write_of_the_other_does_not_bring_it_back(seated):
    """What the placement loop does next in the same pass: TFFG is built
    and written again.  Before the restore its write RE-APPLIED TNCM's
    recorded edits (#25's composition)."""
    seated.write(_tncm, "w1")
    seated.write(_tffg, "w2")
    _restore(seated, "TNCM")

    seated.write(_tffg, "w3")

    text = seated.dsf.read_text(encoding="utf-8")
    assert "OBJECT_MSL 0 -63.1 18.04 5.0 10.0\n" in text
    assert "objects/b__b" not in text
    assert _objs(seated.pack) == ["d__b0.obj"]
    assert UP.seated_airports(str(seated.dsf)) == ("TFFG",)


# ── 3 ───────────────────────────────────────────────────────────────────


def test_an_airport_that_never_seated_the_pack_is_a_no_op(seated):
    before = _snapshot(seated.pack)
    assert _restore(seated, "TNCM").state == UP.NONE     # no record at all
    assert _snapshot(seated.pack) == before

    seated.write(_tffg, "w1")                            # someone else's
    before = _snapshot(seated.pack)
    out = _restore(seated, "TNCM")
    assert out.state == UP.NONE and out.kept == ("TFFG",)
    assert _snapshot(seated.pack) == before


# ── 4 ───────────────────────────────────────────────────────────────────


def test_a_lost_original_is_unproven_and_nothing_is_written(seated):
    seated.write(_tncm, "w1")
    os.remove(str(seated.dsf) + ".anchor_bak")
    B.invalidate_memo()
    before = _snapshot(seated.pack)

    out = _restore(seated, "TNCM")

    assert out.state == UP.UNPROVEN
    assert "original" in out.reason and DSF in out.reason
    assert _snapshot(seated.pack) == before


def test_a_failed_rebuild_is_unproven_and_the_pack_is_untouched(
        seated, monkeypatch):
    seated.write(_tncm, "w1")
    seated.write(_tffg, "w2")
    before = _snapshot(seated.pack)

    def broken(*args, **kwargs):
        raise RuntimeError("DSFTool failed (rc 1)")

    monkeypatch.setattr(UP._dw, "encode", broken)
    out = _restore(seated, "TNCM")

    assert out.state == UP.UNPROVEN and "rc 1" in out.reason
    assert _snapshot(seated.pack) == before
    assert UP.seated_airports(str(seated.dsf)) == ("TFFG", "TNCM")


# ── 5: the object stage's hook ──────────────────────────────────────────


@pytest.fixture
def tile(seated, monkeypatch):
    """A tile built without TNCM, whose scenery folder holds the pack."""
    import O4_Scenery_Packs as SP
    from auto_patch import dsf_reader as DSFR
    monkeypatch.delenv("O4_PACK_WRITES", raising=False)
    monkeypatch.setattr(SP, "pack_enabled", lambda root: True)
    monkeypatch.setattr(DSFR, "_dsftool_path", lambda: seated.tool)
    monkeypatch.setattr(UP._dw, "live_install_roots", lambda path: False)
    said = []
    monkeypatch.setattr(UI, "loud_warning",
                        lambda *words: said.append(" ".join(map(str, words))))
    t = types.SimpleNamespace(lat=18, lon=-64, modify_custom_airports=True,
                              build_dir=str(seated.tmp / "tile"), said=said)
    UNPATCHED.record(t, [{"icao": "TNCM", "stage": "build", "error": "boom"}])
    del t.auto_patch_unpatched            # the mesh step is another process
    return t


def test_the_hook_restores_from_the_records_alone(seated, tile):
    seated.write(_tncm, "w1")

    counts = ENGINE.restore_unpatched_packs(tile, str(seated.tmp))

    assert counts == {"restored": 1, "recomposed": 0, "unproven": 0}
    assert seated.dsf.read_text(encoding="utf-8") == DUMP4
    assert tile.said == []
    assert UNPATCHED.PACK_RESTORE_KEY not in UNPATCHED.read(tile)[0]


def test_the_hook_does_nothing_for_a_tile_with_every_patch(seated, tile):
    seated.write(_tncm, "w1")
    UNPATCHED.record(tile, [])
    del tile.auto_patch_unpatched
    before = _snapshot(seated.pack)

    counts = ENGINE.restore_unpatched_packs(tile, str(seated.tmp))

    assert counts == {"restored": 0, "recomposed": 0, "unproven": 0}
    assert _snapshot(seated.pack) == before


def test_the_hook_names_an_unprovable_restore_on_the_record(seated, tile):
    seated.write(_tncm, "w1")
    os.remove(str(seated.dsf) + ".anchor_bak")
    B.invalidate_memo()

    counts = ENGINE.restore_unpatched_packs(tile, str(seated.tmp))

    assert counts["unproven"] == 1
    (rec,) = UNPATCHED.read(tile)
    assert rec["icao"] == "TNCM" and rec["error"] == "boom"
    assert "pack" in rec[UNPATCHED.PACK_RESTORE_KEY]
    assert "float or sink" in rec[UNPATCHED.PACK_RESTORE_KEY]
    assert tile.said and "TNCM" in tile.said[0]


def test_a_lane_build_writes_nothing_and_says_so(seated, tile, monkeypatch):
    seated.write(_tncm, "w1")
    monkeypatch.setenv("O4_PACK_WRITES", "measure_only")
    before = _snapshot(seated.pack)

    counts = ENGINE.restore_unpatched_packs(tile, str(seated.tmp))

    assert counts["unproven"] == 1 and counts["restored"] == 0
    assert _snapshot(seated.pack) == before
    assert "measure_only" in UNPATCHED.read(tile)[0][UNPATCHED.PACK_RESTORE_KEY]


# ── 6: the art the user accepted to build without stays out (#433) ──────


def _omission():
    from auto_patch_v2.airport import pack_art as PA
    # ``objects/d.obj`` is not installed; placement 3 uses it
    return (PA.MissingDef("object", 3, "objects/d.obj", 1),)


def _write_with_omission(world, make, tag):
    plan, files = make(world.pack, world.dsf)
    PW.apply_plan(plan, files, world.tool, patch_dir=world.patch,
                  work_dir=str(world.tmp / tag), omit=_omission())


def test_the_only_airports_restore_keeps_the_accepted_omission(seated):
    _write_with_omission(seated, _tncm, "w1")
    assert "objects/d.obj" not in seated.dsf.read_text(encoding="utf-8")

    out = _restore(seated, "TNCM")

    assert out.state == UP.RESTORED and out.kept == ()
    text = seated.dsf.read_text(encoding="utf-8")
    # the definition X-Plane cannot load, and the row that placed it, stay out
    assert "objects/d.obj" not in text and "18.11" not in text
    # every other placement is as authored, TNCM's two included
    assert "OBJECT_MSL 0 -63.1 18.04 5.0 10.0\n" in text
    assert "OBJECT_MSL 1 -63.11 18.041 6.0 20.0\n" in text
    assert "OBJECT_MSL 2 -63.15 18.1 7.0 30.0\n" in text
    assert _objs(seated.pack) == []
    # the record still names the omission, and no airport
    entry = _record_doc(seated.dsf)["dsfs"][DSF]
    assert entry["airports"] == {}
    assert entry["omitted_art"]["accepted"] is True
    assert [d["path"] for d in entry["omitted_art"]["definitions"]] == [
        "objects/d.obj"]
    assert UP.seated_airports(str(seated.dsf)) == ()
    assert _restore(seated, "TNCM").state == UP.NONE


def test_the_recompose_keeps_the_accepted_omission(seated):
    seated.write(_tffg, "w1")                 # TFFG seats placement 2 only
    _write_with_omission(seated, _tncm, "w2")

    out = _restore(seated, "TNCM")

    assert out.state == UP.RECOMPOSED and out.kept == ("TFFG",)
    text = seated.dsf.read_text(encoding="utf-8")
    assert "OBJECT_DEF objects/d.obj\n" not in text
    assert "OBJECT 2 -63.15 18.1 30.0\n" in text          # TFFG kept
    assert "OBJECT_MSL 0 -63.1 18.04 5.0 10.0\n" in text  # TNCM as authored
    entry = _record_doc(seated.dsf)["dsfs"][DSF]
    assert set(entry["airports"]) == {"TFFG"}
    assert entry["omitted_art"]["accepted"] is True


def test_without_an_omission_the_restore_is_the_backup_byte_for_byte(seated):
    seated.write(_tncm, "w1")
    _restore(seated, "TNCM")
    backup = seated.dsf.parent / (DSF + ".anchor_bak")
    assert seated.dsf.read_bytes() == backup.read_bytes()
    assert not (seated.dsf.parent / "o4_placement_provenance.json").exists()


def test_an_omission_recorded_for_another_pristine_file_is_not_applied():
    from auto_patch_v2.airport import pack_art as PA
    entry = {"omitted_art": PA.record("aa", _omission(), {}, "t")}
    assert PA.recorded(entry, "aa") == _omission()
    assert PA.recorded(entry, "bb") == ()
    assert PA.recorded({}, "aa") == () and PA.recorded(None, "aa") == ()
