"""#1916: an airport pack's ADJUSTMENTS as one question — the object
stage's report, the user's answer and the wire surface.

One ``PackAdjust`` per pack and tile lists every row that applies: the
3D trees, the draped photos and the large draped ground textures (each a
choice; the ground textures unticked when asked, #1962), and the
apt.dat's flatten flag (automatic: removed with no question).  Every
other pack on the tile — an airport pack not built, a companion that
lays the airport's photos — is asked on its own, once per tile build
(#1968, RULINGS 2026-11-09a (9)).  The trees no longer
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
SHEET = PA.MissingDef("polygon", 5, "ground/grass.pol", 2)


@pytest.fixture
def stage(tmp_path, monkeypatch):
    pack = tmp_path / "Custom Scenery" / "Some Pack"
    pack.mkdir(parents=True)
    seen = {"adjust": [], "forests": [], "flatten": "removed",
            "pf": FS.PackForests("Some Pack", "/p/d.dsf", (OLD,), {}),
            "pd": DS.PackDrapes("Some Pack", "/p/d.dsf", (PHOTO,), (), (SHEET,)),
            "gd": DS.PackDrapes("Some Pack", "/p/d.dsf", (SHEET,), (), (PHOTO,)),
            "scanned": [], "answers": []}
    monkeypatch.setattr(FS, "choices_path",
                        lambda: str(tmp_path / "prefs" / "forests.json"))
    from auto_patch import pack_choice as PC
    monkeypatch.setattr(PC, "store_path",
                        lambda name: str(tmp_path / "prefs" / name))
    monkeypatch.setattr(FS, "check", lambda *a, **k: seen["pf"])
    monkeypatch.setattr(DS, "check_all", lambda *a, **k: {
        k_: v for k_, v in (("drapes", seen["pd"]), ("ground", seen["gd"]))
        if v is not None})
    monkeypatch.setattr(DS, "scanned", lambda d, lat, lon: [
        r for r in seen["scanned"] if os.path.dirname(r) == d])
    monkeypatch.setattr(AS, "_flatten", lambda root, *, writes: seen["flatten"])
    monkeypatch.setattr(UI, "pack_adjust", lambda **f: seen["adjust"].append(f))
    monkeypatch.setattr(UI, "pack_old_forests",
                        lambda **f: seen["forests"].append(f))
    monkeypatch.setattr(UI, "vprint", lambda *a, **k: None)
    seen["plan"] = types.SimpleNamespace(pack_root=str(pack))
    return seen


def test_one_question_lists_every_row(stage):
    out = AS.adjust_stage(stage["plan"], TILE, writes=True)
    assert out == {"flatten": "removed", "trees": "found", "drapes": "found",
                   "ground": "found"}
    assert stage["forests"] == [], "the trees no longer ask on their own"
    [ev] = stage["adjust"]
    assert ev["state"] == "found" and (ev["lat"], ev["lon"]) == (25, 51)
    assert [(r["key"], r["automatic"], r["checked"]) for r in ev["items"]] == [
        ("trees", False, True), ("drapes", False, True),
        ("ground", False, False), ("flatten", True, True)], \
        "the ground textures are offered unticked (RULINGS 2026-11-09a (3))"
    assert ev["items"][1]["count"] == 1 and ev["items"][1]["uses"] == 4
    assert ev["items"][2]["count"] == 1 and ev["items"][2]["uses"] == 2


def test_the_ground_textures_are_never_hidden_unasked(stage, monkeypatch):
    hidden = []
    monkeypatch.setattr(DS, "_hide", lambda pd, root, kind: hidden.append(
        kind.key) or "hidden")
    DS.STORE.remember(stage["plan"].pack_root, "update")
    out = AS.adjust_stage(stage["plan"], TILE, writes=True)
    assert out["drapes"] == "hidden" and out["ground"] == "found"
    assert hidden == ["drapes"]
    DS.GROUND.store.remember(stage["plan"].pack_root, "update")
    assert AS.adjust_stage(stage["plan"], TILE, writes=True)["ground"] == "hidden"


def test_every_pack_on_the_tile_is_asked_once(stage, tmp_path):
    other = tmp_path / "Custom Scenery" / "Overlay Pack"
    other.mkdir()
    stage["scanned"] = [stage["plan"].pack_root, str(other)]
    stage["pf"] = None
    asked: set = set()
    AS.adjust_stage(stage["plan"], TILE, writes=True, asked=asked)
    assert AS.adjust_stage(stage["plan"], TILE, writes=True,
                           asked=asked) == {}, "a second airport of the pack"
    AS.tile_stage(TILE, writes=True, asked=asked)
    own, comp = stage["adjust"]
    assert own["pack_root"] == stage["plan"].pack_root, \
        "the built pack is not asked again by the tile's scan"
    assert comp["pack"] == "Overlay Pack" and comp["pack_root"] == str(other)
    assert [r["key"] for r in comp["items"]] == ["drapes", "ground"]


def test_a_case_folding_file_system_keeps_the_pack_name(stage, tmp_path,
                                                        monkeypatch):
    """Windows CI (#1994): ``asked`` held the case-folded key, so the tile
    scan re-read a lower-cased Custom Scenery folder and named its packs
    in lower case.  The ask still matches across case where the file
    system folds it (``normcase`` as on Windows)."""
    monkeypatch.setattr(os.path, "normcase", str.lower)
    asked: set = set()
    assert AS._first_ask(stage["plan"].pack_root, asked)
    assert not AS._first_ask(stage["plan"].pack_root.upper(), asked)
    assert asked == {os.path.normpath(stage["plan"].pack_root)}
    test_every_pack_on_the_tile_is_asked_once(stage, tmp_path)


def test_the_tile_scan_asks_with_no_airport_built(stage, tmp_path):
    other = tmp_path / "Custom Scenery" / "Unbuilt Airport"
    other.mkdir()
    stage["scanned"] = [str(other)]
    AS.tile_stage(TILE, writes=False,
                  scenery_dirs=[str(tmp_path / "Custom Scenery")])
    [ev] = stage["adjust"]
    assert ev["pack"] == "Unbuilt Airport", "built or not (RULINGS 2026-11-09a (9))"
    assert [r["key"] for r in ev["items"]] == ["drapes", "ground"], \
        "the scan asks the drape rows only"


def test_the_flatten_flag_alone_asks_nothing(stage):
    stage["pf"] = stage["pd"] = stage["gd"] = None
    assert AS.adjust_stage(stage["plan"], TILE, writes=True)["flatten"] == "removed"
    assert stage["adjust"] == []


def test_a_row_already_answered_never_is_left_out(stage):
    DS.STORE.remember(stage["plan"].pack_root, "never")
    AS.adjust_stage(stage["plan"], TILE, writes=True)
    [ev] = stage["adjust"]
    assert [r["key"] for r in ev["items"]] == ["trees", "ground", "flatten"]


def _answers(monkeypatch, stage):
    def tree(root, action, lat, lon):
        stage["answers"].append(("trees", action))
        return {"files": ["a.dsf"] if action == "update" else []}

    def drape(root, action, lat, lon, kind=DS.PHOTOS):
        stage["answers"].append((kind.key, action))
        return action, []

    monkeypatch.setattr(FS, "forest_choice", tree)
    monkeypatch.setattr(DS, "drape_choice", drape)


def test_apply_ticked_updates_unticked_never(stage, monkeypatch):
    _answers(monkeypatch, stage)
    out = AS.adjust_choice(stage["plan"].pack_root, "update", 25, 51,
                           items=["trees", "ground"],
                           shown=["trees", "drapes", "ground"])
    assert stage["answers"] == [("trees", "update"), ("drapes", "never"),
                                ("ground", "update")]
    assert out["state"] == "applied" and out["files"] == ["a.dsf"]
    assert stage["adjust"][-1]["state"] == "applied"


def test_never_and_undo_go_to_every_row(stage, monkeypatch):
    _answers(monkeypatch, stage)
    root = stage["plan"].pack_root
    assert AS.adjust_choice(root, "never", shown=["drapes"])["state"] == "never"
    assert stage["answers"] == [("drapes", "never")]
    AS.adjust_choice(root, "undo")
    assert stage["answers"][1:] == [("trees", "undo"), ("drapes", "undo"),
                                    ("ground", "undo")]


def test_ask_is_the_report(stage):
    out = AS.adjust_choice(stage["plan"].pack_root, "ask", 25, 51)
    assert out["state"] == "ask"
    assert [r["key"] for r in out["items"]] == ["trees", "drapes", "ground",
                                                "flatten"]


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


def test_the_object_stage_scans_the_tile_with_no_airport_placed(tmp_path,
                                                                monkeypatch):
    """RULINGS 2026-11-09a (9): the tile's scan runs whatever return the
    object stage takes — here the tile has no placement plan at all."""
    from auto_patch import object_stage as OS
    from auto_patch import post_mesh as PM
    scans = []
    monkeypatch.setattr(OS, "restore_unpatched_packs", lambda tile: {
        "restored": 0, "recomposed": 0})
    monkeypatch.setattr(OS, "restore_stopped_build", lambda *a: None,
                        raising=False)
    monkeypatch.setattr(PM, "object_anchor_worklist_path",
                        lambda tile: str(tmp_path / "patches" / "w.json"))
    monkeypatch.setattr(AS, "tile_stage", lambda tile, **k: scans.append(k))
    tile = types.SimpleNamespace(lat=25, lon=51, build_dir=str(tmp_path),
                                 modify_custom_airports=True)
    OS.rebake_after_mesh(tile)
    assert len(scans) == 1 and scans[0]["asked"] == set()
    tile.modify_custom_airports = False
    OS.rebake_after_mesh(tile)
    assert len(scans) == 1, "the user's switch stands the scan down too"
