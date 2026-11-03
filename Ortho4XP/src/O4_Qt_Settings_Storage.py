"""Settings ▸ Storage's sizes and Clear buttons, as the Mac app shows them
(#1724; ``StorageSettingsView.swift``'s ``StorageSection``).

Every store of the data folder with the space deleting it frees and when
it was last used (``o4_engine.storage``), a Clear… button per cache, and
"Clear cache files not used for N days" across every cache.  Built tiles,
patches and overlays are listed under Kept and never cleared here.  Every
clear asks first and names the space it frees (a whole cache: its measured
size; by age: a dry run).  The folder walks and deletions run on a daemon
thread; nothing is deleted while a build runs.

:func:`run_auto_clean` is the automatic cleanup the window runs at launch
and after each run (the two setting rows below this section; off by
default).
"""

import threading
import time

from o4_engine import storage as STORAGE
from O4_Qt_Library import emit_from_thread, fmt_size
from O4_Qt_Settings_General import _row, _Section, _value
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

__all__ = ["StorageSection", "AGE_CHOICES", "run_auto_clean"]

#: "Clear cache files not used for": days (the Mac picker's choices)
AGE_CHOICES = (30, 60, 90, 180, 365)
NOTE_STYLE = "color: gray; font-size: 11px;"
BUSY = "A build is running; stop it or let it finish before deleting anything."


def _date(unix):
    return "—" if unix is None else time.strftime("%Y-%m-%d %H:%M",
                                                  time.localtime(unix))


def _age_label(days):
    return "1 year" if days >= 365 else "%d days" % days


def run_auto_clean(busy, report):
    """The automatic cleanup on a daemon thread; ``report(sentence)`` gets
    one line when it freed anything.  Skipped while ``busy()``."""
    if busy():
        return

    def work():
        try:
            done = STORAGE.storage_auto_clean(abort=busy)
        except Exception:                   # a cleanup never fails the app
            return
        if done["ran"] and done["files"]:
            report("Storage cleanup freed %s in %d file(s) (logs/storage.log)."
                   % (fmt_size(done["freed_bytes"]), done["files"]))
    threading.Thread(target=work, daemon=True, name="o4-storage-clean").start()


class StorageSection(_Section):
    """The Storage pane's sections above its two setting rows."""

    title = "Data Folder"
    loaded = Signal(object)
    cleared = Signal(object)
    previewed = Signal(object)

    def __init__(self, busy=lambda: False, parent=None):
        super().__init__(parent)
        self.busy = busy
        self._searchable("storage", "cache", "disk", "space", "clear",
                         *(store.label for store in STORAGE.STORES))
        self.folder_label = _value()
        _row(self.layout_, "Folder", self.folder_label)
        self.caches_label = _value()
        _row(self.layout_, "Caches", self.caches_label)
        self.kept_label = _value()
        _row(self.layout_, "Your tiles and patches", self.kept_label)
        bar = QHBoxLayout()
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.refresh)
        bar.addWidget(self.refresh_btn)
        self.status_label = _value(style=NOTE_STYLE)
        bar.addWidget(self.status_label, 1)
        self.layout_.addLayout(bar)

        self.rows = QWidget()
        self.rows_layout = QVBoxLayout(self.rows)
        self.rows_layout.setContentsMargins(0, 0, 0, 0)
        self.layout_.addWidget(self.rows)
        self.age_combo = QComboBox()
        for days in AGE_CHOICES:
            self.age_combo.addItem(_age_label(days), days)
        self.age_combo.setCurrentIndex(AGE_CHOICES.index(90))
        self.older_btn = QPushButton("Clear…")
        self.older_btn.clicked.connect(self.ask_clear_older)
        _row(self.layout_, "Clear cache files not used for", self.age_combo,
             self.older_btn)
        self.clear_buttons = {}
        self.scan = None
        self.loaded.connect(self._on_loaded)
        self.cleared.connect(self._on_cleared)
        self.previewed.connect(self._on_previewed)

    # -- threads -------------------------------------------------------
    def _run(self, work, signal):
        emit_from_thread(work, signal, "o4-qt-storage")

    def refresh(self):
        self.status_label.setText("Measuring the data folder…")
        self.refresh_btn.setEnabled(False)
        self._run(STORAGE.storage_scan, self.loaded)

    def _on_loaded(self, result):
        self.refresh_btn.setEnabled(True)
        if isinstance(result, Exception):
            self.status_label.setText(str(result))
            return
        self.status_label.setText("")
        self.set_scan(result)

    def set_scan(self, scan):
        """Show one ``storage_scan`` result (tests call it directly)."""
        self.scan = scan
        self.folder_label.setText(scan["root"])
        self.caches_label.setText(fmt_size(scan["cache_bytes"]))
        self.kept_label.setText(fmt_size(scan["kept_bytes"]))
        while self.rows_layout.count():
            item = self.rows_layout.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        self.clear_buttons = {}
        for heading, policy in (("Caches", STORAGE.CACHE), ("Kept", STORAGE.KEPT)):
            self.rows_layout.addWidget(_value("<b>%s</b>" % heading))
            for store in scan["stores"]:
                if store["policy"] == policy:
                    self.rows_layout.addWidget(self._store_row(store))

    def _store_row(self, store):
        row = QWidget()
        line = QHBoxLayout(row)
        line.setContentsMargins(0, 0, 0, 0)
        name = _value("%s<br><span style='%s'>%s</span>"
                      % (store["label"], NOTE_STYLE, store["note"]))
        name.setToolTip(store["path"])
        line.addWidget(name, 1)
        line.addWidget(_value("%s<br><span style='%s'>Last used %s</span>"
                              % (fmt_size(store["bytes"]), NOTE_STYLE,
                                 _date(store["last_used"]))))
        if store["policy"] == STORAGE.CACHE:
            button = QPushButton("Clear…")
            button.setEnabled(store["files"] > 0)
            button.clicked.connect(lambda _c=False, s=store: self.ask_clear(s))
            line.addWidget(button)
            self.clear_buttons[store["kind"]] = button
        return row

    # -- clearing ------------------------------------------------------
    def confirm(self, title, message):
        """Ask before deleting (a seam: tests answer without a modal)."""
        return QMessageBox.question(self, title, message) == QMessageBox.Yes

    def ask_clear(self, store):
        if self.busy():
            self.status_label.setText(BUSY)
            return
        if self.confirm("Clear %s?" % store["label"],
                        "This frees up to %s. %s"
                        % (fmt_size(store["bytes"]), store["note"])):
            self._clear([store["kind"]], None)

    def ask_clear_older(self):
        if self.busy():
            self.status_label.setText(BUSY)
            return
        days = self.age_combo.currentData()
        self.status_label.setText("Measuring what would go…")
        self._run(lambda: (days, STORAGE.storage_clear(
            older_than_days=days, dry_run=True)), self.previewed)

    def _on_previewed(self, result):
        if isinstance(result, Exception):
            self.status_label.setText(str(result))
            return
        days, preview = result
        self.status_label.setText("")
        if not preview["files"]:
            self.status_label.setText(
                "No cache file is older than %d days." % days)
            return
        if self.confirm("Clear cache files not used for %s?" % _age_label(days),
                        "This deletes %d file(s) and frees %s. Built tiles and "
                        "airport patches are kept."
                        % (preview["files"], fmt_size(preview["freed_bytes"]))):
            self._clear([], days)

    def _clear(self, kinds, days):
        self.status_label.setText("Clearing…")
        self._run(lambda: STORAGE.storage_clear(
            kinds=kinds, older_than_days=days, confirm=True, abort=self.busy),
            self.cleared)

    def _on_cleared(self, result):
        if isinstance(result, Exception):
            self.status_label.setText(str(result))
            return
        self.status_label.setText(
            "Freed %s in %d file(s).%s" % (
                fmt_size(result["freed_bytes"]), result["files"],
                " A build started, so the rest was kept."
                if result["stopped"] else ""))
        self.refresh()
