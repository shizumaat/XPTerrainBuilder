"""Settings' two detail controls (issue #1985), Qt side.

* :class:`AirportDetailRow` — General's **Detail** choice under the preset
  cards: None / ICAO airports / All airports (``O4_Airport_Detail``), with
  Custom shown while no choice's keys all hold.  The Mac app's
  ``AirportDetailPicker`` (``SettingsDetailPickers.swift``).
* :class:`ImageryZoomRow` — Imagery's build zoom (moved from General):
  the :class:`O4_Qt_Detail_Combo.DetailCombo` with its label.  The Mac
  app's ``ImageryZoomPicker``.

Both are presentation only; the Settings window applies a choice.
"""

import O4_Airport_Detail as AIRPORT_DETAIL
import O4_Glossary as GLOSSARY
from O4_Qt_Detail_Combo import DetailCombo
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QVBoxLayout, QWidget

__all__ = ["AirportDetailRow", "ImageryZoomRow", "CUSTOM_KEY"]

#: The combo's data for the Custom entry (no choice holds).
CUSTOM_KEY = "custom"


class AirportDetailRow(QWidget):
    """Label, combo and one-line summary; emits :attr:`chosen` (a choice
    key) when the user picks a choice."""

    chosen = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        row = QHBoxLayout()
        row.addWidget(QLabel("%s:" % AIRPORT_DETAIL.TITLE))
        self.combo = QComboBox()
        for key, title in AIRPORT_DETAIL.CHOICES:
            self.combo.addItem(title, key)
        self.combo.setToolTip(AIRPORT_DETAIL.SUMMARY)
        self.combo.activated.connect(self._activated)
        row.addWidget(self.combo)
        row.addStretch(1)
        layout.addLayout(row)
        summary = QLabel(AIRPORT_DETAIL.SUMMARY)
        summary.setWordWrap(True)
        summary.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(summary)

    def current_key(self):
        return self.combo.currentData()

    def set_current(self, key):
        """Show ``key``, or Custom for ``None``."""
        self.combo.blockSignals(True)
        custom = self.combo.findData(CUSTOM_KEY)
        if key is None:
            if custom < 0:
                self.combo.addItem(AIRPORT_DETAIL.CUSTOM_TITLE, CUSTOM_KEY)
                custom = self.combo.count() - 1
            self.combo.setCurrentIndex(custom)
        else:
            if custom >= 0:
                self.combo.removeItem(custom)
            self.combo.setCurrentIndex(self.combo.findData(key))
        self.combo.blockSignals(False)

    def _activated(self, index):
        key = self.combo.itemData(index)
        if key and key != CUSTOM_KEY:
            self.chosen.emit(key)


class ImageryZoomRow(QWidget):
    """Imagery's build-zoom row: its label and :attr:`combo`."""

    #: Words a settings search finds the row by.
    SEARCH_WORDS = "imagery detail zoom level zl build"

    def __init__(self, help_text, parent=None):
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 4, 0, 4)
        row.addWidget(QLabel("%s:" % GLOSSARY.TERMS["imagery_detail"]))
        self.combo = DetailCombo(range(12, 22))
        self.combo.setToolTip(help_text)
        row.addWidget(self.combo)
        row.addStretch(1)

    def matches(self, query):
        return query in self.SEARCH_WORDS
