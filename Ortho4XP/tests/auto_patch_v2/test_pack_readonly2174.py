"""#2174 (RULINGS 2026-11-19d): a READ-ONLY pack (folders ``dr-xr-xr-x``
as unzipped) is reported at once — never a 900 s wait on a lock that could
not be made — and asked about; Make writable lets the paused write go on
in the same run, Not now leaves the pack and lists it on the tile's row."""
from __future__ import annotations

import os
import stat
import threading
import time

import O4_File_Lock as FL
import O4_UI_Utils as UI
import pytest
from auto_patch import object_rebake as OR
from auto_patch_v2.airport import pack_access as PA
from auto_patch_v2.airport import pack_lock as PL
from auto_patch_v2.airport import pack_readonly as RO

pytestmark = pytest.mark.skipif(
    os.name == "nt" or (hasattr(os, "geteuid") and os.geteuid() == 0),
    reason="POSIX folder permissions (root ignores them)")


@pytest.fixture
def pack(tmp_path, monkeypatch):
    """A temp ``Custom Scenery/KTST - Test`` read-only as unzipped: the
    pack and its folders r-x, the files inside rw."""
    scenery = tmp_path / "Custom Scenery"
    root = scenery / "KTST - Test"
    dsf_dir = root / "Earth nav data" / "+41-087"
    dsf_dir.mkdir(parents=True)
    (root / "Earth nav data" / "apt.dat").write_text(
        "1302 flatten 1\n", encoding="utf-8", newline="\n")
    (dsf_dir / "+41-087.dsf").write_bytes(b"XPLNEDSF")
    monkeypatch.setattr(RO, "_path", lambda: str(tmp_path / RO.FILE))
    events: list[dict] = []
    monkeypatch.setattr(UI, "pack_readonly", lambda **f: events.append(f))
    monkeypatch.setattr(UI, "engine_session", None)
    monkeypatch.setattr(UI, "red_flag", False, raising=False)
    for d in (dsf_dir, dsf_dir.parent, root):
        os.chmod(d, 0o555)
    yield str(root), events
    for d, _dirs, _files in os.walk(root):
        os.chmod(d, 0o755)


def test_readonly_folders_names_the_unzipped_folders(pack):
    root, _ = pack
    got = PA.relative_folders(root, PA.readonly_folders(root))
    assert got[0] == "KTST - Test"
    assert os.path.join("KTST - Test", "Earth nav data", "+41-087") in got


def test_lock_refused_at_once_never_900_s(pack):
    root, _ = pack
    t0 = time.monotonic()
    with pytest.raises(PA.PackReadOnlyError) as err:
        with PL.hold(root, allow_live_install=True):
            pass
    assert time.monotonic() - t0 < 2.0
    assert "read-only (as it was downloaded)" in str(err.value)
    assert "held its lock" not in str(err.value)


def test_file_lock_denied_never_waits(tmp_path):
    folder = tmp_path / "ro"
    folder.mkdir()
    os.chmod(folder, 0o555)
    try:
        t0 = time.monotonic()
        with FL.hold_file_lock(str(folder / "x"), timeout_seconds=60) as got:
            assert got is False
        with pytest.raises(OSError):
            with FL.hold_file_lock(str(folder / "x"), timeout_seconds=60,
                                   denied_raises=True):
                pass
        assert time.monotonic() - t0 < 2.0
    finally:
        os.chmod(folder, 0o755)


def test_no_front_end_asks_nothing_waits_nothing(pack):
    root, events = pack
    t0 = time.monotonic()
    assert RO.gate(root, 41, -87) is False
    assert time.monotonic() - t0 < 2.0
    assert [e["state"] for e in events] == ["found"]
    assert events[0]["pack"] == "KTST - Test" and events[0]["folders"]
    assert RO._entry(root)["state"] == RO.NOT_NOW


def _answer_later(root, action, delay=0.3):
    def go():
        time.sleep(delay)
        RO.choice(root, action, 41, -87)
    t = threading.Thread(target=go)
    t.start()
    return t


def test_make_writable_lets_the_paused_write_go_on(pack, monkeypatch):
    root, events = pack
    monkeypatch.setattr(UI, "engine_session", object())
    monkeypatch.setattr(RO, "POLL_SECONDS", 0.05)
    t = _answer_later(root, "writable")
    assert RO.gate(root, 41, -87) is True          # the same run goes on
    t.join()
    states = [e["state"] for e in events]
    assert states == ["found", "writable"]
    assert events[1]["changed"] >= 3 and events[1]["rebuild"] is False
    assert PA.readonly_folders(root) == []
    assert RO._entry(root) == {}
    with PL.hold(root, allow_live_install=True):     # the write proceeds
        with open(os.path.join(root, "Earth nav data", "apt.dat.o4tmp"), "w",
                  encoding="utf-8", newline="\n") as fh:
            fh.write("ok")
    # files kept their own bits plus u+w only
    mode = stat.S_IMODE(os.stat(root).st_mode)
    assert mode == 0o755


def test_a_writer_that_passes_mid_answer_leaves_no_stale_entry(pack, monkeypatch):
    """CI run 45270210136: the paused writer saw the folders writable and
    forgot the pack BEFORE Make writable recorded its answer, which then
    outlived it.  A slow answer widens that window to certain."""
    root, _events = pack
    monkeypatch.setattr(UI, "engine_session", object())
    monkeypatch.setattr(RO, "POLL_SECONDS", 0.02)
    real = PA.make_writable

    def slow(pack_root):
        changed = real(pack_root)
        time.sleep(0.4)                  # the writer polls through this
        return changed
    monkeypatch.setattr(PA, "make_writable", slow)
    t = _answer_later(root, "writable", delay=0.1)
    assert RO.gate(root, 41, -87) is True
    t.join()
    assert RO._entry(root) == {}


def test_not_now_leaves_the_pack_and_lists_its_row(pack, monkeypatch):
    root, events = pack
    monkeypatch.setattr(UI, "engine_session", object())
    monkeypatch.setattr(RO, "POLL_SECONDS", 0.05)
    t = _answer_later(root, "not_now")
    assert RO.gate(root, 41, -87) is False
    t.join()
    assert PA.readonly_folders(root)                  # untouched
    # a later build is quiet: no second question, no wait
    events.clear()
    t0 = time.monotonic()
    assert RO.gate(root, 41, -87) is False
    assert events == [] and time.monotonic() - t0 < 2.0
    rows = OR.modified_packs(os.path.dirname(root), tile="+41-087")
    assert [(r["pack_name"], r.get("read_only")) for r in rows] == [
        ("KTST - Test", True)]
    assert OR.modified_packs(os.path.dirname(root), tile="+40-087") == []
    # the row's Ask again, then Make writable: the tile is rebuilt
    assert RO.choice(root, "ask")["state"] == "ask"
    out = RO.choice(root, "writable")
    assert out["state"] == "writable" and out["rebuild"] is True
    assert (out["lat"], out["lon"]) == (41, -87)
    assert OR.modified_packs(os.path.dirname(root), tile="+41-087") == []


def test_make_writable_only_inside_custom_scenery(tmp_path):
    for parent, name in (("Elsewhere", "KTST"),
                         ("Custom Scenery", "*GLOBAL_AIRPORTS*")):
        root = tmp_path / parent / name
        root.mkdir(parents=True)
        os.chmod(root, 0o555)
        try:
            with pytest.raises(PermissionError):
                PA.make_writable(str(root))
            assert stat.S_IMODE(os.stat(root).st_mode) == 0o555
        finally:
            os.chmod(root, 0o755)


def test_a_folder_with_nothing_to_edit_is_never_asked_about(pack):
    """#2198: a read-only ``plugins`` folder (nothing a build edits) is
    not named, asks nothing and is left read-only by Make writable; a
    read-only folder holding an OBJ (a body is written beside it) is."""
    root, events = pack
    os.chmod(root, 0o755)
    for d, _dirs, _files in os.walk(root):
        os.chmod(d, 0o755)
    plugins = os.path.join(root, "plugins", "lua")
    objects = os.path.join(root, "objects")
    os.makedirs(plugins)
    os.makedirs(objects)
    with open(os.path.join(plugins, "init.lua"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("-- read only\n")
    with open(os.path.join(objects, "Hangar.obj"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("A\n800\nOBJ\n")
    for d in (plugins, os.path.dirname(plugins)):
        os.chmod(d, 0o555)
    assert PA.readonly_folders(root) == []
    assert RO.gate(root, 41, -87) is True and events == []
    os.chmod(objects, 0o555)
    assert PA.readonly_folders(root) == [objects]
    PA.make_writable(root)
    assert PA.readonly_folders(root) == []
    assert stat.S_IMODE(os.stat(plugins).st_mode) == 0o555
