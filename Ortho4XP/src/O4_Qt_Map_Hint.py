"""The first-visit hint over the Qt map (issue #828).

A small rounded bar at the top of the map -- "Search your airport, or
click its square on the map", pointing up at the toolbar search field --
with a close button.  Whether it shows is :mod:`O4_Map_Guidance`'s rule
(shared with the macOS app); the window owns the stored state and calls
:meth:`MapHint.apply` with each event.  Mac twin:
``Sources/XPTerrainBuilder/MapHintOverlay.swift``.
"""

from PySide6.QtCore import QEvent, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QToolButton

import O4_Map_Guidance as GUIDE

__all__ = ["MapHint"]


class MapHint(QFrame):
    """The hint bar, kept centred at the top of its parent (the map).

    :attr:`dismissed_changed` carries the new dismissed state whenever an
    event changes it, for the window to persist.
    """

    dismissed_changed = Signal(bool)

    def __init__(self, parent, dismissed: bool) -> None:
        super().__init__(parent)
        self.setObjectName("map_hint")
        self.setStyleSheet(
            "#map_hint { background: rgba(28, 30, 36, 225);"
            " border-radius: 14px; }"
            "#map_hint QLabel { color: #F0F2F5; font-weight: 600; }"
            "#map_hint QToolButton { color: #C8CCD4; border: none; }")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 6, 8, 6)
        layout.setSpacing(8)
        self.label = QLabel("↖  " + GUIDE.HINT_TEXT)
        self.label.setToolTip("The search field is at the top left of the "
                              "window")
        layout.addWidget(self.label)
        close = QToolButton()
        close.setText("✕")
        close.setToolTip("Hide this tip (Help ▸ %s brings it back)"
                         % GUIDE.SHOW_TIPS_TITLE)
        close.clicked.connect(lambda _c=False: self.apply(GUIDE.CLOSED))
        layout.addWidget(close)
        self.close_button = close
        self._dismissed = bool(dismissed)
        parent.installEventFilter(self)
        self.setVisible(not self._dismissed)
        self._place()

    @property
    def dismissed(self) -> bool:
        return self._dismissed

    def apply(self, event: str) -> None:
        """Feed one O4_Map_Guidance event; show or hide accordingly."""
        dismissed = GUIDE.dismissed_after(self._dismissed, event)
        changed = dismissed != self._dismissed
        self._dismissed = dismissed
        self.setVisible(not dismissed)
        if not dismissed:
            self.raise_()
            self._place()
        if changed:
            self.dismissed_changed.emit(dismissed)

    def _place(self) -> None:
        self.adjustSize()
        parent = self.parentWidget()
        if parent is not None:
            self.move(max(0, (parent.width() - self.width()) // 2), 12)

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Resize:
            self._place()
        return False
