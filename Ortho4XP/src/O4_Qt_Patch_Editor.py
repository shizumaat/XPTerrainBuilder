"""The Qt app's 2D patch editor, assembled (issue #46, spec
patch-editor-20261015 §4, §6): one call wires the engine door, the model,
the viewport controller, the pack outlines, the map layer and its
gestures, the map toolbar, the side-panel box and the 3D preview window
(opened on demand) onto the main window's map and session.  The window keeps a handful of wiring lines: the box
below Activity, the ``PackObjectsReady`` route, the Edit / File menu
actions, the quit check, its build path for "Rebuild tile" and the copy
items of the map's right-click menu (#1281), and "Insert shape" there
(#1314, ``O4_Qt_Patch_Insert``).
"""
from __future__ import annotations

import typing as _t

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QAction, QGuiApplication, QKeySequence

import O4_Geo_Utils as GEO
import O4_Glossary as GLOSSARY
import O4_Qt_Map as QTMAP
import O4_Qt_Patch_Elevation_Dialog as ELEVDIALOG
import O4_Qt_Patch_Reference as REFERENCE
from O4_Qt_Pack_Outlines import PackOutlines
from O4_Qt_Patch_Controller import PatchController
from O4_Qt_Patch_Engine import PatchEngine
from O4_Qt_Patch_Gestures import PatchGestures
from O4_Qt_Patch_Insert import INSERT_SHAPE_TITLE, ShapeInserter
from O4_Qt_Patch_Model import MODE_EDIT, PatchEditModel
from O4_Qt_Patch_Overlay import PatchOverlay
from O4_Qt_Patch_Panel import PatchPanel, node_lat_lon
from O4_Qt_Patch_Toolbar import PatchToolbar
from O4_Qt_Terrain_Relief import TerrainRelief

__all__ = ["PatchEditor", "PACK_OUTLINES_PREF", "SLICE_TITLE", "TERRAIN_PREF",
           "TERRAIN_OPACITY_PREF"]

#: The prefs key that remembers the "Pack outlines" toggle (on by default).
PACK_OUTLINES_PREF = "patch_editor_pack_outlines"
#: ... and the "Terrain" toggle (off by default) and its opacity (#1320).
TERRAIN_PREF = "patch_editor_terrain"
TERRAIN_OPACITY_PREF = "patch_editor_terrain_opacity"

#: The right-click item that cuts a shape between two selected nodes
#: (#1318; the Mac app's ``TileContextMenu.sliceTitle``).
SLICE_TITLE = "Slice"


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
        self.inserter = ShapeInserter(self.engine, self.controller, built, window)

        def remember(on: bool) -> None:
            prefs[PACK_OUTLINES_PREF] = on
            save_prefs(prefs)
        self.outlines = PackOutlines(self.engine, self.model, QTMAP.SCENE_ZL,
                                     enabled=bool(prefs.get(PACK_OUTLINES_PREF, True)),
                                     remember=remember, parent=window)

        def remember_terrain(on: bool, opacity: float) -> None:
            prefs[TERRAIN_PREF], prefs[TERRAIN_OPACITY_PREF] = on, opacity
            save_prefs(prefs)
        self.terrain = TerrainRelief(self.engine, self.model, map_view, built,
                                     enabled=bool(prefs.get(TERRAIN_PREF, False)),
                                     opacity=float(prefs.get(TERRAIN_OPACITY_PREF, 0.6)),
                                     remember=remember_terrain,
                                     showing=lambda: self.controller.is_showing, parent=window)
        self.controller.state_changed.connect(self.terrain.view_changed)
        self.overlay = PatchOverlay(map_view, self.controller, self.outlines, self.terrain)
        self.gestures = PatchGestures(self.overlay)
        self.overlay.toolbar = PatchToolbar(map_view.viewport(), self.controller, self.outlines,
                                            open_preview=self.open_preview, terrain=self.terrain)
        map_view.add_layer(self.overlay)
        self.panel = PatchPanel(self.controller)
        self._window, self._map, self._built = window, map_view, built
        #: The 3D preview window, made the first time it is opened.
        self.preview = None
        self.shortcuts = self.gestures.install_shortcuts(window)

    def menu_actions(self, window) -> dict[str, QAction]:
        """Edit ▸ Undo / Redo (Ctrl/⌘Z, Shift+Ctrl/⌘Z; a drag is one step),
        File ▸ Save (Ctrl/⌘S) and View ▸ 3D Preview (Ctrl/⌘3)."""
        stack = self.model.undo_stack
        undo = stack.createUndoAction(window, "Undo")
        undo.setShortcut(QKeySequence.Undo)
        redo = stack.createRedoAction(window, "Redo")
        redo.setShortcuts([QKeySequence("Ctrl+Shift+Z"), QKeySequence.Redo])
        save = QAction(GLOSSARY.TERMS["save_edits"], window)
        save.setShortcut(QKeySequence.Save)
        # #1694: Ctrl/⌘S reaches Save from any window of the app.
        save.setShortcutContext(Qt.ApplicationShortcut)
        save.triggered.connect(self.controller.save)

        def enable_save() -> None:
            save.setEnabled(self.model.unsaved_edits > 0 and not self.model.is_saving)
        self.model.status_changed.connect(enable_save)
        enable_save()
        preview = QAction("3D Preview", window)
        preview.setShortcut(QKeySequence("Ctrl+3"))
        preview.triggered.connect(self.open_preview)
        return {"undo": undo, "redo": redo, "save": save, "preview": preview}

    def add_to_menu(self, menu) -> None:
        """The map's right-click menu in Edit mode (#1318; the Mac app's
        ``TileContextMenu``): "Slice" first, enabled only when two nodes of
        one shape that are not neighbours are selected."""
        model = self.model
        if model.doc is None or model.mode != MODE_EDIT:
            return
        first = menu.actions()[0] if menu.actions() else None
        action = QAction(SLICE_TITLE, menu)
        try:
            model.slice_args()
        except (KeyError, ValueError) as why:
            action.setEnabled(False)
            action.setToolTip(str(why).strip("'\""))
        action.triggered.connect(model.slice_selection)
        menu.insertAction(first, action)
        if first is not None:
            menu.insertSeparator(first)
        menu.setToolTipsVisible(True)

    def context_actions(self, at: tuple[float, float] | None = None
                        ) -> list[tuple[str, _t.Callable[[], _t.Any]]]:
        """The map's right-click items: "Set elevation…" on the Edit-mode
        selected shapes (#1357), then "Insert shape" at ``at`` (#1314)."""
        items = []
        m = self.model
        if m.mode == MODE_EDIT and m.shape_selection and m.doc is not None:
            items.append((ELEVDIALOG.TITLE, self.panel.open_set_elevation))
        if at is not None and self.inserter.available():
            items.append((INSERT_SHAPE_TITLE, lambda: self.inserter.insert(*at)))
        return items

    def lat_lon_at(self, x: float, y: float) -> tuple[float, float]:
        """The map's ``(lat, lon)`` at viewport ``(x, y)``."""
        scene = self._map.mapToScene(QPoint(round(x), round(y)))
        return GEO.pix_to_wgs84(scene.x(), scene.y(), QTMAP.SCENE_ZL)

    def open_preview(self) -> None:
        """Ctrl/⌘3 or the map's "3D" button: show (or raise) the window."""
        if self.preview is None:
            from O4_Qt_Preview3D_Window import PreviewWindow
            imagery = getattr(self._map, "imagery_cache", None)
            self.preview = PreviewWindow(self.engine, self.model, self._built, imagery, self._window)
            built_changed = getattr(self._map, "built_changed", None)
            if built_changed is not None:
                built_changed.connect(self.preview.model.tile_built)
        self.preview.show()
        self.preview.raise_()
        self.preview.activateWindow()

    def pack_label_at(self, lat: float, lon: float) -> str | None:
        """The cursor readout's pack outline label (#1316), while the
        patch and its outlines are showing."""
        return self.outlines.label_at(lat, lon) if self.controller.is_showing else None

    def copy_items(self, x: float, y: float) -> list[tuple[str, str]]:
        """``(title, text)`` for a right-click at viewport ``(x, y)``:
        "Copy coordinates" of a node (8 px), else of the click (#1314);
        "Copy shape reference" while one shape is selected and the patch
        layer shows."""
        m, index = self.model, self.overlay.index
        if not self.overlay.showing or m.doc is None or index is None:
            return [(REFERENCE.COPY_COORDINATES, node_lat_lon(*self.lat_lon_at(x, y)))]
        index.project(self.overlay.transform())
        node = index.node_at(x, y)
        lat, lon = m.doc.nodes[node][1:3] if node is not None else self.lat_lon_at(x, y)
        items = [(REFERENCE.COPY_COORDINATES, node_lat_lon(lat, lon))]
        if len(m.shape_selection) == 1:
            (way_id,) = m.shape_selection
            if any(w.id == way_id for w in m.doc.ways):
                items.append((REFERENCE.COPY_SHAPE_REFERENCE, self.panel.shape_reference(way_id)))
        return items

    def add_copy_actions(self, menu, x: float, y: float) -> None:
        """Put :meth:`copy_items` at the top of the map's right-click
        ``menu``, then a separator."""
        items = self.copy_items(x, y)
        if not items:
            return
        first = menu.actions()[0] if menu.actions() else None
        clipboard = QGuiApplication.clipboard()
        for title, text in items:
            action = QAction(title, menu)
            action.triggered.connect(lambda _checked=False, t=text: clipboard.setText(t))
            menu.insertAction(first, action)
        menu.insertSeparator(first)

    def on_pack_objects_ready(self, event) -> None:
        self.engine.on_pack_objects_ready(event)

    def confirm_quit(self) -> bool:
        return self.controller.confirm_quit()
