"""The Qt map's top-right controls (#2016): zoom out, zoom in and "Center
on aircraft" beside them, disabled without a current aircraft position;
centering pans and keeps the zoom.  Mac twin: ``CenterOnAircraftTests``;
the order in both apps: ``test_qt_layout_parity.MAP_CONTROLS``.

Offscreen, no network (map workers off), a fake clock.
"""

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest  # noqa: E402

pytest.importorskip("PySide6")

import O4_Fly_Text as TEXT  # noqa: E402
import O4_Qt_Map as QTMAP  # noqa: E402
import O4_Qt_Map_Controls as QTMAPCONTROLS  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402


class _Clock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now


@pytest.fixture(scope="module")
def qapp():
    yield QApplication.instance() or QApplication([])


@pytest.fixture
def view(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(QTMAP, "livemap_cache_dir", lambda: str(tmp_path / "livemap"))
    monkeypatch.setattr(QTMAP.MapView, "_start_workers", lambda self: None)
    v = QTMAP.MapView()
    v.resize(800, 600)
    v._update_timer.stop()
    clock = _Clock()
    v.controls.deleteLater()
    v.controls = QTMAPCONTROLS.MapControls(v, clock=clock)
    v.controls.place()
    yield v, clock
    v.deleteLater()


def test_the_button_sits_beside_the_zoom_buttons(view):
    v, _clock = view
    c = v.controls
    layout = c.layout()
    at = [layout.indexOf(b) for b in (c.zoom_out_btn, c.zoom_in_btn, c.center_btn)]
    assert -1 not in at and at == sorted(at)
    assert c.center_btn.accessibleName() == TEXT.CENTER_ON_AIRCRAFT
    # Top-right of the viewport.
    assert c.x() + c.width() == v.viewport().width() - 8 and c.y() == 8


def test_disabled_without_a_position(view):
    v, clock = view
    c = v.controls
    assert not c.center_btn.isEnabled()
    assert c.center_btn.toolTip() == TEXT.NO_AIRCRAFT_POSITION
    c.show_aircraft(30.1, 31.4)
    assert c.center_btn.isEnabled()
    assert c.center_btn.toolTip() == TEXT.CENTER_ON_AIRCRAFT
    # X-Plane goes quiet: stale after AIRCRAFT_FRESH_S.
    clock.now += TEXT.AIRCRAFT_FRESH_S
    c.refresh()
    assert not c.center_btn.isEnabled()
    assert c.center_btn.toolTip() == TEXT.NO_AIRCRAFT_POSITION


def test_centers_on_the_aircraft_and_keeps_the_zoom(view):
    v, _clock = view
    v.center_on_point(45.0, -100.0, zoom=9)
    zoom = v.zoom_level()
    v.controls.show_aircraft(30.1, 31.4)
    v.controls.center_btn.click()
    assert v.zoom_level() == zoom
    centre = v.mapToScene(v.viewport().rect().center())
    x, y = QTMAP.GEO.wgs84_to_pix(30.1, 31.4, QTMAP.SCENE_ZL)
    scale = 2.0 ** (zoom - QTMAP.SCENE_ZL)
    assert abs(centre.x() - x) * scale < 2 and abs(centre.y() - y) * scale < 2


def test_zoom_buttons_step_by_the_macs_factor(view):
    v, _clock = view
    v.center_on_point(45.0, -100.0, zoom=9)
    v.controls.zoom_in_btn.click()
    assert v.zoom_level() == pytest.approx(9 + QTMAPCONTROLS.ZOOM_STEP)
    v.controls.zoom_out_btn.click()
    assert v.zoom_level() == pytest.approx(9)
