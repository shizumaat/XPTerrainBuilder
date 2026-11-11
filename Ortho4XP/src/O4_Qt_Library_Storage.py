"""Settings ▸ Storage's rows in the Qt window (RULINGS 2026-11-11k (2);
the Library pane's from #2007 until 11k retired Library mode; the Mac
app's ``LibraryStorage.swift``): the data folder, then the ONE disk budget
(RULINGS 2026-11-10d; its default 2026-11-11a/h) that everything the app
keeps fits in, caches included, then Convert existing tiles and the
Caches line: one total, Clear… and Details…, the per-cache list in its own
window (``O4_Qt_Settings_Storage.StorageSection``).  One section's scan
feeds all of them (its ``scan_shown`` signal).

- :class:`StorageRows` -- the four, top to bottom, as Settings shows them.
- :class:`DataFolderRow` -- the data folder.
- :class:`DiskBudgetBox` -- the budget, visible and editable; unset, the
  default applies, holds the current install (RULINGS 2026-11-11h (1))
  and Confirm records it; a budget below what is in use asks
  "downgrade scenery to low res to fit?" with the bytes first (Cancel
  keeps the old budget).
- :class:`CachesLine` -- the total, Clear… and Details….
"""

from __future__ import annotations

import O4_Qt_Convert_Tiles as QTCONVERT
import O4_Qt_Settings_Storage as QTSTORAGE
import O4_Storage_Text as TEXT
from O4_Qt_Library import fmt_size
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

__all__ = ["StorageRows"]

NOTE_STYLE = "color: gray; font-size: 11px;"
WARNING_STYLE = "color: #C0392B; font-size: 11px;"


def _title(text):
    return QLabel("<b>%s</b>" % text)


def _note(style=NOTE_STYLE):
    label = QLabel("")
    label.setWordWrap(True)
    label.setStyleSheet(style)
    return label


class DataFolderRow(QWidget):
    """The data folder (``storage_scan``'s root)."""

    def __init__(self, storage, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(_title(TEXT.FOLDER_TITLE))
        self.folder_label = _note()
        layout.addWidget(self.folder_label)
        storage.scan_shown.connect(lambda scan: self.folder_label.setText(scan["root"]))


class DiskBudgetBox(QWidget):
    """The disk budget: its line, the default and recommended figures, a
    field with Set (and Use Default once set, Confirm until then)."""

    def __init__(self, storage, parent=None):
        super().__init__(parent)
        self.storage = storage
        self.budget = {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(_title(TEXT.BUDGET_TITLE))
        self.budget_label = QLabel("")
        self.budget_label.setWordWrap(True)
        self.budget_label.setToolTip(TEXT.BUDGET_HELP)
        layout.addWidget(self.budget_label)
        self.default_label = _note()
        layout.addWidget(self.default_label)
        self.budget_warning = _note(WARNING_STYLE)
        self.budget_warning.setVisible(False)
        layout.addWidget(self.budget_warning)
        row = QHBoxLayout()
        self.budget_edit = QLineEdit()
        self.budget_edit.setPlaceholderText(TEXT.BUDGET_FIELD)
        self.budget_edit.setMaximumWidth(90)
        self.budget_edit.returnPressed.connect(self.submit)
        row.addWidget(self.budget_edit)
        self.set_btn = QPushButton(TEXT.BUDGET_SET)
        self.set_btn.clicked.connect(self.submit)
        row.addWidget(self.set_btn)
        self.default_btn = QPushButton(TEXT.BUDGET_USE_DEFAULT)
        self.default_btn.clicked.connect(lambda: self._set(0.0))
        row.addWidget(self.default_btn)
        self.confirm_btn = QPushButton(TEXT.BUDGET_CONFIRM)
        self.confirm_btn.clicked.connect(
            lambda: self._set(int(self.budget.get("budget_bytes") or 0) / 1e9))
        row.addWidget(self.confirm_btn)
        row.addStretch(1)
        layout.addLayout(row)
        storage.scan_shown.connect(self.show_scan)
        self.show_scan({})

    def show_scan(self, scan):
        self.budget = (scan or {}).get("budget") or {}
        line, warning = TEXT.budget_lines(self.budget) if self.budget else ("", "")
        self.budget_label.setText(line)
        self.default_label.setText(TEXT.default_line(self.budget) if self.budget else "")
        held = TEXT.held_line(self.budget) if self.budget else ""
        self.default_label.setText("<br>".join(
            t for t in (self.default_label.text(), held) if t))
        self.budget_warning.setText(warning)
        self.budget_warning.setVisible(bool(warning))
        self.default_btn.setVisible(bool(self.budget.get("budget_set")))
        self.confirm_btn.setVisible(bool(held))
        self._show_field()

    def _show_field(self):
        """The field shows the budget that applies (the default when unset)."""
        nbytes = self.budget.get("budget_bytes")
        self.budget_edit.setText("%.0f" % (nbytes / 1e9) if nbytes else "")

    def submit(self):
        try:
            gigabytes = float(self.budget_edit.text())
        except ValueError:
            gigabytes = 0.0
        if gigabytes <= 0:
            self._show_field()
            return
        nbytes = int(gigabytes * 1e9)
        if self.budget and TEXT.needs_downgrade(self.budget, nbytes):
            self._ask(nbytes)
        else:
            self._set(gigabytes)

    def confirm(self, title, text):
        """A seam: tests answer without a modal."""
        return QMessageBox.question(self, title, text) == QMessageBox.Yes

    def _ask(self, nbytes):
        """Below what is in use: downgrade to fit, asked first; Cancel
        keeps the old budget."""
        if self.confirm(TEXT.DOWNGRADE_TITLE, TEXT.downgrade_text(self.budget, nbytes)):
            self.storage.apply_budget(nbytes / 1e9)
        else:
            self._show_field()

    def _set(self, gigabytes):
        import O4_Settings_Model as SM
        from O4_Qt_Settings_Storage import BUDGET_SETTING
        SM.write_global({BUDGET_SETTING: str(float(gigabytes))})
        self.storage.refresh()


class CachesLine(QWidget):
    """Caches: one total, Clear… (every cache, asked first), Details…."""

    def __init__(self, storage, parent=None):
        super().__init__(parent)
        self.storage = storage
        self.dialog = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        top = QHBoxLayout()
        top.addWidget(_title(TEXT.CACHES_TITLE))
        top.addStretch(1)
        self.total_label = QLabel("—")
        self.total_label.setToolTip(TEXT.CACHES_HELP)
        top.addWidget(self.total_label)
        layout.addLayout(top)
        row = QHBoxLayout()
        self.clear_btn = QPushButton(TEXT.CACHES_CLEAR)
        self.clear_btn.clicked.connect(storage.ask_clear_all)
        row.addWidget(self.clear_btn)
        self.details_btn = QPushButton(TEXT.CACHES_DETAILS)
        self.details_btn.clicked.connect(self.show_details)
        row.addWidget(self.details_btn)
        row.addStretch(1)
        layout.addLayout(row)
        storage.scan_shown.connect(self._shown)

    def _shown(self, scan):
        self.total_label.setText(fmt_size(scan["cache_bytes"]))
        self.clear_btn.setEnabled(bool(scan["cache_bytes"]))

    def show_details(self):
        """The per-cache list, out of the pane (owner 2026-11-11)."""
        if self.dialog is None:
            self.dialog = _StorageDetailsDialog(self.storage, self.window())
        self.dialog.show()
        self.dialog.raise_()
        return self.dialog


class StorageRows(QWidget):
    """Settings ▸ Storage, top to bottom (11k (2), in 11a's order): the
    data folder (``folder_row``), the disk budget (``budget_box``),
    Convert existing tiles (``convert_box``, World spec §13) and the
    Caches line (``caches_box``; Details… opens ``storage``, the
    per-cache list, in its own window).  Measured the first time it is
    shown (:meth:`refresh`)."""

    def __init__(self, scenery_dir, busy=lambda: False, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        self.storage = QTSTORAGE.StorageSection(busy=busy)
        self.folder_row = DataFolderRow(self.storage)
        self.budget_box = DiskBudgetBox(self.storage)
        self.convert_box = QTCONVERT.ConvertTilesSection(scenery_dir)
        self.caches_box = CachesLine(self.storage)
        for row in (self.folder_row, self.budget_box, self.convert_box,
                    self.caches_box):
            layout.addWidget(row)

    @property
    def scan(self):
        return self.storage.scan

    def refresh(self):
        self.storage.refresh()

    def matches(self, query: str) -> bool:
        return self.storage.matches(query) or any(
            word in query.lower() for word in ("budget", "convert", "tiles"))


class _StorageDetailsDialog(QDialog):
    """The window around Settings ▸ Storage's ``StorageSection``."""

    def __init__(self, storage, parent=None):
        super().__init__(parent)
        self.setWindowTitle(TEXT.CACHES_DETAILS_TITLE)
        self.resize(560, 520)
        layout = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(storage)
        layout.addWidget(scroll, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.hide)
        layout.addWidget(buttons)
