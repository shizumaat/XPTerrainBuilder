"""The map toolbar's Filter menu on the Qt window (#2097; Mac:
``MapFilterMenu`` in ``MapFilter.swift``): the two non-selectable section
headers of ``O4_Map_Filter.SECTIONS``, each item a checkable action that
toggles on its own.  A click on an item ticks it and leaves the menu open,
so several can be toggled in one visit.
"""
from __future__ import annotations

from typing import Dict

import O4_Map_Filter as MAPFILTER
from PySide6.QtCore import Signal
from PySide6.QtGui import QAction, QFont
from PySide6.QtWidgets import QMenu

__all__ = ["FilterMenu"]


class FilterMenu(QMenu):
    """Headers and toggles; ``changed`` carries the items turned off."""

    changed = Signal(frozenset)

    def __init__(self, parent=None) -> None:
        super().__init__("Filter", parent)
        self.setToolTip(MAPFILTER.MENU_HELP)
        #: key -> its checkable action.
        self.items: Dict[str, QAction] = {}
        self.headers = []
        bold = QFont(self.font())
        bold.setBold(True)
        for index, (header, items) in enumerate(MAPFILTER.SECTIONS):
            if index:
                self.addSeparator()
            title = self.addAction(header)
            title.setEnabled(False)
            title.setFont(bold)
            self.headers.append(title)
            for key, label in items:
                action = self.addAction(label)
                action.setCheckable(True)
                action.setChecked(True)
                action.toggled.connect(self._emit)
                self.items[key] = action

    def hidden(self) -> frozenset:
        """The items turned off."""
        return frozenset(key for key, action in self.items.items()
                         if not action.isChecked())

    def set_hidden(self, hidden) -> None:
        """Tick every item but ``hidden``, without emitting ``changed``."""
        for key, action in self.items.items():
            action.blockSignals(True)
            action.setChecked(key not in hidden)
            action.blockSignals(False)

    def _emit(self, _checked=False) -> None:
        self.changed.emit(self.hidden())

    def mouseReleaseEvent(self, event) -> None:
        """Toggle a checkable item without closing the menu."""
        action = self.actionAt(event.position().toPoint())
        if action is not None and action.isCheckable() and action.isEnabled():
            action.trigger()
            return
        super().mouseReleaseEvent(event)
