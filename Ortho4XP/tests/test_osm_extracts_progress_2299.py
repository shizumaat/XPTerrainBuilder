"""#2299 / #2294: a slow regional-extract download says how far it is at
least every DOWNLOAD_PROGRESS_EVERY_SECONDS (the leader and a foreground
joiner), so the app's stuck detector never reads a 2 MB/min transfer as a
hang; and the first foreground extract use of a process sweeps the store
of dead downloads' partials (the Mac app's engine never ran the Qt
window's maintenance sweep).  Headless: injected clock, no network."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import O4_OSM_Extracts as EXTRACTS  # noqa: E402
import O4_UI_Utils as UI  # noqa: E402

MB = 1 << 20


class _Clock:
    def __init__(self, now):
        self.now = now

    def __call__(self):
        return self.now


def _lines(monkeypatch):
    out = []
    monkeypatch.setattr(UI, "vprint", lambda *a: out.append(" ".join(map(str, a[1:]))))
    monkeypatch.setattr(UI, "progress_bar", lambda *_a: None)
    return out


def test_a_slow_leader_reports_every_ten_seconds(monkeypatch):
    clock = _Clock(1000.0)
    monkeypatch.setattr(EXTRACTS.time, "time", clock)
    lines = _lines(monkeypatch)
    w = EXTRACTS._ExtractWatcher("algeria", foreground=False)
    received = 0
    for _ in range(60):                    # 2 MB/min, one chunk a second
        clock.now += 1.0
        received += MB // 30
        w.chunk(MB // 30, received, 288 * MB)
    said = [ln for ln in lines if "MB so far" in ln]
    assert len(said) == 60 // int(EXTRACTS.DOWNLOAD_PROGRESS_EVERY_SECONDS)
    assert said[-1].endswith("1/288 MB so far")


def test_a_fast_leader_keeps_the_byte_cadence(monkeypatch):
    clock = _Clock(1000.0)
    monkeypatch.setattr(EXTRACTS.time, "time", clock)
    lines = _lines(monkeypatch)
    w = EXTRACTS._ExtractWatcher("morocco", foreground=False)
    for k in range(1, 201):                # 200 MB in 2 s
        clock.now += 0.01
        w.chunk(MB, k * MB, 200 * MB)
    said = [ln for ln in lines if "MB so far" in ln]
    assert len(said) == 200 // (EXTRACTS.DOWNLOAD_PROGRESS_EVERY_BYTES >> 20)


def test_a_foreground_joiner_says_how_far_the_other_download_is(monkeypatch):
    clock = _Clock(500.0)
    monkeypatch.setattr(EXTRACTS.time, "time", clock)
    lines = _lines(monkeypatch)
    w = EXTRACTS._ExtractWatcher("castilla-y-leon", foreground=True)
    clock.now += EXTRACTS.DOWNLOAD_PROGRESS_EVERY_SECONDS
    w.waited(20 * MB, 171 * MB)
    w.finished()
    assert any("another tile's download" in ln and "20/171 MB" in ln for ln in lines)


def test_the_first_foreground_use_sweeps_the_store_once(monkeypatch):
    swept = []
    monkeypatch.setattr(EXTRACTS, "_swept_this_process", EXTRACTS.threading.Event())
    monkeypatch.setattr(EXTRACTS, "_sweep_interrupted_downloads",
                        lambda: swept.append(1) or 0)
    monkeypatch.setattr(EXTRACTS, "_extract_ready", lambda region_id: True)
    assert EXTRACTS._ensure_extracts_foreground([("morocco", "u")])
    assert EXTRACTS._ensure_extracts_foreground([("morocco", "u")])
    assert swept == [1]
