"""A STOPPED BUILD PUTS THE SCENERY PACKS BACK AS THEY WERE (issue #598,
owner decision 2026-10-12).

The object stage re-seats pack objects at the end of the mesh step; a
build stopped afterwards leaves the tile's PREVIOUS scenery active, so
every pack file that stage rewrote must be as it was BEFORE THE BUILD —
the previous completed build's seating, not the pristine pack.  These
twins drive the real writers (``placement_write.apply_plan``, the
stand-in DSFTool of ``test_backup_state``) and pin:

* stopped after the stage rewrote a pack: DSF, record and split bodies
  byte-identical to before the build;
* killed mid-stage: the next build's object stage restores before it
  does anything;
* a completed build: journal gone, the new seating kept;
* a pack the build never wrote: untouched, no journal;
* a pack file the user replaced meanwhile: left, and NAMED.
"""
from __future__ import annotations

import json
import os
import types

import pytest

import O4_Stopped_Build as STOPPED
import O4_UI_Utils as UI
from auto_patch import engine_v2 as ENGINE
from auto_patch_v2.airport import backup_state as B
from auto_patch_v2.airport import pack_journal as PJ
from auto_patch_v2.airport import placement_write as PW

from test_backup_state import DUMP4, _snapshot, _tffg, _tncm  # noqa: E402
from test_unpatched_pack import _clean_memo, seated  # noqa: E402,F401

LAT, LON, TILE = 18, -64, "+18-064"


def _bytes(root) -> dict:
    """Every file of the pack: relative name -> bytes."""
    out = {}
    for folder, _sub, names in os.walk(root):
        for name in names:
            path = os.path.join(folder, name)
            with open(path, "rb") as fh:
                # ``/`` on every platform: the names below are literals
                out[os.path.relpath(path, root).replace(os.sep, "/")] = (
                    fh.read())
    return out


@pytest.fixture
def build(seated, monkeypatch):
    """One tile's builds over the ``seated`` pack: ``stage(*makers)`` is
    an object stage writing those airports' plans."""
    said = []
    monkeypatch.setattr(UI, "loud_warning",
                        lambda *words: said.append(" ".join(map(str, words))))
    build_dir = str(seated.tmp / "tile")
    os.makedirs(build_dir)
    count = [0]

    def stage(*makers):
        PJ.begin(build_dir, TILE)
        try:
            for make in makers:
                count[0] += 1
                seated.write(make, "w%d" % count[0])
        finally:
            PJ.end()

    return types.SimpleNamespace(
        dir=build_dir, stage=stage, said=said, pack=seated.pack,
        dsf=seated.dsf, journal=PJ.path_for(build_dir, TILE),
        stop=lambda: ENGINE.restore_stopped_build(build_dir, LAT, LON),
        complete=lambda: ENGINE.discard_pack_journal(build_dir, LAT, LON))


def test_a_stop_after_the_stage_puts_the_pack_back_byte_for_byte(build):
    build.stage(_tncm)                    # the previous, COMPLETED build
    build.complete()
    before = _bytes(build.pack)
    assert "objects/b__b0.obj" in before

    build.stage(_tncm, _tffg)             # this build re-seats and adds TFFG
    assert _bytes(build.pack) != before
    assert PJ.pending(build.dir, TILE)

    assert build.stop() == []             # stopped during masks / imagery

    assert _bytes(build.pack) == before   # DSF, record, bodies — and no more
    assert not os.path.exists(build.journal)
    assert build.said == []
    assert B.classify_dsf(str(build.dsf)).state is B.State.OURS


def test_a_stop_of_the_first_build_leaves_the_authored_pack(build):
    authored = _bytes(build.pack)

    build.stage(_tncm)
    assert build.stop() == []

    after = _bytes(build.pack)
    backup = os.path.relpath(str(build.dsf), str(build.pack)).replace(
        os.sep, "/") + ".anchor_bak"
    assert after.pop(backup) == DUMP4.encode()     # the backup it made stays
    assert after == authored                       # no record, no body


def test_a_build_killed_mid_stage_is_put_back_by_the_next_stage(
        build, monkeypatch):
    build.stage(_tncm)
    build.complete()
    before = _bytes(build.pack)

    def killed(*args, **kwargs):          # after step 0 and the new bodies
        raise KeyboardInterrupt

    with monkeypatch.context() as dying:
        dying.setattr(PW._dw, "write_pack", killed)
        with pytest.raises(KeyboardInterrupt):
            build.stage(_tffg, _tncm)
    assert _bytes(build.pack) != before   # torn: bodies changed, DSF not
    assert PJ.pending(build.dir, TILE)

    tile = types.SimpleNamespace(lat=LAT, lon=LON, build_dir=build.dir,
                                 modify_custom_airports=False)
    ENGINE.rebake_after_mesh(tile)        # the next build's object stage

    assert _bytes(build.pack) == before
    assert not os.path.exists(build.journal)


def test_a_completed_build_keeps_its_seating_and_drops_the_journal(build):
    build.stage(_tncm)
    seated_once = _bytes(build.pack)
    assert PJ.pending(build.dir, TILE)

    build.complete()

    assert not os.path.exists(build.journal)
    assert build.stop() == []             # nothing left to put back
    assert _bytes(build.pack) == seated_once


def test_a_pack_the_build_never_wrote_is_untouched(build):
    build.stage(_tncm)
    build.complete()
    before = _snapshot(build.pack)        # sizes AND mtimes

    build.stage()                         # an object stage with no write
    assert not os.path.exists(build.journal)
    assert build.stop() == []

    assert _snapshot(build.pack) == before


def test_a_write_outside_a_build_is_not_journalled(seated):
    seated.write(_tncm, "w1")             # e.g. the user's art command

    assert not PJ.pending(str(seated.tmp / "tile"), TILE)


def test_a_file_the_user_replaced_is_left_and_named(build):
    build.stage(_tncm)
    build.complete()
    build.stage(_tncm, _tffg)
    build.dsf.write_text("the user's new version of the pack\n",
                         encoding="utf-8", newline="")
    B.invalidate_memo()

    (sentence,) = build.stop()

    assert "The scenery pack pack was changed by the build that did not " \
           "finish and could not be put back as it was:" in sentence
    assert build.said == ["   " + sentence]
    assert build.dsf.read_text(encoding="utf-8").startswith("the user's")
    assert not os.path.exists(build.journal)


def test_the_stopped_row_carries_the_unprovable_restore(build):
    build.stage(_tncm)
    build.dsf.write_text("the user's new version\n", encoding="utf-8",
                         newline="")
    B.invalidate_memo()

    detail = STOPPED.settle(build.dir, LAT, LON)

    assert detail.startswith(STOPPED.NO_SCENERY + " The scenery pack pack ")
    assert STOPPED.settle(build.dir, LAT, LON) == STOPPED.NO_SCENERY


def test_a_sibling_dsfs_record_entry_survives_the_restore(build):
    build.stage(_tncm)
    build.complete()
    record = B.record_path_for(str(build.dsf))
    with open(record, "rb") as fh:
        before = fh.read()
    build.stage(_tffg)
    # another tile's build recorded ITS DSF in the same folder meanwhile
    B.update_dsf_entry(os.path.join(os.path.dirname(record), "+19-064.dsf"),
                       {"written_sha256": "other"})

    assert build.stop() == []

    with open(record, encoding="utf-8") as fh:
        doc = json.load(fh)
    assert doc["dsfs"]["+19-064.dsf"] == {"written_sha256": "other"}
    assert doc["dsfs"][build.dsf.name] == json.loads(before)["dsfs"][
        build.dsf.name]
    assert sorted(doc["dsfs"][build.dsf.name]["airports"]) == ["TNCM"]


# ── the journal's names are the record's, on every platform ─────────────

def test_the_journal_names_bodies_as_the_record_does(build):
    build.stage(_tncm)
    build.complete()
    build.stage(_tncm, _tffg)

    with open(os.path.join(build.journal, "journal.json"),
              encoding="utf-8") as fh:
        (entry,) = json.load(fh)["entries"]

    assert [name for name, _copy in entry["bodies"]] == [
        "objects/b__b0.obj", "objects/b__b1.obj"]
    assert entry["minted"] == ["objects/b__b0.obj", "objects/b__b1.obj",
                               "objects/d__b0.obj"]


@pytest.mark.parametrize("flavour", ["ntpath", "posixpath"])
def test_the_bodies_to_remove_are_compared_as_record_names(flavour):
    """Run with Windows' path rules AND POSIX's on every machine: the
    record spells a body ``objects/b__b0.obj`` whatever the platform, the
    filesystem spells it with the platform's separator, and a body that
    was there before the build must never be among those removed."""
    import ntpath
    import posixpath
    rules = {"ntpath": ntpath, "posixpath": posixpath}[flavour]
    root = "C:\\X-Plane\\Custom Scenery\\pack" if flavour == "ntpath" \
        else "/x-plane/Custom Scenery/pack"
    recorded = [rules.join(root, "objects", "b__b0.obj"),     # there before
                rules.join(root, "objects", "sub", "e__b0.obj")]
    assert PJ._rel(root, recorded[1], rules) == "objects/sub/e__b0.obj"

    stale = PJ._stale_bodies(
        root, recorded, minted=["objects/d__b0.obj", "objects/b__b1.obj"],
        before=["objects/b__b0.obj", "objects/b__b1.obj"], _path=rules)

    assert stale == [rules.join(root, "objects", "d__b0.obj"),
                     rules.join(root, "objects", "sub", "e__b0.obj")]
    # a journal written before this spelling was fixed (``\\`` names)
    assert PJ._stale_bodies(root, [], ["objects\\b__b0.obj"],
                            ["objects/b__b0.obj"], _path=rules) == []
