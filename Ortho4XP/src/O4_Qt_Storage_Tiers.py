"""Settings ▸ Storage ▸ Storage tiers in the Qt window (RULINGS 2026-11-12g,
``o4_engine.storage_tiers``; the Mac app's ``StorageTiersSection.swift``):
each mounted drive other than the app's own, with the size it may hold of
sharp imagery (0: not used).  A tier set on a drive that is not connected
says so: its imagery is downloaded again while it is away.

The volume listing (``storage_tiers``) runs on a daemon thread when the
box is shown; a size is written (``storage_tier_set``) when its field is
finished.
"""

from __future__ import annotations

import O4_Storage_Text as TEXT
from O4_Qt_Library import emit_from_thread, fmt_size
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

__all__ = ["TiersBox"]

NOTE_STYLE = "color: gray; font-size: 11px;"


class TiersBox(QWidget):
    """The Storage tiers rows (module doc)."""

    listed = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(QLabel("<b>%s</b>" % TEXT.TIERS_TITLE))
        help_label = QLabel(TEXT.TIERS_HELP)
        help_label.setWordWrap(True)
        help_label.setStyleSheet(NOTE_STYLE)
        layout.addWidget(help_label)
        self.rows_box = QVBoxLayout()
        layout.addLayout(self.rows_box)
        self.status_label = QLabel("")
        self.status_label.setStyleSheet(NOTE_STYLE)
        layout.addWidget(self.status_label)
        self.fields = {}
        self.listed.connect(self._show)
        self._asked = False

    def showEvent(self, event):
        super().showEvent(event)
        if not self._asked:
            self._asked = True
            self.refresh()

    def refresh(self):
        from o4_engine import storage_tiers as TIERS
        emit_from_thread(TIERS.storage_tiers, self.listed, "o4-qt-storage-tiers")

    def _clear(self):
        while self.rows_box.count():
            item = self.rows_box.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.fields = {}

    def _show(self, result):
        if isinstance(result, Exception):
            self.status_label.setText(str(result))
            return
        self._clear()
        volumes = (result or {}).get("volumes") or []
        if not volumes:
            self.rows_box.addWidget(QLabel(TEXT.TIERS_NONE))
        for volume in volumes:
            self.rows_box.addWidget(self._row(volume))

    def _row(self, volume):
        row = QWidget()
        line = QHBoxLayout(row)
        line.setContentsMargins(0, 0, 0, 0)
        names = QVBoxLayout()
        names.addWidget(QLabel(volume.get("name") or volume.get("mount", "")))
        if volume.get("mounted"):
            detail = TEXT.TIERS_USED.format(
                used=fmt_size(int(volume.get("used_bytes") or 0)),
                free=fmt_size(int(volume.get("free_bytes") or 0)))
        else:
            detail = TEXT.TIERS_ABSENT
        note = QLabel(detail)
        note.setStyleSheet(NOTE_STYLE)
        names.addWidget(note)
        line.addLayout(names, 1)
        field = QDoubleSpinBox()
        field.setRange(0.0, 1_000_000.0)
        field.setDecimals(0)
        field.setSuffix(" GB")
        field.setValue(float(volume.get("size_gb") or 0.0))
        mount = volume.get("mount", "")
        field.editingFinished.connect(lambda m=mount, f=field: self._apply(m, f))
        self.fields[mount] = field
        line.addWidget(field)
        return row

    def _apply(self, mount, field):
        from o4_engine import storage_tiers as TIERS
        size = float(field.value())
        emit_from_thread(lambda: TIERS.storage_tier_set(mount, size),
                         self.listed, "o4-qt-storage-tier-set")
