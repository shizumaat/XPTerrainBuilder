"""The Qt patch editor's document, selection and undo history (spec
patch-editor-20261015 §3, §4; the Mac app's ``PatchEditModel`` +
``PatchEditActions``).

Every edit is one call into ``o4_engine.patch_edit`` (never re-implemented
here) and ONE step on a ``QUndoStack``: a drag is one step, a move that
ends snapped is one step of ``move`` + ``merge_nodes``.  The history
survives a save (the stack's clean index marks the saved state); a load or
a revert starts it afresh.  No engine I/O happens here — the controller
(``O4_Qt_Patch_Controller``) loads, saves and reverts and tells the model.
"""
from __future__ import annotations

import dataclasses as _dc
import os
import typing as _t

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QUndoCommand, QUndoStack

import O4_File_Names as FNAMES
from o4_engine import patch_edit as PE

__all__ = ["LoadedPatch", "PatchEditModel", "MODE_VIEW", "MODE_EDIT"]

MODE_VIEW = "View"
MODE_EDIT = "Edit"


@_dc.dataclass
class LoadedPatch:
    """What the open file is (from ``patch_load``); ``path``, ``source``
    and ``header`` change only through :meth:`PatchEditModel.mark_saved`."""

    tile: str
    icao: str
    source: str               # "auto" | "manual"
    path: str
    header: dict
    stale: bool = False
    stale_inputs: list = _dc.field(default_factory=list)
    identity_dp: int = 11
    min_distinct_spacing_m: float = 0.5

    @classmethod
    def from_reply(cls, tile: str, reply: _t.Mapping) -> "LoadedPatch":
        return cls(tile=tile, icao=str(reply["icao"]), source=str(reply["source"]),
                   path=str(reply["path"]), header=dict(reply.get("header") or {}),
                   stale=bool(reply.get("stale")),
                   stale_inputs=list(reply.get("stale_inputs") or []),
                   identity_dp=int(reply.get("identity_dp", 11)),
                   min_distinct_spacing_m=float(reply.get("min_distinct_spacing_m", 0.5)))

    @property
    def file_name(self) -> str:
        return os.path.basename(self.path)

    @property
    def is_hand_made(self) -> bool:
        """A manual patch the editor did not name (a JOSM file): saves back
        to itself, no "Revert to auto".  Decided by FILE NAME (§1.2) —
        ``patch_save`` stamps ``o4_user_edited`` into such a file too."""
        return self.source == "manual" and self.file_name != FNAMES.edited_patch_name(self.icao)


class _EditStep(QUndoCommand):
    """One undoable edit: the document before and after (immutable
    ``PatchDoc``s, so holding both is two references)."""

    def __init__(self, model: "PatchEditModel", name: str,
                 before: PE.PatchDoc, after: PE.PatchDoc):
        super().__init__(name)
        self._model, self._before, self._after = model, before, after
        self._generation = model.generation

    def redo(self) -> None:
        if self._generation == self._model.generation:
            self._model._replace(self._after)

    def undo(self) -> None:
        if self._generation == self._model.generation:
            self._model._replace(self._before)


class PatchEditModel(QObject):
    """The open patch, the Edit-mode selection, the undo stack and the
    save-bar counters."""

    document_changed = Signal()      # an edit, undo, redo or load
    selection_changed = Signal()
    status_changed = Signal()        # unsaved count, saving, error, mode, rebuild note

    def __init__(self, parent=None):
        super().__init__(parent)
        self.patch: LoadedPatch | None = None
        self.doc: PE.PatchDoc | None = None
        #: Node values as loaded ("was 62.40 m").
        self.loaded_nodes: dict[int, PE.Node] = {}
        self.selection: set[int] = set()
        self.mode = MODE_VIEW
        self.is_saving = False
        #: The last refused edit, save or revert, in the engine's words.
        self.edit_error: str | None = None
        #: Tiles whose patch was saved or reverted since their last build.
        self.tiles_needing_rebuild: set[str] = set()
        #: Bumped on every load: a step of an older document never applies.
        self.generation = 0
        self._saved_index = 0
        self.undo_stack = QUndoStack(self)
        self.undo_stack.indexChanged.connect(self._stack_moved)

    def _stack_moved(self, _index: int) -> None:
        self.status_changed.emit()

    # ─── load ──────────────────────────────────────────────────────────
    def load(self, patch: LoadedPatch, doc: PE.PatchDoc) -> None:
        """A new document (load, reload, revert): history and counters
        restart."""
        self.generation += 1
        self.patch, self.doc = patch, doc
        self.loaded_nodes = dict(doc.nodes)
        self.undo_stack.clear()
        self.undo_stack.setClean()
        self._saved_index = 0
        self.edit_error = None
        self.selection = set()
        self.document_changed.emit()
        self.selection_changed.emit()
        self.status_changed.emit()

    def close(self) -> None:
        """No document (zoomed out, nothing in view)."""
        if self.doc is None:
            return
        self.generation += 1
        self.patch, self.doc = None, None
        self.undo_stack.clear()
        self.selection = set()
        self.document_changed.emit()
        self.selection_changed.emit()
        self.status_changed.emit()

    # ─── counters ──────────────────────────────────────────────────────
    @property
    def unsaved_edits(self) -> int:
        """"● N unsaved edits": steps between now and the saved state;
        at least 1 once an edit branched off below the save."""
        index = self.undo_stack.index()
        if self.undo_stack.cleanIndex() >= 0:
            return abs(index - self.undo_stack.cleanIndex())
        return max(1, abs(index - self._saved_index))

    def set_mode(self, mode: str) -> None:
        if mode != self.mode:
            self.mode = mode
            self.status_changed.emit()

    def set_error(self, text: str | None) -> None:
        self.edit_error = text
        self.status_changed.emit()

    def set_saving(self, saving: bool) -> None:
        self.is_saving = saving
        self.status_changed.emit()

    # ─── selection ─────────────────────────────────────────────────────
    def set_selection(self, ids: _t.Iterable[int]) -> None:
        ids = set(ids)
        if ids != self.selection:
            self.selection = ids
            self.selection_changed.emit()

    def toggle(self, nid: int) -> None:
        self.set_selection(self.selection ^ {nid})

    # ─── edits ─────────────────────────────────────────────────────────
    def perform(self, name: str, edit: _t.Callable[[PE.PatchDoc], PE.PatchDoc]) -> bool:
        """Apply one edit as one undo step named ``name``.  A refused edit
        (unknown ids, a non-edge) changes nothing and says why."""
        before = self.doc
        if before is None:
            return False
        try:
            after = edit(before)
        except (KeyError, ValueError) as error:
            self.set_error(str(error).strip("'\""))
            return False
        if after == before:
            return False
        self.edit_error = None
        self.undo_stack.push(_EditStep(self, name, before, after))
        return True

    def _replace(self, doc: PE.PatchDoc) -> None:
        """An edit, undo or redo landed: drop vanished nodes from the
        selection and announce the change."""
        self.doc = doc
        gone = {n for n in self.selection if n not in doc.nodes}
        if gone:
            self.selection -= gone
            self.selection_changed.emit()
        self.document_changed.emit()
        self.status_changed.emit()

    def move_selection(self, ids: _t.Sequence[int], dlat: float, dlon: float,
                       merge: tuple[int, int] | None = None) -> bool:
        """Move ``ids`` by (dlat, dlon); ``merge`` = ``(grabbed, target)``
        when the snap held at release (§3.3): ONE step."""
        def edit(doc: PE.PatchDoc) -> PE.PatchDoc:
            doc = PE.move(doc, ids, dlat, dlon)
            return PE.merge_nodes(doc, *merge) if merge else doc
        done = self.perform("Move and Merge" if merge else "Move", edit)
        if done and merge:
            self.set_selection((self.selection - {merge[0]}) | {merge[1]})
        return done

    def delete_selection(self) -> bool:
        ids = sorted(self.selection)
        if not ids:
            return False
        done = self.perform("Delete Node" if len(ids) == 1 else "Delete Nodes",
                            lambda doc: PE.delete_nodes(doc, ids))
        if done:
            self.set_selection(())
        return done

    def insert_node(self, a: int, b: int) -> bool:
        """The "+" handle on edge a–b: the new node becomes the selection."""
        new_id = PE.next_node_id(self.doc) if self.doc is not None else None
        done = self.perform("Insert Node", lambda doc: PE.insert_on_edge(doc, a, b, new_id))
        if done:
            self.set_selection({new_id})
        return done

    def set_selection_alt(self, alt: float) -> bool:
        ids = sorted(self.selection)
        return bool(ids) and self.perform("Set Elevation", lambda doc: PE.set_alt(doc, ids, alt))

    def offset_selection_alt(self, d: float) -> bool:
        ids = sorted(self.selection)
        return bool(ids) and self.perform("Offset Elevation", lambda doc: PE.offset_alt(doc, ids, d))

    # ─── save ──────────────────────────────────────────────────────────
    def save_payload(self) -> dict:
        """``patch_save``'s arguments for the document as it is now."""
        p = self.patch
        return dict(tile=p.tile, icao=p.icao, base_path=p.path, **self.doc.to_wire())

    def mark_saved(self, path: str) -> None:
        """After ``patch_save`` wrote the document to ``path``: it now IS
        that manual patch (history kept)."""
        p = self.patch
        p.path, p.source = path, "manual"
        p.header["o4_user_edited"] = "1"
        self.undo_stack.setClean()
        self._saved_index = self.undo_stack.index()
        self.edit_error = None
        self.tiles_needing_rebuild.add(p.tile)
        self.status_changed.emit()

    def discard_to_saved(self) -> None:
        """Forget the unsaved edits' count (the caller reloads the file)."""
        self.undo_stack.clear()
        self._saved_index = 0
        self.status_changed.emit()
