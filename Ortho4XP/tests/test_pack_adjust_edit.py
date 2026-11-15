"""The pack row's Adjust… (owner 2026-11-15T13:12Z): "an option on any
modified pack to adjust the settings rather than just reset, so the user
can change what's hidden or optimized without saving to rebuild the
tile".

``pack_adjust`` ``"adjust"`` reports every row and Optimise step ticked as
the pack is now; ``"change"`` writes ONLY what differs — through each
row's own stage, whose DSF rewrite (``pack_rewrite``) is stubbed here so
every write is counted — and says ``rebuild`` when the change is one the
tile's mesh reads (the terrain objects: ``terrain_cut_stage``).  The
checks are stubbed (their own twins: ``test_pack_adjust``,
``auto_patch_v2/test_pack_drapes``, ``test_pack_optimise_steps``).
"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "src"))

import O4_UI_Utils as UI  # noqa: E402
from auto_patch import adjust_edit as AE  # noqa: E402
from auto_patch import adjust_stage as AS  # noqa: E402
from auto_patch import drape_stage as DS  # noqa: E402
from auto_patch import forest_stage as FS  # noqa: E402
from auto_patch import optimise_stage as OS  # noqa: E402
from auto_patch import pack_rewrite as PR  # noqa: E402
from auto_patch import terrain_cut_stage as TC  # noqa: E402
from auto_patch_v2.airport import pack_art as PA  # noqa: E402
from auto_patch_v2.airport import pack_forests as PF  # noqa: E402

OLD = PF.OldForest(0, "lib/g8/terrain/wet_hot_flat.for", 2,
                   "lib/g8/broad_vhot_wet.for")
PHOTO = PA.MissingDef("polygon", 3, "ortho/photo.pol", 4)
SHEET = PA.MissingDef("polygon", 5, "ground/grass.pol", 2)
HILL = PA.MissingDef("object", 7, "objects/hill.obj", 1)
STEPS = ({"key": "dedupe", "count": 4, "tris": 1000, "mb": 0.0},
         {"key": "swap", "count": 2, "tris": 500, "mb": 0.0},
         {"key": "textures", "count": 3, "tris": 0, "mb": 12.0})


@pytest.fixture
def pack(tmp_path, monkeypatch):
    """A pack whose tile DSF hides its ground sheets and carries no other
    change; every DSF write and optimise answer is recorded."""
    root = tmp_path / "Custom Scenery" / "Some Pack"
    root.mkdir(parents=True)
    from auto_patch import pack_choice as PC
    monkeypatch.setattr(PC, "store_path",
                        lambda name: str(tmp_path / "prefs" / name))
    monkeypatch.setattr(FS, "choices_path",
                        lambda: str(tmp_path / "prefs" / "forests.json"))
    seen = {"root": str(root), "writes": [], "undos": [], "optimise": [],
            "hidden": (SHEET,), "upgraded": {},
            "pw": OS.PackWeight("Some Pack", "/p/d.dsf", 9, 5, 4, {},
                                steps=STEPS)}

    def check_all(*_a, **_k):
        rows = {"drapes": (PHOTO,), "ground": (SHEET,), "terrain": (HILL,)}
        return {k: DS.PackDrapes("Some Pack", "/p/d.dsf", v, seen["hidden"],
                                 tuple(m for o, w in rows.items() if o != k
                                       for m in w))
                for k, v in rows.items()}

    monkeypatch.setattr(DS, "check_all", check_all)
    monkeypatch.setattr(FS, "check", lambda *a, **k: FS.PackForests(
        "Some Pack", "/p/d.dsf", (OLD,), seen["upgraded"],
        PF.UPGRADE_VERSION if seen["upgraded"] else 0))
    monkeypatch.setattr(OS, "check", lambda *a, **k: seen["pw"])
    monkeypatch.setattr(AS, "_flatten", lambda root, *, writes: "")
    monkeypatch.setattr(PR, "rewrite_dsf", lambda root, name, dsf, **c:
                        seen["writes"].append(c) or dsf + ".anchor_bak")
    monkeypatch.setattr(PR, "undo_recorded", lambda root, lat, lon, key, fn,
                        **k: seen["undos"].append(key) or ["d.dsf"])

    def optimise_choice(root, action, lat=None, lon=None, steps=None):
        seen["optimise"].append((action, None if steps is None
                                 else tuple(steps)))
        return {"state": "optimised" if action == "update" else "undone",
                "files": ["d.dsf"] if action == "undo" else []}

    monkeypatch.setattr(OS, "optimise_choice", optimise_choice)
    for name in ("pack_adjust", "pack_old_forests", "pack_optimise", "vprint"):
        monkeypatch.setattr(UI, name, lambda *a, **k: None)
    DS.GROUND.store.remember(str(root), "update")
    return seen


def _report(pack):
    return AS.adjust_choice(pack["root"], "adjust", 25, 51)


def _change(pack, items, steps=None):
    return AS.adjust_choice(pack["root"], "change", 25, 51, items=items,
                            shown=["trees", "drapes", "ground", "terrain"],
                            steps=steps)


def test_the_report_ticks_the_pack_as_it_is(pack):
    out = _report(pack)
    assert out["state"] == "adjust"
    assert [(r["key"], r["checked"], r["applied"], r["rebuild"])
            for r in out["items"]] == [
        ("trees", False, False, False), ("drapes", False, False, False),
        ("ground", True, True, False), ("terrain", False, False, True)], \
        "pre-filled with the pack's choices; only the terrain row rebuilds"
    assert [(s["key"], s["checked"]) for s in out["steps"]] == [
        ("dedupe", False), ("swap", False), ("textures", False)], \
        "a pack not optimised: every step off"
    assert pack["writes"] == pack["undos"] == pack["optimise"] == []


def test_nothing_changed_writes_nothing(pack):
    out = _change(pack, ["ground"], steps=[])
    assert out["state"] == "none" and out["files"] == []
    assert out["rebuild"] is False
    assert pack["writes"] == pack["undos"] == pack["optimise"] == [], \
        "the same ticks rewrite no file: the pack stays byte for byte"


def test_only_the_changed_row_is_written(pack):
    out = _change(pack, ["ground", "drapes"])
    assert out["state"] == "applied" and out["rebuild"] is False
    assert len(pack["writes"]) == 1 and pack["undos"] == []
    assert set(pack["writes"][0]["drapes"]) == {PHOTO, SHEET}, \
        "the photos hidden, the ground sheets kept hidden"
    assert DS.PHOTOS.store.choice(pack["root"]) == "update"
    assert pack["optimise"] == [], "steps=None leaves Optimise alone"


def test_an_untick_puts_an_applied_change_back(pack):
    out = _change(pack, [])
    assert pack["undos"] == ["hidden_drapes"] and pack["writes"] == []
    assert out["state"] == "applied" and out["files"] == ["d.dsf"]
    assert DS.GROUND.store.choice(pack["root"]) == "never"


def test_the_terrain_objects_rebuild_the_tile(pack):
    out = _change(pack, ["ground", "terrain"])
    assert out["rebuild"] is True
    assert DS.TERRAIN.store.choice(pack["root"]) == "update"
    rec = {"hideable": True}
    assert TC._hidden(rec, pack["root"]), \
        "the tile's cut reads the answer: the model is no longer cut"
    pack["hidden"] += (HILL,)
    out = _change(pack, ["ground"])
    assert out["rebuild"] is True and not TC._hidden(rec, pack["root"])


def test_a_build_question_says_rebuild_for_the_terrain_objects(pack):
    out = AS.adjust_choice(pack["root"], "update", 25, 51,
                           items=["terrain"], shown=["terrain"])
    assert out["rebuild"] is True
    out = AS.adjust_choice(pack["root"], "update", 25, 51,
                           items=["drapes"], shown=["drapes"])
    assert out["rebuild"] is False


def test_the_optimise_steps_change_only_when_they_differ(pack):
    pack["pw"] = pack["pw"]._replace(optimised={"key": "k"},
                                     chosen=("dedupe", "swap"))
    out = _report(pack)
    assert [(s["key"], s["checked"]) for s in out["steps"]] == [
        ("dedupe", True), ("swap", True), ("textures", False)]
    assert _change(pack, ["ground"], steps=["swap", "dedupe"])["state"] == "none"
    assert pack["optimise"] == []
    _change(pack, ["ground"], steps=["dedupe", "textures"])
    assert pack["optimise"] == [("update", ("dedupe", "textures"))]
    out = _change(pack, ["ground"], steps=[])
    assert pack["optimise"][-1] == ("undo", None) and out["files"] == ["d.dsf"]
    assert OS.STORE.choice(pack["root"]) == "never"
    assert pack["writes"] == [], "no adjustment row was touched"


def test_a_pack_with_nothing_to_adjust_says_none(pack, monkeypatch):
    monkeypatch.setattr(DS, "check_all", lambda *a, **k: {})
    monkeypatch.setattr(FS, "check", lambda *a, **k: None)
    monkeypatch.setattr(OS, "check", lambda *a, **k: None)
    assert _report(pack)["state"] == "none"
