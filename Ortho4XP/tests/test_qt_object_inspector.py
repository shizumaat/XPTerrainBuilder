"""The object inspector on the Qt patch layer (#1702; the Mac app's
``PatchObjectInspector``): a click on a pack object's footprint selects it,
asks the engine's ``object_seat`` and grows the name box with its lines.

Offscreen, no network, a fake engine.
"""

import base64
import os
import sys
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import numpy as np  # noqa: E402
import pytest  # noqa: E402

pytest.importorskip("PySide6")

import O4_Qt_Map as QTMAP  # noqa: E402
import O4_Qt_Object_Inspector as OI  # noqa: E402
import O4_Qt_Pack_Outlines as POL  # noqa: E402
from O4_Qt_Patch_Geometry import scene_xy  # noqa: E402
from PySide6.QtCore import QObject, Signal  # noqa: E402
from PySide6.QtGui import QColor, QImage, QPainter, QTransform  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

OBJ = {"index": 41, "model": "objects/t1.obj", "lat": 30.0015, "lon": 31.0015, "agl_m": 0.0,
       "y_min": 0.0, "y_max": 12.5}
SEAT = {"pending": False, "lines": ["Height 12.5 m", "Top 612.5 m MSL", "Bottom 600.0 m MSL",
                                    "Kept as the pack places it, on the ground."]}


@pytest.fixture(scope="module")
def qapp():
    yield QApplication.instance() or QApplication([])


class _Model(QObject):
    document_changed = Signal()
    selection_changed = Signal()

    def __init__(self):
        super().__init__()
        self.has_selection = False
        self.patch = SimpleNamespace(tile="+30+031", icao="ZZZZ")


class _Engine:
    def __init__(self, reply=SEAT, error=None):
        self.calls, self.reply, self.error = [], reply, error

    def has(self, name):
        return name == "object_seat"

    def call(self, name, callback, **kw):
        self.calls.append((name, kw))
        callback(None if self.error else self.reply, self.error)


def _inspector(engine):
    model = _Model()
    outlines = POL.PackOutlines(SimpleNamespace(), model, QTMAP.SCENE_ZL)
    sq = lambda la, lo, d: [(la, lo), (la, lo + d), (la + d, lo + d), (la + d, lo)]  # noqa: E731
    outlines.pavement = POL._outlines([("Apron A", [sq(30.0, 31.0, 0.01)])], QTMAP.SCENE_ZL)
    outlines.footprints = POL._outlines([("t1.obj", [sq(30.001, 31.001, 0.001)], OBJ),
                                         ("gate.fac", [sq(30.003, 31.003, 0.001)])],
                                        QTMAP.SCENE_ZL)
    return OI.ObjectInspector(engine, model, outlines, lambda: {}), model, outlines


def test_object_footprints_carry_the_placement():
    hull = np.array([[0, 0], [10, 0], [10, -4], [0, -4]], "<f4")
    result = {"models": [{"key": "m.obj", "y_min": -0.5, "y_max": 9.0,
                          "plan_hull_f32_b64": base64.b64encode(hull.tobytes()).decode()}],
              "placements": [{"model": "m.obj", "lat": 45.0, "lon": -122.0, "heading_deg": 0,
                              "agl_m": 2.0, "index": 7},
                             {"model": "m.obj", "lat": 45.0, "lon": -122.0, "heading_deg": 0,
                              "agl_m": 0.0}],
              "facades": [{"ring": [[45.1, -122.1], [45.1, -122.09], [45.11, -122.09]],
                           "def": "a.fac"}]}
    rows = POL._object_footprints(result)
    assert [r[2] and r[2]["index"] for r in rows] == [7, None, None]
    assert rows[0][2] == {"index": 7, "model": "m.obj", "lat": 45.0, "lon": -122.0,
                          "agl_m": 2.0, "y_min": -0.5, "y_max": 9.0}
    assert POL.labelled_footprints(result) == [(r[0], r[1]) for r in rows]


def test_a_click_on_an_object_asks_its_seat(qapp):
    engine = _Engine()
    ins, model, outlines = _inspector(engine)
    assert not ins.select_at(30.008, 31.008)            # the apron: no object
    assert not ins.select_at(30.0035, 31.0035)          # a facade: not an object
    assert ins.select_at(30.0015, 31.0015)
    (name, kw), = engine.calls
    assert name == "object_seat" and kw["index"] == 41 and kw["y_max"] == 12.5
    assert kw["tile"] == "+30+031" and kw["icao"] == "ZZZZ"
    assert ins.lines == ["t1.obj"] + SEAT["lines"]
    assert ins.select_at(30.0015, 31.0015) and len(engine.calls) == 1   # the same object
    model.has_selection = True
    model.selection_changed.emit()                      # a node or shape selected
    assert ins.selected is None and ins.lines == []


def test_a_failed_read_says_so_and_a_reload_clears(qapp):
    ins, _model, outlines = _inspector(_Engine(error="no plan"))
    assert ins.select_at(30.0015, 31.0015)
    assert ins.lines == ["t1.obj", "Its seat could not be read: no plan"]
    outlines.footprints = []
    outlines.changed.emit()                             # a new document's outlines
    assert ins.selected is None


def test_the_selection_paints(qapp):
    ins, _model, _outlines = _inspector(_Engine())
    ins.select_at(30.0015, 31.0015)
    size, zl = 400, 19.0
    k = 2.0 ** (zl - QTMAP.SCENE_ZL)
    x, y = scene_xy(30.0015, 31.0015, QTMAP.SCENE_ZL)
    view = QTransform(k, 0, 0, k, size / 2 - float(x) * k, size / 2 - float(y) * k)
    img = QImage(size, size, QImage.Format_ARGB32)
    img.fill(0)
    p = QPainter(img)
    ins.paint(p, view, QColor("#FFD60A"))
    p.end()
    assert QColor(img.pixel(size // 2, size // 2)).alpha() > 0      # the name box
