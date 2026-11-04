"""A shape's classification by hand on the Qt patch layer (issue #1697;
the Mac app's ``PatchShapeRole.swift``).

In Edit mode one selected shape that belongs to a pack pavement (its
``ref`` is ``pav<N>``) shows "Classification" — the role it was built
with — and a menu of the pavement roles.  A choice is stored at once by
the engine (``patch_role_set``) beside the patch, keyed by the pavement's
apt.dat ring: a user edit the classifier honours on every rebuild (RULINGS
2026-10-15d), so the next build regrades the whole airport with it.  One
Ctrl/⌘Z step (``O4_Qt_Object_Seat.SeatStep``), which is not an unsaved patch edit.
"Automatic" hands the shape back to the classifier.
"""
from __future__ import annotations

from auto_patch_v2.airport.user_roles import source_of
from O4_Qt_Object_Seat import SeatStep
from O4_Qt_Patch_Model import MODE_EDIT
from PySide6.QtWidgets import QHBoxLayout, QLabel, QMenu, QPushButton, QVBoxLayout, QWidget

__all__ = ["TITLE", "AUTOMATIC", "RoleRow"]

TITLE = "Classification"
AUTOMATIC = "Automatic"


class RoleRow(QWidget):
    """The Patch box's "Classification" row for one selected shape."""

    def __init__(self, engine, model, parent=None):
        super().__init__(parent)
        self.engine, self.model = engine, model
        self.roles: dict | None = None
        self._roles_for: tuple | None = None
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        row = QHBoxLayout()
        key = QLabel(TITLE)
        key.setStyleSheet("color: gray;")
        row.addWidget(key)
        row.addStretch(1)
        self.button = QPushButton()
        self.button.setToolTip("Change what this pavement is; the whole airport is regraded "
                               "with it on the next rebuild")
        self.menu = QMenu(self.button)
        self.button.setMenu(self.menu)
        row.addWidget(self.button)
        v.addLayout(row)
        self.note = QLabel()
        self.note.setWordWrap(True)
        self.note.setStyleSheet("color: gray; font-size: 11px;")
        v.addWidget(self.note)
        model.selection_changed.connect(self.refresh)
        model.document_changed.connect(self.refresh)
        model.status_changed.connect(self.refresh)
        self.refresh()

    # ─── what is shown ─────────────────────────────────────────────────
    def way(self):
        m = self.model
        if m.mode != MODE_EDIT or m.doc is None or m.patch is None or len(m.shape_selection) != 1:
            return None
        wid = next(iter(m.shape_selection))
        w = next((w for w in m.doc.ways if w.id == wid), None)
        return w if w is not None and source_of(w.tags.get("ref")) else None

    def hand(self, way) -> dict | None:
        source = source_of(way.tags.get("ref"))
        return next((o for o in (self.roles or {}).get("overrides", ())
                     if o.get("source") == source), None)

    def label(self, role: str) -> str:
        return next((c["label"] for c in (self.roles or {}).get("choices", ())
                     if c["role"] == role), role or "shape")

    def refresh(self) -> None:
        way = self.way() if self.engine.has("patch_role_set") else None
        self.setVisible(way is not None)
        if way is None:
            return
        p = self.model.patch
        if self._roles_for != (p.tile, p.icao):
            self._roles_for = (p.tile, p.icao)
            self.roles = None
            self.reload()
        built = way.tags.get("role") or ""
        hand = self.hand(way)
        current = hand["role"] if hand else built
        self.button.setText(self.label(current))
        self.button.setEnabled(self.roles is not None)
        self.menu.clear()
        for c in (self.roles or {}).get("choices", ()):
            act = self.menu.addAction(c["label"])
            act.setEnabled(c["role"] != current)
            act.triggered.connect(lambda _=False, r=c["role"]: self.set_role(r))
        if hand:
            self.menu.addSeparator()
            self.menu.addAction(AUTOMATIC).triggered.connect(lambda: self.set_role(None))
        text = ""
        if hand:
            text = ("Set by hand (the classifier said %s)." % self.label(hand.get("was", ""))
                    if hand["role"] == built else
                    "Set by hand: %s. Rebuild the tile to regrade the airport with it."
                    % self.label(hand["role"]))
            if p.source == "manual":
                text += (" The edited ground shape is in use, so the build uses it instead "
                         "until you go back to the automatic shape.")
        self.note.setText(text)
        self.note.setVisible(bool(text))

    def reload(self) -> None:
        p = self.model.patch
        if p is None:
            return
        key = (p.tile, p.icao)

        def answered(reply, error) -> None:
            if error is None and self._roles_for == key:
                self.roles = reply
                self.refresh()
        self.engine.call("patch_roles", answered, tile=p.tile, icao=p.icao)

    # ─── the change ────────────────────────────────────────────────────
    def set_role(self, role: str | None) -> None:
        """Store ``role`` (None: back to the classifier) for the selected
        shape's pavement; ONE undo step (``SeatStep``)."""
        way, p = self.way(), self.model.patch
        if way is None:
            return
        hand = self.hand(way)
        ref, tile, icao = way.tags["ref"], p.tile, p.icao
        was = hand.get("was") if hand else (way.tags.get("role") or "")
        name = "Automatic Classification" if role is None else "Change Classification"

        def stored(error) -> None:
            if error is not None:
                self.model.set_error("The shape's classification could not be changed: %s" % error)
                return
            self.model.tiles_needing_rebuild.add(tile)
            self.model.status_changed.emit()
            self.reload()

        def send(r) -> None:
            self.engine.call("patch_role_set", lambda _reply, e: stored(e), tile=tile, icao=icao,
                             ref=ref, was=was, **({"role": r} if r else {}))

        def first(reply, error) -> None:
            stored(error)
            if error is None:
                self.model.undo_stack.push(SeatStep(name, send, reply.get("previous_role"),
                                                    reply.get("role")))
        self.engine.call("patch_role_set", first, tile=tile, icao=icao, ref=ref, was=was,
                         **({"role": role} if role else {}))
