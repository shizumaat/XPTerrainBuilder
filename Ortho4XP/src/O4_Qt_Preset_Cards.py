"""The three settings preset cards of the Qt app (#822).

One row of cards (``O4_Settings_Presets.PRESETS``) with a "Current: …"
line; the Settings window and the first-run wizard both show it.  The
widget only displays and reports a click: the caller applies the preset
(``chosen`` carries its key) and tells the row what is current
(:meth:`PresetCards.set_current`).
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

import O4_Settings_Presets as PRESETS
from O4_Qt_Widgets import never_widen, wrap_and_never_widen

__all__ = ["PresetCards"]

_CARD_STYLE = "QFrame#presetCard { border: 1px solid palette(mid); border-radius: 6px; }"
_CURRENT_STYLE = (
    "QFrame#presetCard { border: 2px solid palette(highlight); border-radius: 6px; }"
)


class PresetCards(QWidget):
    """A titled row of preset cards; ``chosen(key)`` fires on Use."""

    chosen = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        head = QHBoxLayout()
        title = QLabel("<b>%s</b>" % PRESETS.SECTION_TITLE)
        head.addWidget(title)
        head.addStretch(1)
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: gray;")
        head.addWidget(self.status_label)
        root.addLayout(head)

        row = QHBoxLayout()
        self.cards = {}    # preset key -> QFrame
        self.buttons = {}  # preset key -> QPushButton
        for entry in PRESETS.PRESETS:
            card = QFrame()
            card.setObjectName("presetCard")
            card.setStyleSheet(_CARD_STYLE)
            lay = QVBoxLayout(card)
            lay.setContentsMargins(10, 8, 10, 8)
            lay.addWidget(wrap_and_never_widen(QLabel("<b>%s</b>" % entry.title)))
            summary = wrap_and_never_widen(QLabel(entry.summary))
            lay.addWidget(summary)
            cost = wrap_and_never_widen(QLabel(entry.cost))
            cost.setStyleSheet("color: gray; font-size: 11px;")
            lay.addWidget(cost)
            lay.addStretch(1)
            button = QPushButton("Use")
            never_widen(button)
            button.setToolTip("Use the %s settings" % entry.title)
            button.clicked.connect(
                lambda _checked=False, key=entry.key: self.chosen.emit(key))
            lay.addWidget(button)
            row.addWidget(card, 1)
            self.cards[entry.key] = card
            self.buttons[entry.key] = button
        root.addLayout(row)
        note = wrap_and_never_widen(QLabel(PRESETS.SECTION_NOTE))
        note.setStyleSheet("color: gray; font-size: 11px;")
        root.addWidget(note)
        self.current_key = None

    def set_current(self, current: dict) -> None:
        """Highlight the preset ``current`` matches; "Custom" when none."""
        entry = PRESETS.matching_preset(current)
        self.current_key = entry.key if entry else None
        self.status_label.setText(PRESETS.status_text(current))
        for key, card in self.cards.items():
            card.setStyleSheet(
                _CURRENT_STYLE if key == self.current_key else _CARD_STYLE)
            self.buttons[key].setEnabled(key != self.current_key)
