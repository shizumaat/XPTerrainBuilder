"""The Qt editor's shape elevation tags (issue #2137): the model's edits
(one undo step, tags written as ``patch_shape_alt`` says), the inspector
rows, and the sloping rectangle's map drawing with its label edit handles.
Offscreen, no engine."""

import os
import sys
from types import SimpleNamespace as NS

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest  # noqa: E402

pytest.importorskip("PySide6")

from PySide6.QtCore import QPointF  # noqa: E402
from PySide6.QtGui import QImage, QPainter  # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

import O4_Qt_Patch_Shape_Alt as SHAPEALT  # noqa: E402
from O4_Qt_Patch_Model import LoadedPatch, PatchEditModel  # noqa: E402
from o4_engine import patch_edit as PE  # noqa: E402

NODES = [[-1, 30.0, 31.0, 5.0], [-2, 30.0007, 31.0, 5.0], [-3, 30.0007, 31.0001, None],
         [-4, 30.0, 31.0001, None], [-5, 30.001, 31.001, 9.0], [-6, 30.0012, 31.001, None],
         [-7, 30.0012, 31.0012, None]]
WAYS = [{"id": -10, "refs": [-1, -2, -3, -4, -1],
         "tags": {"role": "tunnel_ramp", "altitude_high": "172.40", "altitude_low": "170.90"}},
        {"id": -11, "refs": [-5, -6, -7, -5], "tags": {"role": "apron", "cst_alt_abs": "80"}},
        {"id": -12, "refs": [-1, -5], "tags": {"highway": "service"}}]


@pytest.fixture(scope="module")
def qapp():
    yield QApplication.instance() or QApplication([])


@pytest.fixture
def model(qapp):
    doc = PE.PatchDoc.from_wire(NODES, WAYS)
    m = PatchEditModel()
    m.load(LoadedPatch(tile="+30+031", icao="ZZZZ", source="auto", path="/x/ZZZZ_auto.patch.osm",
                       header={}), doc)
    m.set_mode("Edit")
    return m


def _tags(model, way_id):
    return next(w.tags for w in model.doc.ways if w.id == way_id)


def test_slope_and_level_edits_are_one_undo_step_each(model):
    assert model.set_slope(-10, "low", 168.5)
    assert _tags(model, -10)["altitude_low"] == "168.50"
    assert _tags(model, -10)["altitude_high"] == "172.40"
    assert model.set_shape_level(-11, 81.25)
    assert _tags(model, -11)["cst_alt_abs"] == "81.25"
    assert model.unsaved_edits == 2
    model.undo_stack.undo()
    assert _tags(model, -11)["cst_alt_abs"] == "80"
    model.undo_stack.undo()
    assert _tags(model, -10)["altitude_low"] == "170.90"
    assert model.undo_stack.undoText() == ""
    assert not model.set_slope(-99, "high", 1.0)


def test_inspector_rows(model):
    box = SHAPEALT.ShapeAltBox(model)
    ways = {w.id: w for w in model.doc.ways}
    box.refresh(ways[-10], 2)
    assert not box.isHidden()
    assert box.high.title.text() == SHAPEALT.HIGH_TITLE and box.high.edit.text() == "172.40"
    assert box.low.edit.text() == "170.90"
    assert box.level.isHidden()
    box.low.edit.setText("169")
    box.low.edit.returnPressed.emit()
    assert _tags(model, -10)["altitude_low"] == "169.00"
    box.refresh(ways[-11], 1)
    assert box.level.title.text() == SHAPEALT.LEVEL_TITLE and box.level.edit.text() == "80.00"
    assert "1 nodes carry their own elevation" in box.notes.text()
    box.level.edit.setText("82.5")
    box.level.edit.returnPressed.emit()
    assert _tags(model, -11)["cst_alt_abs"] == "82.50"
    box.refresh(ways[-12], 0)
    assert box.isHidden()


def test_slope_layer_draws_labels_that_edit_their_side(model):
    host = QWidget()
    host.resize(400, 400)

    def screen_of(lat, lon):   # 1 px ≈ 0.11 m around the ramp
        return QPointF((lon - 31.0) * 1e6 + 100, (30.0008 - lat) * 4e5 + 40)

    overlay = NS(model=model, screen_of=screen_of, map=NS(viewport=lambda: host))
    layer = SHAPEALT.SlopeLayer(overlay)
    layer.rebuild(model.doc)
    assert [s[0] for s in layer.shapes] == [-10]
    image = QImage(400, 400, QImage.Format_ARGB32)
    painter = QPainter(image)
    layer.paint(painter)
    painter.end()
    sides = [(wid, side) for _box, wid, side, _v in layer.labels]
    assert sides == [(-10, "high"), (-10, "low")]
    high_box = layer.labels[0][0]
    low_box = layer.labels[1][0]
    assert high_box.center().y() > low_box.center().y()   # high side is the south edge here
    assert layer.press(low_box.center())
    layer.popup.edit.setText("167.25")
    layer.popup.edit.returnPressed.emit()
    assert _tags(model, -10)["altitude_low"] == "167.25"
    assert not layer.press(QPointF(1, 1))
