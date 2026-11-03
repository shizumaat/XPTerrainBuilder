"""A shape's classification by hand on the Qt patch layer (#1697; the Mac
app's ``PatchShapeRole.swift``).  Offscreen, no network, a fake engine."""

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest  # noqa: E402

pytest.importorskip("PySide6")

import O4_Qt_Patch_Role as ROLE  # noqa: E402
from o4_engine import patch_edit as PE  # noqa: E402
from O4_Qt_Patch_Model import MODE_EDIT, LoadedPatch, PatchEditModel  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

CHOICES = [{"role": "apron", "label": "Apron"}, {"role": "junction", "label": "Taxiway: junction"},
           {"role": "parking_lot", "label": "Parking lot"}]


@pytest.fixture(scope="module")
def qapp():
    yield QApplication.instance() or QApplication([])


class _Engine:
    def __init__(self):
        self.calls, self.rows = [], {}

    def has(self, name):
        return name in ("patch_roles", "patch_role_set")

    def call(self, name, callback, **kw):
        self.calls.append((name, kw))
        if name == "patch_role_set":
            src = kw["ref"].split("#")[0]
            prev = self.rows.pop(src, None)
            if kw.get("role"):
                self.rows[src] = {"source": src, "role": kw["role"],
                                  "was": prev["was"] if prev else kw["was"], "description": ""}
            callback({"source": src, "role": kw.get("role"),
                      "previous_role": prev["role"] if prev else None, "description": ""}, None)
        else:
            callback({"choices": CHOICES, "overrides": list(self.rows.values())}, None)


def _setup():
    model = PatchEditModel()
    doc = PE.PatchDoc.from_wire(
        [[1, 30.0, 31.0, None], [2, 30.001, 31.0, None], [3, 30.001, 31.001, None]],
        [{"id": 9, "refs": [1, 2, 3, 1], "tags": {"role": "junction", "ref": "pav7#1"}},
         {"id": 10, "refs": [1, 2], "tags": {"role": "graded_strip", "ref": "adjacent_ground"}}])
    model.load(LoadedPatch.from_reply("+30+031", {"icao": "ZZZZ", "path": "/x/ZZZZ_auto.patch.osm",
                                                  "source": "auto", "header": {}}), doc)
    model.set_mode(MODE_EDIT)
    engine = _Engine()
    return ROLE.RoleRow(engine, model), model, engine


def test_only_a_pack_pavement_offers_a_classification(qapp):
    row, model, _engine = _setup()
    model.shape_selection = {10}
    row.refresh()
    assert not row.isVisibleTo(None) and row.way() is None
    model.shape_selection = {9}
    row.refresh()
    assert row.way() is not None and row.button.text() == "Taxiway: junction"
    assert [a.text() for a in row.menu.actions()] == [c["label"] for c in CHOICES]


def test_a_change_is_one_undo_step_and_no_patch_edit(qapp):
    row, model, engine = _setup()
    model.shape_selection = {9}
    row.refresh()
    row.set_role("apron")
    kw = [kw for name, kw in engine.calls if name == "patch_role_set"][-1]
    assert kw == {"tile": "+30+031", "icao": "ZZZZ", "ref": "pav7#1", "was": "junction",
                  "role": "apron"}
    assert engine.rows["pav7"]["role"] == "apron" and row.button.text() == "Apron"
    assert "regrade the airport" in row.note.text()
    assert model.undo_stack.count() == 1 and model.unsaved_edits == 0
    assert "+30+031" in model.tiles_needing_rebuild
    assert row.menu.actions()[-1].text() == ROLE.AUTOMATIC
    model.undo_stack.undo()
    assert engine.rows == {}                             # back to the classifier
    model.undo_stack.redo()
    assert engine.rows["pav7"]["role"] == "apron" and engine.rows["pav7"]["was"] == "junction"
