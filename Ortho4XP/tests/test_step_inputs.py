"""Twins for ``o4_engine.step_inputs`` (owner 2026-11-18T13:05Z: "Any
cache file should not fail, it should just be rebuilt"): a step whose
input from an earlier step is absent -- before it starts or vanishing
while it runs (the +53+010 incident: ``.node`` moved mid mesh step) --
runs that earlier step again; one log line, no failure.  Synthetic: the
steps are stubs writing the real file names; no build."""
from __future__ import annotations

import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import O4_File_Names as FNAMES  # noqa: E402
import O4_Step_Reuse as REUSE  # noqa: E402
import O4_UI_Utils as UI  # noqa: E402
import pytest  # noqa: E402
from o4_engine import step_inputs as STEP_INPUTS  # noqa: E402


@pytest.fixture
def tile(tmp_path, monkeypatch):
    t = SimpleNamespace(lat=53, lon=10, build_dir=str(tmp_path / "tile"),
                        iterate=0)
    os.makedirs(t.build_dir)
    cache = str(tmp_path / "cache")
    os.makedirs(cache)
    monkeypatch.setattr(FNAMES, "input_node_file",
                        lambda tl: os.path.join(cache, "Data.node"))
    monkeypatch.setattr(FNAMES, "input_poly_file",
                        lambda tl: os.path.join(cache, "Data.poly"))
    monkeypatch.setattr(FNAMES, "alt_file",
                        lambda tl: os.path.join(cache, "Data.alt"))
    monkeypatch.setattr(FNAMES, "mesh_file",
                        lambda d, la, lo: os.path.join(cache, "Data.mesh"))
    calls = {"forget": [], "record": []}
    monkeypatch.setattr(REUSE, "forget_from",
                        lambda tl, s: calls["forget"].append(s))
    monkeypatch.setattr(REUSE, "record",
                        lambda tl, s: calls["record"].append(s))
    monkeypatch.setattr(UI, "red_flag", False)
    lines = []
    monkeypatch.setattr(UI, "vprint", lambda lvl, *a: lines.append(" ".join(
        str(x) for x in a)))
    t.calls, t.lines = calls, lines
    return t


def _write(*paths):
    for path in paths:
        with open(path, "w") as handle:
            handle.write("x")


class _Steps:
    """Stub steps that check their inputs as the real ones do (a missing
    one: 0, the step's "could not find"): vector writes the mesh inputs,
    mesh the mesh -- with ``vanish``, its .node goes while it runs, as in
    the incident."""

    def __init__(self, tile, vanish=0):
        self.tile, self.vanish, self.ran = tile, vanish, []

    def __call__(self, key):
        self.ran.append(key)
        t = self.tile
        if STEP_INPUTS.missing_inputs(t, key):
            return 0
        if key == "vector":
            _write(*STEP_INPUTS.required_inputs(t, "mesh"))
        elif key == "mesh":
            node = FNAMES.input_node_file(t)
            if self.vanish:
                self.vanish -= 1
                os.remove(node)
            with open(node) as handle:          # FileNotFoundError
                handle.read()
            _write(FNAMES.mesh_file(t.build_dir, t.lat, t.lon))
        return 1


def _fed(steps, tile, step, recall=lambda: None):
    dropped = []
    out = STEP_INPUTS.run_fed(steps, tile, step, recall,
                              lambda: dropped.append(step))
    tile.dropped = dropped
    return out


def test_absent_input_reruns_its_producer_then_the_step(tile):
    """An output deleted after its step's record: the consumer step finds
    it absent and its producer runs again; one line, no failure kept."""
    steps = _Steps(tile)
    assert _fed(steps, tile, "mesh") == 1
    assert steps.ran == ["mesh", "vector", "mesh"]
    assert tile.calls == {"forget": ["vector"], "record": ["vector"]}
    assert tile.dropped == ["mesh"]
    assert len(tile.lines) == 1 and "Data.node is missing" in tile.lines[0]


def test_an_input_vanishing_mid_step_reruns_producer_and_step(tile):
    """THE INCIDENT: inputs present at the start, gone mid-step."""
    _write(*STEP_INPUTS.required_inputs(tile, "mesh"))
    steps = _Steps(tile, vanish=1)
    assert _fed(steps, tile, "mesh") == 1
    assert steps.ran == ["mesh", "vector", "mesh"]


def test_a_tier_copy_is_laid_back_before_any_rebuild(tile):
    def recall():
        _write(*STEP_INPUTS.required_inputs(tile, "mesh"))
    steps = _Steps(tile)
    assert _fed(steps, tile, "mesh", recall) == 1
    assert steps.ran == ["mesh", "mesh"]
    assert not [line for line in tile.lines if "building" in line]


def test_the_chain_reaches_back_two_steps(tile):
    steps = _Steps(tile)
    assert _fed(steps, tile, "masks") == 1
    assert steps.ran == ["masks", "mesh", "vector", "mesh", "masks"]


def test_a_failed_producer_fails_the_step(tile):
    steps = _Steps(tile)
    run = lambda key: 0 if key == "vector" else steps(key)  # noqa: E731
    assert _fed(run, tile, "mesh") == 0
    assert tile.calls["record"] == []


def test_a_step_failing_for_another_cause_is_not_rerun(tile):
    _write(*STEP_INPUTS.required_inputs(tile, "mesh"))
    ran = []
    assert _fed(lambda k: ran.append(k) or 0, tile, "mesh") == 0
    assert ran == ["mesh"] and tile.dropped == []


def test_any_other_missing_file_still_fails(tile):
    _write(*STEP_INPUTS.required_inputs(tile, "mesh"))

    def run(key):
        raise FileNotFoundError(2, "gone", "/elsewhere/osm.bz2")
    with pytest.raises(FileNotFoundError):
        _fed(run, tile, "mesh")


def test_a_step_that_keeps_losing_its_input_fails_after_one_retry(tile):
    _write(*STEP_INPUTS.required_inputs(tile, "mesh"))
    steps = _Steps(tile, vanish=5)
    with pytest.raises(FileNotFoundError):
        _fed(steps, tile, "mesh")
    assert steps.ran == ["mesh", "vector", "mesh"]


def test_a_session_run_survives_the_node_vanishing_mid_mesh(
        tile, monkeypatch, tmp_path):
    """The +53+010 run, through ``EngineSession``: the vector step writes
    the .node, a cleanup takes it while the mesh step reads it; the tile
    still ends built, the vector step having run again."""
    from o4_engine import events as EV
    from o4_engine.session import EngineSession
    from test_engine_session import install_stub_pipeline, run_build
    ran, state = [], {"vanish": 1}

    def vector(t):
        ran.append("vector")
        _write(*STEP_INPUTS.required_inputs(tile, "mesh"))
        return 1

    def mesh(t):
        ran.append("mesh")
        node = FNAMES.input_node_file(t)
        if state["vanish"]:
            state["vanish"] = 0
            os.remove(node)
        with open(node) as handle:
            handle.read()
        return 1
    install_stub_pipeline(monkeypatch, results={"vector": vector,
                                                "mesh": mesh})
    events = run_build(EngineSession(), [(53, 10)], tmp_path,
                       do_imagery=False)
    assert ran == ["vector", "mesh", "vector", "mesh"]
    done = [e for e in events if isinstance(e, EV.BuildDone)]
    assert len(done) == 1 and done[0].ok is True
