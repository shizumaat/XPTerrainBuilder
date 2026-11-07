"""A non-modal per-pack question that answers like a ``QMessageBox`` —
the base of the Qt window's checkbox questions ("Optimise pack", #1707;
the package adjustments, #1916).

A subclass lays out its words and checkboxes, adds its buttons to
``self._buttons`` (a ``QDialogButtonBox``) with ``self.not_now`` the
escape, and connects ``self._buttons.clicked`` to :meth:`_on_clicked`.
The window's per-pack choice handler then reads :meth:`clickedButton`
from ``finished`` like it does a message box's.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog


class ChoiceDialog(QDialog):
    """The ``QMessageBox`` surface of a per-pack question."""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self._title = title
        self._clicked = None
        self._buttons = None
        self.not_now = None
        self.setWindowTitle(title)
        self.setWindowModality(Qt.NonModal)

    def _on_clicked(self, button) -> None:
        self._clicked = button
        if button is self.not_now:
            self.reject()
        else:
            self.accept()

    def reject(self) -> None:                       # Esc is Not now
        if self._clicked is None:
            self._clicked = self.not_now
        super().reject()

    def clickedButton(self):
        return self._clicked

    def buttons(self):
        return self._buttons.buttons() if self._buttons is not None else []

    def text(self) -> str:
        return self._title

    def escapeButton(self):
        return self.not_now
