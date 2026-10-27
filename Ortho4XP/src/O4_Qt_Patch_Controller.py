"""Which airport's patch the Qt map shows, and the engine round trips of
the patch editor (spec patch-editor-20261015 §4 "Display", save bar,
unsaved-edits prompt; the Mac app's ``PatchEditModel`` viewport half and
``PatchEditActions`` save / revert / rebuild).

When the view is narrower than 0.08° of longitude and a built tile in view
has a patch (``patch_list``) whose bbox intersects the view, the airport
whose bbox is nearest the view centre is loaded (``patch_load``), one at a
time.  Switching airport, or quitting, with unsaved edits asks first.
"""
from __future__ import annotations

import math
import os
import time
import typing as _t

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import QMessageBox

import O4_File_Names as FNAMES
import O4_Geo_Utils as GEO
import O4_Qt_Map as QTMAP
from o4_engine import patch_edit as PE

from O4_Qt_Patch_Model import LoadedPatch, PatchEditModel

__all__ = ["PatchController", "MAX_VIEW_SPAN_DEG", "ask_unsaved_dialog",
           "unsaved_prompt_text"]

#: The view must be narrower than this (degrees of longitude) before any
#: patch is listed or drawn.
MAX_VIEW_SPAN_DEG = 0.08

ANSWER_SAVE, ANSWER_DISCARD, ANSWER_KEEP = "save", "discard", "keep"


def unsaved_prompt_text(doc_icao: str, edits: int, switching_to: str | None) -> tuple[str, str]:
    """``(title, message)`` of the unsaved-edits question (the Mac words);
    ``switching_to`` None = quitting."""
    noun = "%d unsaved edit%s" % (edits, "" if edits == 1 else "s")
    title = "Unsaved edits to %s" % doc_icao
    if switching_to is None:
        return title, "Save your %s before quitting?" % noun
    if switching_to == doc_icao:
        return title, ("%s's patch changed on disk. Save your %s before "
                       "reloading it?" % (doc_icao, noun))
    return title, "Save your %s before showing %s?" % (noun, switching_to)


def ask_unsaved_dialog(parent, title: str, message: str, quitting: bool) -> str:
    """The question as a Qt message box: Save / Don't Save / Keep Editing
    (Cancel when quitting)."""
    box = QMessageBox(parent)
    box.setWindowTitle(title)
    box.setText(title)
    box.setInformativeText(message)
    save = box.addButton("Save", QMessageBox.AcceptRole)
    discard = box.addButton("Don't Save", QMessageBox.DestructiveRole)
    keep = box.addButton("Cancel" if quitting else "Keep Editing", QMessageBox.RejectRole)
    box.setDefaultButton(save)
    box.setEscapeButton(keep)
    box.exec()
    clicked = box.clickedButton()
    return ANSWER_SAVE if clicked is save else ANSWER_DISCARD if clicked is discard else ANSWER_KEEP


def absence(tile_built: bool, scanning: bool) -> str:
    """The state for an airport with no patch listed: never "not built"
    while the scan that would list its tile is still running."""
    if not tile_built and scanning:
        return PatchController.CHECKING
    return PatchController.NO_PATCH


def tile_key(lat: int, lon: int) -> str:
    return "%+03d%+04d" % (lat, lon)


class PatchController(QObject):
    """Viewport → airport → document, and save / revert / rebuild."""

    state_changed = Signal()

    # LoadState names (the Mac enum's cases)
    HIDDEN, LOADING, LOADED, FAILED, NO_PATCH = "hidden", "loading", "loaded", "failed", "no_patch"
    #: Not in the built set YET: the tile scan is still running, so "Build
    #: this tile first" would be a guess (the Mac's ``.checking``).
    CHECKING = "checking"

    def __init__(self, engine, model: PatchEditModel, map_view,
                 built: _t.Callable[[], dict], parent=None):
        super().__init__(parent)
        self.engine = engine
        self.model = model
        self.map = map_view
        self._built = built
        self.state = self.HIDDEN
        self.state_icao: str | None = None
        self.state_message = ""
        self.tile_built = False
        #: The patch file's modification time (the source line's "built …").
        self.file_mtime: float | None = None
        #: (lat, lon) → {"info": built info, "entries": [...] | None}
        self._listings: dict[tuple[int, int], dict] = {}
        self._loading_key: str | None = None
        self._reload_document = False
        self._dismissed_key: str | None = None
        #: ``rebuild(tile_key) -> error sentence | None`` (the window's build path).
        self.rebuild: _t.Callable[[str], str | None] = lambda _tile: "The build path is not connected."
        self.is_building: _t.Callable[[], bool] = lambda: False
        #: Whether the window's tile scan is still running.
        self.is_scanning: _t.Callable[[], bool] = lambda: False
        #: ``ask(title, message, quitting) -> "save" | "discard" | "keep"``.
        self.ask: _t.Callable[[str, str, bool], str] = (
            lambda title, message, quitting: ask_unsaved_dialog(map_view, title, message, quitting))
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(0)
        self._timer.timeout.connect(self.evaluate)
        map_view.view_changed.connect(self.schedule)
        built_changed = getattr(map_view, "built_changed", None)
        if built_changed is not None:
            built_changed.connect(self.schedule)

    @property
    def is_showing(self) -> bool:
        return self.state == self.LOADED and self.model.doc is not None

    def schedule(self) -> None:
        self._timer.start()

    def _set_state(self, state: str, icao: str | None = None, message: str = "") -> None:
        if (state, icao, message) != (self.state, self.state_icao, self.state_message):
            self.state, self.state_icao, self.state_message = state, icao, message
            self.state_changed.emit()

    # ─── viewport ──────────────────────────────────────────────────────
    def _read_viewport(self):
        lat_lo, lat_hi, lon_lo, lon_hi = self.map.visible_bounds()
        if lon_hi - lon_lo >= MAX_VIEW_SPAN_DEG or lon_hi <= lon_lo:
            return None
        centre = self.map.mapToScene(self.map.viewport().rect().center())
        c_lat, c_lon = GEO.pix_to_wgs84(centre.x(), centre.y(), QTMAP.SCENE_ZL)
        return (lat_lo, lat_hi, lon_lo, lon_hi, c_lat, c_lon)

    def evaluate(self) -> None:
        """The map moved (or tiles were built): choose the airport."""
        viewport = self._read_viewport()
        if viewport is None:
            self._set_state(self.HIDDEN)
            return
        lat_lo, lat_hi, lon_lo, lon_hi, c_lat, c_lon = viewport
        built = self._built() or {}
        tiles = [(la, lo) for la in range(math.floor(lat_lo), math.floor(lat_hi) + 1)
                 for lo in range(math.floor(lon_lo), math.floor(lon_hi) + 1)]
        pending = False
        candidates = []
        for tile in tiles:
            info = built.get(tile)
            if info is None:
                continue
            listing = self._listings.get(tile)
            if listing is None or listing["info"] != info:
                if listing is not None:
                    self.model.tiles_needing_rebuild.discard(tile_key(*tile))  # built again
                if self.model.patch and self.model.patch.tile == tile_key(*tile):
                    self._reload_document = True
                self._listings[tile] = listing = {"info": info, "entries": None}
                self._list(tile)
            if listing["entries"] is None:
                pending = True
                continue
            for entry in listing["entries"]:
                b = entry.get("bbox")
                if b and b[0] <= lat_hi and b[2] >= lat_lo and b[1] <= lon_hi and b[3] >= lon_lo:
                    candidates.append((tile_key(*tile), entry))
        chosen = self._nearest(candidates, c_lat, c_lon)
        if chosen is not None:
            self._show(*chosen)
        elif pending:
            return
        else:
            airport = self._nearest_airport(viewport)
            if airport is None:
                self._set_state(self.HIDDEN)
            else:
                code, a_lat, a_lon = airport
                self.tile_built = (math.floor(a_lat), math.floor(a_lon)) in built
                self._set_state(absence(self.tile_built, self.is_scanning()), code)

    @staticmethod
    def _nearest(candidates, c_lat: float, c_lon: float):
        """The airport whose bbox is nearest the view centre (0 inside it);
        ties to the bbox whose centre is nearer, then to the ICAO."""
        k = math.cos(math.radians(c_lat))

        def score(item):
            b = item[1]["bbox"]
            d_lat = max(b[0] - c_lat, 0, c_lat - b[2])
            d_lon = max(b[1] - c_lon, 0, c_lon - b[3]) * k
            m_lat = (b[0] + b[2]) / 2 - c_lat
            m_lon = ((b[1] + b[3]) / 2 - c_lon) * k
            return (math.hypot(d_lat, d_lon), math.hypot(m_lat, m_lon), item[1]["icao"])
        return min(candidates, key=score) if candidates else None

    def _nearest_airport(self, viewport):
        lat_lo, lat_hi, lon_lo, lon_hi, c_lat, c_lon = viewport
        marks = getattr(self.map, "airport_marks", lambda: [])()
        k = math.cos(math.radians(c_lat))
        best = None
        for code, a_lat, a_lon in marks:
            if lat_lo <= a_lat <= lat_hi and lon_lo <= a_lon <= lon_hi:
                d = math.hypot(a_lat - c_lat, (a_lon - c_lon) * k)
                if best is None or d < best[0]:
                    best = (d, code, a_lat, a_lon)
        return None if best is None else best[1:]

    # ─── engine calls ──────────────────────────────────────────────────
    def _list(self, tile: tuple[int, int]) -> None:
        info = self._listings[tile]["info"]

        def done(reply, _error):
            # A refused listing shows as "no patch"; the load reports its own.
            listing = self._listings.get(tile)
            if listing is None or listing["info"] != info:
                return
            listing["entries"] = list((reply or {}).get("airports") or [])
            self.schedule()
        self.engine.call("patch_list", done, tile=tile_key(*tile))

    def _show(self, tile: str, entry: dict) -> None:
        key = "%s|%s|%s" % (tile, entry["icao"], entry["path"])
        p = self.model.patch
        if (not self._reload_document and p is not None and p.tile == tile
                and p.icao == entry["icao"] and p.path == entry["path"]):
            self._loading_key = None
            self._set_state(self.LOADED)
            return
        if self._hold_for_unsaved(entry["icao"], key):
            if self.model.doc is not None:
                self._set_state(self.LOADED)
            return
        if self._loading_key == key:
            return
        self._reload_document = False
        self._loading_key = key
        self._set_state(self.LOADING, entry["icao"])

        def done(reply, error):
            if self._loading_key != key:
                return
            self._loading_key = None
            if error is not None:
                self._set_state(self.FAILED, entry["icao"], error)
                return
            self.model.load(LoadedPatch.from_reply(tile, reply),
                            PE.PatchDoc.from_wire(reply["nodes"], reply["ways"]))
            self._dismissed_key = None
            self.file_mtime = _mtime(reply["path"])
            self._set_state(self.LOADED)
        self.engine.call("patch_load", done, tile=tile, icao=entry["icao"])

    # ─── unsaved edits ─────────────────────────────────────────────────
    def _hold_for_unsaved(self, icao: str, key: str) -> bool:
        """Whether a switch to ``key`` waits for the user (unsaved edits)."""
        m = self.model
        if m.doc is None or m.unsaved_edits == 0:
            return False
        if self._dismissed_key == key:
            return True
        title, message = unsaved_prompt_text(m.patch.icao, m.unsaved_edits, icao)
        answer = self.ask(title, message, False)
        if answer == ANSWER_SAVE:
            return not self.save_now()
        if answer == ANSWER_DISCARD:
            m.discard_to_saved()
            return False
        self._dismissed_key = key
        return True

    def confirm_quit(self) -> bool:
        """The window's close check: unsaved edits ask first; False = stay."""
        m = self.model
        if m.doc is None or m.unsaved_edits == 0:
            return True
        title, message = unsaved_prompt_text(m.patch.icao, m.unsaved_edits, None)
        answer = self.ask(title, message, True)
        if answer == ANSWER_SAVE:
            return self.save_now()
        return answer == ANSWER_DISCARD

    # ─── save / revert / rebuild ───────────────────────────────────────
    def save(self) -> None:
        """Save (the save bar, Ctrl/⌘S) — off the GUI thread."""
        m = self.model
        if m.doc is None or m.is_saving or m.unsaved_edits == 0:
            return
        m.set_saving(True)
        generation = m.generation
        self.engine.call("patch_save", lambda reply, error: self._saved(generation, reply, error),
                         **m.save_payload())

    def save_now(self) -> bool:
        """Save on the GUI thread (the prompts' Save); whether it saved."""
        m = self.model
        if m.doc is None:
            return False
        reply, error = self.engine.call_now("patch_save", **m.save_payload())
        self._saved(m.generation, reply, error)
        return error is None

    def _saved(self, generation: int, reply, error) -> None:
        m = self.model
        m.set_saving(False)
        if generation != m.generation:
            return
        if error is not None:
            m.set_error(error)
            return
        m.mark_saved(reply["path"])
        self.file_mtime = _mtime(reply["path"])
        tile = FNAMES.parse_tile_key(m.patch.tile)
        listing = self._listings.get(tuple(tile)) if tile else None
        if listing and listing["entries"]:
            listing["entries"] = [dict(e, source="manual", path=reply["path"])
                                  if e["icao"] == m.patch.icao else e
                                  for e in listing["entries"]]
        self.state_changed.emit()

    def revert_to_auto(self) -> None:
        """"Revert to auto…" (after the in-panel confirmation): the editor's
        own file is moved aside (``patch_revert``, never deleted) and the
        auto patch reloads; on an auto patch it discards the unsaved edits."""
        m = self.model
        p = m.patch
        if p is None or p.is_hand_made:
            return
        if p.source != "manual":
            self.discard_edits()
            return

        def done(_reply, error):
            if error is not None:
                m.set_error(error)
                return
            m.tiles_needing_rebuild.add(p.tile)
            tile = FNAMES.parse_tile_key(p.tile)
            if tile:
                self._listings.pop(tuple(tile), None)    # list the tile again
            self.discard_edits()
        self.engine.call("patch_revert", done, tile=p.tile, icao=p.icao)

    def relist(self, tile: str) -> None:
        """A patch of ``tile`` changed on disk outside the open document
        ("Insert shape" into another airport's patch, #1314): list the
        tile again (the open document is not reloaded) and mark it for a
        rebuild."""
        self.model.tiles_needing_rebuild.add(tile)
        parsed = FNAMES.parse_tile_key(tile)
        listing = self._listings.get(tuple(parsed)) if parsed else None
        if listing is not None:
            listing["entries"] = None
            self._list(tuple(parsed))

    def discard_edits(self) -> None:
        """Forget the unsaved edits and load the airport's file again."""
        self.model.discard_to_saved()
        self._reload_document = True
        self.schedule()

    def rebuild_tile(self) -> None:
        """"Rebuild tile": the window's own build path for the patch's tile."""
        p = self.model.patch
        if p is None:
            return
        error = self.rebuild(p.tile)
        if error:
            self.model.set_error(error)


def _mtime(path: str) -> float | None:
    try:
        return os.path.getmtime(path)
    except OSError:
        return None


def built_date_text(mtime: float | None) -> str:
    """"12 Oct" for the source line."""
    return time.strftime("%d %b", time.localtime(mtime)).lstrip("0") if mtime else ""
