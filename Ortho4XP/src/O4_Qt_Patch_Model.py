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
import O4_Qt_Patch_Elevation as ELEV
import O4_Qt_Patch_ShapePick as PICK
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
        #: Selected shapes, by way id (#759: a click on a line selects its
        #: whole shape).
        self.shape_selection: set[int] = set()
        #: The last click on a line, for the repeat-click cycle.
        self.last_shape_click: PICK.ShapeClick | None = None
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
        self.shape_selection = set()
        self.last_shape_click = None
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
        self.shape_selection = set()
        self.last_shape_click = None
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

    # ─── shapes (#759) ─────────────────────────────────────────────────
    def set_shape_selection(self, way_ids: _t.Iterable[int]) -> None:
        way_ids = set(way_ids)
        if way_ids != self.shape_selection:
            self.shape_selection = way_ids
            self.selection_changed.emit()

    def select_shapes(self, way_ids: _t.Iterable[int]) -> None:
        """Make ``way_ids`` the whole selection (no nodes)."""
        self.set_selection(())
        self.set_shape_selection(way_ids)

    def select_node(self, nid: int) -> None:
        """One node, no shapes."""
        self.set_shape_selection(())
        self.set_selection({nid})

    def clear_selection(self) -> None:
        """Esc, a click on empty map: nothing selected."""
        self.set_selection(())
        self.set_shape_selection(())
        self.last_shape_click = None

    @property
    def has_selection(self) -> bool:
        return bool(self.selection or self.shape_selection)

    @property
    def shape_nodes(self) -> set[int]:
        """The nodes of the selected shapes."""
        if self.doc is None or not self.shape_selection:
            return set()
        return {r for w in self.doc.ways if w.id in self.shape_selection for r in w.refs}

    @property
    def marked_nodes(self) -> set[int]:
        """Every node drawn as selected (and marked in 3D)."""
        return self.selection | self.shape_nodes

    def click_edge(self, a: int, b: int, x: float, y: float, toggle: bool = False) -> int | None:
        """A click on the edge a–b at viewport point (x, y): ``toggle``
        (Shift) adds or removes the edge's smallest shape; otherwise the
        shape replaces the selection, and a repeat click on the same spot
        steps to the next shape on that edge.  Returns the chosen way id."""
        if self.doc is None:
            return None
        candidates = PICK.shapes_on_edge(self.doc, a, b)
        if toggle:
            if not candidates:
                return None
            self.last_shape_click = None
            self.set_shape_selection(self.shape_selection ^ {candidates[0]})
            return candidates[0]
        last = self.last_shape_click
        previous = last if last is not None and self.shape_selection == {last.chosen} else None
        click = PICK.choose_shape(candidates, x, y, previous)
        if click is None:
            return None
        self.last_shape_click = click
        self.select_shapes({click.chosen})
        return click.chosen

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
        present = {w.id for w in doc.ways}
        gone_shapes = self.shape_selection - present
        if gone or gone_shapes:
            self.selection -= gone
            self.shape_selection -= gone_shapes
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
        n = len(self.shape_selection)
        name = ("Move and Merge" if merge else "Move" if not n
                else "Move Shape" if n == 1 else "Move Shapes")
        done = self.perform(name, edit)
        if done and merge:
            self.set_selection((self.selection - {merge[0]}) | {merge[1]})
        return done

    def delete_selection(self) -> bool:
        """Delete the selected shapes (``delete_ways``), then the selected
        nodes still there (``delete_nodes``) — ONE undo step."""
        ways, ids = sorted(self.shape_selection), sorted(self.selection)
        if not ways and not ids:
            return False

        def edit(doc: PE.PatchDoc) -> PE.PatchDoc:
            if ways:
                doc = PE.delete_ways(doc, ways)
            left = [i for i in ids if i in doc.nodes]
            return PE.delete_nodes(doc, left) if left else doc
        if ways:
            name = "Delete Shape" if len(ways) == 1 else "Delete Shapes"
        else:
            name = "Delete Node" if len(ids) == 1 else "Delete Nodes"
        done = self.perform(name, edit)
        if done:
            self.clear_selection()
        return done

    def insert_node(self, a: int, b: int) -> bool:
        """The "+" handle on edge a–b: the new node becomes the selection."""
        new_id = PE.next_node_id(self.doc) if self.doc is not None else None
        done = self.perform("Insert Node", lambda doc: PE.insert_on_edge(doc, a, b, new_id))
        if done:
            self.select_node(new_id)
        return done

    def slice_args(self) -> dict:
        """``slice_shape``'s arguments for the selection (#1318): exactly two
        nodes, not neighbours, on one shape — the selected shape when it
        holds both.  Raises ``ValueError`` saying why Slice is not offered."""
        if self.doc is None or len(self.selection) != 2:
            raise ValueError("Select two nodes of one shape that are not neighbours.")
        a, b = sorted(self.selection)
        chosen = [w for w in self.shape_selection
                  if any(x.id == w and a in x.refs and b in x.refs for x in self.doc.ways)]
        way = chosen[0] if len(chosen) == 1 else None
        PE.slice_way(self.doc, a, b, way)
        return {"a": a, "b": b, "way": way}

    def slice_selection(self) -> bool:
        """"Slice": cut the shape between the two selected nodes (one
        step); the selection is cleared, the two halves are selected."""
        try:
            args = self.slice_args()
        except (KeyError, ValueError) as error:
            self.set_error(str(error).strip("'\""))
            return False
        way = PE.slice_way(self.doc, **args).id
        before = {w.id for w in self.doc.ways}
        done = self.perform("Slice", lambda doc: PE.slice_shape(doc, **args))
        if done:
            self.select_shapes({way, *({w.id for w in self.doc.ways} - before)})
        return done

    def set_selection_alt(self, alt: float) -> bool:
        ids = sorted(self.selection)
        return bool(ids) and self.perform("Set Elevation", lambda doc: PE.set_alt(doc, ids, alt))

    def offset_selection_alt(self, d: float) -> bool:
        ids = sorted(self.selection)
        return bool(ids) and self.perform("Offset Elevation", lambda doc: PE.offset_alt(doc, ids, d))

    def set_shapes_alt(self, alt: float, include_shared: bool = True) -> bool:
        """"Set elevation…" on the selected shapes (#1357): every node of
        theirs, holes too, and the nodes they share unless told not to."""
        ways = sorted(self.shape_selection)
        if not ways or self.doc is None:
            return False
        p = ELEV.plan(self.doc, ways)
        name = "Set Shape Elevation" if len(ways) == 1 else "Set Shapes Elevation"
        return self.perform(name, lambda doc: ELEV.apply(doc, p, alt, include_shared))

    def add_shape(self, corners: _t.Sequence[_t.Sequence]) -> bool:
        """"Insert shape" into the open patch (#1314): ONE step; the editor
        turns to Edit mode with the new shape selected."""
        if self.doc is None:
            return False
        way = PE.next_way_id(self.doc)
        done = self.perform("Insert Shape", lambda doc: PE.add_shape(doc, corners))
        if done:
            self.set_mode(MODE_EDIT)
            self.select_shapes({way})
        return done

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
