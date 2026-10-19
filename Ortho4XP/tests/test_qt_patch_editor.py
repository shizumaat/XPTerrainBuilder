"""The Qt 2D patch editor (issue #46, spec patch-editor-20261015 §3.3, §4,
§6): the snap target, undo / redo of every edit operation through the
QUndoStack (the shared twin fixture's cases), save → reload through the
engine's patch commands in ``tmp_path``, the hand-made rule, and the map
gestures end to end (a drag that ends snapped is ONE step: move + merge).

Headless (offscreen Qt); no engine process, no network, no X-Plane."""

import json
import os
import sys
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest  # noqa: E402

pytest.importorskip("PySide6")

from PySide6.QtCore import QEvent, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QMouseEvent  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

import O4_File_Names as FNAMES  # noqa: E402
import O4_Qt_Map as QTMAP  # noqa: E402
from O4_Qt_Patch_Editor import PatchEditor  # noqa: E402
from O4_Qt_Patch_Geometry import scene_xy, snap_target, style_class  # noqa: E402
from O4_Qt_Patch_Model import LoadedPatch, PatchEditModel  # noqa: E402
from O4_Qt_Pack_Outlines import footprints_from_pack_objects  # noqa: E402
from O4_Qt_Patch_Panel import parse_number, source_line  # noqa: E402
from o4_engine import patch_commands as PC  # noqa: E402
from o4_engine import patch_edit as PE  # noqa: E402

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "patch_edit_ops.json")
with open(FIXTURE, encoding="utf-8") as _f:
    CASES = json.load(_f)["cases"]

TILE = "+30+031"
_AUTO = """<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6" generator="o4">
  <node id="-1" lat="30.1" lon="31.4"><tag k="alt_abs" v="100.125"/></node>
  <node id="-2" lat="30.1" lon="31.401"><tag k="alt_abs" v="101"/></node>
  <node id="-3" lat="30.101" lon="31.401"><tag k="alt_abs" v="102"/></node>
  <node id="-4" lat="30.101" lon="31.4"><tag k="alt_abs" v="103"/></node>
  <node id="-5" lat="30.1012" lon="31.4012"><tag k="alt_abs" v="104"/></node>
  <way id="-10"><nd ref="-1"/><nd ref="-2"/><nd ref="-3"/><nd ref="-4"/><nd ref="-1"/><tag k="aeroway" v="apron"/><tag k="role" v="apron"/></way>
  <way id="-11"><nd ref="-3"/><nd ref="-5"/><tag k="highway" v="service"/></way>
</osm>
"""


@pytest.fixture(scope="module")
def qapp():
    yield QApplication.instance() or QApplication([])


@pytest.fixture
def patches(tmp_path, monkeypatch):
    """A Patches root under tmp_path with one auto patch; staleness
    answered without an X-Plane install."""
    monkeypatch.setattr(FNAMES, "Patch_dir", str(tmp_path / "Patches"))
    monkeypatch.setattr(PC, "_staleness", lambda tile, icao, doc, source: (False, []))
    directory = FNAMES.patch_dir(30, 31)
    os.makedirs(directory)
    with open(os.path.join(directory, "ZZZZ_auto.patch.osm"), "w", encoding="utf-8", newline="\n") as f:
        f.write(_AUTO)
    return directory


# ─── the snap target (§3.3) ────────────────────────────────────────────────

def test_snap_target_nearest_within_8px_inclusive():
    cands = [(-1, 100.0, 100.0, 30.0, 31.0), (-2, 105.0, 100.0, 30.1, 31.1)]
    assert snap_target(103.0, 100.0, cands, 11) == -2          # 2 px beats 3 px
    assert snap_target(92.0, 100.0, cands, 11) == -1           # exactly 8 px: inside
    assert snap_target(91.9, 100.0, cands, 11) is None         # 8.1 px: outside
    assert snap_target(0.0, 0.0, [], 11) is None


def test_snap_target_ties_go_to_the_lowest_survivor_key_then_id():
    # equidistant: the lower (lat, lon) at the identity wins, whatever the order
    a, b = (-7, 96.0, 100.0, 30.2, 31.0), (-9, 104.0, 100.0, 30.1, 31.0)
    assert snap_target(100.0, 100.0, [a, b], 11) == -9
    assert snap_target(100.0, 100.0, [b, a], 11) == -9
    # same key at the identity: the lowest id
    c, d = (-3, 96.0, 100.0, 30.1, 31.0), (-4, 104.0, 100.0, 30.1, 31.0)
    assert snap_target(100.0, 100.0, [c, d], 11) == -4


def test_style_classes_follow_role_over_aeroway():
    assert style_class({"aeroway": "apron", "role": "graded_strip"}) == "ground"
    assert style_class({"aeroway": "taxiway", "role": "primary_parallel"}) == "taxiway"
    assert style_class({"highway": "service"}) == "road"
    assert style_class({}) == "ground"


# ─── undo / redo of every op through the QUndoStack ───────────────────────

def _loaded(doc, name="ZZZZ_auto.patch.osm", source="auto"):
    return LoadedPatch(tile=TILE, icao="ZZZZ", source=source,
                       path=os.path.join("/x", name), header={})


@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_every_fixture_case_undoes_and_redoes(qapp, case):
    doc0 = PE.PatchDoc.from_wire(case["doc"]["nodes"], case["doc"]["ways"])
    model = PatchEditModel()
    model.load(_loaded(doc0), doc0)
    want = doc0
    steps = 0
    for op in case["ops"]:
        want = PE.apply_op(want, op["op"], op["args"])
        if model.perform(op["op"], lambda d, op=op: PE.apply_op(d, op["op"], op["args"])):
            steps += 1
    assert model.doc == want
    assert model.unsaved_edits == model.undo_stack.count() == steps
    while model.undo_stack.canUndo():
        model.undo_stack.undo()
    assert model.doc == doc0 and model.unsaved_edits == 0
    while model.undo_stack.canRedo():
        model.undo_stack.redo()
    assert model.doc == want


def test_move_and_merge_is_one_step_and_a_refused_edit_is_none(qapp):
    case = next(c for c in CASES if c["name"] == "move_then_merge_is_the_release_while_snapped")
    doc0 = PE.PatchDoc.from_wire(case["doc"]["nodes"], case["doc"]["ways"])
    want = doc0
    for op in case["ops"]:
        want = PE.apply_op(want, op["op"], op["args"])
    move, merge = (op["args"] for op in case["ops"])
    model = PatchEditModel()
    model.load(_loaded(doc0), doc0)
    model.set_selection(move["ids"])
    assert model.move_selection(move["ids"], move["dlat"], move["dlon"],
                                (merge["source"], merge["target"]))
    assert model.doc == want and model.undo_stack.count() == 1
    assert merge["target"] in model.selection and merge["source"] not in model.selection
    model.undo_stack.undo()
    assert model.doc == doc0
    # a refused edit (not an edge) changes nothing and says why
    model.undo_stack.redo()
    assert not model.insert_node(10**9, 10**9 + 1)
    assert model.undo_stack.count() == 1 and model.edit_error


def test_history_survives_a_save_and_counts_back_to_it(qapp):
    doc0 = PE.PatchDoc.from_wire(CASES[0]["doc"]["nodes"], CASES[0]["doc"]["ways"])
    model = PatchEditModel()
    model.load(_loaded(doc0), doc0)
    model.set_selection([-1])
    model.offset_selection_alt(1.0)
    model.offset_selection_alt(1.0)
    model.mark_saved("/x/ZZZZ_edited.patch.osm")
    assert model.unsaved_edits == 0 and model.patch.source == "manual"
    model.undo_stack.undo()
    assert model.unsaved_edits == 1
    model.offset_selection_alt(5.0)          # branches off below the save
    assert model.unsaved_edits >= 1


# ─── the hand-made rule (§1.2, by FILE NAME) ──────────────────────────────

def test_hand_made_is_decided_by_file_name():
    assert _loaded(None, "ZZZZ_runways.patch.osm", "manual").is_hand_made
    assert not _loaded(None, "ZZZZ_edited.patch.osm", "manual").is_hand_made
    assert not _loaded(None, "ZZZZ_auto.patch.osm", "auto").is_hand_made
    assert source_line(_loaded(None, "ZZZZ_runways.patch.osm", "manual"), None) \
        == "Manual · ZZZZ_runways.patch.osm"
    assert source_line(_loaded(None, "ZZZZ_edited.patch.osm", "manual"), None) \
        == "Edited · ZZZZ_edited.patch.osm"
    assert source_line(_loaded(None), None) == "Automatic"
    assert parse_number(" 62,7 ") == 62.7 and parse_number("+0.50") == 0.5
    assert parse_number("x") is None


# ─── the editor on a map: load, drag-snap-merge, save → reload ────────────

@pytest.fixture
def editor(qapp, patches, tmp_path, monkeypatch):
    monkeypatch.setattr(QTMAP, "livemap_cache_dir", lambda: str(tmp_path / "livemap"))
    view = QTMAP.MapView()
    view.resize(900, 700)
    view._start_workers = lambda: None
    view._update_timer.stop()
    built = {(30, 31): {"provider": "BI", "zl": 17}}
    ed = PatchEditor(view, view, mock.Mock(), lambda: built, run_async=False)
    ed.outlines.set_enabled(False)
    asked = []
    ed.controller.ask = lambda title, message, quitting: asked.append(message) or "keep"
    ed.asked = asked
    # zoom onto the patch (a few hundred metres across)
    x, y = scene_xy(30.1006, 31.4006, QTMAP.SCENE_ZL)
    view._zoom = 18.0
    view._apply_zoom()
    view.centerOn(QPointF(float(x), float(y)))
    view._update_timer.stop()
    yield ed, view
    view.deleteLater()


def _screen(ed, nid):
    ed.overlay.index.project(ed.overlay.transform())
    return QPointF(*ed.overlay.index.screen(nid))


def _mouse(view, kind, pos, buttons=Qt.LeftButton, mods=Qt.NoModifier):
    ev = QMouseEvent(kind, pos, view.viewport().mapToGlobal(pos.toPoint()),
                     Qt.LeftButton, buttons, mods)
    {QEvent.MouseButtonPress: view.mousePressEvent,
     QEvent.MouseMove: view.mouseMoveEvent,
     QEvent.MouseButtonRelease: view.mouseReleaseEvent}[kind](ev)


def test_load_drag_snap_merge_save_and_reload(editor, patches):
    ed, view = editor
    ed.controller.evaluate()                       # lists the tile …
    ed.controller.evaluate()                       # … and loads the airport
    assert ed.controller.state == ed.controller.LOADED
    assert ed.model.patch.icao == "ZZZZ" and len(ed.model.doc.nodes) == 5
    assert not ed.panel.isHidden() and ed.panel.title() == "Airport ground shape · ZZZZ"
    ed.model.set_mode("Edit")
    # drag -5 onto -3: the pointer within 8 px snaps; release merges (1 step)
    start, target = _screen(ed, -5), _screen(ed, -3)
    _mouse(view, QEvent.MouseButtonPress, start)
    assert ed.model.selection == {-5}
    _mouse(view, QEvent.MouseMove, (start + target) / 2)
    assert ed.gestures.snap_target is None
    _mouse(view, QEvent.MouseMove, target + QPointF(3, 0))
    assert ed.gestures.snap_target == -3
    _mouse(view, QEvent.MouseButtonRelease, target + QPointF(3, 0), buttons=Qt.NoButton)
    assert ed.model.undo_stack.count() == 1
    assert -5 not in ed.model.doc.nodes                       # merged into -3
    assert ed.model.doc.nodes[-3] == ed.model.loaded_nodes[-3]  # target kept as it was
    assert ed.model.selection == {-3}
    # Set to, then save through patch_save
    ed.model.set_selection([-1])
    ed.model.set_selection_alt(99.5)
    assert ed.model.unsaved_edits == 2
    ed.controller.save()
    edited = os.path.join(patches, "ZZZZ_edited.patch.osm")
    assert os.path.isfile(edited) and ed.model.unsaved_edits == 0
    assert ed.model.patch.path == edited and TILE in ed.model.tiles_needing_rebuild
    # reload: the build's override now serves the edited file
    reply = PC.patch_load(TILE, "ZZZZ")
    assert reply["source"] == "manual" and reply["path"] == edited
    doc = PE.PatchDoc.from_wire(reply["nodes"], reply["ways"])
    assert doc.nodes[-1][3] == 99.5 and -5 not in doc.nodes
    assert doc.ways == ed.model.doc.ways
    # undo still works after the save (history survives it)
    ed.model.undo_stack.undo()
    assert ed.model.unsaved_edits == 1


def test_unsaved_edits_ask_before_quitting_and_revert_moves_the_file_aside(editor, patches):
    ed, view = editor
    ed.controller.evaluate()
    ed.controller.evaluate()
    ed.model.set_selection([-2])
    ed.model.offset_selection_alt(0.5)
    assert not ed.confirm_quit() and ed.asked[-1] == "Save your 1 unsaved edit before quitting?"
    ed.controller.ask = lambda *a: "save"
    assert ed.confirm_quit()
    assert ed.model.patch.file_name == "ZZZZ_edited.patch.osm"
    ed.controller.revert_to_auto()
    assert os.path.isfile(os.path.join(patches, "ZZZZ_edited.patch.osm.disabled"))
    ed.controller.evaluate()
    ed.controller.evaluate()
    assert ed.model.patch.source == "auto" and ed.model.unsaved_edits == 0


def test_hand_made_patch_saves_back_to_itself(editor, patches):
    ed, view = editor
    hand = os.path.join(patches, "ZZZZ_runways.patch.osm")
    with open(hand, "w", encoding="utf-8", newline="\n") as f:
        f.write(_AUTO)
    ed.controller.evaluate()
    ed.controller.evaluate()
    assert ed.model.patch.path == hand and ed.model.patch.is_hand_made
    ed.model.set_mode("Edit")
    ed.model.set_selection([-4])
    ed.model.delete_selection()
    ed.controller.save()
    assert ed.model.patch.path == hand
    assert not os.path.exists(os.path.join(patches, "ZZZZ_edited.patch.osm"))
    assert not ed.panel.hand_made_note.isHidden()
    assert ed.panel.revert_button.isHidden()


def test_box_select_and_escape_and_delete_keys(editor):
    ed, view = editor
    ed.controller.evaluate()
    ed.controller.evaluate()
    ed.model.set_mode("Edit")
    a, b = _screen(ed, -1), _screen(ed, -3)
    lo = QPointF(min(a.x(), b.x()) - 5, min(a.y(), b.y()) - 5)
    hi = QPointF(max(a.x(), b.x()) + 5, max(a.y(), b.y()) + 5)
    _mouse(view, QEvent.MouseButtonPress, lo, mods=Qt.ShiftModifier)
    _mouse(view, QEvent.MouseMove, hi, mods=Qt.ShiftModifier)
    _mouse(view, QEvent.MouseButtonRelease, hi, buttons=Qt.NoButton, mods=Qt.ShiftModifier)
    assert ed.model.selection == {-1, -2, -3, -4}
    view.viewport().grab()                          # selection squares + "+" handles
    assert ed.gestures.key("escape") and ed.model.selection == set()
    ed.model.set_selection([-5])
    assert ed.gestures.key("delete") and -5 not in ed.model.doc.nodes
    assert ed.model.undo_stack.undoText() == "Delete Node"


def test_footprints_turn_with_the_heading():
    import base64
    import numpy as np
    # a 10 m (east) x 2 m (south) box at heading 90: 10 m south, 2 m west
    v = np.array([[0, 0, 0], [10, 0, 0], [10, 0, 2], [0, 0, 2], [0, 5, 0]], dtype="<f4")
    t = np.array([[0, 1, 2], [0, 2, 3], [0, 1, 4]], dtype="<u4")
    result = {"models": [{"key": "m", "vertices_f32_b64": base64.b64encode(v.tobytes()).decode(),
                          "triangles_u32_b64": base64.b64encode(t.tobytes()).decode()}],
              "placements": [{"model": "m", "lat": 30.0, "lon": 31.0, "heading_deg": 90.0, "agl_m": 0}],
              "facades": [{"ring": [[30, 31], [30, 31.001], [30.001, 31.001]], "height_m": 5}]}
    rings = footprints_from_pack_objects(result)
    assert len(rings) == 2
    lats = [p[0] for p in rings[0]]
    lons = [p[1] for p in rings[0]]
    assert (30.0 - min(lats)) * 111320 == pytest.approx(10, abs=1e-6)
    assert max(lats) == pytest.approx(30.0, abs=1e-12)
    assert (31.0 - min(lons)) * 111320 * np.cos(np.radians(30)) == pytest.approx(2, abs=1e-6)


def test_pack_outlines_follow_the_patch_through_pack_objects_ready(editor):
    from o4_engine import events as EV
    ed, view = editor
    asked = {}

    def pack_objects(**kw):
        asked.update(kw)
        return {"status": "started"}
    table = ed.engine._table()
    table["pack_objects"] = pack_objects
    table["pack_outlines"] = lambda tile, icao: {
        "pavement": [{"kind": "pavement", "rings": [[[30.1, 31.4], [30.1, 31.401], [30.101, 31.4]]]}],
        "missing": ["The pack draws no boundary."]}
    ed.controller.evaluate()
    ed.controller.evaluate()
    ed.outlines.set_enabled(True)
    assert asked["tile"] == TILE and asked["icao"] == "ZZZZ"
    s, w, n, e = asked["bbox"]                      # the patch bbox + 500 m (A9)
    assert (30.1 - s) * 111320 == pytest.approx(500)
    assert not ed.outlines._pavement.isEmpty() and ed.outlines._footprints.isEmpty()
    ed.on_pack_objects_ready(EV.PackObjectsReady(request=asked["request"], result={
        "models": [], "placements": [], "missing": [],
        "facades": [{"ring": [[30.1, 31.4], [30.1, 31.4005], [30.1005, 31.4005]], "height_m": 4}]}))
    assert not ed.outlines._footprints.isEmpty()
    assert "The pack draws no boundary." in ed.outlines.help_text
    assert ed.overlay.toolbar.outlines_box.isChecked()
    view.viewport().grab()                          # paints every layer once


def test_a_save_never_asks_for_pack_objects_again(editor):
    """Owner 1.0.398: a save moves the patch's path (auto → edited file);
    the outlines ask ``pack_objects`` once per open, never on a save or
    the edits after it."""
    ed, view = editor
    calls = []
    table = ed.engine._table()
    table["pack_objects"] = lambda **kw: calls.append(kw) or {"status": "started"}
    table["pack_outlines"] = lambda tile, icao: {"pavement": [], "missing": []}
    ed.controller.evaluate()
    ed.controller.evaluate()
    ed.outlines.set_enabled(True)
    assert len(calls) == 1
    ed.model.set_selection([-1])
    ed.model.set_selection_alt(99.5)
    ed.controller.save()
    assert ed.model.patch.path.endswith("ZZZZ_edited.patch.osm")
    north = max(ed.model.doc.nodes.values(), key=lambda n: n[1])[0]
    assert ed.model.move_selection([north], 0.001, 0.0)   # an edit after it grows the box
    assert len(calls) == 1


def test_the_3d_button_and_ctrl_3_open_one_preview_window(editor):
    ed, view = editor
    table = ed.engine._table()
    table["pack_objects"] = lambda **kw: {"status": "started"}

    def no_dem(**kw):
        raise ValueError("No elevation data for tile +30+031.")
    table["terrain_sample"] = no_dem
    ed.controller.evaluate()
    ed.controller.evaluate()
    button = ed.overlay.toolbar.preview_button
    assert button.text() == "3D" and "3D preview" in button.toolTip()
    button.click()
    window = ed.preview
    assert window.isVisible() and window.windowTitle() == "3D Preview · ZZZZ"
    assert "No elevation data for tile +30+031." in window.chip_text()
    action = ed.menu_actions(view)["preview"]
    assert action.shortcut().toString() == "Ctrl+3"
    action.trigger()
    assert ed.preview is window                     # one window, raised
    window.close()


# ─── a line selects its whole shape (#759) ────────────────────────────────

def test_shape_pick_rules_are_pure():
    import O4_Qt_Patch_ShapePick as PICK
    assert PICK.click_target(-5, True, True) == ("node", -5)
    assert PICK.click_target(None, True, True) == ("handle",)
    assert PICK.click_target(None, False, True) == ("edge",)
    assert PICK.click_target(None, False, False) == ("empty",)
    case = next(c for c in CASES if c["name"] == "delete_ways_shared_edge_keeps_shared_nodes")
    doc = PE.PatchDoc.from_wire(case["doc"]["nodes"], case["doc"]["ways"])
    # two equal squares share -2/-3: equal area goes to the lower way id
    assert PICK.shapes_on_edge(doc, -3, -2) == [-102, -101]
    assert PICK.shapes_on_edge(doc, -1, -3) == []
    first = PICK.choose_shape([-102, -101], 10, 10, None)
    second = PICK.choose_shape([-102, -101], 13, 10, first)
    assert (first.chosen, second.chosen) == (-102, -101)
    assert PICK.choose_shape([-102, -101], 13, 10, second).chosen == -102
    assert PICK.choose_shape([-102, -101], 14.5, 10, first).chosen == -102
    st = PICK.shape_stats(doc, -101)
    assert st.node_count == 4 and st.neighbours == 2 and (st.min_alt, st.max_alt) == (100.0, 106.0)
    assert st.area_m2 == pytest.approx(108.7 * 94.2, rel=0.01)
    assert PICK.shape_stats(doc, -103).area_m2 == 0.0


_TRIANGLE = '  <way id="-12"><nd ref="-2"/><nd ref="-3"/><nd ref="-5"/><nd ref="-2"/>' \
            '<tag k="building" v="yes"/><tag k="role" v="building"/></way>\n</osm>'


def _along(ed, a, b, t):
    pa, pb = _screen(ed, a), _screen(ed, b)
    return pa + (pb - pa) * t


def _click(view, pos, mods=Qt.NoModifier):
    _mouse(view, QEvent.MouseButtonPress, pos, mods=mods)
    _mouse(view, QEvent.MouseButtonRelease, pos, buttons=Qt.NoButton, mods=mods)


def test_click_line_selects_cycles_drags_and_deletes_the_shape(editor, patches):
    ed, view = editor
    with open(os.path.join(patches, "ZZZZ_auto.patch.osm"), "w", encoding="utf-8", newline="\n") as f:
        f.write(_AUTO.replace("</osm>", _TRIANGLE.split("\n</osm>")[0] + "\n</osm>"))
    ed.controller.evaluate()
    ed.controller.evaluate()
    ed.model.set_mode("Edit")
    assert len(ed.model.doc.ways) == 3
    # a click on the shared edge -2/-3 picks the smaller shape, repeats cycle
    spot = _along(ed, -2, -3, 0.25)
    _click(view, spot)
    assert ed.model.shape_selection == {-12} and ed.model.selection == set()
    _click(view, spot + QPointF(2, 0))
    assert ed.model.shape_selection == {-10}
    _click(view, spot)
    assert ed.model.shape_selection == {-12}
    assert not ed.panel.shape_box.isHidden() and ed.panel.delete_shapes.text() == "Delete shape"
    view.viewport().grab()                          # outline, tint, node squares, "+" handles
    spot = _along(ed, -2, -3, 0.25)                 # the first paint lays the view out anew
    # Shift-click on another line adds its shape; a node click is a node again
    _click(view, _along(ed, -1, -2, 0.25), mods=Qt.ShiftModifier)
    assert ed.model.shape_selection == {-12, -10}
    _click(view, _screen(ed, -4))
    assert ed.model.shape_selection == set() and ed.model.selection == {-4}
    # drag the selected triangle by its line: every node moves, one step, no snap
    _click(view, spot)
    assert ed.model.shape_selection == {-12}
    before = dict(ed.model.doc.nodes)
    press = _along(ed, -2, -3, 0.75)
    _mouse(view, QEvent.MouseButtonPress, press)
    _mouse(view, QEvent.MouseMove, press + QPointF(10, 0))
    _mouse(view, QEvent.MouseMove, _screen(ed, -4))   # over a node: a shape drag never snaps
    assert ed.gestures.snap_target is None
    _mouse(view, QEvent.MouseButtonRelease, _screen(ed, -4), buttons=Qt.NoButton)
    assert ed.model.undo_stack.count() == 1 and ed.model.undo_stack.undoText() == "Move Shape"
    moved = {n for n in before if ed.model.doc.nodes[n] != before[n]}
    assert moved == {-2, -3, -5}                       # shared -2/-3 stretch the apron
    # Delete: the triangle goes, the apron keeps its (shared) nodes; one step
    assert ed.gestures.key("delete")
    assert [w.id for w in ed.model.doc.ways] == [-10, -11]
    assert -5 in ed.model.doc.nodes                    # still the service road's
    assert ed.model.undo_stack.undoText() == "Delete Shape" and ed.model.shape_selection == set()
    ed.model.undo_stack.undo()
    assert len(ed.model.doc.ways) == 3


def test_mixed_selection_deletes_shapes_then_nodes_in_one_step(editor):
    ed, view = editor
    ed.controller.evaluate()
    ed.controller.evaluate()
    ed.model.set_mode("Edit")
    ed.model.select_shapes({-11})
    ed.model.set_selection({-1})
    assert ed.model.delete_selection()
    assert [w.id for w in ed.model.doc.ways] == [-10]
    assert -5 not in ed.model.doc.nodes and -1 not in ed.model.doc.nodes and -3 in ed.model.doc.nodes
    assert ed.model.undo_stack.count() == 1
    assert ed.model.undo_stack.undoText() == "Delete Shape"
