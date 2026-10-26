"""The Library window (#824): every built tile with its size, zoom level,
imagery source, built date, graded airports, modified packs and the
"In X-Plane" switch, plus the disk panel (tiles total and each download
cache, each with "Free space…").

The Qt face of :mod:`o4_engine.library` — the Mac app's ``LibraryView``
drives the same functions through the engine's ``library_*`` commands.
Folder walks run on a daemon thread; results come back through a queued
signal (never touch widgets from a worker thread).  A tile built by
another tool is read-only: it can be linked into X-Plane or out of it,
never rebuilt or deleted.  Deleting and freeing space ask first.
"""

import threading
import time

import O4_Scenery_Links as LINKS
from o4_engine import library as LIB
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

#: (header, row key) of the table's columns, left to right — the Mac
#: app's LibraryView shows the same columns in the same order.
COLUMNS = (
    ("Tile", "tile"),
    ("Size", "size_bytes"),
    ("ZL", "zl"),
    ("Imagery", "provider"),
    ("Built", "built"),
    ("Airports", "airports"),
    ("Packs modified", "packs_modified"),
    ("In X-Plane", "in_xplane"),
    ("Built by", "built_by"),
)
SIZE_COLUMN = 1
IN_XPLANE_COLUMN = 7


def fmt_size(nbytes):
    """``1.5 GB`` — the main window's size format."""
    value = float(nbytes or 0)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return "%.1f %s" % (value, unit)
        value /= 1024


def _cell(row, key):
    """``(text, sort value)`` of one cell."""
    value = row.get(key)
    if key == "size_bytes":
        return fmt_size(value), value or 0
    if key == "built":
        text = time.strftime("%Y-%m-%d %H:%M", time.localtime(value)) if value else "—"
        return text, value or 0
    if key == "zl":
        return ("" if value is None else str(value)), value or 0
    if key == "airports":
        return ", ".join(value), len(value)
    if key == "packs_modified":
        return ", ".join(p["pack_name"] for p in value), len(value)
    if key == "in_xplane":
        return "", int(bool(value))
    if key == "built_by":
        text = "XPTerrainBuilder" if value == LIB.BUILT_HERE else "Other tool (read-only)"
        return text, text
    return str(value or ""), str(value or "")


class _Item(QTableWidgetItem):
    """A cell that sorts by its value, not its text (sizes, dates)."""

    def __init__(self, text, sort_value):
        super().__init__(text)
        self.sort_value = sort_value

    def __lt__(self, other):
        try:
            return self.sort_value < other.sort_value
        except (AttributeError, TypeError):
            return super().__lt__(other)


class LibraryDialog(QDialog):
    """What is built, and how much space it and the caches take."""

    loaded = Signal(object)
    done = Signal(str)

    def __init__(self, parent, working_dir, scenery_dir, building=lambda: False,
                 on_rebuild=None, on_changed=None, restore_pack=None):
        super().__init__(parent)
        self.setWindowTitle("Library")
        self.resize(980, 560)
        self.working_dir = working_dir
        self.scenery_dir = scenery_dir
        self._building = building
        self._on_rebuild = on_rebuild
        self._on_changed = on_changed
        self._restore_pack = restore_pack
        self.rows = []
        self.caches = []
        self.tiles_bytes = 0

        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search tiles, airports, imagery…")
        self.search_edit.textChanged.connect(self._apply_filter)
        top.addWidget(self.search_edit, 1)
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.refresh)
        top.addWidget(self.refresh_btn)
        layout.addLayout(top)

        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels([h for h, _k in COLUMNS])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSortingEnabled(True)
        self.table.itemSelectionChanged.connect(self._sync_buttons)
        self.table.itemChanged.connect(self._on_item_changed)
        layout.addWidget(self.table, 1)

        actions = QHBoxLayout()
        self.install_btn = QPushButton("Install")
        self.install_btn.clicked.connect(lambda: self._set_installed(True))
        self.uninstall_btn = QPushButton("Uninstall")
        self.uninstall_btn.clicked.connect(lambda: self._set_installed(False))
        self.rebuild_btn = QPushButton("Rebuild")
        self.rebuild_btn.clicked.connect(self._rebuild)
        self.delete_btn = QPushButton("Delete…")
        self.delete_btn.clicked.connect(self._delete)
        self.restore_btn = QPushButton("Restore originals…")
        self.restore_btn.setToolTip(
            "Put back the original object files of the custom packs these "
            "tiles' builds modified")
        self.restore_btn.clicked.connect(self._restore_originals)
        for button in (self.install_btn, self.uninstall_btn, self.rebuild_btn,
                       self.delete_btn, self.restore_btn):
            actions.addWidget(button)
        actions.addStretch(1)
        self.status_label = QLabel("")
        actions.addWidget(self.status_label)
        layout.addLayout(actions)

        disk = QGroupBox("Disk")
        self.disk_grid = QGridLayout(disk)
        self.tiles_total_label = QLabel("—")
        self.disk_grid.addWidget(QLabel("Tiles"), 0, 0)
        self.disk_grid.addWidget(self.tiles_total_label, 0, 1)
        self.cache_labels = {}
        self.free_buttons = {}
        for index, (kind, (label, redownload)) in enumerate(LIB.CACHE_KINDS.items(), 1):
            self.disk_grid.addWidget(QLabel(label), index, 0)
            size = QLabel("—")
            self.disk_grid.addWidget(size, index, 1)
            button = QPushButton("Free space…")
            button.setToolTip(redownload)
            button.clicked.connect(lambda _c=False, k=kind: self._free_cache(k))
            self.disk_grid.addWidget(button, index, 2)
            self.cache_labels[kind] = size
            self.free_buttons[kind] = button
        self.disk_grid.setColumnStretch(1, 1)
        layout.addWidget(disk)

        self.loaded.connect(self._on_loaded)
        self.done.connect(self._on_done)
        self._sync_buttons()

    # ── loading ──────────────────────────────────────────────────────────
    def _run(self, work, signal):
        """``work()`` on a daemon thread; its result (or error sentence)
        is emitted on ``signal``."""
        def run():
            try:
                result = work()
            except Exception as error:      # shown, never raised on a thread
                result = error
            signal.emit(result)
        threading.Thread(target=run, daemon=True, name="o4-qt-library").start()

    def refresh(self):
        self.status_label.setText("Reading tiles…")
        self.refresh_btn.setEnabled(False)
        self._run(lambda: LIB.library_scan(self.working_dir, self.scenery_dir),
                  self.loaded)

    def _on_loaded(self, result):
        self.refresh_btn.setEnabled(True)
        if isinstance(result, Exception):
            self.status_label.setText(str(result))
            return
        self.set_library(result)

    def set_library(self, result):
        """Show one ``library_scan`` result (tests call it directly)."""
        self.rows = list(result["tiles"])
        self.caches = list(result["caches"])
        self.tiles_bytes = result["tiles_bytes"]
        self.table.blockSignals(True)
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(self.rows))
        for r, row in enumerate(self.rows):
            for c, (_header, key) in enumerate(COLUMNS):
                text, sort_value = _cell(row, key)
                item = _Item(text, sort_value)
                item.setData(Qt.UserRole, r)
                if key == "in_xplane":
                    item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                    item.setCheckState(Qt.Checked if row["in_xplane"] else Qt.Unchecked)
                if row["read_only"]:
                    item.setToolTip("Built by another tool: listed read-only, "
                                    "never rebuilt or deleted here.")
                self.table.setItem(r, c, item)
        self.table.setSortingEnabled(True)
        self.table.blockSignals(False)
        self.tiles_total_label.setText("%s in %d tile%s" % (
            fmt_size(self.tiles_bytes), len(self.rows),
            "" if len(self.rows) == 1 else "s"))
        for cache in self.caches:
            if cache["kind"] in self.cache_labels:
                self.cache_labels[cache["kind"]].setText(fmt_size(cache["bytes"]))
        self.status_label.setText("")
        self._apply_filter()
        self._sync_buttons()

    # ── table ────────────────────────────────────────────────────────────
    def _row_of(self, table_row):
        item = self.table.item(table_row, 0)
        return self.rows[item.data(Qt.UserRole)] if item is not None else None

    def selected_rows(self):
        indexes = sorted({i.row() for i in self.table.selectedIndexes()})
        return [row for row in (self._row_of(i) for i in indexes) if row is not None]

    def visible_tiles(self):
        """The tile keys in table order, hidden rows left out."""
        return [self._row_of(i)["tile"] for i in range(self.table.rowCount())
                if not self.table.isRowHidden(i)]

    def _apply_filter(self):
        needle = self.search_edit.text().strip().lower()
        for i in range(self.table.rowCount()):
            text = " ".join((self.table.item(i, c).text() if self.table.item(i, c) else "")
                            for c in range(len(COLUMNS))).lower()
            self.table.setRowHidden(i, bool(needle) and needle not in text)

    def _sync_buttons(self):
        rows = self.selected_rows()
        busy = bool(self._building())
        writable = bool(rows) and not any(r["read_only"] for r in rows)
        self.install_btn.setEnabled(bool(rows))
        self.uninstall_btn.setEnabled(bool(rows))
        self.rebuild_btn.setEnabled(writable and self._on_rebuild is not None)
        self.delete_btn.setEnabled(writable and not busy)
        self.restore_btn.setEnabled(
            not busy and any(r["packs_modified"] for r in rows))
        for button in self.free_buttons.values():
            button.setEnabled(not busy)

    def _on_item_changed(self, item):
        if item.column() != IN_XPLANE_COLUMN:
            return
        row = self.rows[item.data(Qt.UserRole)]
        wanted = item.checkState() == Qt.Checked
        if wanted != row["in_xplane"]:
            self._link([row], wanted)

    # ── actions ──────────────────────────────────────────────────────────
    def _link(self, rows, install):
        errors = []
        for row in rows:
            try:
                if install:
                    LINKS.install(row["lat"], row["lon"], row["build_dir"], self.scenery_dir)
                else:
                    LINKS.uninstall(row["lat"], row["lon"], row["build_dir"], self.scenery_dir)
            except (OSError, ValueError) as error:
                errors.append("%s: %s" % (row["tile"], error))
        if errors:
            QMessageBox.warning(self, "Install in X-Plane", "\n".join(errors))
        self._changed()

    def _set_installed(self, install):
        self._link(self.selected_rows(), install)

    def _rebuild(self):
        rows = [r for r in self.selected_rows() if not r["read_only"]]
        if rows and self._on_rebuild is not None:
            self._on_rebuild([(r["lat"], r["lon"]) for r in rows])

    def _delete(self):
        rows = self.selected_rows()
        if not rows or any(r["read_only"] for r in rows):
            return
        packs = sorted({p["pack_name"] for r in rows for p in r["packs_modified"]})
        text = ("Delete %d tile%s (%s)? Their folders are deleted and they are "
                "taken out of X-Plane. Your airport patches and the download "
                "caches stay." % (len(rows), "" if len(rows) == 1 else "s",
                                  fmt_size(sum(r["size_bytes"] for r in rows))))
        if packs:
            text += ("\n\nThese custom packs stay modified for the deleted "
                     "ground: %s. Use Restore originals first to put them "
                     "back." % ", ".join(packs))
        if not self.confirm("Delete tiles", text):
            return
        tiles = [[r["lat"], r["lon"]] for r in rows]
        self.status_label.setText("Deleting…")
        self._run(lambda: "Deleted %d tile(s), freed %s." % (
            len(tiles), fmt_size(LIB.library_delete(
                tiles, self.working_dir, self.scenery_dir, confirm=True)["freed_bytes"])),
            self.done)

    def _free_cache(self, kind):
        label, redownload = LIB.CACHE_KINDS[kind]
        size = next((c["bytes"] for c in self.caches if c["kind"] == kind), 0)
        if not self.confirm("Free space", "Free %s of %s cache? %s" % (
                fmt_size(size), label.lower(), redownload)):
            return
        self.status_label.setText("Freeing space…")
        self._run(lambda: "Freed %s of %s cache." % (
            fmt_size(LIB.free_cache(kind, confirm=True)["freed_bytes"]), label.lower()),
            self.done)

    def _restore_originals(self):
        packs = {p["pack_path"]: p for r in self.selected_rows()
                 for p in r["packs_modified"]}
        if not packs or self._restore_pack is None:
            return
        names = ", ".join(sorted(p["pack_name"] for p in packs.values()))
        if not self.confirm("Restore originals",
                            "Put back the original object files of %s?" % names):
            return

        def work():
            for path in sorted(packs):
                self._restore_pack(path)
            return "Restored %d pack%s." % (len(packs), "" if len(packs) == 1 else "s")
        self._run(work, self.done)

    def _on_done(self, result):
        self.status_label.setText(str(result))
        self._changed()

    def _changed(self):
        if self._on_changed is not None:
            self._on_changed()
        self.refresh()

    def confirm(self, title, text):
        """Ask first (a seam: tests answer without a modal)."""
        return QMessageBox.question(self, title, text) == QMessageBox.Yes

