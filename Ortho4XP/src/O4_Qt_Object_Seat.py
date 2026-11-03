"""An object's elevation by hand, and a node snapped to an object, on the
Qt patch layer (issue #1703; the Mac app's ``PatchObjectElevation.swift``).

* "Set object elevation…" (the map's right-click menu and the Patch box,
  with an object selected): the object's bottom in m or ft MSL, stored at
  once by the engine (``object_seat_set``) as a user edit the object stage
  honours on every rebuild that places the airport's objects.  Only the
  object moves; the ground stays as solved (owner decision (1)(b)).  One
  Ctrl/⌘Z step (:class:`SeatStep`), which is not an unsaved patch edit.
* A dragged node snaps to a placed object's footprint corners and edge
  middles too (:func:`vertex_at`, owner (3)(a)); dropped there, and
  the object has a height, a small pop-up asks Top / Bottom / Keep current
  (owner (2)(a), (4)(a)).  The node's ``alt_abs`` then pins it.
"""
from __future__ import annotations

import html
import math
import typing as _t

import O4_Qt_Patch_Elevation as ELEV
from O4_Qt_Patch_Elevation_Dialog import UnitValue
from O4_Qt_Patch_Model import MODE_EDIT
from PySide6.QtGui import QUndoCommand
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

__all__ = ["SET_ELEVATION_TITLE", "KEEP_CURRENT", "vertex_at",
           "has_height", "SeatStep", "ObjectSeatDialog", "ObjectBox", "top_or_bottom_menu"]

SET_ELEVATION_TITLE = "Set object elevation…"
KEEP_CURRENT = "Keep current"
#: An object whose top and bottom differ by less has no height to snap to.
MIN_HEIGHT_M = 0.05


def _vertices(ring: _t.Sequence[tuple[float, float]]) -> list[tuple[float, float]]:
    """A ring's snap points: each corner, then the middle of each edge (the
    Mac's ``PatchObjectSnap.vertices``)."""
    r = list(ring)
    if len(r) > 1 and r[0] == r[-1]:
        r.pop()
    if len(r) < 2:
        return r
    n = len(r)
    return r + [((r[k][0] + r[(k + 1) % n][0]) / 2, (r[k][1] + r[(k + 1) % n][1]) / 2)
                for k in range(n)]


def vertex_at(outlines: _t.Iterable, to_screen: _t.Callable[[float, float], tuple[float, float]],
              px: float, py: float, radius: float):
    """``(outline, lat, lon)`` of the placed object's snap point nearest the
    viewport point within ``radius`` px, or None."""
    best = None
    for o in outlines:
        if o.object is None:
            continue
        for lat, lon in _vertices(o.rings[0]):
            x, y = to_screen(lat, lon)
            d = math.hypot(x - px, y - py)
            if d <= radius and (best is None or d < best[0]):
                best = (d, o, lat, lon)
    return None if best is None else best[1:]


def has_height(seat: _t.Mapping | None) -> bool:
    """Whether a seat has a top and bottom to choose between."""
    return bool(seat) and seat.get("top_m") is not None and seat.get("bottom_m") is not None \
        and seat["top_m"] - seat["bottom_m"] >= MIN_HEIGHT_M


def top_or_bottom_menu(parent, top: float, bottom: float,
                       choose: _t.Callable[[float, str], None]) -> QMenu:
    """The snap's small pop-up: Top / Bottom / Keep current."""
    menu = QMenu(parent)
    head = menu.addAction("Node elevation")
    head.setEnabled(False)
    menu.addAction("Top of the object (%.2f m)" % top).triggered.connect(
        lambda: choose(top, "Set Elevation to Object Top"))
    menu.addAction("Bottom of the object (%.2f m)" % bottom).triggered.connect(
        lambda: choose(bottom, "Set Elevation to Object Bottom"))
    menu.addAction(KEEP_CURRENT)
    return menu


class SeatStep(QUndoCommand):
    """One hand-set elevation as an undo step: ``redo`` stores ``after``,
    ``undo`` ``before`` (zeros, m MSL; None = the stage's own seat).  The
    first ``redo`` (the push) is the write that already happened."""

    def __init__(self, name: str, send: _t.Callable[[float | None], None],
                 before: float | None, after: float | None):
        super().__init__(name)
        self._send, self._before, self._after = send, before, after
        self._pushed = False

    def redo(self) -> None:
        if self._pushed:
            self._send(self._after)
        self._pushed = True

    def undo(self) -> None:
        self._send(self._before)


class ObjectSeatDialog(UnitValue, QDialog):
    """"Set object elevation…": the bottom in m or ft MSL, prefilled with
    the seat the inspector shows; "Automatic" drops a hand-set elevation."""

    def __init__(self, inspector, parent=None):
        super().__init__(parent)
        self.inspector = inspector
        seat = inspector.seat or {}
        self.setWindowTitle("Set object elevation")
        v = QVBoxLayout(self)
        name = inspector.selected.label if inspector.selected is not None else "Object"
        v.addWidget(QLabel("<b>%s</b>" % name))
        note = QLabel("Only the object moves; the ground stays as built. It is placed "
                      "there on the next rebuild.")
        note.setWordWrap(True)
        v.addWidget(note)
        row = QHBoxLayout()
        row.addWidget(QLabel("Bottom"))
        self.value = QLineEdit()
        row.addWidget(self.value, 1)
        self.unit = QComboBox()
        self.unit.addItems(ELEV.UNITS)
        row.addWidget(self.unit)
        row.addWidget(QLabel("MSL"))
        v.addLayout(row)
        if seat.get("height_m") is not None:
            v.addWidget(QLabel("Its top is %.2f m above its bottom." % seat["height_m"]))
        self.buttons = QDialogButtonBox(QDialogButtonBox.Apply | QDialogButtonBox.Cancel)
        self.apply_button = self.buttons.button(QDialogButtonBox.Apply)
        self.apply_button.setDefault(True)
        self.apply_button.clicked.connect(self.apply)
        self.automatic = None
        if seat.get("user_zero_m") is not None:
            self.automatic = self.buttons.addButton("Automatic", QDialogButtonBox.ResetRole)
            self.automatic.setToolTip("Let the build seat the object again")
            self.automatic.clicked.connect(self.clear)
        self.buttons.rejected.connect(self.reject)
        v.addWidget(self.buttons)
        self._unit = ELEV.UNITS[0]
        self._fill(seat.get("bottom_m"))
        self.unit.currentTextChanged.connect(self._unit_changed)
        self.value.textChanged.connect(self._refresh)
        self._refresh()

    def _refresh(self, *_args) -> None:
        self.apply_button.setEnabled(ELEV.parse_number(self.value.text()) is not None)

    def apply(self) -> None:
        v = ELEV.parse_number(self.value.text())
        if v is None:
            return
        self.inspector.set_elevation(ELEV.to_metres(v, self._unit))
        self.accept()

    def clear(self) -> None:
        self.inspector.set_elevation(None)
        self.accept()


class ObjectBox(QWidget):
    """The Patch box in Edit mode with an object selected: the inspector's
    lines and "Set object elevation…"."""

    def __init__(self, inspector, open_dialog: _t.Callable[[], _t.Any], parent=None):
        super().__init__(parent)
        self.inspector = inspector
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        self.text = QLabel()
        self.text.setWordWrap(True)
        v.addWidget(self.text)
        self.button = QPushButton(SET_ELEVATION_TITLE)
        self.button.setToolTip("Set where this object stands; only the object moves")
        self.button.clicked.connect(open_dialog)
        v.addWidget(self.button)
        inspector.changed.connect(self.refresh)
        self.refresh()

    def refresh(self) -> None:
        i = self.inspector
        shown = i.selected is not None and i.model.mode == MODE_EDIT
        self.setVisible(shown)
        if shown:
            lines = i.lines
            self.text.setText("<b>%s</b><br>%s" % (html.escape(lines[0]),
                                                   "<br>".join(html.escape(t) for t in lines[1:])))
            self.button.setVisible(i.can_set_elevation)
            self.button.setEnabled(i.seat is not None)

