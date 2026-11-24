"""The tile rebuild a terrain-objects answer owes (follow-up to the pack
Adjust, 2026-11-15): "Hide terrain objects" opens ticked, and its answer
is read by the tile's vector step (``terrain_cut_stage``) — an answer
given during a build leaves the pack hiding the object over ground still
cut to it.  The engine keeps the debt (``o4_engine.tile_rebuild_pending``),
names it after the run (``PackAdjust(state="pending")``) and, when a build
ran the vector step on the answers as they are now, pays it with a note
on the tile's ``BuildDone``.
"""
from __future__ import annotations

import os
import sys
import time
import types

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "src"))

import O4_Step_Reuse as SR  # noqa: E402
from auto_patch import adjust_edit as AE  # noqa: E402
from auto_patch import adjust_stage as AS  # noqa: E402
from auto_patch import terrain_cut_stage as TC  # noqa: E402
from auto_patch_v2.airport import pack_choice as PC  # noqa: E402
from o4_engine import events as EV  # noqa: E402
from o4_engine import tile_rebuild_pending as TRP  # noqa: E402

TILE = types.SimpleNamespace(lat=-23, lon=-44, build_dir="/b")


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(PC, "store_path",
                        lambda name: str(tmp_path / "prefs" / name))
    cut = {"recorded": ["dsf:obj7"], "live": ["dsf:obj7"]}
    monkeypatch.setattr(SR, "committed_entry", lambda tile, step: {
        "inputs": {"terrain_cut": cut["recorded"]}} if step == "vector" else {})
    monkeypatch.setattr(TC, "cut_records", lambda folder, icaos=None: [
        {"id": i} for i in cut["live"]])
    return cut


def test_a_mark_is_pending_until_a_build_matches(store):
    TRP.mark(-23, -44, "/cs/Pack", "Pack", (False,), (True,))
    [row] = TRP._pending()
    assert (row["tile"], row["pack"], row["change"]) == ("-23-044", "Pack",
                                                        "hidden")
    store["live"] = []                 # the model is hidden: no longer cut
    assert TRP.resolve(TILE) == [], "the mesh was built with the old cut"
    assert len(TRP._pending()) == 1
    store["recorded"] = []             # the rebuild's vector step ran on it
    [paid] = TRP.resolve(TILE)
    assert TRP._pending() == []
    note = TRP.note(paid)
    assert note["what"] == ("Tile -23-044 was built to match: terrain "
                            "objects hidden in “Pack”.")
    assert note["severity"] == "info"


def test_an_answer_back_to_the_built_state_drops_the_debt(store):
    TRP.mark(-23, -44, "/cs/Pack", "Pack", (False,), (True,))
    TRP.mark(-23, -44, "/cs/Pack", "Pack", (True,), (False,))
    assert TRP._pending() == [] and TRP.announcement() is None


def test_the_announcement_names_every_tile(store):
    TRP.mark(-23, -44, "/cs/A", "A", (False,), (True,))
    TRP.mark(30, 31, "/cs/B", "B", (True,), (False,))
    got = TRP.announcement()
    assert got["state"] == "pending"
    assert [(r["tile"], r["change"]) for r in got["items"]] == [
        ("+30+031", "shown"), ("-23-044", "hidden")]


def test_the_session_marks_an_answer_and_announces_after_a_run(store,
                                                               monkeypatch):
    from o4_engine.session import EngineSession
    session = EngineSession()
    got = []
    session.subscribe(got.append)
    state = {"hidden": False}
    monkeypatch.setattr(AE, "tile_state", lambda root: (state["hidden"],))

    def answer(root, action, lat, lon, items=None, shown=None, steps=None, objects=None):
        state["hidden"] = True
        return {"pack": "Pack", "rebuild": True}

    monkeypatch.setattr(AS, "adjust_choice", answer)
    session.pack_adjust("/cs/Pack", "update", -23, -44, items=["terrain"],
                        shown=["terrain"])
    deadline = time.time() + 10
    while not TRP._pending() and time.time() < deadline:
        time.sleep(0.01)
    assert [r["tile"] for r in TRP._pending()] == ["-23-044"]
    session._announce_rebuild_pending(cancelled=True)
    assert not [e for e in got if isinstance(e, EV.PackAdjust)], \
        "a cancelled run rebuilds nothing"
    session._announce_rebuild_pending(cancelled=False)
    [ev] = [e for e in got if isinstance(e, EV.PackAdjust)]
    assert ev.state == "pending" and ev.items[0]["tile"] == "-23-044"


def test_a_built_tile_carries_the_note_once(store, monkeypatch):
    from o4_engine.session import EngineSession
    session = EngineSession()
    monkeypatch.setattr(session, "tile_build_dir", lambda lat, lon: "/b")
    TRP.mark(-23, -44, "/cs/Pack", "Pack", (False,), (True,))
    store["live"] = store["recorded"] = []
    built = session.with_paid_rebuilds(EV.BuildDone(lat=-23, lon=-44, ok=True))
    assert [n["code"] for n in built.notes] == ["rebuilt_to_match"]
    again = session.with_paid_rebuilds(EV.BuildDone(lat=-23, lon=-44, ok=True))
    assert again.notes == []
