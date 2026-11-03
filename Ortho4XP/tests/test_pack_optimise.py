"""#1707: "Optimise pack" in the object stage — the offer, the user's
answer, Undo and the protocol 1.31 surface.

The stage (``auto_patch.optimise_stage``) names a pack the build modifies
whose own objects draw more than 50 M triangles on the tile and whose
recipe can lighten it; a lane build (measure-only) only reports; the DSF
is rewritten only after the user said Optimise (now, or remembered for
the pack); "Never for this pack" stops the question; Undo puts the
original placements back, byte for byte when nothing else of ours is in
the DSF; Revert to default forgets the answer.  ``PackOptimise`` and the
``pack_optimise`` command are additive (``events.py`` class names ARE
the wire names; ``OrthoEngineClient.swift`` matches them as literals).
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
import pack_optimise_fixture as FX  # noqa: E402
from auto_patch import forest_stage as FS  # noqa: E402
from auto_patch import object_rebake as OR  # noqa: E402
from auto_patch import optimise_stage as OS  # noqa: E402
from auto_patch import pack_choice as PC  # noqa: E402
from auto_patch_v2.airport import pack_forests as PF  # noqa: E402
from auto_patch_v2.airport import pack_optimise as PO  # noqa: E402
from o4_engine import events as EV  # noqa: E402

PLAN = types.SimpleNamespace(pack_root="/X/Custom Scenery/Some Pack")
TILE = types.SimpleNamespace(lat=25, lon=51)
HEAVY = OS.PackWeight("Some Pack", "/p/+25+051.dsf", 275_000_000,
                      221_000_000, 2720, {})


@pytest.fixture
def choices(tmp_path, monkeypatch):
    paths = {n: str(tmp_path / "prefs" / n)
             for n in (OS.CHOICES_NAME, FS.CHOICES_NAME)}
    monkeypatch.setattr(PC, "store_path", lambda name: paths[name])
    return paths


@pytest.fixture
def stage(monkeypatch, choices):
    """Stub the check and the write; collect what the UI hook was told."""
    seen = {"events": [], "writes": [], "pw": None, "raise": None}

    def fake_check(pack_root, lat, lon, *, read_only):
        seen["read_only"] = read_only
        return seen["pw"]

    def fake_write(pw, pack_root, recipe):
        if seen["raise"]:
            raise seen["raise"]
        seen["writes"].append(dict(recipe))

    monkeypatch.setattr(OS, "check", fake_check)
    monkeypatch.setattr(OS, "_write", fake_write)
    monkeypatch.setattr(UI, "pack_optimise", lambda **f: seen["events"].append(f))
    monkeypatch.setattr(UI, "vprint", lambda *a, **k: None)
    return seen


# ── the stage's decision ────────────────────────────────────────────────

def test_a_heavy_pack_is_offered_and_nothing_is_written(stage):
    stage["pw"] = HEAVY
    assert OS.optimise_stage(PLAN, TILE, writes=True) == "found"
    assert stage["writes"] == []
    [ev] = stage["events"]
    assert ev["state"] == "found" and ev["can_optimise"] is True
    assert (ev["dedupe"], ev["est_tris_before"], ev["est_tris_after"]) == (
        2720, 275_000_000, 221_000_000)


def test_a_light_pack_is_not_offered(stage):
    stage["pw"] = HEAVY._replace(tris_before=11_000_000)
    assert OS.optimise_stage(PLAN, TILE, writes=True) == ""
    stage["pw"] = HEAVY._replace(dedupe=0)
    assert OS.optimise_stage(PLAN, TILE, writes=True) == ""
    assert stage["events"] == []


def test_update_writes_and_never_stops_the_question(stage):
    stage["pw"] = HEAVY
    OS.STORE.remember(PLAN.pack_root, "update")
    assert OS.optimise_stage(PLAN, TILE, writes=False) == "found", \
        "a lane build only reports"
    assert stage["read_only"] is True and stage["writes"] == []
    assert OS.optimise_stage(PLAN, TILE, writes=True) == "optimised"
    assert stage["writes"] == [PO.default_recipe()]
    OS.STORE.remember(PLAN.pack_root, "never")
    assert OS.optimise_stage(PLAN, TILE, writes=True) == "never"


def test_a_pack_already_optimised_is_current(stage):
    stage["pw"] = HEAVY._replace(optimised=PO.default_recipe())
    assert OS.optimise_stage(PLAN, TILE, writes=True) == "current"
    assert stage["events"] == [] and stage["writes"] == []


def test_a_failed_write_says_so_and_never_raises(stage):
    stage["pw"], stage["raise"] = HEAVY, RuntimeError("boom")
    OS.STORE.remember(PLAN.pack_root, "update")
    assert OS.optimise_stage(PLAN, TILE, writes=True) == "failed"
    assert stage["events"][-1]["state"] == "failed"


def test_the_answers_are_their_own_store(choices):
    OS.STORE.remember("/a", "never")
    assert OS.STORE.choice("/a") == "never" and FS.pack_choice("/a") == ""
    OS.STORE.remember("/a", "")
    assert OS.STORE.choice("/a") == ""


# ── on a real pack ──────────────────────────────────────────────────────

@pytest.fixture
def rp(tmp_path, monkeypatch, choices):
    rp = FX.make_pack(tmp_path, monkeypatch)
    rp.events = []
    monkeypatch.setattr(UI, "pack_optimise", lambda **f: rp.events.append(f))
    monkeypatch.setattr(UI, "pack_old_forests", lambda **f: None)
    from auto_patch import object_stage as OST
    from auto_patch_v2.airport.dsf_write import pristine_dsf_path

    def fake_dump(pack_root, lat, lon, *, read_only):
        pristine = pristine_dsf_path(str(rp.dsf))
        return OST._PackDump(rp.pack.name, str(rp.dsf), pristine, pristine,
                             str(tmp_path))
    monkeypatch.setattr(OST, "pack_dump", fake_dump)
    return rp


def test_optimise_then_undo_is_byte_identical(rp):
    original = rp.dsf.read_bytes()
    out = OS.optimise_choice(str(rp.pack), "update", 25, 51)
    assert out["state"] == "optimised" and len(FX.rows(rp)) == 4
    assert OS.STORE.choice(str(rp.pack)) == "update"
    assert rp.events[-1]["state"] == "optimised" and rp.events[-1]["dedupe"] == 2
    [row] = OR.modified_packs(str(rp.pack.parent), tile="+25+051")
    assert row["optimised"] == 2 and row["forests"] == 0
    out = OS.optimise_choice(str(rp.pack), "undo")
    assert out["state"] == "undone"
    assert out["files"] == ["Earth nav data/+20+050/+25+051.dsf"]
    assert rp.dsf.read_bytes() == original
    assert OS.STORE.choice(str(rp.pack)) == ""
    assert OR.recorded_dsfs(str(rp.pack), PO.RECORD_KEY) == []


def test_undo_keeps_the_3d_trees_and_vice_versa(rp):
    FX.write(rp, forests=FX.RENAMES)
    OS.optimise_choice(str(rp.pack), "update", 25, 51)
    assert OS.undo(str(rp.pack)) == ["Earth nav data/+20+050/+25+051.dsf"]
    assert "broad_vhot_wet" in rp.dsf.read_text(encoding="utf-8")
    assert len(FX.rows(rp)) == 6
    OS.optimise_choice(str(rp.pack), "update", 25, 51)
    assert FS.undo(str(rp.pack)) == ["Earth nav data/+20+050/+25+051.dsf"]
    assert "wet_hot_flat" in rp.dsf.read_text(encoding="utf-8")
    assert len(FX.rows(rp)) == 4
    assert PF.recorded(FX.entry(rp), FX.entry(rp)["backup_sha256"]) == {}


def test_revert_to_default_forgets_the_answer(rp):
    OS.optimise_choice(str(rp.pack), "update", 25, 51)
    OR.restore_detail(str(rp.pack))
    assert OS.STORE.choice(str(rp.pack)) == ""


def test_the_reuse_key_follows_the_record(rp):
    assert OS.recorded_key(str(rp.pack), 25, 51) == ""
    OS.optimise_choice(str(rp.pack), "update", 25, 51)
    assert OS.recorded_key(str(rp.pack), 25, 51) == \
        FX.entry(rp)[PO.RECORD_KEY]["key"]


def test_a_bad_action_or_folder_fails_cleanly(rp, tmp_path):
    assert OS.optimise_choice(str(rp.pack), "burn")["state"] == "failed"
    assert OS.optimise_choice(str(tmp_path / "gone"), "never")["state"] == "failed"


# ── protocol 1.31 ───────────────────────────────────────────────────────

def test_the_protocol_version_is_1_31():
    assert tuple(int(p) for p in EV.PROTOCOL_VERSION.split(".")) >= (1, 31)


def test_the_wire_name_and_fields_are_frozen():
    assert EV.PackOptimise.__name__ == "PackOptimise"
    assert [f.name for f in dataclasses.fields(EV.PackOptimise)
            if f.name not in ("seq", "ts")] == [
        "pack", "pack_root", "lat", "lon", "dedupe", "est_tris_before",
        "est_tris_after", "can_optimise", "swapped", "files", "state",
        "error"]
    assert EV.PackOptimise().can_optimise is False, "no offer without a yes"


def test_it_serialises_and_the_swift_client_matches_it():
    from o4_engine.jsonl import serialize_event

    line = json.dumps(serialize_event(EV.PackOptimise(pack="P", dedupe=3,
                                                      can_optimise=True)))
    assert '"PackOptimise"' in line and '"est_tris_before"' in line
    swift = os.path.join(os.path.dirname(__file__), "..", "..", "Sources",
                         "SceneryKit", "OrthoEngineClient.swift")
    if not os.path.exists(swift):
        pytest.skip("Swift sources not present in this tree")
    text = open(swift, encoding="utf-8").read()
    assert 'case "PackOptimise"' in text and '"pack_optimise"' in text


def test_the_parallel_forwarder_carries_it():
    from o4_engine import parallel as P

    assert "PackOptimise" in P._FORWARDED_EVENT_TYPES
    event = P._rebuild_event({"event": "PackOptimise", "pack": "P",
                              "can_optimise": True, "state": "found"})
    assert isinstance(event, EV.PackOptimise) and event.can_optimise


def test_the_command_is_registered_and_never_blocks(monkeypatch):
    from o4_engine import jsonl as J
    from o4_engine.session import EngineSession

    session = EngineSession()
    assert J._build_handlers(session)["pack_optimise"] == session.pack_optimise
    got = []
    session.subscribe(got.append)

    def fake_choice(root, action, lat, lon):
        UI.pack_optimise(pack="P", pack_root=root, state="never", junk=1)

    monkeypatch.setattr(OS, "optimise_choice", fake_choice)
    monkeypatch.setattr(UI, "engine_session", session)
    assert session.pack_optimise("/p", "never", 25, 51) == {"status": "started"}
    deadline = time.time() + 10
    while not [e for e in got if isinstance(e, EV.PackOptimise)] \
            and time.time() < deadline:
        time.sleep(0.01)
    [ev] = [e for e in got if isinstance(e, EV.PackOptimise)]
    assert ev.state == "never" and ev.pack_root == "/p"
