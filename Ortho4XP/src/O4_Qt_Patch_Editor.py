"""The Qt app's 2D patch editor, assembled (issue #46, spec
patch-editor-20261015 §4, §6): one call wires the engine door, the model,
the viewport controller, the pack outlines, the map layer and its
gestures, the map toolbar and the side-panel box onto the main window's
map and session.  The window keeps a handful of wiring lines: the box
below Activity, the ``PackObjectsReady`` route, the Edit / File menu
actions, the quit check and its build path for "Rebuild tile".
"""
from __future__ import annotations

import typing as _t

from PySide6.QtGui import QAction, QKeySequence

import O4_Qt_Map as QTMAP
from O4_Qt_Pack_Outlines import PackOutlines
from O4_Qt_Patch_Controller import PatchController
from O4_Qt_Patch_Engine import PatchEngine
from O4_Qt_Patch_Gestures import PatchGestures
from O4_Qt_Patch_Model import PatchEditModel
from O4_Qt_Patch_Overlay import PatchOverlay
from O4_Qt_Patch_Panel import PatchPanel
from O4_Qt_Patch_Toolbar import PatchToolbar

__all__ = ["PatchEditor", "PACK_OUTLINES_PREF"]

#: The prefs key that remembers the "Pack outlines" toggle (on by default).
PACK_OUTLINES_PREF = "patch_editor_pack_outlines"


class PatchEditor:
    """Everything the patch editor adds to a window, held together."""

    def __init__(self, window, map_view, session, built: _t.Callable[[], dict],
                 prefs: dict | None = None,
                 save_prefs: _t.Callable[[dict], None] = lambda _p: None,
                 run_async: bool = True):
        prefs = prefs if prefs is not None else {}
        self.engine = PatchEngine(session, window, run_async=run_async)
        self.model = PatchEditModel(window)
        self.controller = PatchController(self.engine, self.model, map_view, built, window)

        def remember(on: bool) -> None:
            prefs[PACK_OUTLINES_PREF] = on
            save_prefs(prefs)
        self.outlines = PackOutlines(self.engine, self.model, QTMAP.SCENE_ZL,
                                     enabled=bool(prefs.get(PACK_OUTLINES_PREF, True)),
                                     remember=remember, parent=window)
        self.overlay = PatchOverlay(map_view, self.controller, self.outlines)
        self.gestures = PatchGestures(self.overlay)
        self.overlay.toolbar = PatchToolbar(map_view.viewport(), self.controller, self.outlines)
        map_view.add_layer(self.overlay)
        self.panel = PatchPanel(self.controller)
        self.shortcuts = self.gestures.install_shortcuts(window)

    def menu_actions(self, window) -> dict[str, QAction]:
        """Edit ▸ Undo / Redo (Ctrl/⌘Z, Shift+Ctrl/⌘Z; a drag is one step)
        and File ▸ Save Patch (Ctrl/⌘S)."""
        stack = self.model.undo_stack
        undo = stack.createUndoAction(window, "Undo")
        undo.setShortcut(QKeySequence.Undo)
        redo = stack.createRedoAction(window, "Redo")
        redo.setShortcuts([QKeySequence("Ctrl+Shift+Z"), QKeySequence.Redo])
        save = QAction("Save Patch", window)
        save.setShortcut(QKeySequence.Save)
        save.triggered.connect(self.controller.save)

        def enable_save() -> None:
            save.setEnabled(self.model.unsaved_edits > 0 and not self.model.is_saving)
        self.model.status_changed.connect(enable_save)
        enable_save()
        return {"undo": undo, "redo": redo, "save": save}

    def on_pack_objects_ready(self, event) -> None:
        self.engine.on_pack_objects_ready(event)

    def confirm_quit(self) -> bool:
        return self.controller.confirm_quit()
