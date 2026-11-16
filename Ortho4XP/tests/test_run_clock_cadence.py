"""The run clock moves at least twice a second in both apps (owner
2026-11-16: "the console and progress bar are updating, should be probably
a couple times per second").  The engine emits RunEta, TileClocks and the
clock steps' StepProgress every ``ETA_EMIT_SECONDS`` (serial heartbeat and
parallel ticker alike); the Mac app renders each event as it lands, the Qt
window re-reads its clock on a timer of the same period.
"""
from __future__ import annotations

import inspect
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from o4_engine import parallel, session

SRC = os.path.join(os.path.dirname(__file__), "..", "src")


def test_engine_clock_cadence_is_at_least_two_hertz():
    assert session.ETA_EMIT_SECONDS <= 0.5
    ticker = inspect.getsource(parallel.ParallelBuildRun._ticker)
    assert "time.sleep(ETA_EMIT_SECONDS)" in ticker


def test_qt_clock_timer_follows_the_engine_cadence():
    with open(os.path.join(SRC, "O4_Qt_GUI.py"), encoding="utf-8") as fh:
        text = fh.read()
    assert "self._elapsed_timer.setInterval(int(ETA_EMIT_SECONDS * 1000))" \
        in text
