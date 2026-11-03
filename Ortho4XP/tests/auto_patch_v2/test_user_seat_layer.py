"""Hand-set object seats are a layer of the pack DSF's write (#1703,
owner 2026-11-03 "yes, apply only the objects you set by hand").

Synthetic ``tmp_path`` pack written through the real ``apply_plan`` /
``write_pack`` with the byte-copy DSFTool stand-in of
``test_backup_state`` (the live DSF IS the edited dump text): TNCM's
placement converts row 0 and splits row 1, rows 2 and 3 are the pack's.

1. a build with the EDITED patch writes the hand-set row and nothing
   else — every other line of the live DSF byte-identical, the airport's
   recorded placement untouched; again, it writes nothing;
2. Automatic (the seat cleared) gives back the DSF byte for byte — a
   split row's bodies too, which the seat never removed;
3. a later auto-patch placement still applies it, and a write that
   knows nothing of seats (a forest upgrade, an omission) keeps it;
4. no seat, or no edited patch: the stage writes nothing;
5. the inspector reads the record: "Set by hand", or "rebuild".
"""
from __future__ import annotations

import os
import types

import pytest

import O4_File_Names as FNAMES
from auto_patch import dsf_reader as DSFR
from auto_patch import object_stage as ENGINE
from auto_patch import user_seat_stage as STAGE
from auto_patch_v2.airport import backup_state as B
from auto_patch_v2.airport import dsf_write as W
from auto_patch_v2.airport import placement_write as PW
from auto_patch_v2.airport import user_seats as US
from auto_patch_v2.model import placement as PM
from o4_engine import object_seat as OS

from test_backup_state import (DUMP4, _objs, _pack, _plan,  # noqa: E402
                               _record_doc, _stand_in_dsftool, _tncm)

DSF = "+18-064.dsf"
#: row 3 in the live DSF (TNCM's write dropped b.obj, unused once split:
#: d.obj is definition 2 there)
ROW3 = "OBJECT_MSL 2 -63.16 18.11 8.0 40.0\n"
SEATED3 = "OBJECT_MSL 2 -63.160000000 18.110000000 12.5000 40.000000\n"


@pytest.fixture(autouse=True)
def _clean_memo():
    B.invalidate_memo()
    yield
    B.invalidate_memo()


@pytest.fixture
def world(tmp_path, monkeypatch):
    """TNCM placed; its edited patch beside the auto one."""
    pack, dsf = _pack(tmp_path, dsf_text=DUMP4, name=DSF)
    tool = _stand_in_dsftool(tmp_path, monkeypatch)
    patch = tmp_path / "patch"
    patch.mkdir()
    for name in ("TNCM_auto.patch.osm", "TNCM_edited.patch.osm"):
        (patch / name).write_text("<osm/>\n", encoding="utf-8", newline="")
    plan, files = _tncm(pack, dsf)
    PW.apply_plan(plan, files, tool, patch_dir=str(patch), work_dir=str(tmp_path / "w0"))
    dump = ENGINE._PackDump(pack.name, str(dsf), str(dsf) + PM.BACKUP_SUFFIX,
                            "", str(tmp_path))
    monkeypatch.setattr(ENGINE, "pack_dump", lambda *a, **k: dump)
    monkeypatch.setattr(ENGINE, "_engine_version", lambda: "1.0.352")
    monkeypatch.setattr(DSFR, "_dsftool_path", lambda: tool)
    monkeypatch.setattr(DSFR, "ensure_dsf_text_path", lambda *a, **k: None)
    return types.SimpleNamespace(pack=pack, dsf=dsf, tool=tool, patch=patch, tmp=tmp_path,
                                 source=types.SimpleNamespace(icao="TNCM", pack_root=str(pack)),
                                 tile=types.SimpleNamespace(lat=18, lon=-64))


def _seat(world, index, model, lat, lon, zero):
    US.set_seat(str(world.patch), "TNCM",
                None if zero is None else US.UserSeat(index, model, lat, lon, zero),
                index=index)


def _stage(world, writes=True):
    return STAGE.seat_stage(world.source, world.tile, str(world.patch), writes=writes)


def _text(dsf):
    return dsf.read_text(encoding="utf-8")


def _rows(text):
    """Every placement row with its definition's PATH (a split's bodies
    renumber the definitions, never the objects)."""
    defs, out = [], []
    for raw in text.splitlines():
        toks = raw.split()
        if toks and toks[0] == "OBJECT_DEF":
            defs.append(toks[1])
        elif toks and toks[0].startswith("OBJECT"):
            out.append((toks[0], defs[int(toks[1])], *toks[2:]))
    return out


def _airport_row(dsf):
    row = dict(_record_doc(dsf)["dsfs"][DSF]["airports"]["TNCM"])
    row.pop("time", None)
    return row


# ── 1 + 2 ───────────────────────────────────────────────────────────────

def test_an_edited_patch_writes_only_the_hand_set_row_and_automatic_undoes_it(world):
    before, placed = _text(world.dsf), _airport_row(world.dsf)
    assert ROW3 in before
    _seat(world, 3, "objects/d.obj", 18.11, -63.16, 12.5)

    assert _stage(world) is True
    after = _text(world.dsf)
    old, new = before.splitlines(True), after.splitlines(True)
    assert len(old) == len(new)
    diff = [(a, b) for a, b in zip(old, new, strict=True) if a != b]
    assert diff == [(ROW3, SEATED3)]
    assert _airport_row(world.dsf) == placed, "TNCM's placement is recorded as it was"
    rec = _record_doc(world.dsf)["dsfs"][DSF][US.RECORD_KEY]
    assert rec["applied"] == [3] and rec["airports"]["TNCM"][0]["zero_m"] == 12.5
    # the DSF already carries it: nothing is written again
    stamp = os.stat(world.dsf).st_mtime_ns
    assert _stage(world) is False and os.stat(world.dsf).st_mtime_ns == stamp

    _seat(world, 3, "", 0, 0, None)                   # Automatic
    assert _stage(world) is True
    assert _text(world.dsf) == before
    assert _record_doc(world.dsf)["dsfs"][DSF][US.RECORD_KEY] is None


def test_a_split_row_is_placed_whole_and_its_bodies_come_back(world):
    before = _text(world.dsf)
    assert _objs(world.pack) == ["b__b0.obj", "b__b1.obj"]
    _seat(world, 1, "objects/b.obj", 18.041, -63.11, 30.0)

    assert _stage(world) is True
    after = _text(world.dsf)
    whole = ("OBJECT_MSL", "objects/b.obj", "-63.110000000", "18.041000000", "30.0000",
             "20.000000")
    assert "objects/b__b" not in after
    assert _rows(after) == [whole if r[1].startswith("objects/b__b") else r
                            for r in _rows(before) if r[1] != "objects/b__b1.obj"]
    assert _objs(world.pack) == ["b__b0.obj", "b__b1.obj"], "kept for the Undo"

    _seat(world, 1, "", 0, 0, None)
    assert _stage(world) is True
    assert _text(world.dsf) == before


# ── 3 ───────────────────────────────────────────────────────────────────

def test_a_later_placement_applies_it_and_other_writes_keep_it(world):
    _seat(world, 3, "objects/d.obj", 18.11, -63.16, 12.5)
    seated = SEATED3
    plan, files = _tncm(world.pack, world.dsf)
    res = PW.apply_plan(plan, files, world.tool, patch_dir=str(world.patch),
                        work_dir=str(world.tmp / "w1"),
                        seats=STAGE.file_seats(str(world.patch), "TNCM"))
    assert res.dsf.hand_seated == (3,) and seated in _text(world.dsf)
    assert "objects/b__b0.obj" in _text(world.dsf), "the placement is as built"
    # a write that knows nothing of seats (the forest upgrade's, #1360)
    W.write_pack(str(world.pack), _plan(world.pack, world.dsf, icao="", conversions=()),
                 world.tool, work_dir=str(world.tmp / "w2"))
    assert seated in _text(world.dsf)
    # the airport left without a patch loses its seats with its seating
    W.write_pack(str(world.pack), _plan(world.pack, world.dsf, icao="", conversions=()),
                 world.tool, work_dir=str(world.tmp / "w3"), drop=("TNCM",))
    text = _text(world.dsf)
    assert seated not in text and "OBJECT_MSL 3 -63.16 18.11 8.0 40.0\n" in text
    assert _record_doc(world.dsf)["dsfs"][DSF][US.RECORD_KEY] is None


def test_a_seat_on_a_changed_row_is_refused_and_named(world):
    _seat(world, 3, "objects/zz.obj", 18.11, -63.16, 12.5)
    before = _text(world.dsf)
    plan = _plan(world.pack, world.dsf, icao="", conversions=())
    res = W.write_pack(str(world.pack), plan, world.tool, work_dir=str(world.tmp / "w4"),
                       seats=STAGE.file_seats(str(world.patch), "TNCM"))
    assert res.hand_seated == () and _text(world.dsf) == before
    assert any("now places objects/d.obj" in n for n in res.notes)


# ── 4 ───────────────────────────────────────────────────────────────────

def test_no_seat_or_no_edited_patch_writes_nothing(world):
    stamp = os.stat(world.dsf).st_mtime_ns
    assert _stage(world) is False                         # no seat
    _seat(world, 3, "objects/d.obj", 18.11, -63.16, 12.5)
    assert _stage(world, writes=False) is False           # a lane build
    os.remove(world.patch / "TNCM_edited.patch.osm")
    assert _stage(world) is False                         # the auto patch is in the mesh
    assert os.stat(world.dsf).st_mtime_ns == stamp


# ── 5 ───────────────────────────────────────────────────────────────────

def test_the_inspector_says_set_by_hand_once_the_dsf_has_it(world, monkeypatch):
    tile = "+18-064"
    monkeypatch.setattr(FNAMES, "patch_dir", lambda *a: str(world.patch))
    _seat(world, 3, "objects/d.obj", 18.11, -63.16, 12.5)
    rec = OS.object_seat(tile, "TNCM", 3, 18.11, -63.16)
    assert rec["why"] == "Set by hand at 12.5 m MSL; rebuild the tile to place it there"
    assert _stage(world) is True
    assert OS.object_seat(tile, "TNCM", 3, 18.11, -63.16)["why"] == \
        "Set by hand at 12.5 m MSL"
