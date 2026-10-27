"""#1360: old flat (X-Plane 11) forests in an airport pack — the object
stage's offer, the user's answer and the protocol 1.17 surface.

The stage (``auto_patch.forest_stage``) names a pack the build modifies
whose DSF draws flat forests with X-Plane 12 3D equivalents; a lane build
(measure-only) only reports; the DSF is rewritten only after the user
said Update (now, or remembered for the pack); "Never for this pack"
stops the question; Undo puts the originals back, byte for byte when
nothing else of ours is in the DSF.  ``PackOldForests`` and the
``pack_forests`` command are additive (``events.py`` class names ARE the
wire names; ``OrthoEngineClient.swift`` matches them as literals).

Headless, no network.  The check is stubbed where the stage's decision is
the subject (its own twins are ``tests/auto_patch_v2/test_pack_forests.
py``); Undo runs on a synthetic pack with a byte-copy DSFTool.
"""
from __future__ import annotations

import dataclasses
import json
import os
import sys
import time
import types

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "src"))

import O4_UI_Utils as UI  # noqa: E402
from auto_patch import forest_stage as FS  # noqa: E402
from auto_patch_v2.airport import backup_state as B  # noqa: E402
from auto_patch_v2.airport import dsf_write as W  # noqa: E402
from auto_patch_v2.airport import pack_forests as PF  # noqa: E402
from auto_patch_v2.model import placement as PM  # noqa: E402
from o4_engine import events as EV  # noqa: E402

MAPPED = PF.OldForest(0, "lib/g8/terrain/wet_hot_flat.for", 2,
                      "lib/g8/broad_vhot_wet.for")
UNMAPPED = PF.OldForest(2, "forests/local.for", 1, "", True)
RENAMES = {MAPPED.path: MAPPED.target}
PLAN = types.SimpleNamespace(pack_root="/X/Custom Scenery/Some Pack")
TILE = types.SimpleNamespace(lat=25, lon=51)


@pytest.fixture
def choices(tmp_path, monkeypatch):
    path = tmp_path / "prefs" / FS.CHOICES_NAME
    monkeypatch.setattr(FS, "choices_path", lambda: str(path))
    return path


@pytest.fixture
def stage(monkeypatch, choices):
    """Stub the check and the write; collect what the UI hook was told."""
    seen = {"events": [], "writes": [], "pf": None, "raise": None}

    def fake_check(pack_root, lat, lon, *, read_only):
        seen["read_only"] = read_only
        if isinstance(seen["pf"], Exception):
            raise seen["pf"]
        return seen["pf"]

    def fake_write(pf, pack_root, renames):
        if seen["raise"]:
            raise seen["raise"]
        seen["writes"].append(dict(renames))

    monkeypatch.setattr(FS, "check", fake_check)
    monkeypatch.setattr(FS, "_write", fake_write)
    monkeypatch.setattr(UI, "pack_old_forests",
                        lambda **f: seen["events"].append(f))
    monkeypatch.setattr(UI, "vprint", lambda *a, **k: None)
    return seen


def _pf(old=(MAPPED, UNMAPPED), upgraded=None):
    return FS.PackForests("Some Pack", "/p/+25+051.dsf", tuple(old),
                          dict(upgraded or {}))


# ── the stage's decision ────────────────────────────────────────────────

def test_found_asks_and_writes_nothing(stage):
    stage["pf"] = _pf()
    assert FS.forest_stage(PLAN, TILE, writes=True) == "found"
    assert stage["writes"] == []
    [ev] = stage["events"]
    assert ev["state"] == "found" and ev["can_update"] is True
    assert (ev["total"], ev["mapped"], ev["uses"], ev["unmapped"]) == (2, 1, 2, 1)
    assert ev["first_unmapped"] == ["forests/local.for"]
    assert (ev["pack"], ev["lat"], ev["lon"]) == ("Some Pack", 25, 51)


def test_a_read_only_run_reports_and_never_writes(stage, choices):
    FS.set_pack_choice(PLAN.pack_root, "update")
    stage["pf"] = _pf()
    assert FS.forest_stage(PLAN, TILE, writes=False) == "found"
    assert stage["read_only"] is True and stage["writes"] == []


def test_nothing_mapped_is_logged_not_asked(stage):
    stage["pf"] = _pf(old=(UNMAPPED,))
    assert FS.forest_stage(PLAN, TILE, writes=True) == ""
    assert stage["events"] == [] and stage["writes"] == []


def test_no_forest_says_nothing(stage):
    stage["pf"] = _pf(old=())
    assert FS.forest_stage(PLAN, TILE, writes=True) == ""
    stage["pf"] = None
    assert FS.forest_stage(PLAN, TILE, writes=True) == ""
    assert stage["events"] == []


def test_an_upgrade_already_on_disk_is_quiet(stage):
    stage["pf"] = _pf(upgraded=RENAMES)
    assert FS.forest_stage(PLAN, TILE, writes=True) == "current"
    assert stage["events"] == [] and stage["writes"] == []


def test_never_for_this_pack_stops_the_question(stage):
    FS.set_pack_choice(PLAN.pack_root, "never")
    stage["pf"] = _pf()
    assert FS.forest_stage(PLAN, TILE, writes=True) == "never"
    assert stage["events"] == [] and stage["writes"] == []


def test_update_remembered_upgrades_and_says_so(stage):
    FS.set_pack_choice(PLAN.pack_root, "update")
    stage["pf"] = _pf()
    assert FS.forest_stage(PLAN, TILE, writes=True) == "upgraded"
    assert stage["writes"] == [RENAMES]
    [ev] = stage["events"]
    assert ev["state"] == "upgraded" and ev["files"]


def test_a_failed_write_says_failed(stage):
    FS.set_pack_choice(PLAN.pack_root, "update")
    stage["pf"] = _pf()
    stage["raise"] = RuntimeError("disk full")
    assert FS.forest_stage(PLAN, TILE, writes=True) == "failed"
    [ev] = stage["events"]
    assert ev["state"] == "failed" and ev["error"] == "disk full"


def test_a_check_that_raises_never_costs_the_airport(stage):
    stage["pf"] = OSError("unreadable dump")
    assert FS.forest_stage(PLAN, TILE, writes=True) == ""
    assert stage["events"] == []


# ── the remembered answer ───────────────────────────────────────────────

def test_the_answer_is_remembered_per_pack(choices):
    assert FS.pack_choice("/a") == ""
    FS.set_pack_choice("/a", "never")
    FS.set_pack_choice("/b", "update")
    assert (FS.pack_choice("/a"), FS.pack_choice("/b")) == ("never", "update")
    FS.set_pack_choice("/a", "")
    assert FS.pack_choice("/a") == ""
    assert FS.pack_choice("/b") == "update"
    choices.write_text("not json", encoding="utf-8", newline="")
    assert FS.pack_choice("/b") == "", "a garbled file is no answer"


def test_the_answer_lives_outside_the_pack():
    import O4_File_Names as FNAMES
    assert os.path.dirname(FS.choices_path()) == os.path.dirname(
        FNAMES.data_root_pointer_file)


# ── the user's answer (the pack_forests command) ────────────────────────

def test_never_remembers_and_writes_nothing(stage, tmp_path):
    pack = tmp_path / "Some Pack"
    pack.mkdir()
    out = FS.forest_choice(str(pack), "never", 25, 51)
    assert out["state"] == "never" and FS.pack_choice(str(pack)) == "never"
    assert stage["writes"] == []
    assert stage["events"][-1]["state"] == "never"


def test_update_remembers_and_upgrades(stage, tmp_path):
    pack = tmp_path / "Some Pack"
    pack.mkdir()
    stage["pf"] = _pf()
    out = FS.forest_choice(str(pack), "update", 25, 51)
    assert out["state"] == "upgraded" and FS.pack_choice(str(pack)) == "update"
    assert stage["writes"] == [RENAMES]
    assert [e["state"] for e in stage["events"]] == ["upgraded"]


def test_an_unknown_action_or_folder_fails_cleanly(stage, tmp_path):
    assert FS.forest_choice(str(tmp_path), "burn")["state"] == "failed"
    assert FS.forest_choice(str(tmp_path / "gone"), "never")["state"] == "failed"
    assert stage["writes"] == []


# ── Undo, on a real pack ────────────────────────────────────────────────

DUMP = ("PROPERTY sim/west 51\n"
        "POLYGON_DEF lib/g8/terrain/wet_hot_flat.for\n"
        "BEGIN_POLYGON 0 255 2\n"
        "BEGIN_WINDING\nPOLYGON_POINT 51.0 25.0\nEND_WINDING\n"
        "END_POLYGON\n")


@pytest.fixture
def real_pack(tmp_path, monkeypatch, choices):
    """A pack whose DSF a write gave the 3D upgrade (byte-copy DSFTool)."""
    tool = tmp_path / "dsftool.py"
    tool.write_text("import shutil, sys\n"
                    "shutil.copyfile(sys.argv[2], sys.argv[3])\n",
                    encoding="utf-8", newline="")
    real_run = W.subprocess.run
    monkeypatch.setattr(W.subprocess, "run", lambda args, **kw: real_run(
        [sys.executable, str(tool)] + list(args[1:]), **kw))
    from auto_patch import dsf_reader as DSFR
    monkeypatch.setattr(DSFR, "_dsftool_path", lambda: str(tool))
    monkeypatch.setattr(DSFR, "ensure_dsf_text_path", lambda *a, **k: None)
    monkeypatch.setattr(UI, "vprint", lambda *a, **k: None)
    events = []
    monkeypatch.setattr(UI, "pack_old_forests", lambda **f: events.append(f))
    B.invalidate_memo()
    pack = tmp_path / "Custom Scenery" / "Some Pack"
    dsf = pack / "Earth nav data" / "+20+050" / "+25+051.dsf"
    dsf.parent.mkdir(parents=True)
    dsf.write_bytes(DUMP.encode("utf-8"))
    yield types.SimpleNamespace(pack=pack, dsf=dsf, tool=str(tool),
                                events=events)
    B.invalidate_memo()


def _upgrade(rp, icao=""):
    plan = PM.PlacementPlan(icao, rp.pack.name, str(rp.pack), str(rp.dsf),
                            str(rp.dsf) + PM.BACKUP_SUFFIX,
                            PM.Provenance("", "1.0.test", "", {}))
    W.write_pack(str(rp.pack), plan, rp.tool, allow_live_install=True,
                 forests=RENAMES)
    assert b"broad_vhot_wet" in rp.dsf.read_bytes()


def test_undo_restores_the_original_byte_for_byte(real_pack):
    rp = real_pack
    original = rp.dsf.read_bytes()
    _upgrade(rp)
    FS.set_pack_choice(str(rp.pack), "update")
    out = FS.forest_choice(str(rp.pack), "undo")
    assert out["state"] == "undone"
    assert out["files"] == ["Earth nav data/+20+050/+25+051.dsf"]
    assert rp.dsf.read_bytes() == original
    assert FS.pack_choice(str(rp.pack)) == "", "the answer is forgotten"
    from auto_patch import object_rebake as OR
    assert OR.forest_upgraded_dsfs(str(rp.pack)) == []
    assert rp.events[-1]["state"] == "undone"


def test_undo_keeps_an_airports_seating(real_pack):
    rp = real_pack
    _upgrade(rp, icao="OTST")
    assert FS.undo(str(rp.pack)) == ["Earth nav data/+20+050/+25+051.dsf"]
    live = rp.dsf.read_text(encoding="utf-8")
    assert "wet_hot_flat" in live and "broad_vhot_wet" not in live
    doc = json.loads((rp.dsf.parent / PM.PROVENANCE_FILENAME)
                     .read_text(encoding="utf-8"))
    entry = doc["dsfs"][rp.dsf.name]
    assert "OTST" in entry["airports"] and entry[PF.RECORD_KEY] is None


def test_undo_of_another_tile_touches_nothing(real_pack):
    rp = real_pack
    _upgrade(rp)
    assert FS.undo(str(rp.pack), 10, 10) == []
    assert b"broad_vhot_wet" in rp.dsf.read_bytes()


def test_the_pack_row_counts_the_upgrade(real_pack):
    from auto_patch import object_rebake as OR
    rp = real_pack
    _upgrade(rp)
    [row] = OR.modified_packs(str(rp.pack.parent), tile="+25+051")
    assert row["forests"] == 1 and row["pack_path"] == str(rp.pack)
    [row] = OR.modified_packs(str(rp.pack.parent))
    assert row["forests"] == 1


# ── protocol 1.17 ───────────────────────────────────────────────────────

def test_the_protocol_version_is_1_17():
    assert tuple(int(p) for p in EV.PROTOCOL_VERSION.split(".")) >= (1, 17)


def test_the_wire_name_and_fields_are_frozen():
    assert EV.PackOldForests.__name__ == "PackOldForests"
    assert [f.name for f in dataclasses.fields(EV.PackOldForests)
            if f.name not in ("seq", "ts")] == [
        "pack", "pack_root", "lat", "lon", "total", "mapped", "uses",
        "first_paths", "unmapped", "first_unmapped", "can_update", "files",
        "state", "error"]
    assert EV.PackOldForests().can_update is False, "no offer without a yes"


def test_it_serialises_and_the_swift_client_matches_it():
    from o4_engine.jsonl import serialize_event

    line = json.dumps(serialize_event(EV.PackOldForests(
        pack="P", total=2, mapped=1, first_paths=["a.for"], can_update=True)))
    assert '"PackOldForests"' in line and '"first_unmapped"' in line
    swift = os.path.join(os.path.dirname(__file__), "..", "..", "Sources",
                         "SceneryKit", "OrthoEngineClient.swift")
    if not os.path.exists(swift):
        pytest.skip("Swift sources not present in this tree")
    text = open(swift, encoding="utf-8").read()
    assert 'case "PackOldForests"' in text
    assert '"pack_forests"' in text


def test_the_parallel_forwarder_carries_it():
    from o4_engine import parallel as P

    assert "PackOldForests" in P._FORWARDED_EVENT_TYPES
    event = P._rebuild_event({"event": "PackOldForests", "pack": "P",
                              "can_update": True, "state": "found"})
    assert isinstance(event, EV.PackOldForests) and event.can_update


def test_the_command_is_registered_and_never_blocks(monkeypatch):
    from o4_engine import jsonl as J
    from o4_engine.session import EngineSession

    session = EngineSession()
    assert J._build_handlers(session)["pack_forests"] == session.pack_forests
    got = []
    session.subscribe(got.append)

    def fake_choice(root, action, lat, lon):
        UI.pack_old_forests(pack="P", pack_root=root, state="never")

    monkeypatch.setattr(FS, "forest_choice", fake_choice)
    monkeypatch.setattr(UI, "engine_session", session)
    assert session.pack_forests("/p", "never", 25, 51) == {"status": "started"}
    deadline = time.time() + 10
    while not [e for e in got if isinstance(e, EV.PackOldForests)] \
            and time.time() < deadline:
        time.sleep(0.01)
    [ev] = [e for e in got if isinstance(e, EV.PackOldForests)]
    assert ev.state == "never" and ev.pack_root == "/p"


def test_the_session_hook_drops_unknown_fields():
    from o4_engine.session import EngineSession

    session = EngineSession()
    got = []
    session.subscribe(got.append)
    session.pack_old_forests(pack="P", state="found", someday_field=1)
    [ev] = [e for e in got if isinstance(e, EV.PackOldForests)]
    assert ev.pack == "P"
