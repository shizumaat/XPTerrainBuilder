"""#1707: the user picks the steps of "Optimise pack" (owner 2026-11-03:
"present the user with the options, all defaulted on with an explanation
and estimated impact, but provide check boxes").  The recipe carries only
the steps chosen, each step's estimate goes out on ``PackOptimise.steps``
(capability ``pack_optimise_steps``), and a re-Optimise remembers the
last choice per pack; Revert to default forgets it.  Headless.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "src"))

import pack_optimise_fixture as FX  # noqa: E402
from auto_patch import optimise_stage as OS  # noqa: E402
from auto_patch import pack_choice as PC  # noqa: E402
from auto_patch_v2.airport import pack_optimise as PO  # noqa: E402
from auto_patch_v2.airport.pack_optimise import impact as IM  # noqa: E402
from auto_patch_v2.airport.pack_optimise import swap as SW  # noqa: E402
from o4_engine import events as EV  # noqa: E402
from test_pack_optimise_swap import CAR, CAR_LIB, LIB_CAR  # noqa: E402


def _pack(tmp_path, monkeypatch):
    rp = FX.make_pack(tmp_path, monkeypatch)
    (rp.pack / "objects" / "car.obj").write_text(CAR, encoding="utf-8", newline="")
    monkeypatch.setattr(SW, "MIN_SAVING", 1)
    lib = tmp_path / "libcar.obj"
    lib.write_text(LIB_CAR, encoding="utf-8", newline="")
    return rp, (lambda v: [str(lib)] if v == CAR_LIB else [])


def test_the_recipe_carries_only_the_steps_chosen(tmp_path, monkeypatch):
    rp, exports_of = _pack(tmp_path, monkeypatch)
    lines = FX.DUMP.splitlines(keepends=True)
    every = PO.build_recipe(str(rp.pack), lines, exports_of)
    assert "dedupe" in every and "swap" in every and "steps" not in every
    only = PO.build_recipe(str(rp.pack), lines, exports_of, ["swap"])
    assert "dedupe" not in only and only["steps"] == ["swap"] and "swap" in only
    assert PO.drop_ordinals(lines, only, frozenset())[0] == set(), \
        "no duplicates dropped without their step"
    assert PO.chosen_steps(["textures", "bogus", "dedupe"]) == ("dedupe", "textures")


def test_each_step_s_estimate(tmp_path, monkeypatch):
    rp, exports_of = _pack(tmp_path, monkeypatch)
    lines = FX.DUMP.splitlines(keepends=True)
    rows = IM.steps(str(rp.pack), lines, PO.build_recipe(str(rp.pack), lines, exports_of))
    assert [r["key"] for r in rows] == ["dedupe", "swap"], "nothing to do: not listed"
    dedupe, swap = rows
    assert dedupe["count"] == 2 and dedupe["tris"] > 0
    assert swap["count"] == 2 and swap["tris"] > 0


def test_the_last_choice_is_remembered_and_revert_forgets_it(tmp_path, monkeypatch):
    paths = {}
    monkeypatch.setattr(PC, "store_path", lambda name: paths.setdefault(
        name, str(tmp_path / "prefs" / name)))
    seen = []
    pw = OS.PackWeight("P", str(tmp_path / "x.dsf"), 1, 1, 1, {}, PO.default_recipe())
    monkeypatch.setattr(OS, "check", lambda *a, **k: seen.append(k["steps"]) or pw)
    monkeypatch.setattr(OS, "_optimise", lambda *a: "optimised")
    root = str(tmp_path)
    OS.optimise_choice(root, "update", 25, 51, steps=["swap", "dedupe"])
    assert OS._remembered_steps(root) == ("dedupe", "swap")
    OS.optimise_choice(root, "update", 25, 51)
    assert seen == [("dedupe", "swap"), ("dedupe", "swap")], "a re-Optimise remembers"
    OS.optimise_choice(root, "update", 25, 51, steps=list(PO.STEPS))
    assert OS.STEPS_STORE.choice(root) == "", "every step is the default"
    OS.optimise_choice(root, "update", 25, 51, steps=["textures"])
    from auto_patch import object_rebake as OR
    OR.restore_detail(root)
    assert OS._remembered_steps(root) == PO.STEPS
    assert OS.optimise_choice(root, "update", 25, 51, steps=[])["state"] == "failed"


def test_the_wire_carries_the_steps():
    ev = EV.PackOptimise(steps=[{"key": "swap", "count": 3, "tris": 9, "mb": 0.0}],
                         chosen=["swap"])
    assert ev.steps[0]["key"] == "swap" and ev.chosen == ["swap"]
    from o4_engine.events import CAPABILITIES
    assert "pack_optimise_steps" in CAPABILITIES
