"""A row widget that reports a click on itself (issue #816).

The Activity list's per-tile rows use it: clicking a row selects its tile
and frames it on the map.  A click on a CONTROL inside the row (stop,
resume, report buttons) never reaches the row -- the button accepts its
own mouse events -- so a control keeps its own action and does not also
move the map.  Labels do not accept clicks, so clicking the title, the
status or the bar counts as clicking the row -- except a status that
has been made clickable (:class:`ClickableStatus`, #1341): a finished
row's gold or red status reopens its tile's messages instead.
"""

from O4_Qt_Widgets import ElidedRowLabel
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QWidget

__all__ = ["ClickableRow", "ClickableStatus"]


class ClickableRow(QWidget):
    """A plain container that emits :attr:`clicked` on a left click
    released over itself (a press dragged off the row does nothing)."""

    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.PointingHandCursor)

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
