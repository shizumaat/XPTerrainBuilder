"""The Build box's cost panel in the Qt window (#820), offscreen.

The engine's answer is handed in as a ``PlanEstimateReady`` event; the
tests read the panel's lines and the Build button.  No engine, no network.
"""

import json
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest  # noqa: E402

pytest.importorskip("PySide6")

import O4_Qt_GUI as GUI  # noqa: E402
import O4_Qt_Plan_Estimate as QTPLAN  # noqa: E402
from o4_engine import events as EV  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

LAT, LON = 45, -123

_RESULT = {
    "tiles": [{"lat": LAT, "lon": LON, "download_gb": [0.5, 2.7],
               "disk_gb": [1.8, 8.5], "time_s": [500, 2500]}],
    "total": {"download_gb": [0.5, 2.7], "disk_gb": [1.8, 8.5],
              "time_s": [500, 2500]},
    "free_gb": 27.3, "cache_free_gb": None, "verdict": "ok", "reason": "",
}


@pytest.fixture
def window(tmp_path, monkeypatch):
    QApplication.instance() or QApplication([])
    prefs = tmp_path / "prefs.json"
    prefs.write_text(json.dumps({"output_dir": str(tmp_path)}), encoding="utf-8", newline="")
    monkeypatch.setattr(GUI, "PREFS_FILE", str(prefs))
    monkeypatch.setattr(GUI, "TILE_SCAN_CACHE_FILE", str(tmp_path / "scan.json"))
    saved_stdout = sys.stdout
    win = GUI.MainWindow()
    monkeypatch.setattr(win, "refresh_tiles", lambda: None)
    monkeypatch.setattr(win, "xplane_block_reason", lambda: None)
    monkeypatch.setattr(win.map, "selection", lambda: {(LAT, LON)})
    try:
        yield win
    finally:
        win._building = False
        win.close()
        win.deleteLater()
        sys.stdout = saved_stdout


def _answer(window, result, error=""):
    window._on_plan_estimate_ready(EV.PlanEstimateReady(
        request=window._plan_request, result=result, error=error))


def test_qt_asks_for_the_tiles_and_steps_of_the_next_press(window, monkeypatch):
    sent = []
    monkeypatch.setattr(window, "_plan_handler", lambda **kw: sent.append(kw), raising=False)
    window.chk_overlays.setChecked(False)
    window._request_plan_estimate()
    assert sent and sent[-1]["tiles"] == [[LAT, LON]]
    assert sent[-1]["request"] == window._plan_request
    assert (sent[-1]["do_vector"], sent[-1]["do_imagery"], sent[-1]["do_overlays"]) == (
        True, True, False)
    assert sent[-1]["custom_build_dir"] == window.output_dir()


def test_qt_panel_shows_the_ranges(window, monkeypatch):
    monkeypatch.setattr(window, "_plan_handler", lambda **kw: None, raising=False)
    window._request_plan_estimate()
    _answer(window, _RESULT)
    panel = window.plan_panel
    assert not panel.isHidden()
    assert panel.total_label.text() == (
        "Download 0.5–2.7 GB · Disk 1.8–8.5 GB of 27.3 GB free · 8–42 min")
    assert panel.tiles_label.isHidden()
    panel.details_btn.setChecked(True)
    assert not panel.tiles_label.isHidden()
    assert panel.tiles_label.text() == QTPLAN.tile_text(_RESULT["tiles"][0])
    assert window.build_btn.isEnabled()
    assert panel.verdict_label.isHidden()


def test_qt_build_is_off_with_the_reason_when_the_disk_is_short(window, monkeypatch):
    monkeypatch.setattr(window, "_plan_handler", lambda **kw: None, raising=False)
    window._request_plan_estimate()
    reason = "This build needs at least 1.8 GB on the tile folder's drive, which has 0.9 GB free."
    _answer(window, dict(_RESULT, verdict="refuse", reason=reason))
    assert not window.build_btn.isEnabled()
    assert window.build_btn.toolTip() == reason
    assert window.build_block_label.text() == reason
    assert window.plan_panel.verdict_label.isHidden(), "said once, under Build"
    # A stale answer (an older request) changes nothing.
    window._plan_request += 1
    window._on_plan_estimate_ready(EV.PlanEstimateReady(
        request=window._plan_request - 1, result=_RESULT))
    assert not window.build_btn.isEnabled()
    _answer(window, _RESULT)
    assert window.build_btn.isEnabled()


def test_qt_warn_keeps_build_on(window, monkeypatch):
    monkeypatch.setattr(window, "_plan_handler", lambda **kw: None, raising=False)
    window._request_plan_estimate()
    _answer(window, dict(_RESULT, verdict="warn", reason="This build may need up to 8.5 GB"))
    assert window.build_btn.isEnabled()
    assert not window.plan_panel.verdict_label.isHidden()


def test_time_text_is_a_range_in_minutes_or_hours():
    assert QTPLAN.time_text([500, 2500]) == "8–42 min"
    assert QTPLAN.time_text([60, 70]) == "1–2 min"
    assert QTPLAN.time_text([3600, 3 * 3600]) == "1.0–3.0 h"
    assert QTPLAN.gb_text([0.0, 0.01]) == "none"


def test_qt_reaches_the_engine_through_the_one_command_table(window):
    from o4_engine import jsonl

    handler = window._plan_command()
    assert callable(handler) and window._plan_command() is handler
    assert "plan_estimate" in jsonl.command_table(window._session)
