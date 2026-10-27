"""A row widget that reports a click on itself (issue #816).

The Activity list's per-tile rows use it: clicking a row selects its tile
and frames it on the map.  A click on a CONTROL inside the row (stop,
resume, report buttons) never reaches the row -- the button accepts its
own mouse events -- so a control keeps its own action and does not also
move the map.  Labels do not accept clicks, so clicking the title, the
status or the bar counts as clicking the row -- except a status that
has been made clickable (:class:`ClickableStatus`, #1341): a finished
row's gold or red status reopens its tile's messages instead.

A row whose tile is selected is filled (:meth:`ClickableRow.set_filled`,
#1537) in :func:`fill_color`, which raises contrast against the group
box subtly, as a square band across the box's whole width
(:func:`span_box`); which rows: ``O4_Activity_Order.filled_rows``
(:func:`apply_fills`).
"""

import O4_Activity_Order as ACTORDER
from O4_Qt_Widgets import ElidedRowLabel
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPalette
from PySide6.QtWidgets import QFrame, QHBoxLayout, QWidget

__all__ = ["ClickableRow", "ClickableStatus", "apply_fills", "span_box"]

#: The share of the first (#1537) contrast step kept (owner on 1.0.438:
#: "a little too stark").  The Mac app's ``ActivityRowFill.step``.
FILL_STEP = 0.25


def fill_color(palette):
    """A selected row's fill (#1537): the pane (Window) moved a quarter of
    the way to the text background (Base) taken halfway on away from the
    text -- a little darker in a dark palette, lighter in a light one.
    The Mac app's twin: ``ActivityRowFill``."""
    pane = QColor(palette.color(QPalette.Window))
    base = QColor(palette.color(QPalette.Base))
    level = 255 if base.lightness() >= 128 else 0

    def mix(p, b):
        return round(p + ((b + level) / 2 - p) * FILL_STEP)
    return QColor(mix(pane.red(), base.red()), mix(pane.green(), base.green()),
                  mix(pane.blue(), base.blue()))


def span_box(layout, scroll):
    """Let ``scroll`` (a box's rows) run the full width of the box that
    ``layout`` lays out: the layout's side margins move onto every other
    item, and the scroll area loses its frame, so a filled row is a band
    from edge to edge (the Mac app's ``PaneBoxMetrics.edgeInset``)."""
    left, top, right, bottom = layout.getContentsMargins()
    layout.setContentsMargins(0, top, 0, bottom)
    scroll.setFrameShape(QFrame.NoFrame)
    for index in range(layout.count()):
        widget = layout.itemAt(index).widget()
        if widget is None or widget is scroll:
            continue
        stretch = layout.stretch(index)
        layout.takeAt(index)
        side = QHBoxLayout()
        side.setContentsMargins(left, 0, right, 0)
        side.addWidget(widget)
        layout.insertLayout(index, side, stretch)


def apply_fills(rows, selected):
    """Fill the rows of selected tiles.  ``rows`` maps a tile to its row
    widget -- every row of both sections."""
    filled = ACTORDER.filled_rows(list(rows), selected)
    for tile, row in rows.items():
        row.set_filled(tile in filled)


class ClickableRow(QWidget):
    """A plain container that emits :attr:`clicked` on a left click
    released over itself (a press dragged off the row does nothing)."""

    clicked = Signal()
    #: The fill's corner radius, in px (the Mac app's ActivityRowFill):
    #: square, a band across the box.
    FILL_RADIUS = 0

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.PointingHandCursor)
        self._filled = False

    def filled(self):
        return self._filled

    def set_filled(self, filled):
        if bool(filled) != self._filled:
            self._filled = bool(filled)
            self.update()

    def paintEvent(self, event):
        if self._filled:
            painter = QPainter(self)
            painter.fillRect(self.rect(), fill_color(self.palette()))
            painter.end()
        super().paintEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if (event.button() == Qt.LeftButton
                and self.rect().contains(event.position().toPoint())):
            event.accept()
            self.clicked.emit()
            return
        super().mouseReleaseEvent(event)


class ClickableStatus(ElidedRowLabel):
    """A row's status label that, once :meth:`set_clickable`, takes a
    left click as its own and emits :attr:`clicked` (#1341); otherwise
    the click passes through to the row like any label's."""

    clicked = Signal()

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self._clickable = False

    def is_clickable(self):
        return self._clickable

    def set_clickable(self, clickable, tooltip=""):
        self._clickable = bool(clickable)
        font = self.font()
        font.setUnderline(self._clickable)
        self.setFont(font)
        self.setToolTip(tooltip if self._clickable else "")
        if self._clickable:
            self.setCursor(Qt.PointingHandCursor)
        else:
            self.unsetCursor()

    def mousePressEvent(self, event):
        if self._clickable and event.button() == Qt.LeftButton:
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if (self._clickable and event.button() == Qt.LeftButton
                and self.rect().contains(event.position().toPoint())):
            event.accept()
            self.clicked.emit()
            return
        super().mouseReleaseEvent(event)
