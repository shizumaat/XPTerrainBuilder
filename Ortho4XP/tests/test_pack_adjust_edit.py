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
    from auto_patch_v2.airport import pack_choice as PC
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
    # the user declined the terrain row (a pack with no answer hides it, #2285)
    DS.TERRAIN.store.remember(str(root), "never")
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


def test_a_pack_with_no_terrain_answer_hides_the_offer(pack):
    """#2285: with no answer the terrain row is "update" -- the report
    ticks it and the tile's cut reads it hidden."""
    DS.TERRAIN.store.remember(pack["root"], "")
    assert DS.TERRAIN.store.choice(pack["root"]) == "update"
    [row] = [r for r in _report(pack)["items"] if r["key"] == "terrain"]
    assert row["checked"] is True and row["applied"] is False
    assert TC._hidden({"resource": "objects/hill.obj", "hideable": True}, pack["root"])
    assert not TC._hidden({"resource": "objects/rock.obj"}, pack["root"])


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


def test_the_terrain_row_lists_every_object_and_takes_per_object_answers(pack):
    """#2272: the build remembered two recognised terrain objects, one
    offered (quality elevation models it), one not; the Adjust… row lists
    both, and a per-object tick that differs from the offer is an answer
    that moves the set the row hides -- and the tile's cut with it."""
    from auto_patch_v2.airport import pack_choice as PC
    root = pack["root"]
    DS.terrain_models(root, ["objects/hill.obj", "objects/rock.obj"])
    DS.terrain_paths(root, ["objects/hill.obj"])
    [row] = [r for r in _report(pack)["items"] if r["key"] == "terrain"]
    assert row["objects"] == [
        {"path": "objects/hill.obj", "hideable": True, "hidden": True},
        {"path": "objects/rock.obj", "hideable": False, "hidden": False}]
    out = _change(pack, ["ground", "terrain"])
    assert out["rebuild"] is True
    assert PC.hidden_terrain(root) == {"objects/hill.obj"}
    # keep the offered hill, hide the rock the build kept
    out = AS.adjust_choice(root, "change", 25, 51, items=["ground", "terrain"],
                           shown=["trees", "drapes", "ground", "terrain"],
                           objects={"objects/hill.obj": False, "objects/rock.obj": True})
    assert out["state"] == "applied" and out["rebuild"] is True
    assert PC.hidden_terrain(root) == {"objects/rock.obj"}
    assert DS.terrain_answers(root) == {"objects/hill.obj": "keep",
                                        "objects/rock.obj": "hide"}
    assert TC._hidden({"resource": "objects/rock.obj"}, root)
    assert not TC._hidden({"resource": "objects/hill.obj", "hideable": True}, root)
    # ticks agreeing with the offer forget the answers
    AS.adjust_choice(root, "change", 25, 51, items=["ground", "terrain"],
                     shown=["trees", "drapes", "ground", "terrain"],
                     objects={"objects/hill.obj": True, "objects/rock.obj": False})
    assert DS.terrain_answers(root) == {}
    assert PC.hidden_terrain(root) == {"objects/hill.obj"}


def _all_row(pack):
    return [r for r in _report(pack)["items"] if r["key"] == "terrain_all"]


def test_hide_them_all_hides_every_recognised_object(pack):
    """RULINGS 2026-11-25l: the row "terrain_all" (listed beside a terrain
    row with objects, unticked) hides every recognised terrain object,
    offered or not and whatever the per-object answers; it answers the
    terrain row too (here "never"), and it reaches the tile's mesh."""
    from auto_patch_v2.airport import pack_choice as PC
    root = pack["root"]
    assert _all_row(pack) == [], "no recognised objects: no row"
    DS.terrain_models(root, ["objects/hill.obj", "objects/rock.obj"])
    DS.terrain_paths(root, ["objects/hill.obj"])
    DS.terrain_answers(root, {"objects/hill.obj": False})       # the user keeps the hill
    keys = [r["key"] for r in _report(pack)["items"]]
    assert keys[keys.index("terrain") + 1] == "terrain_all"
    [row] = _all_row(pack)
    assert (row["checked"], row["applied"], row["rebuild"], row["count"]) == \
        (False, False, True, 2)
    out = AS.adjust_choice(root, "change", 25, 51, items=["ground", "terrain_all"],
                           shown=["trees", "drapes", "ground", "terrain", "terrain_all"])
    assert out["state"] == "applied" and out["rebuild"] is True
    assert DS.TERRAIN.store.choice(root) == "update" and PC.hides_all(root)
    assert PC.hidden_terrain(root) == {"objects/hill.obj", "objects/rock.obj"}
    assert DS.terrain_paths(root) == ("objects/hill.obj", "objects/rock.obj")
    assert all(o["hidden"] for o in DS.terrain_object_rows(root))
    assert TC._hidden({"resource": "objects/rock.obj"}, root)
    assert TC._hidden({"resource": "objects/hill.obj", "hideable": True}, root)
    assert not TC._hidden({"resource": "objects/deck.obj", "hideable": False,
                           "by": "bridge ends"}, root), "a ground object on bridges is no terrain"
    [row] = _all_row(pack)
    assert row["checked"] is True
    hiding = PC.terrain_hiding(root)
    assert hiding.every and PC.hides(hiding, "objects/new.obj", False), \
        "a first build hides what it recognises, offered or not"


def test_unticking_the_terrain_row_shows_them_all_again(pack):
    """The terrain row unticked (the app unticks "hide them all" with it)
    keeps every object; "hide them all" is forgotten."""
    from auto_patch_v2.airport import pack_choice as PC
    root = pack["root"]
    DS.terrain_models(root, ["objects/hill.obj", "objects/rock.obj"])
    DS.terrain_paths(root, ["objects/hill.obj"])
    shown = ["trees", "drapes", "ground", "terrain", "terrain_all"]
    AS.adjust_choice(root, "change", 25, 51, items=["ground", "terrain", "terrain_all"],
                     shown=shown)
    out = AS.adjust_choice(root, "change", 25, 51, items=["ground"], shown=shown)
    assert out["rebuild"] is True
    assert not PC.hides_all(root) and PC.TERRAIN_ALL_STORE.choice(root) == ""
    assert DS.TERRAIN.store.choice(root) == "never"
    assert PC.hidden_terrain(root) == frozenset()
    assert not TC._hidden({"resource": "objects/rock.obj"}, root)


def test_hide_them_all_off_leaves_the_hiding_as_it_was(pack):
    """IDENTITY: with no "hide them all" answer the build's hiding, its
    partition-key digest and the cut read exactly as before (TFFJ / TNCS
    keep their shells)."""
    import hashlib

    from auto_patch_v2.airport import pack_choice as PC
    from auto_patch_v2.airport import partition_cache as PCa
    root = pack["root"]
    DS.TERRAIN.store.remember(root, "")
    DS.terrain_models(root, ["objects/hill.obj", "objects/rock.obj"])
    DS.terrain_paths(root, ["objects/hill.obj"])
    hiding = PC.terrain_hiding(root)
    assert not hiding.every and hiding == {"objects/hill.obj"} and hiding.kept == frozenset()
    assert not PC.hides(hiding, "objects/rock.obj", False)
    assert PC.hides(hiding, "objects/rock.obj", True)
    airport = type("A", (), {"pack": type("P", (), {"pack_root": root})()})()
    old = hashlib.sha256(repr((["objects/hill.obj"], [])).encode()).hexdigest()
    assert PCa._hiding_digest(airport) == old
    PC.TERRAIN_ALL_STORE.remember(root, "update")
    assert PCa._hiding_digest(airport) != old, "hide them all is part of the reading"
