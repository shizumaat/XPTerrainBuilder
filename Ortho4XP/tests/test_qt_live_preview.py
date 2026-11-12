"""The Qt window's "Live flight preview" (#2001; owner 2026-11-12T19:28Z
"show exactly what's showing in X-Plane"): the Fly layer asks the command
table for the viewport's squares and their mips ON A BACKGROUND THREAD and
draws them under the route, coarse first then at each square's own size;
a landed tier re-asks; the image cache is bounded in bytes; stale squares
and the tiles X-Plane draws itself are marked.  Offscreen Qt, a fake
command table, no engine, no network.
"""

from __future__ import annotations

import base64
import io
import os
import sys
import time
from types import SimpleNamespace as NS

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest  # noqa: E402

pytest.importorskip("PySide6")

import O4_Live_Preview_Text as TEXT  # noqa: E402
import O4_Qt_Fly_Layer as QTFLYLAYER  # noqa: E402
import O4_Qt_Fly_Pane as QTFLY  # noqa: E402
import O4_Qt_Live_Preview as QTLIVE  # noqa: E402
from PySide6.QtCore import QObject, QPointF, Signal  # noqa: E402
from PySide6.QtGui import QColor, QImage, QPainter  # noqa: E402
from PySide6.QtWidgets import QApplication, QLabel  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _jpeg(colour, px=32) -> str:
    from PIL import Image
    buffer = io.BytesIO()
    Image.new("RGB", (px, px), colour).save(buffer, "JPEG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


class _Engine:
    """``live_preview_squares`` answers ``self.squares`` / ``self.tiles``;
    each mip is red, ``delay`` seconds late."""

    def __init__(self, squares, tiles=(), delay=0.0):
        self.squares, self.tiles, self.delay = squares, list(tiles), delay
        self.calls = []

    def __call__(self, name, **arguments):
        self.calls.append((name, arguments))
        if name == "live_preview_squares":
            return {"squares": self.squares, "tiles": self.tiles, "reason": ""}
        if name == "live_preview_mip":
            time.sleep(self.delay)
            return {"width": 32, "height": 32, "format": "jpeg",
                    "data": _jpeg((255, 0, 0))}
        raise KeyError(name)

    def asked(self, name):
        return [c for c in self.calls if c[0] == name]


def _square(i, stamp="1-1", px=64, **extra):
    west = -61.0 + 0.1 * (i % 10)
    north = 54.0 - 0.1 * (i // 10)
    return {"key": "+53-061/%d.dds" % i, "path": "/x/%d.dds" % i,
            "stamp": stamp, "px": px, "zl": 16, "north": north,
            "south": north - 0.1, "west": west, "east": west + 0.1, **extra}


def _drain(qapp, preview, seconds=10.0):
    """Run the event loop until the worker is idle and its results are in."""
    deadline = time.monotonic() + seconds
    idle = 0
    while time.monotonic() < deadline:
        qapp.processEvents()
        idle = idle + 1 if not preview.busy() else 0
        if idle > 3:
            return
        time.sleep(0.005)
    raise AssertionError("TIMED_OUT waiting for the live preview")


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


def _point(lat, lon):
    return QPointF((lon + 61.0) * 400.0, (54.0 - lat) * 400.0)


def _paint(preview, size=400):
    image = QImage(size, size, QImage.Format_ARGB32)
    image.fill(0)
    painter = QPainter(image)
    preview.paint(painter, _point)
    painter.end()
    return image


def test_the_preview_draws_squares_under_the_route_in_fly_only(qapp):
    engine = _Engine([_square(0), _square(1)])
    preview = QTLIVE.LivePreview(engine)
    view, pane = _Map(), _pane()
    layer = QTFLYLAYER.FlyLayer(view, pane, preview)
    pane.chk_live_preview.setChecked(True)
    assert not preview.enabled                       # not in Fly yet
    layer.set_shown(True)
    assert preview.enabled
    _drain(qapp, preview)
    (call,) = engine.asked("live_preview_squares")
    assert call[1]["px_per_deg"] == pytest.approx(400.0)
    assert (call[1]["south"], call[1]["north"]) == (53.0, 54.0)
    assert call[1]["scale"] >= 1.0
    mips = engine.asked("live_preview_mip")
    assert len(mips) == 2 and all(c[1]["wait"] for c in mips)
    image = QImage(400, 400, QImage.Format_ARGB32)
    image.fill(0)
    painter = QPainter(image)
    layer.paint(painter)
    painter.end()
    assert QColor(image.pixel(20, 20)).red() > 200   # inside square 0
    assert image.pixel(200, 200) == 0                 # no square there
    layer.set_shown(False)
    assert not preview.enabled and not len(preview.images)


def test_coarse_first_then_each_square_at_its_own_size(qapp):
    engine = _Engine([_square(0, px=1024), _square(1, px=256)])
    preview = QTLIVE.LivePreview(engine)
    preview.set_view(53, -61, 54, -60, 400)
    preview.set_enabled(True)
    _drain(qapp, preview)
    asked = [(c[1]["path"], c[1]["px"]) for c in engine.asked("live_preview_mip")]
    assert asked == [("/x/0.dds", 64), ("/x/1.dds", 64),
                     ("/x/0.dds", 1024), ("/x/1.dds", 256)]
    assert preview.images.peek(_square(0)["key"])[1] == 1024


def test_the_window_never_waits_for_a_read(qapp):
    engine = _Engine([_square(i, px=4096) for i in range(3)], delay=0.3)
    preview = QTLIVE.LivePreview(engine)
    preview.set_view(53, -61, 54, -60, 400)
    start = time.monotonic()
    preview.set_enabled(True)
    qapp.processEvents()
    assert time.monotonic() - start < 0.1             # 6 reads of 0.3 s queued
    _drain(qapp, preview)
    assert len(preview.images) == 3


def test_a_landed_tier_fetches_only_the_changed_square(qapp):
    engine = _Engine([_square(0), _square(1)])
    preview = QTLIVE.LivePreview(engine)
    preview.set_view(53, -61, 54, -60, 400)
    preview.set_enabled(True)
    _drain(qapp, preview)
    preview.follow_landed(0)
    _drain(qapp, preview)
    before = len(engine.asked("live_preview_mip"))
    preview.follow_landed(0)                          # nothing new landed
    assert len(engine.asked("live_preview_squares")) == 2
    engine.squares = [_square(0, stamp="2-2"), _square(1)]
    preview.follow_landed(1)
    _drain(qapp, preview)
    fetched = engine.asked("live_preview_mip")[before:]
    assert [c[1]["path"] for c in fetched] == ["/x/0.dds"]


def test_every_square_is_drawn_and_the_cache_is_bounded_in_bytes(qapp):
    """#2012: no count cap -- every listed square is fetched; the cache
    keeps the most recent within its byte budget."""
    many = [_square(i) for i in range(300)]
    engine = _Engine(many)
    preview = QTLIVE.LivePreview(engine)
    one = QImage.fromData(base64.b64decode(_jpeg((255, 0, 0)))).sizeInBytes()
    preview.images.budget = 40 * one
    preview.set_view(53, -61, 54, -60, 400)
    preview.set_enabled(True)
    _drain(qapp, preview)
    assert len(engine.asked("live_preview_mip")) == 300
    assert len(preview.images) == 40 and preview.images.bytes <= 40 * one
    assert many[-1]["key"] in preview.images and many[0]["key"] not in preview.images


def test_a_refused_command_leaves_the_map_bare(qapp):
    def refuse(name, **_a):
        raise KeyError(name)
    preview = QTLIVE.LivePreview(refuse)
    preview.set_view(53, -61, 54, -60, 400)
    preview.set_enabled(True)
    _drain(qapp, preview)
    assert preview.squares == []
    # The device is held: a QPainter over a temporary QImage paints into
    # freed memory (the CI segfault, runs 42915398276 / 42922505498).
    image = QImage(10, 10, QImage.Format_ARGB32)
    painter = QPainter(image)
    preview.paint(painter, lambda la, lo: QPointF(0, 0))
    painter.end()


def test_a_swapped_world_tile_is_drawn_as_installed(qapp):
    """#2020: build-ahead put a tile in (``WorldStatus.last_swap``
    changed): the squares are asked again and the changed one fetched."""
    engine = _Engine([_square(0)])
    preview = QTLIVE.LivePreview(engine)
    preview.set_view(53, -61, 54, -60, 400)
    preview.set_enabled(True)
    _drain(qapp, preview)
    preview.world_swapped(["+53-061", "drape", "t1"])
    _drain(qapp, preview)
    asked = len(engine.asked("live_preview_squares"))
    preview.world_swapped(["+53-061", "drape", "t1"])     # the same swap
    assert len(engine.asked("live_preview_squares")) == asked
    engine.squares = [_square(0, stamp="2-2"), _square(1)]
    preview.world_swapped(["+53-061", "drape", "t2"])
    _drain(qapp, preview)
    assert len(engine.asked("live_preview_squares")) == asked + 1
    assert set(preview.images.keys()) == {s["key"] for s in engine.squares}


def test_a_late_landed_square_and_x_planes_own_tile_are_marked(qapp):
    """A square X-Plane holds an earlier version of (``stale``) is hatched
    in the ``reload`` color; a tile where X-Plane draws its own scenery is
    washed in ``own``'s; the plain square is not marked."""
    engine = _Engine([_square(0, stale=True), _square(5)],
                     tiles=[{"lat": 52, "lon": -61, "state": "own"}])
    preview = QTLIVE.LivePreview(engine)
    preview.set_view(52, -61, 54, -60, 400)
    preview.set_enabled(True)
    _drain(qapp, preview)
    image = _paint(preview, 400)
    reload = QColor(*TEXT.MARK_COLORS["reload"])

    def marked(x0, y0, x1, y1, colour):
        return any(QColor(image.pixel(x, y)) == colour
                   for x in range(x0, x1) for y in range(y0, y1))
    assert marked(2, 2, 38, 38, reload)                # square 0: hatched
    assert not marked(202, 2, 238, 38, reload)         # square 5: plain
    big = _paint(preview, 800)                         # the own tile, 400 px down
    own = QColor(*TEXT.MARK_COLORS["own"])
    assert any(QColor(big.pixel(x, y)) == own
               for x in range(2, 60) for y in range(402, 460))
