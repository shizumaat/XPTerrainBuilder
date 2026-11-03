"""The Qt tile pane's "Imagery check" row (O4_Qt_Imagery_Freshness, #1666).
Offscreen, no engine, no network: the check itself is replaced."""
import os
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

pytest.importorskip("PySide6")

import O4_Imagery_Freshness as FRESH  # noqa: E402

TILE = (45, 7)
NEWER = {"status": FRESH.NEWER, "label": "Newer imagery available",
         "detail": "2 of 2 sampled spots differ."}


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    yield QApplication.instance() or QApplication([])


def _settle(qapp, until, seconds=3.0):
    deadline = time.time() + seconds
    while time.time() < deadline and not until():
        qapp.processEvents()
        time.sleep(0.02)
    qapp.processEvents()


def _row(monkeypatch, answer):
    import o4_engine.imagery_commands as CMDS
    import O4_Qt_Imagery_Freshness as QTFRESH
    monkeypatch.setattr(CMDS, "freshness_for_info", lambda info, **kw: answer)
    return QTFRESH.ImageryFreshnessRow()


def test_newer_imagery_shows_the_update_button(qapp, monkeypatch):
    row = _row(monkeypatch, NEWER)
    asked = []
    row.update_requested.connect(asked.append)
    row.check(TILE, object())
    assert row.label.text() == "Checking…"
    _settle(qapp, lambda: row.label.text() != "Checking…")
    assert row.label.text() == "Newer imagery available"
    assert row.label.toolTip() == NEWER["detail"]
    assert not row.update_button.isHidden()
    row.update_button.click()
    assert asked == [TILE]
    row.close_probe()


def test_up_to_date_hides_it_and_a_tile_not_built_shows_a_dash(qapp, monkeypatch):
    row = _row(monkeypatch, {"status": FRESH.UP_TO_DATE, "label": "Up to date",
                             "detail": ""})
    row.check(TILE, object())
    _settle(qapp, lambda: row.label.text() != "Checking…")
    assert row.label.text() == "Up to date" and row.update_button.isHidden()
    row.check(TILE, None)
    assert row.label.text() == "—"
    row.close_probe()


def test_an_answer_for_another_tile_is_dropped(qapp, monkeypatch):
    row = _row(monkeypatch, NEWER)
    row.check(TILE, object())
    row._show(((1, 1), NEWER))
    assert row.label.text() == "Checking…"
    row.close_probe()
