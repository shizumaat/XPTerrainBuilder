"""The Qt window's "Divert…" dialog and flight notifications (spec
flight-manager-and-world-20261110 §4.3 step 8, §14 "Notifications"; lane
F2).  The Mac app's ``DivertSheet`` (``FlyPane.swift``) and
``FlightNotifier.swift`` are the same.

* :class:`DivertDialog` -- the plan's alternate first, then any airport
  of X-Plane's list by code or name (``O4_Fly_Divert_Text.divert_matches``);
  :meth:`DivertDialog.choice` is ``"alternate"``, ``{ident, lat, lon}``
  or None (cancelled).
* :func:`post_notice` -- one ``FlightNotice`` as one system notification
  (``QSystemTrayIcon.showMessage``), when the system has a tray.
"""

from __future__ import annotations

from typing import Any, Callable, Optional

import O4_Fly_Divert_Text as DTEXT
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSystemTrayIcon,
    QVBoxLayout,
)

__all__ = ["DivertDialog", "post_notice"]

_TRAY: dict = {}


def _airport_rows(entries) -> list:
    """X-Plane's airport list (``O4_Airport_Index`` entries) as the
    search's rows ``[ident, name, lat, lon]``."""
    return [[e.code, getattr(e, "name", "") or "", e.lat, e.lon]
            for e in entries or ()]


class DivertDialog(QDialog):
    """See the module."""

    def __init__(self, airports: Callable[[], Any], has_alternate: bool,
                 parent=None):
        super().__init__(parent)
        self.setWindowTitle(DTEXT.DIVERT_TITLE)
        self._rows = _airport_rows(airports())
        self._choice: Optional[Any] = None
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<b>%s</b>" % DTEXT.DIVERT_TITLE))
        self.alternate_btn = QPushButton(DTEXT.DIVERT_ALTERNATE)
        self.alternate_btn.setVisible(has_alternate)
        self.alternate_btn.clicked.connect(lambda: self._choose("alternate"))
        layout.addWidget(self.alternate_btn)
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText(DTEXT.DIVERT_SEARCH)
        self.search_edit.textChanged.connect(self._search)
        layout.addWidget(self.search_edit)
        self.results = QListWidget()
        self.results.itemActivated.connect(self._activated)
        layout.addWidget(self.results)
        buttons = QDialogButtonBox(QDialogButtonBox.Cancel)
        self.divert_btn = buttons.addButton(DTEXT.DIVERT_BUTTON,
                                            QDialogButtonBox.AcceptRole)
        self.divert_btn.clicked.connect(
            lambda: self._activated(self.results.currentItem()))
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _search(self, text: str) -> None:
        self.results.clear()
        for row in DTEXT.divert_matches(text, self._rows):
            item = QListWidgetItem(DTEXT.divert_row_label(row))
            item.setData(256, {"ident": str(row[0]).upper(),
                               "lat": float(row[2]), "lon": float(row[3])})
            self.results.addItem(item)
        if self.results.count():
            self.results.setCurrentRow(0)

    def _activated(self, item) -> None:
        if item is not None:
            self._choose(item.data(256))

    def _choose(self, choice) -> None:
        self._choice = choice
        self.accept()

    def choice(self) -> Optional[Any]:
        return self._choice


def post_notice(window, event) -> bool:
    """Show a ``FlightNotice`` as a system notification; False when the
    system has no tray (the Fly pane still shows it)."""
    if not QSystemTrayIcon.isSystemTrayAvailable():
        return False
    tray = _TRAY.get("icon")
    if tray is None:
        tray = QSystemTrayIcon(window.windowIcon(), window)
        tray.show()
        _TRAY["icon"] = tray
    icon = (QSystemTrayIcon.Warning if getattr(event, "severity", "") == "warning"
            else QSystemTrayIcon.Information)
    tray.showMessage(getattr(event, "title", ""), getattr(event, "text", ""),
                     icon)
    return True
