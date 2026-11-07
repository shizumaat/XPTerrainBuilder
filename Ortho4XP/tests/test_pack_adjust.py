"""#1916: an airport pack's ADJUSTMENTS as one question — the object
stage's report, the user's answer and the wire surface.

One ``PackAdjust`` per pack and tile lists every row that applies: the
3D trees and the draped photos (each a choice), and the apt.dat's
flatten flag (automatic: removed with no question).  The trees no longer
ask on their own.  The answer goes through each row's own stage: a row
ticked is "update", a row shown and unticked "never".  The checks are
stubbed (their own twins: ``test_pack_old_forests``, ``auto_patch_v2/
test_pack_drapes``, ``auto_patch_v2/test_apt_flatten``).
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
from auto_patch import adjust_stage as AS  # noqa: E402
from auto_patch import drape_stage as DS  # noqa: E402
from auto_patch import forest_stage as FS  # noqa: E402
from auto_patch_v2.airport import pack_art as PA  # noqa: E402
from auto_patch_v2.airport import pack_forests as PF  # noqa: E402
from o4_engine import events as EV  # noqa: E402

TILE = types.SimpleNamespace(lat=25, lon=51)
OLD = PF.OldForest(0, "lib/g8/terrain/wet_hot_flat.for", 2,
                   "lib/g8/broad_vhot_wet.for")
PHOTO = PA.MissingDef("polygon", 3, "ortho/photo.pol", 4)


@pytest.fixture
def stage(tmp_path, monkeypatch):
    pack = tmp_path / "Custom Scenery" / "Some Pack"
    pack.mkdir(parents=True)
    seen = {"adjust": [], "forests": [], "flatten": "removed",
            "pf": FS.PackForests("Some Pack", "/p/d.dsf", (OLD,), {}),
            "pd": DS.PackDrapes("Some Pack", "/p/d.dsf", (PHOTO,), ()),
            "answers": []}
    monkeypatch.setattr(FS, "choices_path",
                        lambda: str(tmp_path / "prefs" / "forests.json"))
    from auto_patch import pack_choice as PC
    monkeypatch.setattr(PC, "store_path",
                        lambda name: str(tmp_path / "prefs" / name))
    monkeypatch.setattr(FS, "check", lambda *a, **k: seen["pf"])
    monkeypatch.setattr(DS, "check", lambda *a, **k: seen["pd"])
    monkeypatch.setattr(AS, "_flatten", lambda root, *, writes: seen["flatten"])
    monkeypatch.setattr(UI, "pack_adjust", lambda **f: seen["adjust"].append(f))
    monkeypatch.setattr(UI, "pack_old_forests",
                        lambda **f: seen["forests"].append(f))
    monkeypatch.setattr(UI, "vprint", lambda *a, **k: None)
    seen["plan"] = types.SimpleNamespace(pack_root=str(pack))
    return seen


def test_one_question_lists_every_row(stage):
    out = AS.adjust_stage(stage["plan"], TILE, writes=True)
    assert out == {"flatten": "removed", "trees": "found", "drapes": "found"}
    assert stage["forests"] == [], "the trees no longer ask on their own"
    [ev] = stage["adjust"]
    assert ev["state"] == "found" and (ev["lat"], ev["lon"]) == (25, 51)
    assert [(r["key"], r["automatic"]) for r in ev["items"]] == [
        ("trees", False), ("drapes", False), ("flatten", True)]
    assert ev["items"][1]["count"] == 1 and ev["items"][1]["uses"] == 4


def test_the_flatten_flag_alone_asks_nothing(stage):
    stage["pf"] = stage["pd"] = None
    assert AS.adjust_stage(stage["plan"], TILE, writes=True)["flatten"] == "removed"
    assert stage["adjust"] == []


def test_a_row_already_answered_never_is_left_out(stage):
    DS.STORE.remember(stage["plan"].pack_root, "never")
    AS.adjust_stage(stage["plan"], TILE, writes=True)
    [ev] = stage["adjust"]
    assert [r["key"] for r in ev["items"]] == ["trees", "flatten"]


def _answers(monkeypatch, stage):
    def tree(root, action, lat, lon):
        stage["answers"].append(("trees", action))
        return {"files": ["a.dsf"] if action == "update" else []}

    def drape(root, action, lat, lon):
        stage["answers"].append(("drapes", action))
        return action, []

    monkeypatch.setattr(FS, "forest_choice", tree)
    monkeypatch.setattr(DS, "drape_choice", drape)


def test_apply_ticked_updates_unticked_never(stage, monkeypatch):
    _answers(monkeypatch, stage)
    out = AS.adjust_choice(stage["plan"].pack_root, "update", 25, 51,
                           items=["trees"], shown=["trees", "drapes"])
    assert stage["answers"] == [("trees", "update"), ("drapes", "never")]
    assert out["state"] == "applied" and out["files"] == ["a.dsf"]
    assert stage["adjust"][-1]["state"] == "applied"


def test_never_and_undo_go_to_every_row(stage, monkeypatch):
    _answers(monkeypatch, stage)
    root = stage["plan"].pack_root
    assert AS.adjust_choice(root, "never", shown=["drapes"])["state"] == "never"
    assert stage["answers"] == [("drapes", "never")]
    AS.adjust_choice(root, "undo")
    assert stage["answers"][1:] == [("trees", "undo"), ("drapes", "undo")]


def test_ask_is_the_report(stage):
    out = AS.adjust_choice(stage["plan"].pack_root, "ask", 25, 51)
    assert out["state"] == "ask"
    assert [r["key"] for r in out["items"]] == ["trees", "drapes", "flatten"]


def test_a_bad_action_or_folder_fails_cleanly(stage, tmp_path):
    assert AS.adjust_choice(stage["plan"].pack_root, "explode")["state"] == "failed"
    assert AS.adjust_choice(str(tmp_path / "nope"), "ask")["state"] == "failed"


# ── the wire ────────────────────────────────────────────────────────────

def test_the_wire_name_fields_and_flag():
    assert EV.PackAdjust.__name__ == "PackAdjust"
    assert [f.name for f in dataclasses.fields(EV.PackAdjust)
            if f.name not in ("seq", "ts")] == [
        "pack", "pack_root", "lat", "lon", "items", "files", "state", "error"]
    assert "pack_adjust" in EV.CAPABILITIES


def test_it_serialises_and_the_swift_client_matches_it():
    from o4_engine.jsonl import serialize_event
    line = json.dumps(serialize_event(EV.PackAdjust(
        pack="P", items=[{"key": "drapes", "count": 2}])))
    assert '"PackAdjust"' in line and '"items"' in line
    swift = os.path.join(os.path.dirname(__file__), "..", "..", "Sources",
                         "SceneryKit", "OrthoEngineClient.swift")
    if not os.path.exists(swift):
        pytest.skip("Swift sources not present in this tree")
    text = open(swift, encoding="utf-8").read()
    assert 'case "PackAdjust"' in text and '"pack_adjust"' in text


def test_the_parallel_forwarder_carries_it():
    from o4_engine import parallel as P
    assert "PackAdjust" in P._FORWARDED_EVENT_TYPES
    ev = P._rebuild_event({"event": "PackAdjust", "pack": "P",
                           "items": [{"key": "trees"}], "state": "found"})
    assert isinstance(ev, EV.PackAdjust) and ev.items[0]["key"] == "trees"


def test_the_command_is_registered_and_never_blocks(monkeypatch):
    from o4_engine import jsonl as J
    from o4_engine.session import EngineSession

    session = EngineSession()
    assert J._build_handlers(session)["pack_adjust"] == session.pack_adjust
    got = []
    session.subscribe(got.append)

    def fake(root, action, lat, lon, items=None, shown=None):
        UI.pack_adjust(pack="P", pack_root=root, state="never",
                       items=[{"key": k} for k in shown or ()])

    monkeypatch.setattr(AS, "adjust_choice", fake)
    monkeypatch.setattr(UI, "engine_session", session)
    assert session.pack_adjust("/p", "never", 25, 51,
                               shown=["drapes"]) == {"status": "started"}
    deadline = time.time() + 10
    while not [e for e in got if isinstance(e, EV.PackAdjust)] \
            and time.time() < deadline:
        time.sleep(0.01)
    [ev] = [e for e in got if isinstance(e, EV.PackAdjust)]
    assert ev.state == "never" and ev.items == [{"key": "drapes"}]
