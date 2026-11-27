"""#2212: on a first build the Gateway question is asked inside the
vector step once the feeds are on disk, and the patches wait for the
answer, so an Install builds the patch once, against the Gateway pack.

Headless: the ``test_gateway_early`` X-Plane folder and feeds, no Gateway.
"""
from __future__ import annotations

import os
import sys
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import O4_UI_Utils as UI  # noqa: E402
from auto_patch import gateway_stage as GW  # noqa: E402
from auto_patch import gateway_wait as WAIT  # noqa: E402
from test_gateway_early import xp  # noqa: E402,F401  (the fixture)


@pytest.fixture
def session(monkeypatch):
    monkeypatch.setattr(UI, "engine_session", object())
    monkeypatch.delenv("O4_PACK_WRITES", raising=False)
    monkeypatch.setattr(UI, "red_flag", False)


class _Clock:
    def __init__(self, on_sleep=None):
        self.t, self.on_sleep, self.slept = 0.0, on_sleep, 0

    def __call__(self):
        return self.t

    def sleep(self, s):
        self.t += s
        self.slept += 1
        if self.on_sleep:
            self.on_sleep(self)


def _wait(xp, clock):
    return WAIT.wait_for_answers(xp.root, ["KYYY"], clock=clock,
                                 sleep=clock.sleep)


def test_the_step_asks_what_the_run_start_could_not_read(xp, session):
    assert WAIT.ask_tile(44, -124, xp.root, xp.osm) == ["KYYY"]
    assert [(e["state"], [r["icao"] for r in e["items"]])
            for e in xp.events] == [("found", ["KYYY"])]


def test_a_lane_build_or_no_session_asks_nothing(xp, session, monkeypatch):
    monkeypatch.setenv("O4_PACK_WRITES", "/tmp/x")
    assert WAIT.ask_tile(44, -124, xp.root, xp.osm) == []
    monkeypatch.delenv("O4_PACK_WRITES")
    monkeypatch.setattr(UI, "engine_session", None)
    assert WAIT.ask_tile(44, -124, xp.root, xp.osm) == []
    assert xp.events == []


def test_an_install_in_time_ends_the_wait(xp, session, monkeypatch):
    monkeypatch.setattr(GW, "_install", lambda root, icao, fetch=None: {
        "pack": f"{icao} Gateway Airport", "pack_root": "/p", "scenery_id": 7,
        "flatten": "", "files": []})

    def answer(clock):
        if clock.slept == 3:
            GW.gateway_choice(xp.root, "install", 44, -124, items=["KYYY"])
    clock = _Clock(answer)
    assert _wait(xp, clock) == ["KYYY"]
    assert clock.slept == 3


def test_not_now_and_never_end_the_wait_and_the_next_ask(xp, session):
    clock = _Clock(lambda c: GW.gateway_choice(xp.root, "later", 44, -124,
                                               shown=["KYYY"]))
    assert _wait(xp, clock) == []
    assert clock.slept == 1
    # answered this run: the next tile's step neither asks nor waits
    assert WAIT.ask_tile(44, -124, xp.root, xp.osm) == []
    GW.gateway_choice(xp.root, "never", 44, -124, shown=["KYYY"])
    clock = _Clock()
    assert _wait(xp, clock) == [] and clock.slept == 0


def test_no_answer_waits_the_limit_and_a_download_longer(xp, session):
    clock = _Clock()
    assert _wait(xp, clock) == []
    assert clock.t == pytest.approx(WAIT.ANSWER_WAIT_S)
    WAIT.note_answer(xp.root, "KYYY", "installing")
    clock = _Clock()
    _wait(xp, clock)
    assert clock.t == pytest.approx(WAIT.INSTALL_WAIT_S)


def test_an_old_answer_is_not_this_runs(xp, session):
    WAIT.note_answer(xp.root, "KYYY", "later",
                     now=time.time() - WAIT.ANSWER_STANDS_S - 60)
    assert WAIT.ask_tile(44, -124, xp.root, xp.osm) == ["KYYY"]


def test_stop_ends_the_wait(xp, session):
    clock = _Clock(lambda c: setattr(UI, "red_flag", True))
    _wait(xp, clock)
    assert clock.slept == 1


def test_the_vector_step_hook_asks_then_waits(xp, session, monkeypatch):
    from auto_patch_v2.airport import cifp as CIFP
    monkeypatch.setattr(CIFP, "xplane_root_from_cifp_path",
                        lambda path: xp.root)
    import O4_File_Names as FNAMES
    monkeypatch.setattr(FNAMES, "OSM_dir", xp.osm)
    waited = []
    monkeypatch.setattr(WAIT, "wait_for_answers",
                        lambda root, icaos: waited.append((root, icaos)))
    wait = WAIT.before_patches(44, -124, "/cifp")
    assert len(xp.events) == 1 and waited == []
    wait()
    assert waited == [(xp.root, ["KYYY"])]
    GW.gateway_choice(xp.root, "never", 44, -124, shown=["KYYY"])
    assert WAIT.before_patches(44, -124, "/cifp") is None
