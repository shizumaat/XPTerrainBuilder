"""The two modes in the Qt window (RULINGS 2026-11-11k; 10j's third,
Library, is retired; spec ``docs/specs/flight-manager-and-world-20261110.md``
§14, lane U1).

The Mac app's ``AppMode.swift`` and ``FlyPane.swift`` are the layout;
``tests/test_qt_layout_parity.py`` holds the two equal.

- :class:`ModeSwitch` — Build · Fly, leading the toolbar.
- :class:`FlyOfferBanner` — "X-Plane has a flight loaded. Open Fly" above
  the side pane in Build; never switches by itself.
- Fly mode's pane is ``O4_Qt_Fly_Pane.FlyPane`` (lane U2).
- The storage rows Library held are Settings ▸ Storage's
  (``O4_Qt_Library_Storage.StorageRows``); its tiles table and patch
  library (``O4_Qt_Library``) are PARKED until the developer tools of 11k
  (3) are ruled (owner 2026-11-11T15:35Z).
"""

from __future__ import annotations

import O4_App_Modes as MODES
import O4_Glossary as GLOSSARY
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QToolButton,
    QWidget,
)


def _mode_title(mode: str) -> str:
    """The segment's word (the glossary's ``mode_<mode>``)."""
    return GLOSSARY.TERMS["mode_" + mode]


class ModeSwitch(QWidget):
    """A segmented Build · Fly control."""

    mode_changed = Signal(str)

    def __init__(self, mode=MODES.DEFAULT, parent=None):
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.buttons = {}
        for key in MODES.MODES:
            button = QToolButton()
            button.setText(_mode_title(key))
            button.setCheckable(True)
            button.setToolTip("Show the %s pane" % _mode_title(key))
            self.group.addButton(button)
            row.addWidget(button)
            self.buttons[key] = button
            button.toggled.connect(
                lambda on, k=key: on and self.mode_changed.emit(k))
        self.set_mode(mode)

    def mode(self) -> str:
        return next(k for k, b in self.buttons.items() if b.isChecked())

    def set_mode(self, mode: str):
        """Check ``mode``'s segment (emits :attr:`mode_changed` on a change)."""
        self.buttons[MODES.restore(mode)].setChecked(True)


class FlyOfferBanner(QFrame):
    """The offer to open Fly when X-Plane has a flight loaded."""

    open_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        self.offer = MODES.FlyOffer()
        row = QHBoxLayout(self)
        row.setContentsMargins(8, 6, 8, 6)
        self.text_label = QLabel(MODES.OFFER_TEXT)
        self.text_label.setWordWrap(True)
        row.addWidget(self.text_label, 1)
        self.open_btn = QPushButton(MODES.OFFER_OPEN)
        self.open_btn.clicked.connect(self._open)
        row.addWidget(self.open_btn)
        self.dismiss_btn = QPushButton(MODES.OFFER_DISMISS)
        self.dismiss_btn.clicked.connect(self._dismiss)
        row.addWidget(self.dismiss_btn)
        self.setVisible(False)

    def observe(self, event, mode):
        """One ``ImageryFollowStatus`` event, in the window's mode."""
        shown = self.offer.observe(
            getattr(event, "state", ""), getattr(event, "xplane", False),
            int(getattr(event, "flight_loads", 0) or 0), mode)
        self.setVisible(shown)

    def mode_changed(self, mode):
        if mode == "fly":
            self._dismiss()

    def _open(self):
        self._dismiss()
        self.open_requested.emit()

    def _dismiss(self):
        self.offer.dismiss()
        self.setVisible(False)
