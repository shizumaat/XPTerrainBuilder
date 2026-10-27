"""The console drawer's per-tile view and the Build History list (#1226).

Owner Q139: the console filters to the tiles selected on the map (no
tabs); a selected tile with no lines this session shows its newest saved
log, and a Saved logs menu picks one of its last three builds; one date
filter (Today / Last 48 hours / Last 7 days / Last 30 days / All, default
All) drives the Build History list and dims the map; a tile built before
logging reads "Log not saved".  The engine writes the logs and records
(``O4_Tile_Build_Log``); this reads them.

TWIN of the Mac app's ``BuildConsoleModel`` / ``BuildConsoleView`` /
``BuildHistoryView`` / ``BuildHistory.swift`` (the layout authority,
CLAUDE.md "Two UIs, one layout"): the header is title, filter chip,
Saved logs, History, Clear; the history panel sits beside the console.
"""

from __future__ import annotations

import time

import O4_File_Names as FNAMES
import O4_Tile_Build_Log as TILELOG
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

__all__ = [
    "ConsoleDrawer",
    "NOT_SAVED",
]

NOT_SAVED = "Log not saved (built before logging)"
_OUTCOMES = {"ok": "Built", "warnings": "Built with warnings",
             "failed": "Failed", "stopped": "Stopped"}
_OUTCOME_MARKS = {"ok": "✓", "warnings": "⚠", "failed": "✕", "stopped": "■"}


def outcome_text(record):
    """The outcome as the user reads it; the before-logging note when the
    tile has no record."""
    if not record:
        return NOT_SAVED
    return _OUTCOMES.get(record.get("outcome"), record.get("outcome") or "")


def _when(ts):
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(ts)) if ts else "—"


def saved_log_header(tile, record):
    """The line above a saved log in the console."""
    if not record:
        return "=== %s: saved log ===" % tile
    return "=== %s: saved log of the build of %s (%s) ===" % (
        tile, _when(record.get("end")), outcome_text(record))


def _built_date(info):
    record = getattr(info, "last_build", None) or {}
    return record.get("end") or getattr(info, "mesh_date", None)


def history_rows(built, range_key, now=None):
    """The Build History list: ``{tile, key, record, date, built_by}`` per
    built tile in the date range, newest first."""
    rows = []
    for tile, info in built.items():
        date = _built_date(info)
        if not TILELOG.in_date_range(date, range_key, now):
            continue
        record = getattr(info, "last_build", None)
        rows.append({"tile": tuple(tile),
                     "key": FNAMES.short_latlon(*tile),
                     "record": record, "date": date,
                     "built_by": (getattr(info, "built_by", "")
                                  or TILELOG.built_by_text(record))})
    rows.sort(key=lambda row: (-(row["date"] or 0), row["tile"]))
    return rows


def dimmed_tiles(built, range_key, now=None):
    """Built tiles outside the date range: the map draws them faint."""
    if range_key == "all":
        return set()
    return {tile for tile, info in built.items()
            if not TILELOG.in_date_range(_built_date(info), range_key, now)}


class ConsoleLines:
    """The console's lines, each with its tile (TWIN of the Mac app's
    ``BuildConsoleModel``).  Text arrives in chunks; a line is complete at
    its newline."""

    def __init__(self, max_lines=5000, trim_to=4000):
        self.entries = []          # (tile key or None, text)
        self._counts = {}
        self._partial = ""
        self._max_lines = max_lines
        self._trim_to = trim_to
        self.filter = frozenset()
        self.saved = []
        self.live = True

    @property
    def filtered(self):
        return bool(self.filter) or not self.live

    def add_text(self, text):
        """Store a chunk; the complete lines it finished, tagged."""
        pieces = (self._partial + text).split("\n")
        self._partial = pieces.pop()
        added = []
        for line in pieces:
            tile, _rest = TILELOG.tile_of_line(line)
            added.append((tile, line))
            if tile:
                self._counts[tile] = self._counts.get(tile, 0) + 1
        self.entries.extend(added)
        if len(self.entries) > self._max_lines:
            drop = len(self.entries) - self._trim_to
            for tile, _line in self.entries[:drop]:
                if tile:
                    self._counts[tile] -= 1
            del self.entries[:drop]
        return added

    def has_live_lines(self, tile):
        return self._counts.get(tile, 0) > 0

    def shows(self, tile):
        if not self.live:
            return False
        return tile is None or not self.filter or tile in self.filter

    def visible_text(self):
        lines = list(self.saved) + [line for tile, line in self.entries
                                    if self.shows(tile)]
        text = "\n".join(lines) + ("\n" if lines else "")
        if not self.filtered:
            text += self._partial
        return text

    def set_view(self, tiles, saved, live):
        """Change what is shown; True when the view must be rebuilt."""
        tiles = frozenset(tiles)
        if (tiles, list(saved), live) == (self.filter, self.saved, self.live):
            return False
        self.filter, self.saved, self.live = tiles, list(saved), live
        return True

    def clear(self):
        self.entries = []
        self._counts = {}
        self._partial = ""
        self.saved = []


class BuildHistoryPanel(QWidget):
    """The Build History list and its date filter (``BuildHistoryView``)."""

    tile_clicked = Signal(int, int)
    range_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        top = QHBoxLayout()
        title = QLabel("<b>Build History</b>")
        top.addWidget(title)
        top.addStretch(1)
        self.range_combo = QComboBox()
        for key, label in TILELOG.DATE_RANGES:
            self.range_combo.addItem(label, key)
        self.range_combo.setCurrentIndex(len(TILELOG.DATE_RANGES) - 1)
        self.range_combo.setToolTip(
            "Show tiles built in this period; the map dims the rest")
        self.range_combo.currentIndexChanged.connect(
            lambda _i: self.range_changed.emit(self.range_key()))
        top.addWidget(self.range_combo)
        layout.addLayout(top)
        self.list = QListWidget()
        self.list.itemClicked.connect(self._clicked)
        layout.addWidget(self.list, 1)
        self.empty_label = QLabel("No built tiles yet.")
        self.empty_label.setEnabled(False)
        layout.addWidget(self.empty_label)
        self.setFixedWidth(320)

    def range_key(self):
        return self.range_combo.currentData() or "all"

    def set_rows(self, rows, any_built):
        self.list.clear()
        for row in rows:
            record = row["record"] or {}
            parts = [outcome_text(row["record"])]
            if record.get("duration"):
                parts.append("%d min" % max(1, round(record["duration"] / 60)))
            if row["built_by"]:
                parts.append(row["built_by"])
            item = QListWidgetItem("%s %s   %s\n%s" % (
                _OUTCOME_MARKS.get(record.get("outcome"), "·"), row["key"],
                _when(row["date"]), " · ".join(parts)))
            item.setData(Qt.UserRole, row["tile"])
            item.setToolTip(outcome_text(row["record"]))
            self.list.addItem(item)
        self.list.setVisible(bool(rows))
        self.empty_label.setText("No tiles built in this period." if any_built
                                 else "No built tiles yet.")
        self.empty_label.setVisible(not rows)

    def _clicked(self, item):
        tile = item.data(Qt.UserRole)
        if tile:
            self.tile_clicked.emit(int(tile[0]), int(tile[1]))


class ConsoleDrawer(QWidget):
    """The console drawer: header, the console itself and the Build
    History panel beside it.

    ``built`` returns the window's ``{(lat, lon): TileInfo}``;
    ``select_tile(lat, lon)`` selects one tile alone on the map;
    ``dim(tiles)`` hands the map the tiles the date filter leaves out.
    """

    def __init__(self, console, built, select_tile, dim, parent=None):
        super().__init__(parent)
        self.console = console
        self.lines = ConsoleLines(
            max_lines=max(console.maximumBlockCount(), 1) or 5000,
            trim_to=int(max(console.maximumBlockCount(), 1) * 0.8) or 4000)
        self._built = built
        self._select_tile = select_tile
        self._dim = dim
        self._selection = []          # sorted (lat, lon)
        self._active = None
        self._dismissed = False
        self._chosen = None           # (tile key, log name)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        header = QHBoxLayout()
        header.setContentsMargins(8, 2, 8, 2)
        header.addWidget(QLabel("<b>Build Console</b>"))
        self.chip = QWidget()
        chip_layout = QHBoxLayout(self.chip)
        chip_layout.setContentsMargins(6, 0, 2, 0)
        self.chip_label = QLabel("")
        chip_layout.addWidget(self.chip_label)
        self.chip_clear_btn = QToolButton()
        self.chip_clear_btn.setText("✕")
        self.chip_clear_btn.setAutoRaise(True)
        self.chip_clear_btn.setToolTip("Show every tile's lines")
        self.chip_clear_btn.clicked.connect(self._clear_chip)
        chip_layout.addWidget(self.chip_clear_btn)
        self.chip.setVisible(False)
        header.addWidget(self.chip)
        header.addStretch(1)
        self.saved_logs_btn = QToolButton()
        self.saved_logs_btn.setText("Saved logs")
        self.saved_logs_btn.setPopupMode(QToolButton.InstantPopup)
        self.saved_logs_menu = QMenu(self.saved_logs_btn)
        self.saved_logs_btn.setMenu(self.saved_logs_menu)
        self.saved_logs_menu.aboutToShow.connect(self._fill_saved_logs)
        header.addWidget(self.saved_logs_btn)
        self.history_btn = QToolButton()
        self.history_btn.setText("History")
        self.history_btn.setCheckable(True)
        self.history_btn.setToolTip("Show build history")
        self.history_btn.toggled.connect(self._toggle_history)
        header.addWidget(self.history_btn)
        self.console_clear_btn = QToolButton()
        self.console_clear_btn.setText("Clear")
        self.console_clear_btn.setToolTip(
            "Clear the console (saved logs are kept)")
        self.console_clear_btn.clicked.connect(self.clear)
        header.addWidget(self.console_clear_btn)
        outer.addLayout(header)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        body.addWidget(console, 1)
        self.history = BuildHistoryPanel()
        self.history.setVisible(False)
        self.history.tile_clicked.connect(self._select_tile)
        self.history.range_changed.connect(lambda _key: self.refresh_history())
        body.addWidget(self.history)
        outer.addLayout(body, 1)
        self._sync_saved_logs_button()

    # -- the live stream ---------------------------------------------------

    def append_text(self, text):
        """A chunk of console output: shown as it comes when nothing is
        filtered, else only the finished lines the filter shows."""
        filtered = self.lines.filtered
        added = self.lines.add_text(text)
        if not filtered:
            self._insert(text)
            return
        shown = [line for tile, line in added if self.lines.shows(tile)]
        if shown:
            self._insert("\n".join(shown) + "\n")

    def clear(self):
        self.lines.clear()
        self.console.clear()
        self.sync(force=True)

    # -- selection, chip and saved logs ------------------------------------

    def set_selection(self, tiles, active):
        tiles = sorted(tuple(t) for t in tiles)
        if tiles != self._selection:
            self._dismissed = False
            self._chosen = None
        self._selection = tiles
        self._active = tuple(active) if active else None
        self.sync()
        self._sync_saved_logs_button()

    def filter_tiles(self):
        return [] if self._dismissed else list(self._selection)

    def saved_logs(self, tile):
        info = self._built().get(tuple(tile)) if tile else None
        if info is None:
            return []
        return TILELOG.read_records(info.build_dir, *tile)

    def choose_log(self, tile, name):
        """Show one saved log alone (``None`` returns to the live view)."""
        self._chosen = (FNAMES.short_latlon(*tile), name) if name else None
        self.sync()

    def sync(self, force=False):
        built = self._built()
        if self._chosen is not None:
            key, name = self._chosen
            tile = FNAMES.parse_tile_key(key)
            info = built.get(tile)
            record = next((r for r in self.saved_logs(tile)
                           if r.get("log") == name), None)
            text = TILELOG.read_log(info.build_dir, name) if info else ""
            saved = [saved_log_header(key, record)] + text.splitlines()
            self._apply(frozenset([key]), saved, False, force)
            self._show_chip("Saved log of %s" % key)
            return
        tiles = self.filter_tiles()
        saved = []
        for tile in tiles:
            key = FNAMES.short_latlon(*tile)
            info = built.get(tile)
            if info is None or self.lines.has_live_lines(key):
                continue
            record = TILELOG.last_build(info.build_dir, *tile)
            if record is None:
                saved.append("=== %s: %s ===" % (key, NOT_SAVED))
                continue
            saved.append(saved_log_header(key, record))
            saved += TILELOG.read_log(info.build_dir,
                                      record["log"]).splitlines()
        keys = [FNAMES.short_latlon(*t) for t in tiles]
        self._apply(frozenset(keys), saved, True, force)
        if keys:
            self._show_chip("Showing %s%s" % (", ".join(keys[:4]),
                                              " …" if len(keys) > 4 else ""))
        else:
            self.chip.setVisible(False)

    def _apply(self, tiles, saved, live, force):
        if self.lines.set_view(tiles, saved, live) or force:
            self.console.setPlainText(self.lines.visible_text())
            self.console.moveCursor(QTextCursor.End)

    def _show_chip(self, text):
        self.chip_label.setText(text)
        self.chip.setVisible(True)

    def _clear_chip(self):
        if self._chosen is not None:
            self._chosen = None
        else:
            self._dismissed = True
        self.sync()

    def _sync_saved_logs_button(self):
        records = self.saved_logs(self._active)
        self.saved_logs_btn.setEnabled(bool(records) or bool(self._chosen))
        self.saved_logs_btn.setToolTip(
            "Show one of the selected tile's last %d build logs" % len(records)
            if records else "The selected tile has no saved build log")

    def _fill_saved_logs(self):
        menu = self.saved_logs_menu
        menu.clear()
        if self._chosen is not None:
            menu.addAction("Live console", lambda: self.choose_log(None, None))
            menu.addSeparator()
        active = self._active
        for record in self.saved_logs(active):
            title = "%s — %s" % (_when(record.get("end")),
                                 outcome_text(record))
            menu.addAction(title, lambda name=record["log"]:
                           self.choose_log(active, name))

    # -- history -----------------------------------------------------------

    def _toggle_history(self, shown):
        self.history.setVisible(shown)
        self.history_btn.setToolTip(
            "Hide build history" if shown else "Show build history")
        if shown:
            self.refresh_history()

    def refresh_history(self):
        """Rebuild the list and the map's dimming from the scan."""
        built = self._built()
        key = self.history.range_key()
        self._dim(dimmed_tiles(built, key))
        if not self.history.isHidden():
            self.history.set_rows(history_rows(built, key), bool(built))
        self._sync_saved_logs_button()

    def _insert(self, text):
        self.console.moveCursor(QTextCursor.End)
        self.console.insertPlainText(text)
        self.console.moveCursor(QTextCursor.End)
