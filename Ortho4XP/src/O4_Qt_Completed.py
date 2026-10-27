"""The Build panel's Completed section (issue #1556).

Built tiles (``O4_Activity_Order.section``) leave the Activity box for
this one, under it.  Collapsed, it is one disclosure line with the count
-- "Completed (12)"; expanded, the compact rows (#1542) scroll under it.
It starts collapsed and keeps the user's choice for the session.  The Mac
app's twin is ``ActivitySections`` (``ActivitySections.swift``).
"""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QGroupBox, QScrollArea, QToolButton, QVBoxLayout, QWidget

__all__ = ["completed_title", "CompletedSection"]


def completed_title(count):
    """The section's disclosure line (the Mac app's ``completedTitle``)."""
    return "Completed (%d)" % count


class CompletedSection(QGroupBox):
    """A group box: the disclosure toggle, then the rows (``rows_layout``,
    a trailing stretch last) while expanded."""

    #: Emitted with the new expanded state when the user toggles it.
    expanded_changed = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.toggle = QToolButton()
        self.toggle.setCheckable(True)
        self.toggle.setAutoRaise(True)
        font = self.toggle.font()
        font.setBold(True)
        self.toggle.setFont(font)
        layout.addWidget(self.toggle)
        self.rows_scroll = QScrollArea()
        self.rows_scroll.setWidgetResizable(True)
        host = QWidget()
        self.rows_layout = QVBoxLayout(host)
        self.rows_layout.setContentsMargins(0, 2, 0, 2)
        self.rows_layout.setSpacing(6)
        self.rows_layout.addStretch(1)
        self.rows_scroll.setWidget(host)
        layout.addWidget(self.rows_scroll, 1)
        self._count = 0
        self.toggle.toggled.connect(self._toggled)
        self._toggled(False)

    def expanded(self):
        return self.toggle.isChecked()

    def set_count(self, count):
        self._count = count
        self._show_title()

    def _show_title(self):
        self.toggle.setText(("▾ " if self.expanded() else "▸ ")
                            + completed_title(self._count))

    def _toggled(self, shown):
        self.rows_scroll.setVisible(bool(shown))
        self._show_title()
        self.expanded_changed.emit(bool(shown))
