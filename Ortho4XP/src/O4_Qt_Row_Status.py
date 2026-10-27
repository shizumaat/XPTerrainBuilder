"""A progress row's status label that can take a click (issue #1341).

A finished row's gold or red status reopens its tile's messages: once
:meth:`ClickableStatus.set_clickable`, the label takes a left click as its
own -- so the click never also selects the row in the Activity list
(``O4_Qt_Activity_List``) -- and emits ``clicked``; otherwise the click
passes through to the list like any label's.
"""

from O4_Qt_Widgets import ElidedRowLabel
from PySide6.QtCore import Qt, Signal

__all__ = ["ClickableStatus"]


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
