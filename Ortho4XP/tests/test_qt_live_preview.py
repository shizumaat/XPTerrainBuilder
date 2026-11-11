"""The Qt window's "Live flight preview" (#2001): the Fly layer asks the
command table for the viewport's squares and their mips and draws them
under the route; a landed tier re-asks; the image cache is capped.
Offscreen Qt, a fake command table, no engine, no network.
"""

from __future__ import annotations

import base64
import io
import os
import sys
from types import SimpleNamespace as NS

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest  # noqa: E402

pytest.importorskip("PySide6")

import O4_Live_Preview as LIVE  # noqa: E402
import O4_Qt_Fly_Layer as QTFLYLAYER  # noqa: E402
import O4_Qt_Fly_Pane as QTFLY  # noqa: E402
import O4_Qt_Live_Preview as QTLIVE  # noqa: E402
from PySide6.QtCore import QObject, QPointF, Signal  # noqa: E402
from PySide6.QtGui import QColor, QImage, QPainter  # noqa: E402
from PySide6.QtWidgets import QApplication, QLabel  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _jpeg(colour) -> str:
    from PIL import Image
    buffer = io.BytesIO()
    Image.new("RGB", (32, 32), colour).save(buffer, "JPEG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


class _Engine:
    """``live_preview_squares`` answers ``self.squares``; each mip is red."""

    def __init__(self, squares):
        self.squares = squares
        self.calls = []

    def __call__(self, name, **arguments):
        self.calls.append((name, arguments))
        if name == "live_preview_squares":
            return {"squares": self.squares, "capped": False, "reason": ""}
        if name == "live_preview_mip":
            return {"width": 32, "height": 32, "format": "jpeg",
                    "data": _jpeg((255, 0, 0))}
        raise KeyError(name)

    def asked(self, name):
        return [c for c in self.calls if c[0] == name]


def _square(i, stamp="1-1", px=64):
    west = -61.0 + 0.1 * (i % 10)
    north = 54.0 - 0.1 * (i // 10)
    return {"key": "+53-061/%d.dds" % i, "path": "/x/%d.dds" % i,
            "stamp": stamp, "px": px, "zl": 16, "north": north,
            "south": north - 0.1, "west": west, "east": west + 0.1}


def _drain(preview):
    for _ in range(1000):
        if not preview.pending:
            return
        preview._pump()


class _Map(QObject):
    view_changed = Signal()

    def __init__(self):
        super().__init__()
        self.updates = 0

    def viewport(self):
        return NS(update=self._update)

    def _update(self):
        self.updates += 1

    def visible_bounds(self):
        return (53.0, 54.0, -61.0, -60.0)

    def _viewport_point(self, lat, lon):
        return QPointF((lon + 61.0) * 400.0, (54.0 - lat) * 400.0)


def _pane():
    return QTFLY.FlyPane(QLabel("follow"), run=_Engine([]), airports=lambda: [],
                         prefs={}, save_prefs=lambda _p: None)


def test_the_preview_draws_squares_under_the_route_in_fly_only(qapp):
    engine = _Engine([_square(0), _square(1)])
    preview = QTLIVE.LivePreview(engine)
    view, pane = _Map(), _pane()
    layer = QTFLYLAYER.FlyLayer(view, pane, preview)
    pane.chk_live_preview.setChecked(True)
    assert not preview.enabled                       # not in Fly yet
    layer.set_shown(True)
    assert preview.enabled
    (call,) = engine.asked("live_preview_squares")
    assert call[1]["px_per_deg"] == pytest.approx(400.0)
    assert (call[1]["south"], call[1]["north"]) == (53.0, 54.0)
    _drain(preview)
    assert len(engine.asked("live_preview_mip")) == 2
    image = QImage(400, 400, QImage.Format_ARGB32)
    image.fill(0)
    painter = QPainter(image)
    layer.paint(painter)
    painter.end()
    assert QColor(image.pixel(20, 20)).red() > 200   # inside square 0
    assert image.pixel(200, 200) == 0                 # no square there
    layer.set_shown(False)
    assert not preview.enabled and not preview.images


def test_a_landed_tier_fetches_only_the_changed_square(qapp):
    engine = _Engine([_square(0), _square(1)])
    preview = QTLIVE.LivePreview(engine)
    preview.set_view(53, -61, 54, -60, 400)
    preview.set_enabled(True)
    _drain(preview)
    preview.follow_landed(0)
    _drain(preview)
    before = len(engine.asked("live_preview_mip"))
    preview.follow_landed(0)                          # nothing new landed
    assert len(engine.asked("live_preview_squares")) == 2
    engine.squares = [_square(0, stamp="2-2"), _square(1)]
    preview.follow_landed(1)
    _drain(preview)
    fetched = engine.asked("live_preview_mip")[before:]
    assert [c[1]["path"] for c in fetched] == ["/x/0.dds"]


def test_the_image_cache_is_capped(qapp):
    many = [_square(i) for i in range(LIVE.APP_CACHE_IMAGES + 40)]
    engine = _Engine(many)
    preview = QTLIVE.LivePreview(engine)
    preview.set_view(53, -61, 54, -60, 400)
    preview.set_enabled(True)
    _drain(preview)
    assert len(preview.images) == LIVE.APP_CACHE_IMAGES
    assert many[-1]["key"] in preview.images and many[0]["key"] not in preview.images


def test_a_refused_command_leaves_the_map_bare(qapp):
    def refuse(name, **_a):
        raise KeyError(name)
    preview = QTLIVE.LivePreview(refuse)
    preview.set_view(53, -61, 54, -60, 400)
    preview.set_enabled(True)
    assert preview.squares == [] and not preview.pending
    # The device is held: a QPainter over a temporary QImage paints into
    # freed memory (the CI segfault, runs 42915398276 / 42922505498).
    image = QImage(10, 10, QImage.Format_ARGB32)
    painter = QPainter(image)
    preview.paint(painter, lambda la, lo: QPointF(0, 0))
    painter.end()
