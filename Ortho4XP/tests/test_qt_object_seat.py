"""An object's elevation by hand and a node snapped to an object on the Qt
patch layer (#1703; the Mac app's ``PatchObjectElevation.swift``).

Offscreen, no network, a fake engine.
"""

import os
import sys
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest  # noqa: E402

pytest.importorskip("PySide6")

import O4_Qt_Map as QTMAP  # noqa: E402
import O4_Qt_Object_Inspector as OI  # noqa: E402
import O4_Qt_Object_Seat as SEAT  # noqa: E402
import O4_Qt_Pack_Outlines as POL  # noqa: E402
from o4_engine import patch_edit as PE  # noqa: E402
from O4_Qt_Patch_Model import LoadedPatch, PatchEditModel  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

OBJ = {"index": 41, "model": "objects/t1.obj", "lat": 30.0015, "lon": 31.0015, "agl_m": 0.0,
       "y_min": -0.5, "y_max": 12.0}
SEAT_REPLY = {"pending": False, "lines": ["Height 12.5 m"], "top_m": 612.0, "bottom_m": 599.5,
              "height_m": 12.5, "user_zero_m": None}


@pytest.fixture(scope="module")
def qapp():
    yield QApplication.instance() or QApplication([])


class _Engine:
    def __init__(self):
        self.calls, self.zero = [], None

    def has(self, name):
        return name in ("object_seat", "object_seat_set")

    def call(self, name, callback, **kw):
        self.calls.append((name, kw))
        if name == "object_seat_set":
            prev = self.zero
            self.zero = kw.get("zero_m", kw["bottom_m"] - kw["y_min"] if "bottom_m" in kw else None)
            callback({"index": kw["index"], "zero_m": self.zero, "previous_zero_m": prev}, None)
        else:
            callback(dict(SEAT_REPLY, user_zero_m=self.zero), None)


def _setup():
    model = PatchEditModel()
    doc = PE.PatchDoc.from_wire([[1, 30.0, 31.0, None], [2, 30.001, 31.0, 50.0]],
                                [{"id": 9, "refs": [1, 2], "tags": {}}])
    model.load(LoadedPatch.from_reply("+30+031", {"icao": "ZZZZ", "path": "/x/ZZZZ_auto.patch.osm",
                                                  "source": "auto", "header": {}}), doc)
    engine = _Engine()
    outlines = POL.PackOutlines(SimpleNamespace(), model, QTMAP.SCENE_ZL)
    sq = [(30.001, 31.001), (30.001, 31.002), (30.002, 31.002), (30.002, 31.001)]
    outlines.footprints = POL._outlines([("t1.obj", [sq], OBJ)], QTMAP.SCENE_ZL)
    return OI.ObjectInspector(engine, model, outlines, lambda: {}), model, engine, outlines


def test_snap_points_are_corners_and_edge_middles():
    v = SEAT._vertices([(0, 0), (0, 10), (10, 10), (10, 0), (0, 0)])
    assert v[:4] == [(0, 0), (0, 10), (10, 10), (10, 0)] and v[4] == (0, 5) and len(v) == 8


def test_vertex_at_finds_the_nearest_object_point(qapp):
    _ins, _model, _engine, outlines = _setup()

    def screen(lat, lon):                       # 1 px per 1e-5 degree
        return lon * 1e5, -lat * 1e5
    hit = SEAT.vertex_at(outlines.footprints, screen, 31.0015 * 1e5 + 3, -30.001 * 1e5, 8)
    assert hit is not None and hit[0].object == OBJ and hit[1:] == (30.001, 31.0015)
    assert SEAT.vertex_at(outlines.footprints, screen, 0, 0, 8) is None


def test_set_elevation_is_one_undo_step_and_no_patch_edit(qapp):
    ins, model, engine, _outlines = _setup()
    assert ins.select_at(30.0015, 31.0015) and ins.can_set_elevation
    ins.set_elevation(600.0)
    set_kw = [kw for name, kw in engine.calls if name == "object_seat_set"][-1]
    assert set_kw["bottom_m"] == 600.0 and set_kw["y_min"] == -0.5 and engine.zero == 600.5
    assert model.undo_stack.count() == 1 and model.unsaved_edits == 0
    assert "+30+031" in model.tiles_needing_rebuild
    model.undo_stack.undo()
    assert engine.zero is None                          # back to the stage's own seat
    model.undo_stack.redo()
    assert engine.zero == 600.5


def test_a_snapped_node_takes_the_object_top(qapp, monkeypatch):
    ins, model, _engine, _outlines = _setup()
    shown = []
    monkeypatch.setattr(SEAT.QMenu, "popup", lambda self, pos: shown.append(self))
    ins.offer_top_or_bottom(1, OBJ, None, None)
    (menu,) = shown
    titles = [a.text() for a in menu.actions()]
    assert titles[1:] == ["Top of the object (612.00 m)", "Bottom of the object (599.50 m)",
                          SEAT.KEEP_CURRENT]
    menu.actions()[1].trigger()
    assert model.doc.nodes[1][3] == 612.0 and model.unsaved_edits == 1
