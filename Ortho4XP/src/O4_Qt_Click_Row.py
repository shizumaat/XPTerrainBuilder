"""A row widget that reports a click on itself (issue #816).

The Activity list's per-tile rows use it: clicking a row selects its tile
and frames it on the map.  A click on a CONTROL inside the row (stop,
resume, report buttons) never reaches the row -- the button accepts its
own mouse events -- so a control keeps its own action and does not also
move the map.  Labels do not accept clicks, so clicking the title, the
status or the bar counts as clicking the row.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QWidget

__all__ = ["ClickableRow"]


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
