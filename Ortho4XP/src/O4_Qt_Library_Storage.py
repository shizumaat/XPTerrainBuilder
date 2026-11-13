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
- :class:`DiskBudgetBox` -- the budget, visible and editable (#2022): a
  slider from the minimum (what is always kept) to the most (keeping
  50 GB free), a number field, the stacked usage bar (:class:`UsageBar`)
  and, while the slider moves, what that budget would clear; unset, the
  default applies, holds the current install (RULINGS 2026-11-11h (1))
  and Confirm records it; a budget below what is in use asks
  "downgrade scenery to low res to fit?" with the bytes first (Cancel
  keeps the old budget).
- :class:`CachesLine` -- the total, Clear… and Details….
"""

from __future__ import annotations

import O4_Qt_Convert_Tiles as QTCONVERT
import O4_Qt_Settings_Storage as QTSTORAGE
import O4_Qt_Storage_Tiers as QTTIERS
import O4_Storage_Text as TEXT
from O4_Qt_Library import fmt_size
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSlider,
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


class UsageBar(QWidget):
    """What is in use by kind (``O4_Storage_Text.bar_parts``): one
    stacked bar, its legend in :attr:`legend`."""

    COLORS = ("#8E8E93", "#0A84FF", "#FF9F0A", "#30B0C7", "#BF5AF2", "#C7C7CC")

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parts = []
        self.setFixedHeight(10)
        self.legend = _note()

    def show_budget(self, budget):
        self.parts = TEXT.bar_parts(budget) if budget else []
        self.legend.setText(" · ".join(legend for _k, _b, legend in self.parts))
        self.update()

    def paintEvent(self, _event):
        total = sum(nbytes for _k, nbytes, _l in self.parts)
        if total <= 0:
            return
        painter = QPainter(self)
        x = 0.0
        for index, (_key, nbytes, _legend) in enumerate(self.parts):
            width = self.width() * nbytes / total
            painter.fillRect(int(x), 0, max(0, round(x + width) - int(x)),
                             self.height(), QColor(self.COLORS[index % len(self.COLORS)]))
            x += width
        painter.end()


class DiskBudgetBox(QWidget):
    """The disk budget: its line, the usage bar, the slider with its
    labelled ends and a number field, the preview while the slider
    moves, and Use Default once set (Confirm until then)."""

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
        self.usage_bar = UsageBar()
        layout.addWidget(self.usage_bar)
        layout.addWidget(self.usage_bar.legend)
        # One row (owner 2026-11-12): the label left, the slider filling
        # the middle, the number field right.
        row = QHBoxLayout()
        self.budget_field_label = QLabel(TEXT.BUDGET_FIELD)
        row.addWidget(self.budget_field_label)
        self.budget_slider = QSlider(Qt.Horizontal)
        self.budget_slider.sliderMoved.connect(self._moved)
        self.budget_slider.sliderReleased.connect(self._released)
        row.addWidget(self.budget_slider, 1)
        self.budget_edit = QLineEdit()
        self.budget_edit.setAlignment(Qt.AlignRight)
        self.budget_edit.setFixedWidth(70)
        self.budget_edit.returnPressed.connect(self.submit)
        row.addWidget(self.budget_edit)
        layout.addLayout(row)
        ends = QHBoxLayout()
        self.min_label, self.max_label = _note(), _note()
        self.max_label.setAlignment(Qt.AlignRight)
        ends.addWidget(self.min_label, 1)
        ends.addWidget(self.max_label, 1)
        layout.addLayout(ends)
        self.preview_label = _note("font-size: 11px;")
        self.preview_label.setVisible(False)
        layout.addWidget(self.preview_label)
        self.held_label = _note()
        layout.addWidget(self.held_label)
        self.budget_warning = _note(WARNING_STYLE)
        self.budget_warning.setVisible(False)
        layout.addWidget(self.budget_warning)
        buttons = QHBoxLayout()
        self.default_btn = QPushButton(TEXT.BUDGET_USE_DEFAULT)
        self.default_btn.clicked.connect(lambda: self._set(0.0))
        buttons.addWidget(self.default_btn)
        self.confirm_btn = QPushButton(TEXT.BUDGET_CONFIRM)
        self.confirm_btn.clicked.connect(
            lambda: self._set(int(self.budget.get("budget_bytes") or 0) / 1e9))
        buttons.addWidget(self.confirm_btn)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        storage.scan_shown.connect(self.show_scan)
        self.show_scan({})

    def show_scan(self, scan):
        self.budget = (scan or {}).get("budget") or {}
        line, warning = TEXT.budget_lines(self.budget) if self.budget else ("", "")
        self.budget_label.setText(line)
        self.usage_bar.show_budget(self.budget)
        ends = TEXT.end_labels(self.budget) if self.budget else ("", "")
        self.min_label.setText(ends[0])
        self.max_label.setText(ends[1])
        held = TEXT.held_line(self.budget) if self.budget else ""
        self.held_label.setText(held)
        self.held_label.setVisible(bool(held))
        notice = TEXT.range_notice(self.budget) if self.budget else ""
        warnings = "<br>".join(t for t in (notice, warning) if t)
        self.budget_warning.setText(warnings)
        self.budget_warning.setVisible(bool(warnings))
        self.default_btn.setVisible(bool(self.budget.get("budget_set")))
        self.confirm_btn.setVisible(bool(held))
        self._show_field()

    def _range(self):
        """The slider's ends in whole GB (a degenerate range widens)."""
        low = int(self.budget.get("minimum_bytes") or 0) // 10**9
        high = int(self.budget.get("maximum_bytes")
                   or self.budget.get("budget_bytes") or 0) // 10**9
        return low, max(high, low + 1)

    def _show_field(self):
        """The field and slider show the budget that applies (the default
        when unset), the slider inside its range."""
        nbytes = self.budget.get("budget_bytes")
        self.budget_edit.setText("%.0f" % (nbytes / 1e9) if nbytes else "")
        low, high = self._range()
        self.budget_slider.blockSignals(True)
        self.budget_slider.setRange(low, high)
        self.budget_slider.setValue(int(round((nbytes or 0) / 1e9)))
        self.budget_slider.blockSignals(False)
        self.budget_slider.setEnabled(bool(self.budget))

    def _moved(self, gigabytes):
        """While the slider moves: the field and the preview line."""
        self.budget_edit.setText(str(gigabytes))
        if self.budget:
            self.preview_label.setText(TEXT.preview_text(self.budget, gigabytes * 10**9))
            self.preview_label.setVisible(True)

    def _released(self):
        self.preview_label.setVisible(False)
        self.budget_edit.setText(str(self.budget_slider.value()))
        self.submit()

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
    Convert existing tiles (``convert_box``, World spec §13), the
    storage tiers (``tiers_box``, RULINGS 2026-11-12g) and the
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
        # Other drives as optional tiers (RULINGS 2026-11-12g).
        self.tiers_box = QTTIERS.TiersBox()
        self.caches_box = CachesLine(self.storage)
        for row in (self.folder_row, self.budget_box, self.convert_box,
                    self.tiers_box, self.caches_box):
            layout.addWidget(row)

    @property
    def scan(self):
        return self.storage.scan

    def refresh(self):
        self.storage.refresh()

    def show_shared(self):
        """Shown (#2029): the background scan at once, then a quiet
        refresh when it is missing or old (:meth:`refresh`)."""
        self.storage.show_shared(self.refresh)

    def matches(self, query: str) -> bool:
        return self.storage.matches(query) or any(
            word in query.lower() for word in ("budget", "convert", "tiles",
                                               "tier", "drive"))


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
