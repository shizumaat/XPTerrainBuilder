"""The Qt tile pane's missing-textures row (O4_Qt_Missing_Textures) on a
synthetic tile folder.  Offscreen, no engine, no network."""
import os
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

pytest.importorskip("PySide6")

from test_tile_texture_check import _TERRAIN, _tile  # noqa: E402

TILE = (-42, 175)


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    yield QApplication.instance() or QApplication([])


def _settle(qapp, seconds=2.0):
    deadline = time.time() + seconds
    while time.time() < deadline:
        qapp.processEvents()
        time.sleep(0.02)


def _row(qapp):
    import O4_Qt_Missing_Textures as QTMISSING
    row = QTMISSING.MissingTexturesRow()
    row.show()
    return row


def test_a_tile_missing_textures_shows_the_warning_and_rebuilds(
        qapp, tmp_path):
    row = _row(qapp)
    asked = []
    row.rebuild_requested.connect(asked.append)
    row.check(TILE, _tile(tmp_path, _TERRAIN, []))
    _settle(qapp)
    assert row.isVisible()
    assert row.label.text() == ("⚠ 2 textures missing — X-Plane cannot "
                                "load this tile")
    assert "163856_259008_Arc18.dds" in row.label.toolTip()
    row.rebuild_button.click()
    assert asked == [TILE]


def test_a_whole_tile_shows_nothing(qapp, tmp_path):
    row = _row(qapp)
    row.check(TILE, _tile(tmp_path, _TERRAIN, ["163856_259008_Arc18.dds",
                                               "163872_259024_Arc16.dds"]))
    _settle(qapp)
    assert not row.isVisible()


def test_a_late_answer_for_another_tile_is_dropped(qapp, tmp_path):
    row = _row(qapp)
    row.check(TILE, _tile(tmp_path, _TERRAIN, []))
    row.clear()
    _settle(qapp)
    assert not row.isVisible()
