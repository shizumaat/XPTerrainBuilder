"""Background airport-core sharpening shows a row in the Build view
(#2039, owner 2026-11-13T04:32Z):

* every core batch (``imagery_after_build.fetch_cores``, whoever starts
  it) reports one ``ImageryCoresProgress`` per tile at its start, one per
  finished square and its outcome -- ``done``, ``error`` or ``stopped``;
* the row's stop (``imagery_cores_stop``) leaves the squares not started;
* both apps word the row alike (``cores_row_status``), the Qt row sits
  at the foot of Activity, not selectable, and outlives the tile rows'
  re-layout; the Mac app decodes the event by its wire name.

No X-Plane, no network: the lander is a stub.
"""
from __future__ import annotations

from pathlib import Path

import O4_File_Names as FNAMES
import O4_Imagery_OnDemand_Text as TEXT
import pytest
from o4_engine import imagery_after_build as AFTER
from o4_engine import imagery_core_rows as ROWS
from o4_engine.events import CAPABILITIES, ImageryCoresProgress
from test_imagery_after_build import Lander, _fresh_build, _graded, patches  # noqa: F401
from test_imagery_ondemand import LAT, LON, _centre, world  # noqa: F401
from test_imagery_ondemand_ui import qapp  # noqa: F401

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture()
def seen():
    events = []
    ROWS.set_sink(events.append)
    yield events
    ROWS.set_sink(None)


def _cores(world):  # noqa: F811
    tiles = _fresh_build(world)
    _graded(FNAMES.patch_dir(LAT, LON), *_centre(0))
    AFTER.register_built(tiles)
    return tiles


def test_a_batch_reports_each_square_then_done(world, patches, seen):  # noqa: F811
    counts = AFTER.fetch_cores(_cores(world), lander=Lander())
    total = counts["wanted"]
    assert total > 0 and all(isinstance(e, ImageryCoresProgress) for e in seen)
    assert {(e.lat, e.lon) for e in seen} == {(LAT, LON)}
    assert (seen[0].state, seen[0].done, seen[0].total) == ("active", 0, total)
    assert [e.done for e in seen[1:-1]] == list(range(1, total + 1))
    assert (seen[-1].state, seen[-1].done) == ("done", total)


def test_stop_leaves_the_squares_not_started(world, patches, seen):  # noqa: F811
    lander = Lander()

    def land(row, tier):
        assert ROWS.stop(LAT, LON)
        return lander(row, tier)
    counts = AFTER.fetch_cores(_cores(world), lander=land, workers=1)
    assert counts["landed"] == 1 and counts["skipped"] == counts["wanted"] - 1
    assert counts["failed"] == 0
    assert (seen[-1].state, seen[-1].done) == ("stopped", 1)
    assert not ROWS.stopped(LAT, LON)          # forgotten with its batch
    assert ROWS.imagery_cores_stop(lat=LAT, lon=LON) == {"stopped": False}


def test_a_build_leaves_it_stopped_and_a_failure_is_an_error(
        world, patches, seen):  # noqa: F811
    tiles = _cores(world)
    AFTER.fetch_cores(tiles, lander=Lander(), busy=lambda: True)
    assert seen[-1].state == "stopped" and seen[-1].done == 0

    def broken(row, tier):
        raise OSError("no imagery")
    seen.clear()
    AFTER.fetch_cores(tiles, lander=broken)
    assert seen[-1].state == "error" and seen[-1].failed == seen[-1].total


def test_nothing_to_sharpen_has_no_row(seen):
    ROWS.CoreRows({(LAT, LON): 0}).finish()
    assert seen == []


def test_the_wire_and_both_apps():
    assert "imagery_core_rows" in CAPABILITIES
    assert "imagery_cores_stop" in (REPO / "Ortho4XP" / "src" / "o4_engine"
                                    / "jsonl.py").read_text(encoding="utf-8")
    swift = (REPO / "Sources" / "SceneryKit" / "OrthoEngineClient.swift"
             ).read_text(encoding="utf-8")
    assert 'case "ImageryCoresProgress":' in swift
    assert '"imagery_cores_stop"' in swift
    watcher = (REPO / "Ortho4XP" / "src" / "o4_engine"
               / "imagery_after_build.py").read_text(encoding="utf-8")
    assert "ROWS.set_sink(" in watcher


def test_the_row_words():
    assert TEXT.cores_row_status("active", 12, 40) == (
        "Sharpening airport imagery · 12 of 40 squares")
    assert TEXT.cores_row_status("done", 40, 40) == (
        "Airport imagery sharp · 40 of 40 squares")
    assert TEXT.cores_row_status("error", 38, 40, 2) == (
        "Sharpening airport imagery failed · 2 of 40 squares failed")
    assert TEXT.cores_row_status("stopped", 3, 40) == (
        "Sharpening airport imagery stopped · 3 of 40 squares")


def test_the_qt_row_sits_under_the_tiles_and_is_not_selectable(qapp):  # noqa: F811
    from O4_Qt_Activity_List import ActivityList
    from O4_Qt_Core_Rows import CoreRow, CoreRowSet
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QLabel

    tones = {"live": "gray", "done": "green", "warning": "gold",
             "failed": "red", "stopped": "orange"}
    rows = CoreRowSet(lambda tile: CoreRow(tile, QIcon(), 16, tones, 11))
    listed = ActivityList()
    tile_row = QLabel("tile")
    listed.place([((1, 2), "activity")], {(1, 2): tile_row}, set())
    assert rows.show(ImageryCoresProgress(lat=LAT, lon=LON, total=4))
    listed.place_cores(rows.rows())
    listed.place([((1, 2), "activity")], {(1, 2): tile_row}, set())
    item = listed.activity_item
    assert item.childCount() == 2
    core_item = item.child(1)
    assert listed.itemWidget(core_item, 0).row() is rows.rows()[0]
    assert not core_item.flags() & Qt.ItemIsSelectable
    row = rows.rows()[0]
    assert row.status.text() == TEXT.cores_row_status("active", 0, 4)
    assert not row.stop.isHidden()
    stops = []
    row.stop_requested.connect(stops.append)
    row.stop.click()
    assert stops == [(LAT, LON)]
    assert listed.completed_item.isHidden()
    assert rows.show(ImageryCoresProgress(lat=LAT, lon=LON, state="done",
                                          done=4, total=4))
    assert row.stop.isHidden() and row.bar.value() == 1000
    # #2052: a finished row leaves the queue for Completed.
    listed.place_cores(rows.rows())
    assert item.childCount() == 1
    done = listed.completed_item
    assert done.childCount() == 1 and not done.isHidden()
    assert listed.itemWidget(done.child(0), 0).row() is row
    assert done.text(0) == "Completed (1)"
    assert not rows.show(ImageryCoresProgress(lat=LAT, lon=LON, state="done",
                                              done=4, total=4))
    assert rows.drop_finished() and rows.rows() == []
