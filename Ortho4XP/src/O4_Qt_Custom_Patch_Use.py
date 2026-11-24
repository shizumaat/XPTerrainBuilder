"""The custom-patch picker in the Qt window (#2179; owner RULINGS
2026-11-23d/f).

Twin of the Mac app's ``CustomPatchUsePicker.swift``: one row per airport
with a hand-made custom patch, "As made" (the default) or "Our auto
patch", with the warning under an airport used as made.  Shown in the tile
pane's Custom patch row (``O4_Qt_GUI``) and the Build box's Airports card
(``O4_Qt_Build_Airports``).  The rows are ``O4_Custom_Patches.
airport_uses``; a choice is written through ``O4_Custom_Patches.set_use``
by the caller's ``on_choose(row, mode)``.
"""

import O4_Custom_Patch_Use as CUSTOM_USE
import O4_Custom_Patches as CUSTOM_PATCHES
from O4_Qt_Widgets import never_widen, wrap_and_never_widen
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

__all__ = ["CustomPatchUseList", "WARNING_MARK"]

#: Before the warning (the Mac row's ``exclamationmark.triangle``).
WARNING_MARK = "⚠︎ "


class CustomPatchUseList(QWidget):
    """The pickers for a list of rows; ``combos`` / ``warnings`` by ICAO."""

    def __init__(self, on_choose, parent=None, indent=0):
        super().__init__(parent)
        self._on_choose = on_choose
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(indent, 0, 0, 0)
        self._layout.setSpacing(2)
        self.combos = {}
        self.warnings = {}
        self.rows = []

    def set_rows(self, rows):
        """Show *rows* (``airport_uses``), replacing the earlier ones."""
        while self._layout.count():
            item = self._layout.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        (self.combos, self.warnings, self.rows) = ({}, {}, list(rows or ()))
        for row in self.rows:
            line = QWidget()
            h = QHBoxLayout(line)
            h.setContentsMargins(0, 0, 0, 0)
            h.setSpacing(6)
            h.addWidget(QLabel(row["icao"]))
            combo = QComboBox()
            for mode in CUSTOM_USE.MODES:
                combo.addItem(CUSTOM_PATCHES.use_title(mode), mode)
                combo.setItemData(combo.count() - 1, _help(mode),
                                  Qt.ToolTipRole)
            combo.setCurrentIndex(max(0, combo.findData(row.get("use"))))
            combo.setToolTip("%s (%s)" % (_help(row.get("use")),
                                          ", ".join(row.get("files") or ())))
            combo.currentIndexChanged.connect(
                lambda _i, row=row, combo=combo: self._chosen(row, combo))
            never_widen(combo)
            h.addWidget(combo)
            h.addStretch(1)
            self._layout.addWidget(line)
            self.combos[row["icao"]] = combo
            warning = QLabel(WARNING_MARK + row["warning"]
                             if row.get("warning") else "")
            wrap_and_never_widen(warning)
            warning.setStyleSheet("color: palette(placeholder-text);")
            warning.setVisible(bool(row.get("warning")))
            self._layout.addWidget(warning)
            self.warnings[row["icao"]] = warning
        self.setVisible(bool(self.rows))

    def set_enabled_for(self, tile_busy):
        """Disable a row while ``tile_busy((lat, lon))`` (#1922)."""
        for row in self.rows:
            combo = self.combos.get(row["icao"])
            if combo is not None:
                combo.setEnabled(not tile_busy(tuple(row["tile"])))

    def _chosen(self, row, combo):
        mode = combo.currentData()
        if mode and mode != row.get("use"):
            self._on_choose(row, mode)


def _help(mode):
    return (CUSTOM_PATCHES.AUTO_PATCH_HELP if mode == CUSTOM_USE.AUTO_PATCH
            else CUSTOM_PATCHES.AS_MADE_HELP)
