"""Main window of the Ortho4XP Qt UI (map-first shell).

Layout: toolbar (search, imagery, build ZL) / live map / context panel on the
right / collapsible console drawer below / status bar.

The build pipeline is untouched: this window talks to it exactly the way the
legacy Tk GUI does — a worker thread runs the step functions, progress arrives
via UI.progress_bar (adapted to Qt signals), cancellation via UI.red_flag,
console output via a stdout tee.
"""

import json
import math
import os
import queue
import sys
import threading
import time
import traceback

from PySide6.QtCore import (
    QByteArray,
    QEvent,
    QObject,
    QPointF,
    QRectF,
    QSize,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import (
    QAction,
    QColor,
    QIcon,
    QKeySequence,
    QPainter,
    QPainterPath,
    QPixmap,
    QTextCursor,
)
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStatusBar,
    QStyle,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

import O4_File_Names as FNAMES
import O4_Imagery_Utils as IMG
import O4_UI_Utils as UI
import O4_Version
import O4_Airport_Index as APT
import O4_Scenery_Links as LINKS
import O4_Tile_Info as TINFO
import O4_Qt_Map as QTMAP
from o4_engine import EngineSession
from o4_engine import events as EV
import O4_Qt_Settings as QTSET
import O4_Qt_Wizard as QTWIZ

PREFS_FILE = FNAMES.data_path(".qt_prefs.json")
AIRPORT_CACHE = FNAMES.airport_index_cache()
MAX_CONSOLE_LINES = 5000

# Prefs keys for the restored tile selection (docs/specs/qt-parity-
# selection-stop-resume-spec.md §Q1).  The selected set is a list of
# canonical tile keys, the active tile one key ("" = none); both live in
# the same .qt_prefs.json the window geometry does — one store, not two.
SELECTED_TILES_KEY = "selected_tiles"
ACTIVE_TILE_KEY = "active_tile"

# Point size of the per-tile stop / resume glyphs on the Activity rows.
# Shared, so the button never changes size when a row flips between
# them, and big enough to read AS a stop sign (owner, on 1.0.238).
STOP_ICON_PT = 16
STOP_SIGN_COLOR = "#E5372B"
RESUME_COLOR = "#2E9E5B"
STOPPED_COLOR = QTMAP.STOPPED_COLOR

# Build-area texture-mode selector: user-visible label -> tile config value.
# Order is significant (it is the popup-menu item order).
TEXTURE_MODE_CHOICES = (
    ("Full Ortho", "full_ortho"),
    ("Airport Ortho", "airport_ortho"),
    ("Default X-Plane", "default_xplane"),
)

# Build-area elevation-detail selector: user-visible label -> tile config
# value (the elevation analogue of the imagery zoom level; see
# docs/specs/elevation-level-spec.md).  Order is the popup-menu order.
ELEVATION_LEVEL_CHOICES = (
    ("Auto", "auto"),
    ("Auto + coastline", "coastline"),
    ("90 m", "90"),
    ("30 m", "30"),
    ("10 m", "10"),
    ("5 m", "5"),
    ("1 m", "1"),
)

ELEVATION_LEVEL_TOOLTIP = (
    "Tile-wide elevation detail level.\n"
    "Auto: 90 m base data (small downloads) plus meter-class lidar at\n"
    "airports, where the detail is actually visible (standard).\n"
    "Auto + coastline: additionally drapes a lidar band along shorelines,\n"
    "graded by approach visibility — about 10 m detail within 20 km of an\n"
    "airport, 20 m out to 50 km, 30 m beyond.\n"
    "90 m pins the automatic base class explicitly. 30 m and finer\n"
    "restore the 1 arc-second base class and fetch the finest wide-area\n"
    "elevation source covering the whole tile, densifying the mesh grid\n"
    "to match. Levels never coarsen the automatic choice and cap\n"
    "themselves to the finest source actually available. Higher levels\n"
    "mean substantially larger downloads, working files, memory use and\n"
    "triangle counts."
)

# Popup choices for the per-tile ``airport_elevation_level`` config value
# (the warp/storage resolution of the airport lidar insets).  Order is
# the popup-menu order.
AIRPORT_ELEVATION_LEVEL_CHOICES = (
    ("Auto", "auto"),
    ("0.5 m", "0.5"),
    ("1 m", "1"),
    ("5 m", "5"),
    ("10 m", "10"),
    ("30 m", "30"),
)

AIRPORT_ELEVATION_LEVEL_TOOLTIP = (
    "Airport elevation detail level — the resolution the airport lidar\n"
    "insets are warped to and stored at.\n"
    "Auto: each provider's best available native resolution, never finer\n"
    "than 0.5 m (standard).\n"
    "A numeric level pins the warp target instead: coarser stores fewer\n"
    "bytes and warps faster; finer only helps where a provider actually\n"
    "publishes data that fine. Cached insets fetched at an earlier level\n"
    "are recycled as-is until refreshed."
)


def load_prefs():
    try:
        with open(PREFS_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def save_prefs(prefs):
    try:
        with open(PREFS_FILE, "w") as f:
            json.dump(prefs, f, indent=2)
    except Exception:
        pass


def _glyph_pixmap(size):
    """A transparent square pixmap at the screen's device pixel ratio.

    The painter that follows still works in logical points; only the
    backing store is denser, which is what keeps a hand-painted glyph
    crisp on a HiDPI display instead of being upscaled from 16 pixels.
    """
    app = QApplication.instance()
    ratio = float(app.devicePixelRatio()) if app is not None else 1.0
    pixmap = QPixmap(max(1, int(round(size * ratio))),
                     max(1, int(round(size * ratio))))
    pixmap.setDevicePixelRatio(ratio)
    pixmap.fill(Qt.transparent)
    return pixmap


def stop_sign_icon(size=STOP_ICON_PT):
    """The per-tile stop button: a red stop-sign octagon with a centred
    white square.

    Painted rather than taken from the platform style: the standard close
    icon reads as "dismiss this row", and what the button does is stop a
    tile.  The white square is drawn about the octagon's own centre, so
    it is centred by construction — there is no glyph padding to tune
    around, which is what pushed the mac app's first attempt off-centre.
    """
    pixmap = _glyph_pixmap(size)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    center = size / 2.0
    radius = center - 0.5  # half a point of room for the antialiased edge
    path = QPainterPath()
    for index in range(8):
        # The 22.5° offset puts a flat edge on top: the road sign, not a
        # diamond standing on one of its vertices.
        angle = math.radians(22.5 + 45 * index)
        point = QPointF(center + radius * math.cos(angle),
                        center + radius * math.sin(angle))
        if index:
            path.lineTo(point)
        else:
            path.moveTo(point)
    path.closeSubpath()
    painter.fillPath(path, QColor(STOP_SIGN_COLOR))
    side = size * 0.38
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor("#FFFFFF"))
    painter.drawRoundedRect(
        QRectF(center - side / 2, center - side / 2, side, side), 0.75, 0.75
    )
    painter.end()
    return QIcon(pixmap)


def resume_icon(size=STOP_ICON_PT):
    """A stopped row's button: the standard play triangle, in white on a
    green disc, painted at the same size as the stop sign it replaces."""
    pixmap = _glyph_pixmap(size)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(RESUME_COLOR))
    painter.drawEllipse(QRectF(0.5, 0.5, size - 1, size - 1))
    # The triangle sits a touch right of the disc's centre: a play
    # triangle centred on its bounding box reads as left-heavy.
    triangle = QPainterPath()
    triangle.moveTo(QPointF(size * 0.38, size * 0.27))
    triangle.lineTo(QPointF(size * 0.38, size * 0.73))
    triangle.lineTo(QPointF(size * 0.75, size * 0.50))
    triangle.closeSubpath()
    painter.fillPath(triangle, QColor("#FFFFFF"))
    painter.end()
    return QIcon(pixmap)


# ---------------------------------------------------------------------------
# Stop/resume rules (pure — no widgets, no engine)
# ---------------------------------------------------------------------------
def may_overwrite_stopped(state):
    """May an incoming engine state overwrite a row the user STOPPED?

    Only a terminal outcome: a tile that finished before its cancel took
    effect is genuinely built, and saying "stopped" over a built tile
    would be a lie; a failure is just as real.  Everything else is stale
    news from a run the row has already left — the engine goes on sending
    progress (and its own "stopped" notice) until it reaches the phase
    boundary where it notices the cancel flag.
    """
    return state in ("done", "error")


def resolve_tile_state(incoming, current):
    """The row an engine event should leave behind, given what the row
    already shows.  None = the event is stale, drop it."""
    if current is not None and current[0] == "stopped":
        if not may_overwrite_stopped(incoming[0]):
            return None
    return incoming


def enqueue_resume(tile, queue):
    """Ordered, deduped append to the pending-resume queue."""
    return list(queue) if tile in queue else list(queue) + [tile]


class _StdoutTee:
    """Duplicates pipeline stdout into a queue for the console drawer."""

    def __init__(self, original, line_queue):
        self._original = original
        self._queue = line_queue

    def write(self, text):
        try:
            self._original.write(text)
        except Exception:
            pass
        self._queue.put(text)

    def flush(self):
        try:
            self._original.flush()
        except Exception:
            pass


class TwoLineElidedLabel(QLabel):
    """Value label capped at two wrapped lines.

    Text that would need a third line is elided in the MIDDLE so both
    the head and the tail stay readable (elevation source lists carry
    their most specific parts at both ends); the full text moves to the
    tooltip.  The horizontal size policy is Ignored so a long value can
    never widen its panel — extra length costs ellipsis, not width.
    The height is FIXED at two lines: layouts would otherwise grant
    only the one-line minimum (clipping the second line away), and a
    height that depended on width would feed the scroll-area relayout
    loop — width flips the vertical scrollbar, which changes width —
    that oscillates until the stack overflows.
    """

    def __init__(self, text="", parent=None):
        super().__init__(parent)
        self.setWordWrap(True)
        policy = self.sizePolicy()
        policy.setHorizontalPolicy(QSizePolicy.Ignored)
        self.setSizePolicy(policy)
        self._reserve_two_lines()
        self._full_text = ""
        self.setText(text)

    def setText(self, text):
        self._full_text = str(text)
        self._refresh_elision()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._refresh_elision()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.FontChange:
            self._reserve_two_lines()
            self._refresh_elision()

    def _reserve_two_lines(self):
        margins = self.contentsMargins()
        self.setFixedHeight(
            2 * self.fontMetrics().lineSpacing() + 2
            + margins.top() + margins.bottom()
        )

    def _fits_two_lines(self, candidate, width):
        rect = self.fontMetrics().boundingRect(
            0, 0, width, 100000, Qt.TextWordWrap, candidate
        )
        return rect.height() <= 2 * self.fontMetrics().lineSpacing() + 2

    def _refresh_elision(self):
        width = max(self.contentsRect().width(), 10)
        text = self._full_text
        if self._fits_two_lines(text, width):
            display = text
        else:
            # Largest kept-character count whose head…tail split fits.
            low, high = 0, len(text)
            while low < high:
                mid = (low + high + 1) // 2
                head = text[: (mid + 1) // 2]
                tail = text[len(text) - mid // 2 :]
                if self._fits_two_lines(head + "…" + tail, width):
                    low = mid
                else:
                    high = mid - 1
            head = text[: (low + 1) // 2]
            tail = text[len(text) - low // 2 :] if low else ""
            display = head + "…" + tail
        if display != super().text():
            super().setText(display)
        self.setToolTip(self._full_text if display != self._full_text else "")


class _EngineBridge(QObject):
    """Marshals engine-session events onto the GUI thread.

    The session invokes subscriber callbacks on its worker threads;
    cross-thread Signal emission is the one supported hand-off (QTimer
    from a plain worker thread silently never fires)."""

    event = Signal(object)
    size_computed = Signal()
    # (tile, [modified_packs entry, ...]) from a worker probe of the
    # reanchor provenance sidecars in Custom Scenery.
    reanchor_ready = Signal(object)


def gui_provider_codes():
    codes = sorted(
        code
        for code in set(IMG.providers_dict)
        if IMG.providers_dict[code].get("in_GUI")
    )
    codes += sorted(set(IMG.combined_providers_dict))
    return [c for c in codes if c not in ("SEA",)]


def _sync_combo_to_agreed_value(combo, configured_values):
    """Select the single agreed value, or unresolve the combo to "--".

    No configured values: the combo keeps its current choice.  Exactly one
    value that the combo offers: select it.  Anything else — the tiles
    disagree, or their agreed value is not offered by this combo — sets
    ``currentIndex(-1)`` so the "--" placeholder shows and the build guard
    in :meth:`MainWindow.start_build` trips until the user picks a value.
    """
    if not configured_values:
        return
    index = -1
    if len(configured_values) == 1:
        index = combo.findText(next(iter(configured_values)))
    if index != combo.currentIndex():
        combo.setCurrentIndex(index)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Ortho4XP " + O4_Version.version)
        self.resize(1180, 780)

        self.prefs = load_prefs()
        self._first_run = not os.path.isfile(PREFS_FILE)
        self._airports = []
        self._built = {}
        self._installed = set()
        # True while a scenery scan is streaming results in: a tile
        # absent from _built is then merely "not scanned yet", not
        # known-unbuilt, and the info panel says so.  Starts True —
        # the startup scan is already scheduled, so nothing is known
        # until it reports.
        self._scanning = True
        self._progress_states = {}
        self._building = False
        self._stop_requested = False
        # Tiles the user resumed while a run was still going, in press
        # order: they start as ONE follow-up run when the current one
        # ends.  Purely client-side and session-local — the engine knows
        # nothing about this queue.
        self._resume_queue = []
        # What each tile of the current run was STARTED with — the resume
        # path's settings source, so resuming a tile rebuilds it as it was
        # queued and not with whatever the toolbar says now.
        self._run_settings = {}
        # Last (output dir, selection) the toolbar combos were synced to:
        # _sync_build_controls_to_selection runs once per selection so
        # panel refreshes never clobber a user-picked imagery source/ZL.
        self._combos_synced_to = None

        # --- pipeline adapters -----------------------------------------
        UI.verbosity = int(self.prefs.get("verbosity", 1))
        # Console feed: pipeline prints (worker threads included) are teed
        # into a queue and drained onto the console drawer by a GUI-thread
        # timer.  This stays view-side plumbing even under the engine
        # session — stdout is process-global, and the JSON-lines transport
        # has its own stdout discipline instead.
        self._console_queue = queue.Queue()
        sys.stdout = _StdoutTee(sys.stdout, self._console_queue)
        self._console_timer = QTimer(self)
        self._console_timer.setInterval(120)
        self._console_timer.timeout.connect(self._drain_console)
        self._console_timer.start()
        self._session = EngineSession()
        self._bridge = _EngineBridge()
        self._bridge.event.connect(self._on_engine_event)
        self._bridge.reanchor_ready.connect(self._on_reanchor_ready)
        self._session.subscribe(self._bridge.event.emit)
        self._event_handlers = {
            EV.ScanProgress: self._on_scan_progress,
            EV.ScanBatch: self._on_scan_batch,
            EV.ScanDone: self._on_scan_done,
            EV.StepProgress: self._on_step_progress,
            EV.TileState: self._on_tile_state,
            EV.RunEta: self._on_run_eta,
            EV.TileClocks: self._on_tile_clocks,
            EV.BuildDone: self._on_build_done,
            EV.RunDone: self._on_run_done,
        }
        self._scan_built = {}
        self._scan_installed = set()
        self._last_run_eta = None
        # (lat,lon) -> (elapsed_seconds, remaining_seconds|None, finished)
        # from the engine's TileClocks rows (protocol 1.3); rendered by
        # the same 1 Hz clock tick as the run totals.
        self._tile_clocks = {}
        self._build_t0 = None
        # Per-tile timing/outcome for the end-of-run console report:
        # started_at is stamped by the tile's FIRST progress event (queue
        # wait never counts as build time), results by its BuildDone.
        self._tile_started_at = {}
        self._tile_results = {}
        self._done_count = 0
        self._ntiles = 0

        self._make_widgets()
        self._make_menus()
        self._apply_prefs(initial=True)

        # Persisted window layout: geometry (size + position), console
        # drawer visibility and splitter split, remembered across
        # launches in the prefs file.
        self._layout_restored = False
        self._console_defaulted = False
        self._console_height = 0  # remembered while the drawer is hidden
        geometry_b64 = str(self.prefs.get("window_geometry", ""))
        if geometry_b64:
            self.restoreGeometry(
                QByteArray.fromBase64(geometry_b64.encode("ascii"))
            )
        self.console.setVisible(
            bool(self.prefs.get("console_visible", True))
        )
        splitter_b64 = str(self.prefs.get("splitter_state", ""))
        if splitter_b64:
            self._layout_restored = bool(
                self.splitter.restoreState(
                    QByteArray.fromBase64(splitter_b64.encode("ascii"))
                )
            )

        if self._first_run:
            QTimer.singleShot(200, self.run_wizard)
        QTimer.singleShot(300, self.refresh_tiles)
        QTimer.singleShot(400, self._load_airports_async)

        # OSM regional extracts: keep stored region extracts fresh and
        # download newly wanted ones in the background (docs/specs/
        # osm-regional-extracts-spec.md).  Application process only —
        # parallel-build worker children merely record wants.
        try:
            import O4_OSM_Extracts as EXTRACTS

            EXTRACTS.start_background_maintenance()
        except Exception:
            pass

        # The selection outlives the app: last session's selected set and
        # its active tile come back on launch, the same doctrine as the
        # built-tile overlay.  Restored LAST, so the map, the info panel
        # and the toolbar combos see it exactly the way they see a click.
        selection, active = self._restore_selection()
        lat = int(self.prefs.get("last_lat", 48))
        lon = int(self.prefs.get("last_lon", -6))
        if active is not None:
            lat, lon = active
        self.map.center_on_tile(lat, lon, zoom=7)
        if selection:
            self.map.set_selection(selection)
            self.map.set_active(active[0], active[1], select=False)
        else:
            # Nothing stored (or nothing that still parses): exactly the
            # launch this window has always had.
            self.map.set_active(lat, lon)

    # ------------------------------------------------------------------
    # Widgets
    # ------------------------------------------------------------------
    def _make_widgets(self):
        toolbar = QToolBar()
        toolbar.setMovable(False)
        # Breathing room: keep controls off the window edges and apart.
        toolbar.setStyleSheet(
            "QToolBar { padding: 6px 10px; spacing: 6px; }"
        )
        self.addToolBar(toolbar)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText(
            "Search airport, city, country — or tile like +48-006"
        )
        self.search_edit.setFixedWidth(320)
        self.search_edit.textEdited.connect(self._update_search_popup)
        self.search_edit.returnPressed.connect(self._search_accept_first)
        toolbar.addWidget(self.search_edit)
        self.search_popup = QListWidget(self)
        self.search_popup.setWindowFlags(Qt.ToolTip)
        self.search_popup.itemClicked.connect(self._search_accept_item)

        toolbar.addSeparator()
        toolbar.addWidget(QLabel(" Imagery "))
        self.imagery_combo = QComboBox()
        self.imagery_combo.addItems(gui_provider_codes())
        # "--" shows when the selected tiles' configs disagree
        # (currentIndex -1); start_build refuses to run until resolved.
        self.imagery_combo.setPlaceholderText("--")
        self.imagery_combo.currentTextChanged.connect(self._imagery_changed)
        toolbar.addWidget(self.imagery_combo)
        toolbar.addWidget(QLabel(" Build ZL "))
        self.zl_combo = QComboBox()
        self.zl_combo.addItems([str(z) for z in range(12, 22)])
        self.zl_combo.setPlaceholderText("--")
        self.zl_combo.currentTextChanged.connect(
            lambda _text: self._update_build_summary()
        )
        toolbar.addWidget(self.zl_combo)
        toolbar.addSeparator()
        self.zones_btn = QPushButton("✏ Zones")
        self.zones_btn.setEnabled(False)
        self.zones_btn.setToolTip(
            "Zone editing arrives in the next iteration — "
            "use the legacy UI (Ortho4XP.py) for zones meanwhile."
        )
        toolbar.addWidget(self.zones_btn)
        spacer = QWidget()
        spacer.setSizePolicy(spacer.sizePolicy().horizontalPolicy().Expanding,
                             spacer.sizePolicy().verticalPolicy().Preferred)
        toolbar.addWidget(spacer)
        settings_btn = QPushButton("⚙ Settings")
        settings_btn.clicked.connect(self.open_settings)
        toolbar.addWidget(settings_btn)

        # Map + right panel
        self.map = QTMAP.MapView()
        self.map.selection_changed.connect(self._selection_changed)
        self.map.active_changed.connect(self._active_changed)
        self.map.hover_ll.connect(self._hover)
        self.map.status_message.connect(self._status)

        panel = QWidget()
        pv = QVBoxLayout(panel)
        pv.setContentsMargins(10, 10, 10, 10)

        self.info_group = QGroupBox("Selection")
        ig = QFormLayout(self.info_group)
        # macOS's native form style is FieldsStayAtSizeHint, which
        # gives the Ignored-policy elided labels ZERO width (their size
        # hint is meaningless by design) — the values simply vanish.
        ig.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        self.info_title = QLabel("—")
        ig.addRow(self.info_title)
        self.info_provider = QLabel("—")
        ig.addRow("Imagery:", self.info_provider)
        self.info_zl = QLabel("—")
        ig.addRow("Zoom level:", self.info_zl)
        self.info_mesh = QLabel("—")
        ig.addRow("Mesh built:", self.info_mesh)
        self.info_imagery = QLabel("—")
        ig.addRow("Imagery updated:", self.info_imagery)
        self.info_elevation = TwoLineElidedLabel("—")
        ig.addRow("Elevation:", self.info_elevation)
        self.info_airport_lidar = TwoLineElidedLabel("—")
        ig.addRow("Airport lidar:", self.info_airport_lidar)
        # Manual-setup affordance (VIEW): shown by the controller when
        # the model reports manual-download sources that could serve
        # the active tile but are not set up yet.
        self.manual_elevation_btn = QPushButton(
            "ⓘ Better elevation data available…"
        )
        self.manual_elevation_btn.setFlat(True)
        self.manual_elevation_btn.setStyleSheet(
            "QPushButton { text-align: left; color: palette(link); }"
        )
        self.manual_elevation_btn.clicked.connect(
            self._show_manual_elevation_dialog
        )
        self.manual_elevation_btn.setVisible(False)
        ig.addRow(self.manual_elevation_btn)
        self._manual_elevation_entries = []
        self.info_size = QLabel("—")
        ig.addRow("Size on disk:", self.info_size)
        # Custom airport packages whose 3-D objects the auto-patch
        # reseater modified for this tile (reanchor provenance sidecars):
        # one label, one row per pack, each with a small undo button
        # reverting that pack to the authors' original files (the
        # .anchor_bak backups the reseater keeps).
        self.modified_airports_row = QWidget()
        self._modified_airport_rows = QVBoxLayout(self.modified_airports_row)
        self._modified_airport_rows.setContentsMargins(0, 0, 0, 0)
        self._modified_airport_rows.setSpacing(2)
        ig.addRow("Modified airports:", self.modified_airports_row)
        self._info_layout = ig
        self._info_layout.setRowVisible(self.modified_airports_row, False)
        self._modified_airport_packs = []
        self.install_check = QCheckBox("Installed in X-Plane")
        self.install_check.clicked.connect(self._toggle_install)
        ig.addRow(self.install_check)
        pv.addWidget(self.info_group)

        # The Build box always shows the options: builds no longer take
        # the panel over (progress lives in the Activity box below), so
        # more tiles can be selected and queued while a run is going.
        build_group = QGroupBox("Build")
        bg = QVBoxLayout(build_group)
        # Two-line elided: the dynamic summary ("N tiles selected ·
        # rough est. …") must never widen the fixed-width panel into
        # clipping, and plain word wrap here would tie its height to
        # its width — the scroll-area oscillation the class avoids.
        self.build_summary = TwoLineElidedLabel("No tiles selected")
        bg.addWidget(self.build_summary)
        self.chk_vector = QCheckBox("Vector, mesh && masks")
        self.chk_vector.setChecked(True)
        self.chk_imagery = QCheckBox("Imagery && DSF")
        self.chk_imagery.setChecked(True)
        self.chk_overlays = QCheckBox("Extract overlays")
        self.chk_skip_built = QCheckBox("Skip already-built tiles")
        self.chk_skip_built.setChecked(True)
        # Global engine gate (cfg var modify_custom_airports): whether the
        # auto-patch pass may reseat 3-D objects of installed custom
        # airport packs onto the rebuilt ground.
        import O4_Config_Utils as CFG

        self.chk_modify_airports = QCheckBox("Modify custom airports")
        self.chk_modify_airports.setChecked(
            bool(getattr(CFG, "modify_custom_airports", True))
        )
        self.chk_modify_airports.setToolTip(
            "Reseats the 3-D objects of custom airport packages in Custom "
            "Scenery at the new ground elevation this build produces "
            "(edited in place, originals kept as .anchor_bak backups).\n"
            "Unchecked, installed packages are left byte-identical — "
            "objects at reprofiled airports may float or sink."
        )
        self.chk_modify_airports.toggled.connect(
            self._modify_custom_airports_changed
        )
        for c in (
            self.chk_vector,
            self.chk_imagery,
            self.chk_overlays,
            self.chk_skip_built,
            self.chk_modify_airports,
        ):
            bg.addWidget(c)

        # Texture mode: what the base mesh is textured with (per-tile config).
        self.texture_row = QWidget()
        trl = QHBoxLayout(self.texture_row)
        trl.setContentsMargins(0, 0, 0, 0)
        self.texture_label = QLabel("Textures:")
        trl.addWidget(self.texture_label)
        self.texture_combo = QComboBox()
        for label, value in TEXTURE_MODE_CHOICES:
            self.texture_combo.addItem(label, value)
        self.texture_combo.currentIndexChanged.connect(
            self._texture_mode_changed
        )
        trl.addWidget(self.texture_combo, 1)
        bg.addWidget(self.texture_row)

        # Tile elevation detail level: how fine the tile-wide terrain
        # data is (per-tile config), mirroring the texture-mode row above.
        self.elevation_row = QWidget()
        erl = QHBoxLayout(self.elevation_row)
        erl.setContentsMargins(0, 0, 0, 0)
        self.elevation_label = QLabel("Tile elevation:")
        erl.addWidget(self.elevation_label)
        self.elevation_combo = QComboBox()
        for label, value in ELEVATION_LEVEL_CHOICES:
            self.elevation_combo.addItem(label, value)
        self.elevation_combo.setToolTip(ELEVATION_LEVEL_TOOLTIP)
        self.elevation_combo.currentIndexChanged.connect(
            self._elevation_level_changed
        )
        erl.addWidget(self.elevation_combo, 1)
        bg.addWidget(self.elevation_row)

        # Airport elevation detail level: the warp/storage resolution of
        # the airport lidar insets (per-tile config), the airport sibling
        # of the tile-wide row above.
        self.airport_elevation_row = QWidget()
        arl = QHBoxLayout(self.airport_elevation_row)
        arl.setContentsMargins(0, 0, 0, 0)
        self.airport_elevation_label = QLabel("Airport elevation:")
        arl.addWidget(self.airport_elevation_label)
        self.airport_elevation_combo = QComboBox()
        for label, value in AIRPORT_ELEVATION_LEVEL_CHOICES:
            self.airport_elevation_combo.addItem(label, value)
        self.airport_elevation_combo.setToolTip(
            AIRPORT_ELEVATION_LEVEL_TOOLTIP
        )
        self.airport_elevation_combo.currentIndexChanged.connect(
            self._airport_elevation_level_changed
        )
        arl.addWidget(self.airport_elevation_combo, 1)
        bg.addWidget(self.airport_elevation_row)

        self.build_btn = QPushButton("▶ Build")
        self.build_btn.clicked.connect(self.start_build)
        bg.addWidget(self.build_btn)

        # Activity box — live per-tile progress of the run in progress.
        # Hidden while idle; a running build shows it WITHOUT hiding the
        # Build box, so further batches can be queued into the run.
        self.activity_group = QGroupBox("Activity")
        pg = QVBoxLayout(self.activity_group)
        self.progress_title = QLabel("")
        # Ignored: the title is rich text (no elision support), so it
        # clips rather than ever widening the fixed-width panel.
        title_policy = self.progress_title.sizePolicy()
        title_policy.setHorizontalPolicy(QSizePolicy.Ignored)
        self.progress_title.setSizePolicy(title_policy)
        pg.addWidget(self.progress_title)
        rows_scroll = QScrollArea()
        rows_scroll.setWidgetResizable(True)
        rows_host = QWidget()
        self._rows_layout = QVBoxLayout(rows_host)
        self._rows_layout.setContentsMargins(0, 2, 0, 2)
        self._rows_layout.setSpacing(6)
        self._rows_layout.addStretch(1)
        rows_scroll.setWidget(rows_host)
        pg.addWidget(rows_scroll, 1)
        self.elapsed_label = QLabel("Elapsed —")
        pg.addWidget(self.elapsed_label)
        self.eta_label = QLabel("Remaining —")
        pg.addWidget(self.eta_label)
        self.stop_btn = QPushButton("■ Stop")
        self.stop_btn.clicked.connect(self.request_stop)
        pg.addWidget(self.stop_btn)
        self.activity_group.setVisible(False)

        pv.addWidget(build_group)
        # While visible, the Activity box absorbs ALL free panel height
        # (its rows scroll internally).  The trailing spacer keeps the
        # boxes top-aligned while it is hidden — and is zeroed while it
        # shows (_set_activity_box_visible), otherwise the spacer keeps
        # its share and the box stops growing with the window.
        pv.addWidget(self.activity_group, 1)
        pv.addStretch(1)
        self._panel_layout = pv
        self._panel_spacer_index = pv.count() - 1
        self._tile_rows = {}
        self._elapsed_timer = QTimer(self)
        self._elapsed_timer.setInterval(1000)
        self._elapsed_timer.timeout.connect(self._update_build_clock)

        # The panel scrolls vertically instead of imposing its full
        # height on the window: without this its minimum propagates into
        # the splitter, where it silently squeezes the console drawer
        # whenever the panel content grows (e.g. the build progress
        # page) — the "console resizes by itself" jump.
        panel_scroll = QScrollArea()
        panel_scroll.setWidget(panel)
        panel_scroll.setWidgetResizable(True)
        panel_scroll.setFrameShape(QFrame.NoFrame)
        panel_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        panel_scroll.setFixedWidth(280)

        center = QWidget()
        ch = QHBoxLayout(center)
        ch.setContentsMargins(0, 0, 0, 0)
        ch.setSpacing(0)
        ch.addWidget(self.map, 1)
        ch.addWidget(panel_scroll)

        # Console drawer
        self.console = QPlainTextEdit()
        self.console.setReadOnly(True)
        self.console.setMaximumBlockCount(MAX_CONSOLE_LINES)
        font = self.console.font()
        font.setFamily("Menlo" if sys.platform == "darwin" else "Monospace")
        font.setPointSize(11)
        self.console.setFont(font)

        self.splitter = QSplitter(Qt.Vertical)
        self.splitter.addWidget(center)
        self.splitter.addWidget(self.console)
        # The console drawer keeps ITS height when the window resizes
        # (stretch 0: all growth goes to the map) and cannot be dragged
        # to zero — it only changes size at the user's splitter handle,
        # never by itself.
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 0)
        self.splitter.setCollapsible(1, False)
        self.setCentralWidget(self.splitter)

        status = QStatusBar()
        self.setStatusBar(status)
        self.coords_label = QLabel("—")
        status.addWidget(self.coords_label)
        self.zoom_label = QLabel("")
        status.addWidget(self.zoom_label)
        self.selection_label = QLabel("")
        status.addPermanentWidget(self.selection_label)
        self.console_btn = QPushButton("Console ▾")
        self.console_btn.setFlat(True)
        self.console_btn.clicked.connect(self.toggle_console)
        status.addPermanentWidget(self.console_btn)
        self.map.view_changed.connect(self._update_zoom_label)

    def _make_menus(self):
        file_menu = self.menuBar().addMenu("&File")
        settings_action = QAction("Settings…", self)
        settings_action.setShortcut(QKeySequence.Preferences)
        settings_action.triggered.connect(self.open_settings)
        file_menu.addAction(settings_action)
        quit_action = QAction("Quit", self)
        quit_action.setShortcut(QKeySequence.Quit)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        view_menu = self.menuBar().addMenu("&View")
        refresh_action = QAction("Refresh tiles", self)
        refresh_action.setShortcut(QKeySequence.Refresh)
        refresh_action.triggered.connect(self.refresh_tiles)
        view_menu.addAction(refresh_action)
        console_action = QAction("Toggle console", self)
        console_action.triggered.connect(self.toggle_console)
        view_menu.addAction(console_action)

        tools_menu = self.menuBar().addMenu("&Tools")
        overlay_action = QAction("Link overlays folder in X-Plane", self)
        overlay_action.triggered.connect(self._toggle_overlay_link)
        tools_menu.addAction(overlay_action)
        coral_atlas_action = QAction("Allen Coral Atlas reef bathymetry…", self)
        coral_atlas_action.triggered.connect(self.open_coral_atlas_dialog)
        tools_menu.addAction(coral_atlas_action)
        msfs_convert_action = QAction("Convert MSFS airport…", self)
        msfs_convert_action.triggered.connect(self.open_msfs_convert_dialog)
        tools_menu.addAction(msfs_convert_action)

        help_menu = self.menuBar().addMenu("&Help")
        wizard_action = QAction("Run setup assistant…", self)
        wizard_action.triggered.connect(self.run_wizard)
        help_menu.addAction(wizard_action)
        about_action = QAction("About Ortho4XP", self)
        about_action.triggered.connect(
            lambda: QMessageBox.about(
                self,
                "Ortho4XP",
                "Ortho4XP %s\nMap-first Qt UI (preview build)."
                % O4_Version.version,
            )
        )
        help_menu.addAction(about_action)

    # ------------------------------------------------------------------
    # Prefs / settings
    # ------------------------------------------------------------------
    def _apply_prefs(self, initial=False):
        import O4_Config_Utils as CFG

        imagery = self.prefs.get("imagery", "BI")
        if imagery in [
            self.imagery_combo.itemText(i)
            for i in range(self.imagery_combo.count())
        ]:
            self.imagery_combo.setCurrentText(imagery)
        self.zl_combo.setCurrentText(str(self.prefs.get("zl", 16)))
        xplane = self.prefs.get("xplane_dir", "")
        if xplane and not CFG.custom_scenery_dir:
            candidate = os.path.join(xplane, "Custom Scenery")
            if os.path.isdir(candidate):
                CFG.custom_scenery_dir = candidate
        self.map.set_provider(self.imagery_combo.currentText())

    def run_wizard(self):
        wizard = QTWIZ.OnboardingWizard(
            self.prefs, gui_provider_codes(), self
        )
        wizard.exec()
        self.prefs = dict(wizard.prefs)
        save_prefs(self.prefs)
        self._seed_paths_from_xplane()
        self._apply_prefs()
        self._load_airports_async()
        self.refresh_tiles()

    def _seed_paths_from_xplane(self):
        """Fill empty scenery/overlay paths from the X-Plane folder."""
        import O4_Settings_Model as SM

        xplane = self.prefs.get("xplane_dir", "")
        if not xplane:
            return
        seed = {}
        current = SM.read_global_raw()
        scenery = os.path.join(xplane, "Custom Scenery")
        if not current.get("custom_scenery_dir") and os.path.isdir(scenery):
            seed["custom_scenery_dir"] = scenery
        overlays = os.path.join(xplane, "Global Scenery")
        if not current.get("custom_overlay_src") and os.path.isdir(overlays):
            seed["custom_overlay_src"] = overlays
        cifp = SM.autodetect_cifp(xplane)
        if not current.get("cifp_data_path") and cifp:
            seed["cifp_data_path"] = cifp
        if seed:
            try:
                SM.write_global(seed)
                SM.apply_runtime(seed)
                for key, value in seed.items():
                    print("Derived %s from X-Plane folder: %s" % (key, value))
            except OSError as exc:
                print("Could not save derived paths:", exc)

    def open_coral_atlas_dialog(self):
        """Tools menu: the Allen Coral Atlas reef bathymetry setup."""
        import O4_Qt_Coral_Atlas as QTCORAL

        tile = self.map.active_tile() or (
            int(self.prefs.get("last_lat", 0)),
            int(self.prefs.get("last_lon", 0)),
        )
        dialog = QTCORAL.CoralAtlasDialog(
            self, initial_lat=tile[0], initial_lon=tile[1]
        )
        dialog.show()

    def open_msfs_convert_dialog(self):
        """Tools menu: convert an MSFS airport package to Custom Scenery."""
        import O4_Qt_MSFS_Convert as QTMSFS

        dialog = QTMSFS.MSFSConvertDialog(
            self, self.prefs.get("xplane_dir", "")
        )
        dialog.show()

    def open_settings(self):
        # The whole map selection edits together (mixed states across
        # tiles); the active tile alone when nothing is multi-selected.
        selected = sorted(self.map.selection())
        if not selected and self.map.active_tile():
            selected = [self.map.active_tile()]
        dialog = QTSET.SettingsWindow(
            self.prefs,
            selected,
            self.output_dir(),
            self,
        )
        settings_geometry = str(self.prefs.get("settings_geometry", ""))
        if settings_geometry:
            dialog.restoreGeometry(
                QByteArray.fromBase64(settings_geometry.encode("ascii"))
            )
        dialog.exec()
        # Blended settings apply immediately (Option C): every close path
        # keeps the changes, so the result is consumed unconditionally.
        old_xplane = self.prefs.get("xplane_dir", "")
        self.prefs = dialog.result_prefs()
        self.prefs["settings_geometry"] = bytes(
            dialog.saveGeometry().toBase64()
        ).decode("ascii")
        save_prefs(self.prefs)
        self._apply_prefs()
        if self.prefs.get("xplane_dir", "") != old_xplane:
            self._seed_paths_from_xplane()
            self._load_airports_async()
        self.refresh_tiles()
        if dialog.tile_written:
            self._active_changed(self.map.active_tile())

    def output_dir(self):
        """Custom build dir semantics: '' = default Tiles dir; a path with a
        trailing separator = per-tile subdirectories inside it."""
        out = self.prefs.get("output_dir", "")
        if out and not out.endswith(("/", "\\")):
            out += "/"
        return out

    def working_dir(self):
        out = self.prefs.get("output_dir", "")
        return out if out else FNAMES.Tile_dir

    # ------------------------------------------------------------------
    # Airport search
    # ------------------------------------------------------------------
    def _load_airports_async(self):
        """Load the airport search index, rebuilding it when the X-Plane
        apt.dat sources changed since the cache was written (mtime/size)."""
        xplane = self.prefs.get("xplane_dir", "")

        def work():
            try:
                paths = APT.find_apt_dats(xplane) if xplane else []
                if paths and APT.index_is_stale(paths, AIRPORT_CACHE):
                    if os.path.isfile(AIRPORT_CACHE):
                        print(
                            "X-Plane airport data changed — refreshing the "
                            "search index…"
                        )
                    else:
                        print("Building the airport search index…")
                    count = APT.build_index(paths, AIRPORT_CACHE)
                    print(
                        "Airport search index ready: %d airports." % count
                    )
                if os.path.isfile(AIRPORT_CACHE):
                    self._airports = APT.load_index(AIRPORT_CACHE)
            except Exception as exc:
                print("Airport index unavailable:", exc)

        threading.Thread(target=work, daemon=True).start()

    def _update_search_popup(self, text):
        self.search_popup.clear()
        text = text.strip()
        if len(text) < 2:
            self.search_popup.hide()
            return
        coord = APT.parse_coordinate_query(text)
        if coord:
            item = QListWidgetItem("Go to tile %+03d%+04d" % coord)
            item.setData(Qt.UserRole, ("tile", coord))
            self.search_popup.addItem(item)
        for entry in APT.search(self._airports, text, limit=8):
            label = "%s — %s" % (entry.code, entry.name)
            if entry.city:
                label += " (%s)" % entry.city
            item = QListWidgetItem(label)
            item.setData(
                Qt.UserRole,
                ("apt", (math.floor(entry.lat), math.floor(entry.lon))),
            )
            self.search_popup.addItem(item)
        if not self.search_popup.count():
            self.search_popup.hide()
            return
        pos = self.search_edit.mapToGlobal(
            self.search_edit.rect().bottomLeft()
        )
        self.search_popup.move(pos)
        self.search_popup.resize(self.search_edit.width(), 180)
        self.search_popup.show()

    def _search_accept_first(self):
        if self.search_popup.count():
            self._search_accept_item(self.search_popup.item(0))

    def _search_accept_item(self, item):
        kind, (lat, lon) = item.data(Qt.UserRole)
        self.search_popup.hide()
        self.search_edit.clear()
        self.map.center_on_tile(lat, lon, zoom=9 if kind == "apt" else 8)
        self.map.set_active(lat, lon)

    # ------------------------------------------------------------------
    # Selection / tile info
    # ------------------------------------------------------------------
    def refresh_tiles(self):
        import O4_Config_Utils as CFG

        # Fresh accumulators per scan: the display keeps showing the old
        # overlay until ScanDone swaps the authoritative result in, so
        # deleted tiles vanish exactly when the scan completes (the same
        # contract the one-shot scan had).
        self._scan_built = {}
        self._scan_installed = set()
        self._scanning = True
        self._session.scan(self.working_dir(), CFG.custom_scenery_dir)
        # An already-shown "(not built)" verdict is stale the moment a
        # rescan starts — repaint the active tile as pending.
        self._active_changed(self.map.active_tile())

    # ------------------------------------------------------------------
    # Engine event dispatch (the view renders; the session computes)
    # ------------------------------------------------------------------
    def _on_engine_event(self, event):
        handler = self._event_handlers.get(type(event))
        if handler is not None:
            handler(event)

    def _on_scan_progress(self, event):
        self.map.set_scan_status(event.phase, event.done, event.total)

    def _on_scan_batch(self, event):
        self._scan_built.update(event.built)
        self._scan_installed.update(event.installed)
        self._built.update(event.built)
        self._installed.update(event.installed)
        self.map.set_built(self._built)
        self.map.set_installed(self._installed)
        # The active tile stops being "(scanning…)" the moment its
        # own result streams in.
        active = self.map.active_tile()
        if active is not None and active in event.built:
            self._active_changed(active)

    def _on_scan_done(self, event):
        self._scanning = False
        self._built = dict(self._scan_built)
        self._installed = set(self._scan_installed)
        self.map.clear_scan_status()
        self._push_overlays()

    def _push_overlays(self):
        self.map.set_built(self._built)
        self.map.set_installed(self._installed)
        self._active_changed(self.map.active_tile())

    def _selection_changed(self):
        sel = self.map.selection()
        self._sync_build_controls_to_selection(sel)
        self._update_build_summary(sel)
        self._persist_selection(sel)

    def _persist_selection(self, selection=None):
        """Write the selected set and the active tile to the prefs file.

        A selection is hand-sized (the user clicks tiles), so there is
        nothing to debounce.  The panel does refresh on an UNCHANGED
        selection though — scan results streaming in, build bookkeeping —
        so an identical write is skipped rather than re-serialising the
        prefs file behind every one of them.
        """
        if selection is None:
            selection = self.map.selection()
        keys = [QTMAP.tile_key(*tile) for tile in sorted(selection)]
        active = self.map.active_tile()
        active_key = QTMAP.tile_key(*active) if active else ""
        if (keys == self.prefs.get(SELECTED_TILES_KEY)
                and active_key == self.prefs.get(ACTIVE_TILE_KEY)):
            return
        self.prefs[SELECTED_TILES_KEY] = keys
        self.prefs[ACTIVE_TILE_KEY] = active_key
        save_prefs(self.prefs)

    def _restore_selection(self):
        """([tiles], active) from the prefs file — the launch selection.

        Keys that no longer parse are dropped silently, and an active tile
        outside the restored set falls back to the set's first tile (the
        deselect path's rule).  Absent keys give an empty selection: a
        fresh install launches exactly as it always did.
        """
        stored = self.prefs.get(SELECTED_TILES_KEY)
        tiles = []
        if isinstance(stored, list):
            for key in stored:
                tile = QTMAP.parse_tile_key(key)
                if tile is not None and tile not in tiles:
                    tiles.append(tile)
        tiles.sort()
        active = QTMAP.parse_tile_key(self.prefs.get(ACTIVE_TILE_KEY) or "")
        if active not in tiles:
            active = tiles[0] if tiles else None
        return tiles, active

    def _sync_build_controls_to_selection(self, selection):
        """Point the Imagery / Build ZL combos at the selection's config.

        Tiles whose per-tile config records build provenance
        (``default_website`` / ``default_zl``) drive the toolbar combos:
        one agreed value is selected outright; disagreement unresolves the
        combo (it shows "--") and :meth:`start_build` refuses to run until
        the user picks a value.  Tiles with no recorded value impose
        nothing, and an empty selection leaves the combos alone.

        The sync runs once per selection: panel refreshes on an UNCHANGED
        selection (scan results streaming in, build bookkeeping) must not
        snap the combos back to the recorded provenance after the user
        deliberately picked a different value for the next build.
        """
        selection_key = (self.output_dir(), frozenset(selection))
        if selection_key == self._combos_synced_to:
            return
        self._combos_synced_to = selection_key
        import O4_Settings_Model as SM

        websites = set()
        zoomlevels = set()
        for lat, lon in selection:
            raw = SM.read_tile_raw(lat, lon, self.output_dir())
            if not raw:
                continue
            website = raw.get("default_website", "").strip()
            if website:
                websites.add(website)
            zoomlevel = str(raw.get("default_zl", "")).strip()
            if zoomlevel:
                try:
                    zoomlevel = str(int(float(zoomlevel)))
                except ValueError:
                    pass
                zoomlevels.add(zoomlevel)
        _sync_combo_to_agreed_value(self.imagery_combo, websites)
        _sync_combo_to_agreed_value(self.zl_combo, zoomlevels)

    def _update_build_summary(self, sel=None):
        if sel is None:
            sel = self.map.selection()
        n = len(sel)
        if not n:
            self.build_summary.setText("No tiles selected")
        else:
            try:
                zl = int(self.zl_combo.currentText())
            except ValueError:
                zl = 16
            est = n * 3.0 * 4 ** (zl - 16)
            summary_text = "%d tile%s selected · rough est. %.1f GB" % (
                n,
                "s" if n > 1 else "",
                est,
            )
            try:
                import O4_Airport_Elevation_Insets as ELEVATION_PROVIDERS

                covered = ELEVATION_PROVIDERS.tiles_with_inset_coverage(sel)
                if covered and n == 1:
                    summary_text += " · airport lidar available"
                elif covered and len(covered) == n:
                    summary_text += " · airport lidar on all"
                elif covered:
                    summary_text += " · airport lidar on %d" % len(covered)
            except Exception:
                pass
            in_run = sum(1 for t in sel if self._tile_in_active_run(t))
            if in_run:
                summary_text += " · %d in current run" % in_run
            self.build_summary.setText(summary_text)
        self.selection_label.setText("%d selected" % n if n else "")
        if self._building and n:
            # A run is in progress: the button appends to it — counting
            # only tiles NOT already queued or building, so it can never
            # hand the engine a second copy of the same tile.
            fresh = sum(
                1 for t in sel if not self._tile_in_active_run(t))
            self.build_btn.setText(
                "＋ Queue %d tile%s" % (fresh, "s" if fresh > 1 else "")
                if fresh else "＋ Queue")
            self.build_btn.setEnabled(fresh > 0)
            self.build_btn.setToolTip(
                "" if fresh else
                "The selected tiles are already queued or building in "
                "the current run.")
        else:
            self.build_btn.setText(
                "▶ Build %d tile%s" % (n, "s" if n > 1 else "")
                if n else "▶ Build")
            self.build_btn.setEnabled(True)
            self.build_btn.setToolTip("")

    def _active_changed(self, tile):
        self._selection_changed()
        self._refresh_texture_mode(tile)
        self._refresh_elevation_level(tile)
        self._refresh_airport_elevation_level(tile)
        if tile is None:
            self.info_group.setVisible(False)
            return
        lat, lon = tile
        self.info_group.setVisible(True)
        self.info_title.setText(
            "<b>Tile %s</b>" % FNAMES.short_latlon(lat, lon)
        )
        info = self._built.get(tile)
        import O4_Config_Utils as CFG

        # Reanchor probe (worker thread: one sidecar stat per pack in
        # Custom Scenery); the row stays hidden until a result for THIS
        # tile arrives through the bridge.
        self._info_layout.setRowVisible(self.modified_airports_row, False)
        self._modified_airport_packs = []
        if CFG.custom_scenery_dir:
            threading.Thread(
                target=self._probe_modified_airports,
                args=(tile, CFG.custom_scenery_dir),
                daemon=True,
            ).start()

        # The elevation rows populate for built AND unbuilt tiles: what
        # data a build WOULD use matters most before building.
        try:
            import O4_Settings_Model as SM

            raw = SM.read_tile_raw(lat, lon, self.output_dir()) or {}
            (base_text, lidar_text) = _elevation_row_texts(
                lat,
                lon,
                info.custom_dem if info else "",
                raw.get("elevation_level") or "auto",
            )
        except Exception:
            (base_text, lidar_text) = ("?", "?")
        self.info_elevation.setText(base_text)
        self.info_airport_lidar.setText(lidar_text)
        # Manual-setup affordance (CONTROLLER): ask the model which
        # manual-download sources could serve this tile and are not set
        # up yet; the view only renders what it is handed.
        try:
            import O4_Airport_Elevation_Insets as ELEVATION_PROVIDERS

            self._manual_elevation_entries = [
                entry
                for entry in (
                    ELEVATION_PROVIDERS.manual_elevation_setup_for_tile(
                        lat, lon
                    )
                )
                if not entry["already_dropped"]
            ]
        except Exception:
            self._manual_elevation_entries = []
        self.manual_elevation_btn.setVisible(
            bool(self._manual_elevation_entries)
        )

        if info is None:
            # While a scan streams in, absence only means "not scanned
            # yet" — a built tile must not flash as "(not built)".
            pending = self._scanning
            for w in (
                self.info_provider,
                self.info_zl,
                self.info_mesh,
                self.info_imagery,
                self.info_size,
            ):
                w.setText("…" if pending else "—")
            self.info_title.setText(
                self.info_title.text()
                + ("  (scanning…)" if pending else "  (not built)")
            )
            self.install_check.setEnabled(False)
            self.install_check.setChecked(False)
            return
        self.info_provider.setText(info.provider or "?")
        zl_text = str(info.zl) if info.zl else "?"
        # Airport high-ZL cover: show the upgraded zoomlevel and its scope
        # (e.g. "16 + ZL18 ICAO") so the setting is visible at a glance.
        mode = (getattr(info, "high_zl_airports", "") or "").strip()
        if mode not in ("", "False") and info.cover_zl and (
            info.zl is None or info.cover_zl > info.zl
        ):
            scope = {"True": "All", "ICAO": "ICAO", "Existing": "Existing"}
            zl_text += " + ZL%d %s" % (info.cover_zl, scope.get(mode, mode))
        if info.has_zones:
            zl_text += " + zones"
        self.info_zl.setText(zl_text)
        self.info_mesh.setText(_fmt_date(info.mesh_date))
        self.info_imagery.setText(_fmt_date(info.imagery_date))
        if info.size_bytes is None:
            self.info_size.setText("computing…")
            threading.Thread(
                target=self._compute_size_async, args=(info,), daemon=True
            ).start()
        else:
            self.info_size.setText(_fmt_size(info.size_bytes))
        can_link = bool(CFG.custom_scenery_dir)
        self.install_check.setChecked(tile in self._installed)
        physical = False
        if can_link:
            try:
                physical = (
                    LINKS.link_status(
                        lat, lon, info.build_dir, CFG.custom_scenery_dir
                    )
                    is LINKS.LinkStatus.PHYSICAL
                )
            except OSError:
                pass
        # Only a tile that is queued or building RIGHT NOW locks its
        # install toggle — other tiles stay reviewable during a run.
        self.install_check.setEnabled(
            can_link and not physical
            and not self._tile_in_active_run(tile)
        )
        if not can_link:
            self.install_check.setToolTip(
                "Set your X-Plane folder in Settings to install tiles."
            )
        elif physical:
            self.install_check.setToolTip(
                "This tile's folder lives directly in Custom Scenery, so it "
                "is always installed. To manage it as a link, move the "
                "folder elsewhere first."
            )
        else:
            self.install_check.setToolTip("")

    def _refresh_texture_mode(self, tile):
        """Load the active tile's ``texture_mode`` into the build-area combo.

        Reads the per-tile config via :mod:`O4_Settings_Model`; falls back to
        the registry default (``full_ortho``) when the tile has no config or
        the value is unknown.  Signals are blocked so the programmatic update
        does not trigger a write back to disk.
        """
        import O4_Settings_Model as SM

        value = "full_ortho"
        if tile is not None:
            raw = SM.read_tile_raw(tile[0], tile[1], self.output_dir())
            if raw and raw.get("texture_mode"):
                value = raw["texture_mode"]
        index = self.texture_combo.findData(value)
        if index < 0:
            index = 0
        self.texture_combo.blockSignals(True)
        self.texture_combo.setCurrentIndex(index)
        self.texture_combo.blockSignals(False)

    def _refresh_elevation_level(self, tile):
        """Load the active tile's ``elevation_level`` into the build-area combo.

        Mirrors :meth:`_refresh_texture_mode`: reads the per-tile config via
        :mod:`O4_Settings_Model`, falls back to "auto" when the tile has no
        config or an unknown value, and blocks signals so the programmatic
        update does not write back to disk.
        """
        import O4_Settings_Model as SM

        value = "auto"
        if tile is not None:
            raw = SM.read_tile_raw(tile[0], tile[1], self.output_dir())
            if raw and raw.get("elevation_level"):
                value = raw["elevation_level"]
        index = self.elevation_combo.findData(value)
        if index < 0:
            index = 0
        self.elevation_combo.blockSignals(True)
        self.elevation_combo.setCurrentIndex(index)
        self.elevation_combo.blockSignals(False)

    def _elevation_level_changed(self, index):
        """Persist the chosen elevation detail level to the tile's config.

        No-ops when no tile is active.  Writes only the ``elevation_level``
        key; :func:`O4_Settings_Model.write_tile` preserves every other
        tile var.
        """
        tile = self.map.active_tile()
        if tile is None:
            return
        value = self.elevation_combo.itemData(index)
        if value is None:
            return
        import O4_Settings_Model as SM

        try:
            SM.write_tile(
                tile[0],
                tile[1],
                self.output_dir(),
                {"elevation_level": value},
            )
        except OSError as exc:
            print("Could not save elevation level:", exc)

    def _refresh_airport_elevation_level(self, tile):
        """Load the active tile's ``airport_elevation_level`` into its combo.

        Mirrors :meth:`_refresh_elevation_level` for the airport-inset
        detail level.
        """
        import O4_Settings_Model as SM

        value = "auto"
        if tile is not None:
            raw = SM.read_tile_raw(tile[0], tile[1], self.output_dir())
            if raw and raw.get("airport_elevation_level"):
                value = raw["airport_elevation_level"]
        index = self.airport_elevation_combo.findData(value)
        if index < 0:
            index = 0
        self.airport_elevation_combo.blockSignals(True)
        self.airport_elevation_combo.setCurrentIndex(index)
        self.airport_elevation_combo.blockSignals(False)

    def _airport_elevation_level_changed(self, index):
        """Persist the chosen airport elevation detail level to the tile.

        No-ops when no tile is active; mirrors
        :meth:`_elevation_level_changed`.
        """
        tile = self.map.active_tile()
        if tile is None:
            return
        value = self.airport_elevation_combo.itemData(index)
        if value is None:
            return
        import O4_Settings_Model as SM

        try:
            SM.write_tile(
                tile[0],
                tile[1],
                self.output_dir(),
                {"airport_elevation_level": value},
            )
        except OSError as exc:
            print("Could not save airport elevation level:", exc)

    def _modify_custom_airports_changed(self, checked):
        """Persist the global modify-custom-airports switch.

        Gates auto_patch Phase 2 (object reseating inside installed
        packages): the in-session CFG value covers tiles built by this
        process; the cfg write covers parallel worker children, which
        re-read Ortho4XP.cfg from disk.
        """
        import O4_Config_Utils as CFG
        import O4_Settings_Model as SM

        CFG.modify_custom_airports = bool(checked)
        try:
            SM.write_global({"modify_custom_airports": str(bool(checked))})
        except OSError as exc:
            print("Could not save modify_custom_airports:", exc)

    def _texture_mode_changed(self, index):
        """Persist the chosen texture mode to the active tile's config.

        No-ops when no tile is active.  Writes only the ``texture_mode`` key;
        :func:`O4_Settings_Model.write_tile` preserves every other tile var.
        """
        tile = self.map.active_tile()
        if tile is None:
            return
        value = self.texture_combo.itemData(index)
        if value is None:
            return
        import O4_Settings_Model as SM

        try:
            SM.write_tile(
                tile[0], tile[1], self.output_dir(), {"texture_mode": value}
            )
        except OSError as exc:
            print("Could not save texture mode:", exc)

    def _compute_size_async(self, info):
        try:
            TINFO.compute_size(info)
        except Exception:
            return
        self._bridge.size_computed.emit()

    def _probe_modified_airports(self, tile, scenery_dir):
        """Worker thread: which packs did the reseater modify for this
        tile?  Result marshalled to the GUI thread via the bridge."""
        try:
            from auto_patch import object_rebake

            packs = object_rebake.modified_packs(
                scenery_dir, tile=FNAMES.short_latlon(*tile)
            )
        except Exception:
            packs = []
        self._bridge.reanchor_ready.emit((tile, packs))

    def _on_reanchor_ready(self, payload):
        tile, packs = payload
        if tile != self.map.active_tile():
            return  # stale probe: the user moved on
        self._modified_airport_packs = list(packs)
        while self._modified_airport_rows.count():
            item = self._modified_airport_rows.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        if not packs:
            self._info_layout.setRowVisible(
                self.modified_airports_row, False)
            return
        for pack in packs:
            row = QWidget()
            rl = QHBoxLayout(row)
            rl.setContentsMargins(0, 0, 0, 0)
            rl.setSpacing(4)
            objects = pack.get("objects", 0)
            label = QLabel(pack["pack_name"])
            label.setToolTip(
                "%d object file%s reseated to this tile's rebuilt "
                "ground (originals kept as .anchor_bak backups)."
                % (objects, "s" if objects != 1 else "")
            )
            rl.addWidget(label, 1)
            undo = QToolButton()
            undo.setAutoRaise(True)
            undo.setIcon(self.style().standardIcon(
                QStyle.SP_ArrowBack))
            undo.setFixedSize(18, 18)
            undo.setEnabled(not self._building)
            undo.setToolTip(
                "Wait for the current run — the engine may be "
                "rewriting these files."
                if self._building else
                "Revert to default: restores this package's original "
                "object files from the reseater's backups."
            )
            undo.clicked.connect(
                lambda _checked=False, p=pack:
                self._revert_modified_pack(p)
            )
            rl.addWidget(undo, 0, Qt.AlignRight)
            self._modified_airport_rows.addWidget(row)
        self._info_layout.setRowVisible(self.modified_airports_row, True)

    def _revert_modified_pack(self, pack):
        """Put ONE pack's .anchor_bak originals back (engine restore
        semantics: backups stay for the next bake, provenance sidecar
        removed), then re-probe so the row updates."""
        tile = self.map.active_tile()
        if self._building or tile is None:
            return
        import O4_Config_Utils as CFG

        scenery_dir = CFG.custom_scenery_dir

        def work():
            from auto_patch import object_rebake

            try:
                restored = object_rebake.restore(pack["pack_path"])
                print(
                    "Restored %d original object file%s in %s."
                    % (
                        restored,
                        "s" if restored != 1 else "",
                        pack["pack_name"],
                    )
                )
            except Exception as error:
                print(
                    "Revert failed for %s: %s"
                    % (pack["pack_name"], error)
                )
            if scenery_dir:
                self._probe_modified_airports(tile, scenery_dir)

        threading.Thread(target=work, daemon=True).start()

    def _show_manual_elevation_dialog(self):
        """Render the model's manual-setup entries (VIEW only).

        One section per provider: what it is, a clickable download
        page, the numbered steps, and the drop folder with an opener --
        every string comes from the model entry verbatim.
        """
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices

        entries = self._manual_elevation_entries
        if not entries:
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("Better elevation data for this tile")
        layout = QVBoxLayout(dialog)
        introduction = QLabel(
            "These sources cover this tile but must be downloaded once "
            "by hand (their file hosts do not allow automatic "
            "downloads). After the files are in place, every build "
            "uses them automatically."
        )
        introduction.setWordWrap(True)
        layout.addWidget(introduction)
        for entry in entries:
            group = QGroupBox(
                "%s — %s %s"
                % (
                    entry["code"],
                    entry["native_resolution"],
                    "tile-wide" if entry["role"] == "base" else
                    "airport lidar",
                )
            )
            group_layout = QVBoxLayout(group)
            link = QLabel(
                '1. Download from <a href="%s">%s</a>'
                % (entry["download_page"], entry["download_page"])
            )
            link.setOpenExternalLinks(True)
            link.setWordWrap(True)
            group_layout.addWidget(link)
            for (number, step) in enumerate(entry["steps"][1:], start=2):
                step_label = QLabel("%d. %s" % (number, step))
                step_label.setWordWrap(True)
                group_layout.addWidget(step_label)
            folder_row = QHBoxLayout()
            folder_label = QLabel(entry["drop_directory"])
            folder_label.setWordWrap(True)
            folder_label.setTextInteractionFlags(
                Qt.TextSelectableByMouse
            )
            folder_row.addWidget(folder_label, 1)
            open_button = QPushButton("Open folder")

            def _open_drop_folder(_checked=False, path=entry["drop_directory"]):
                os.makedirs(path, exist_ok=True)
                QDesktopServices.openUrl(QUrl.fromLocalFile(path))

            open_button.clicked.connect(_open_drop_folder)
            folder_row.addWidget(open_button)
            group_layout.addLayout(folder_row)
            if entry.get("license"):
                license_label = QLabel(
                    "Licence: %s" % entry["license"]
                )
                license_label.setWordWrap(True)
                license_label.setStyleSheet("color: palette(mid);")
                group_layout.addWidget(license_label)
            layout.addWidget(group)
        close_button = QPushButton("Close")
        close_button.clicked.connect(dialog.accept)
        layout.addWidget(close_button, alignment=Qt.AlignRight)
        dialog.resize(560, min(220 + 200 * len(entries), 640))
        dialog.exec()

    def _toggle_install(self, checked):
        import O4_Config_Utils as CFG

        tile = self.map.active_tile()
        if tile is None:
            return
        lat, lon = tile
        info = self._built.get(tile)
        if info is None:
            self.install_check.setChecked(False)
            return
        try:
            if checked:
                LINKS.install(lat, lon, info.build_dir, CFG.custom_scenery_dir)
                self._installed.add(tile)
                print(
                    "Installed %s in X-Plane." % FNAMES.short_latlon(lat, lon)
                )
            else:
                LINKS.uninstall(
                    lat, lon, info.build_dir, CFG.custom_scenery_dir
                )
                self._installed.discard(tile)
                print(
                    "Removed %s from X-Plane."
                    % FNAMES.short_latlon(lat, lon)
                )
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Install in X-Plane", str(exc))
            self.install_check.setChecked(tile in self._installed)
        self.map.set_installed(self._installed)

    def _toggle_overlay_link(self):
        import O4_Config_Utils as CFG

        if not CFG.custom_scenery_dir:
            QMessageBox.information(
                self,
                "Overlays",
                "Set your X-Plane folder in Settings first.",
            )
            return
        try:
            status = os.path.isdir(
                os.path.join(CFG.custom_scenery_dir, "yOrtho4XP_Overlays")
            )
            if status:
                LINKS.uninstall_overlay_link(
                    FNAMES.Overlay_dir, CFG.custom_scenery_dir
                )
                print("Overlay link removed from Custom Scenery.")
            else:
                LINKS.install_overlay_link(
                    FNAMES.Overlay_dir, CFG.custom_scenery_dir
                )
                print("Overlay link added to Custom Scenery.")
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Overlays", str(exc))

    # ------------------------------------------------------------------
    # Building
    # ------------------------------------------------------------------
    def _imagery_changed(self, code):
        if not code:
            # Unresolved ("--"): the map keeps showing its last provider.
            return
        self.map.set_provider(code)
        self._update_zoom_label()

    def _set_activity_box_visible(self, visible):
        """Show or hide the Activity box.

        While visible, the panel's idle bottom spacer is zeroed so the
        box takes every pixel of free height as the window grows;
        hiding it restores the spacer so the boxes sit top-aligned.
        """
        self.activity_group.setVisible(visible)
        self._panel_layout.setStretch(
            self._panel_spacer_index, 0 if visible else 1)

    def _tile_in_active_run(self, tile):
        """True while the tile is queued or building in the current run."""
        if not self._building:
            return False
        state, label, _percent = self._progress_states.get(
            tile, (None, None, 0))
        if state is None:
            return False
        return (state in ("queued", "active", "indeterminate")
                and label != "stopped")

    def start_build(self):
        """Build the selected tiles — or queue them into the run in
        progress (the map and the Build box stay live during builds)."""
        selection = sorted(self.map.selection())
        if not selection:
            self._status("Select at least one tile to build.")
            return
        unresolved = []
        if self.imagery_combo.currentIndex() < 0:
            unresolved.append("imagery source")
        if self.zl_combo.currentIndex() < 0:
            unresolved.append("build zoom level")
        if unresolved:
            self._status(
                "The selected tiles disagree on the %s — pick one in the "
                "toolbar before building." % " and the ".join(unresolved)
            )
            return
        # Freeze the toolbar choices NOW: the panel refreshes below
        # (_active_changed → _sync_build_controls_to_selection) re-read
        # the selected tiles' recorded provenance and could otherwise
        # snap the combos back to it, silently overriding what the user
        # just picked for this build.
        provider = self.imagery_combo.currentText()
        zoomlevel = int(self.zl_combo.currentText())
        if self.chk_skip_built.isChecked():
            todo = [t for t in selection if t not in self._built]
            skipped = len(selection) - len(todo)
            if skipped:
                print(
                    "Skipping %d already-built tile%s "
                    "(uncheck 'Skip already-built tiles' to rebuild)."
                    % (skipped, "s" if skipped > 1 else "")
                )
        else:
            todo = selection
        if not todo:
            self._status("All selected tiles are already built.")
            return
        do_vector = self.chk_vector.isChecked()
        do_imagery = self.chk_imagery.isChecked()
        do_overlays = self.chk_overlays.isChecked()
        if not (do_vector or do_imagery or do_overlays):
            self._status("Choose at least one build step.")
            return

        if self._building:
            self._queue_into_running_build(
                todo, provider, zoomlevel,
                do_vector, do_imagery, do_overlays)
            return

        self._start_run(todo, {
            "provider": provider,
            "zoomlevel": zoomlevel,
            "do_vector": do_vector,
            "do_imagery": do_imagery,
            "do_overlays": do_overlays,
        })

    def _start_run(self, todo, settings):
        """Start a fresh run for ``todo`` with ``settings``.

        The Build button's own machinery without its selection guard: a
        resumed tile need not still be selected on the map — not having
        to re-find it is the whole point of the resume button.
        """
        self._building = True
        self._stop_requested = False
        self.stop_btn.setEnabled(True)
        self.stop_btn.setText("■ Stop")
        self.map.zoom_to_tiles(todo)
        self._progress_states = {
            t: ("queued", "queued", 0) for t in todo
        }
        self.map.set_progress(self._progress_states)
        self._setup_progress_page(todo)
        self._snapshot_run_settings(todo, settings)
        self._update_build_summary()
        # Re-gate the info panel (install toggle) for the active tile
        # now that it may be part of the run.
        self._active_changed(self.map.active_tile())
        if not self.console.isVisible():
            self.toggle_console()

        started = self._session.enqueue_build(
            todo,
            custom_build_dir=self.output_dir(),
            **settings
        )
        if not started:
            self._building = False
            self._elapsed_timer.stop()
            self._set_activity_box_visible(False)
            self._update_build_summary()
            self._status("The build could not be started.")

    def _queue_into_running_build(self, todo, provider, zoomlevel,
                                  do_vector, do_imagery, do_overlays):
        """Append a batch to the run in progress; it starts as soon as
        the orchestrator has capacity for it."""
        fresh = [t for t in todo if not self._tile_in_active_run(t)]
        if not fresh:
            self._status(
                "The selected tiles are already building or queued.")
            return
        accepted = self._session.enqueue_build(
            fresh,
            provider=provider,
            zoomlevel=zoomlevel,
            custom_build_dir=self.output_dir(),
            do_vector=do_vector,
            do_imagery=do_imagery,
            do_overlays=do_overlays,
        )
        if not accepted:
            self._status(
                "Could not queue the tiles — the previous run is still "
                "winding down; try again in a moment."
            )
            return
        for tile in fresh:
            self._progress_states[tile] = ("queued", "queued", 0)
            # A finished tile being built again starts a fresh stopwatch.
            self._tile_started_at.pop(tile, None)
            self._tile_results.pop(tile, None)
        self._snapshot_run_settings(fresh, {
            "provider": provider,
            "zoomlevel": zoomlevel,
            "do_vector": do_vector,
            "do_imagery": do_imagery,
            "do_overlays": do_overlays,
        })
        self.map.set_progress(self._progress_states)
        self._add_progress_rows(fresh)
        self._ntiles += len(fresh)
        self.progress_title.setText(
            "<b>Building %d tile%s</b>"
            % (self._ntiles, "s" if self._ntiles > 1 else "")
        )
        self._status(
            "Queued %d tile%s into the running build."
            % (len(fresh), "s" if len(fresh) > 1 else "")
        )
        self._active_changed(self.map.active_tile())

    def _setup_progress_page(self, todo):
        """Reset the Activity box to a fresh run's per-tile rows."""
        for bar, status, row, cancel, clock in self._tile_rows.values():
            row.deleteLater()
        self._tile_rows = {}
        self._tile_clocks = {}
        # A fresh run owns the box: rows the previous one left behind
        # (stopped tiles waiting for a resume) go with it, and so do the
        # settings snapshots that belonged to them.
        self._run_settings = {}
        self._add_progress_rows(todo)
        self._done_count = 0
        self._ntiles = len(todo)
        self._tile_started_at = {}
        self._tile_results = {}
        self._build_t0 = time.time()
        self.progress_title.setText(
            "<b>Building %d tile%s</b>"
            % (len(todo), "s" if len(todo) > 1 else "")
        )
        self.elapsed_label.setText("Total elapsed 0 s")
        self.eta_label.setText("Total remaining —")
        self._elapsed_timer.start()
        self._set_activity_box_visible(True)

    def _add_progress_rows(self, tiles):
        """Create Activity rows for tiles that lack one; reset (to
        "queued") the row of a finished or stopped tile being built
        again."""
        for tile in tiles:
            if tile in self._tile_rows:
                bar, status, _row, cancel, clock = self._tile_rows[tile]
                bar.setValue(0)
                status.setText("queued")
                status.setStyleSheet("color: gray; font-size: 11px;")
                clock.setText("")
                cancel.setEnabled(True)
                cancel.setVisible(True)
                self._set_row_button_mode(cancel, "stop")
                continue
            row = QWidget()
            rl = QVBoxLayout(row)
            rl.setContentsMargins(6, 4, 6, 4)
            rl.setSpacing(2)
            head = QHBoxLayout()
            head.setSpacing(6)
            head.addWidget(QLabel(FNAMES.short_latlon(*tile)))
            head.addStretch(1)
            # Per-tile clock (elapsed · ~remaining), fed by TileClocks.
            clock = QLabel("")
            clock.setStyleSheet("color: gray; font-size: 11px;")
            head.addWidget(clock)
            status = QLabel("queued")
            status.setStyleSheet("color: gray; font-size: 11px;")
            head.addWidget(status)
            # Per-tile stop / resume: one button that changes what it
            # offers with the row's state — a red stop sign while the
            # tile is live, a green resume once the user has stopped it.
            # An "X" reads as "dismiss this row", which is not what it
            # does, so the glyphs are painted here (qt-parity spec §Q2).
            cancel = QToolButton()
            cancel.setAutoRaise(True)
            cancel.setIconSize(QSize(STOP_ICON_PT, STOP_ICON_PT))
            cancel.setFixedSize(STOP_ICON_PT + 6, STOP_ICON_PT + 6)
            self._set_row_button_mode(cancel, "stop")
            cancel.clicked.connect(
                lambda _checked=False, t=tile: self._tile_button_clicked(t)
            )
            head.addWidget(cancel)
            rl.addLayout(head)
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setValue(0)
            bar.setTextVisible(False)
            bar.setFixedHeight(6)
            rl.addWidget(bar)
            self._rows_layout.insertWidget(
                self._rows_layout.count() - 1, row
            )
            self._tile_rows[tile] = (bar, status, row, cancel, clock)

    def _on_step_progress(self, event):
        tile = (event.lat, event.lon)
        state = "indeterminate" if event.indeterminate else "active"
        resolved = resolve_tile_state(
            (state, event.label, event.percent),
            self._progress_states.get(tile),
        )
        if resolved is None:
            return  # stale news from a run this row has already left
        self._tile_started_at.setdefault(tile, time.time())
        self._progress_states[tile] = resolved
        self.map.set_progress(self._progress_states)
        self._render_row_state(tile)
        self.setWindowTitle(
            "Ortho4XP — building %s · %s · %d%%"
            % (FNAMES.short_latlon(*tile), event.label, event.percent)
        )

    def _on_tile_state(self, event):
        tile = (event.lat, event.lon)
        resolved = resolve_tile_state(
            (event.state, event.label, event.percent),
            self._progress_states.get(tile),
        )
        if resolved is None:
            # The row is locally stopped and this is not a terminal
            # outcome — including the engine's own late "stopped" notice,
            # which the row said minutes ago.
            return
        state, label, _pct = resolved
        if state == "done":
            self._done_count += 1
        self._progress_states[tile] = resolved
        self.map.set_progress(self._progress_states)
        self._render_row_state(tile)
        if state in ("done", "error") or label == "stopped":
            # The tile left the active run: selected finished/failed
            # tiles become queueable again (button label + gating).
            self._update_build_summary()
        if state == "done":
            self.refresh_tiles()

    def _on_run_eta(self, event):
        self._last_run_eta = event

    def _on_tile_clocks(self, event):
        """Per-tile clocks (protocol 1.3): stash; the 1 Hz clock tick
        renders (same discipline as RunEta — views never compute)."""
        rows = {
            (int(row[0]), int(row[1])): (row[2], row[3], bool(row[4]))
            for row in event.rows
        }
        # A stopped row's clock stays frozen where the stop left it: the
        # engine goes on counting until its cancel lands, and that number
        # describes a tile the user has already stopped.
        for tile in list(rows):
            if self._progress_states.get(tile, (None,))[0] != "stopped":
                continue
            previous = self._tile_clocks.get(tile)
            if previous is None:
                rows.pop(tile)
            else:
                rows[tile] = previous
        self._tile_clocks = rows

    def _update_tile_row(self, tile, pct, label):
        """Legacy entry point (progress push): the row renders itself
        from ``_progress_states``, which this updates first."""
        if tile in self._tile_rows:
            state = self._progress_states.get(tile, ("active", label, pct))[0]
            self._progress_states[tile] = (state, label, pct)
            self._render_row_state(tile)

    def _set_row_button_mode(self, button, mode):
        """Point a row's one button at stop or at resume."""
        if mode == "resume":
            button.setIcon(resume_icon())
            button.setToolTip("Resume this tile")
        else:
            button.setIcon(stop_sign_icon())
            button.setToolTip("Stop this tile")

    def _render_row_state(self, tile):
        """Repaint one Activity row from ``_progress_states``: status text
        and colour, the progress bar, and which of the two things the
        row's button is offering.

        The button is deliberately NOT gated on a run being in progress —
        a stopped row keeps its resume button after the run ends, so the
        tile never has to be found on the map again.
        """
        row = self._tile_rows.get(tile)
        if row is None:
            return
        bar, status, _row, button, _clock = row
        state, label, pct = self._progress_states.get(
            tile, ("queued", "queued", 0))
        color = "gray"
        if state == "done":
            bar.setValue(100)
            status.setText("done ✓")
            color = "green"
        elif state == "error":
            status.setText("failed")
            color = "red"
        elif state == "stopped":
            # Frozen where the stop caught it — the percent is the last
            # thing the tile actually reached, not a number still moving.
            bar.setValue(int(pct))
            status.setText(label or "stopped")
            color = STOPPED_COLOR
        elif state in ("active", "indeterminate"):
            bar.setValue(int(pct))
            status.setText("%s · %d%%" % (label, pct))
        else:
            bar.setValue(int(pct))
            status.setText(label or "queued")
            if label == "stopped":
                color = STOPPED_COLOR
        status.setStyleSheet("color: %s; font-size: 11px;" % color)
        if state in ("done", "error"):
            # Nothing left to stop and nothing to resume: a finished tile
            # goes back through the Build button.
            button.setEnabled(False)
            button.setVisible(False)
            return
        if label == "stopped" and state != "stopped":
            # The ENGINE reports this tile drained (a wholesale stop, or a
            # per-tile cancel that landed on a row the user did not stop
            # here): there is nothing left to stop.
            button.setEnabled(False)
            return
        button.setEnabled(True)
        button.setVisible(True)
        self._set_row_button_mode(
            button, "resume" if state == "stopped" else "stop")

    def _tile_button_clicked(self, tile):
        """The row's one button: stop while the tile is live, resume once
        it is stopped."""
        state = self._progress_states.get(tile, ("queued",))[0]
        if state == "stopped":
            self._resume_tile_clicked(tile)
        else:
            self._cancel_tile_clicked(tile)

    def _cancel_tile_clicked(self, tile):
        """The row's stop sign: this tile stops HERE, at the click.

        The engine only notices its cancel flag at the next phase
        boundary — minutes away inside a mesh step — so a row that waited
        for the engine to agree is what made the button feel broken.  The
        cancel still goes over exactly as before; the ROW goes "stopped"
        now, percent frozen, and the engine's eventual events for the
        tile are stale (``resolve_tile_state`` drops them).
        """
        self._session.cancel_tile(tile[0], tile[1])
        # Stop is the inverse of resume, at any scale: stopping a row that
        # was waiting for the follow-up run takes it out of the queue.
        self._resume_queue = [t for t in self._resume_queue if t != tile]
        _state, _label, pct = self._progress_states.get(
            tile, ("queued", "queued", 0))
        self._progress_states[tile] = ("stopped", "stopped", pct)
        self.map.set_progress(self._progress_states)
        # The clock freezes too: the engine keeps counting until its
        # cancel lands, and a running clock under "stopped" is the same
        # lie the row itself used to tell.
        clock = self._tile_clocks.get(tile)
        if clock is not None:
            self._tile_clocks[tile] = (clock[0], None, True)
        self._render_row_state(tile)
        self._update_build_summary()

    def _resume_tile_clicked(self, tile):
        """The row's green resume: rebuild this tile with the settings ITS
        run was started with, not whatever the toolbar says now.

        A run in progress is left alone — the tile joins a client-side
        queue and starts as one follow-up run when the current one ends
        (no protocol change: the engine knows nothing about the queue).
        """
        settings = self._run_settings.get(tile) or self._toolbar_settings()
        if settings is None:
            self._status(
                "Pick an imagery source and zoom level to resume this tile.")
            return
        if self._building:
            self._resume_queue = enqueue_resume(tile, self._resume_queue)
            self._progress_states[tile] = (
                "queued", "resumes after current run", 0)
            self.map.set_progress(self._progress_states)
            self._tile_clocks.pop(tile, None)
            row = self._tile_rows.get(tile)
            if row is not None:
                row[4].setText("")
            self._render_row_state(tile)
            self._update_build_summary()
            return
        self._resume_queue = [t for t in self._resume_queue if t != tile]
        self._start_run([tile], settings)

    def _toolbar_settings(self):
        """The run settings the toolbar currently spells out, or None while
        a combo is unresolved ("--")."""
        if self.imagery_combo.currentIndex() < 0:
            return None
        if self.zl_combo.currentIndex() < 0:
            return None
        return {
            "provider": self.imagery_combo.currentText(),
            "zoomlevel": int(self.zl_combo.currentText()),
            "do_vector": self.chk_vector.isChecked(),
            "do_imagery": self.chk_imagery.isChecked(),
            "do_overlays": self.chk_overlays.isChecked(),
        }

    def _snapshot_run_settings(self, tiles, settings):
        """Record what each tile is being STARTED with — what a later
        resume of it must use."""
        for tile in tiles:
            self._run_settings[tile] = dict(settings)

    def _start_resume_queue(self):
        """The tiles resumed mid-run, as ONE follow-up run.

        Each carries its own run's settings, so they are grouped: one
        batch per distinct settings set, the first batch starting the run
        and the rest queued into it.
        """
        todo, self._resume_queue = self._resume_queue, []
        batches = []
        for tile in todo:
            settings = self._run_settings.get(tile) or self._toolbar_settings()
            if settings is None:
                continue
            for batch_tiles, batch_settings in batches:
                if batch_settings == settings:
                    batch_tiles.append(tile)
                    break
            else:
                batches.append(([tile], dict(settings)))
        for index, (tiles, settings) in enumerate(batches):
            if index == 0:
                self._start_run(tiles, settings)
            else:
                self._queue_into_running_build(tiles, **settings)

    def _update_build_clock(self):
        import time as _time

        if self._build_t0 is None:
            return
        elapsed = _time.time() - self._build_t0
        self.elapsed_label.setText(
            "Total elapsed %s" % _fmt_duration(elapsed))
        # The engine session owns the estimate (learned per-step model +
        # live in-step rate + the auto-patch model); the view only renders.
        eta = self._last_run_eta
        if eta is not None and eta.remaining_seconds is not None:
            self.eta_label.setText(
                "Total remaining ≈ %s"
                % _fmt_remaining(eta.remaining_seconds)
            )
        else:
            self.eta_label.setText("Total remaining —")
        # Per-tile clocks (TileClocks rows, stashed by _on_tile_clocks).
        for tile, entry in self._tile_clocks.items():
            row = self._tile_rows.get(tile)
            if row is None:
                continue
            row[4].setText(_fmt_tile_clock(*entry))

    def _on_build_done(self, event):
        """One tile's terminal outcome: remember it (with the tile's own
        wall time) for the end-of-run console report."""
        tile = (event.lat, event.lon)
        started_at = self._tile_started_at.get(tile)
        seconds = (time.time() - started_at) if started_at else None
        self._tile_results[tile] = (event.ok, event.error, seconds)

    def _on_run_done(self, event):
        self._building = False
        self._last_run_eta = None
        # One last render so every row shows its frozen final clock,
        # then stop ticking (the stash stays for the visible rows).
        self._update_build_clock()
        self._elapsed_timer.stop()
        self.stop_btn.setEnabled(False)
        self.stop_btn.setText("■ Stop")
        self.setWindowTitle("Ortho4XP " + O4_Version.version)
        total_seconds = (
            time.time() - self._build_t0
            if self._build_t0 is not None else None
        )
        (summary, detail_lines) = _compose_run_report(
            sorted(self._progress_states),
            self._tile_results,
            self._progress_states,
            total_seconds,
            self._stop_requested,
        )
        print("\n".join([summary] + detail_lines))
        self._status(summary)
        self.progress_title.setText("<b>%s</b>" % summary)
        UI.is_working = False
        self._update_build_summary()
        # Re-gate the info panel for the active tile now that the run is
        # over (install toggle, Modified-airports revert re-enabled).
        self._active_changed(self.map.active_tile())

        def revert():
            # A new run may have started inside the linger window; its
            # Activity display must not be torn down under it.
            if self._building:
                return
            # Rows the user STOPPED survive the linger: their resume
            # button is the way back to the tile without hunting for it
            # on the map again, so the row — and the settings a resume
            # needs — has to outlive the run it was stopped in.
            stopped = {
                tile: state
                for tile, state in self._progress_states.items()
                if state[0] == "stopped"
            }
            for tile in list(self._tile_rows):
                if tile in stopped:
                    continue
                self._tile_rows.pop(tile)[2].deleteLater()
                self._tile_clocks.pop(tile, None)
            self._run_settings = {
                tile: settings
                for tile, settings in self._run_settings.items()
                if tile in stopped
            }
            self._progress_states = stopped
            self.map.set_progress(stopped)
            self._set_activity_box_visible(bool(stopped))
            if stopped:
                # The run is over: there is no elapsed left to report,
                # only the stopped rows waiting for a resume.
                self.progress_title.setText("")
                self.elapsed_label.setText("")
                self.eta_label.setText("")
            self._selection_changed()

        QTimer.singleShot(5000, revert)
        # Tiles the user resumed mid-run get their own follow-up run,
        # client-side.  A run the user STOPPED wholesale takes the queue
        # down with it — stop is the inverse of resume, at any scale.
        if self._stop_requested:
            self._resume_queue = []
        else:
            self._start_resume_queue()
        self.refresh_tiles()
        QApplication.beep()

    def request_stop(self):
        self._stop_requested = True
        # Stopping the whole run takes the pending resumes with it: a
        # follow-up run starting behind a wholesale stop is the opposite
        # of what the button was pressed for.
        self._resume_queue = []
        self._session.cancel()
        self.stop_btn.setText("Stopping after current step…")
        self.stop_btn.setEnabled(False)

    # ------------------------------------------------------------------
    # Console / status
    # ------------------------------------------------------------------
    def _drain_console(self):
        chunks = []
        try:
            while True:
                chunks.append(self._console_queue.get_nowait())
        except queue.Empty:
            pass
        if chunks:
            text = "".join(chunks)
            self.console.moveCursor(QTextCursor.End)
            self.console.insertPlainText(text)
            self.console.moveCursor(QTextCursor.End)

    CONSOLE_DEFAULT_LINES = 6

    def _console_default_height(self):
        metrics = self.console.fontMetrics()
        document_margin = int(self.console.document().documentMargin())
        return (
            self.CONSOLE_DEFAULT_LINES * metrics.lineSpacing()
            + 2 * (self.console.frameWidth() + document_margin)
        )

    def _apply_console_height(self, height):
        sizes = self.splitter.sizes()
        total = sum(sizes)
        if total <= 0:
            return
        height = max(0, min(int(height), total // 2))
        self.splitter.setSizes([total - height, height])

    def showEvent(self, event):
        super().showEvent(event)
        if not self._console_defaulted:
            self._console_defaulted = True
            self._sync_console_button()
            if not self._layout_restored and self.console.isVisible():
                self._apply_console_height(self._console_default_height())

    def toggle_console(self):
        self.set_console_visible(not self.console.isVisible())

    def set_console_visible(self, visible):
        """Show or hide the console drawer at a STEADY size: re-opening
        restores the height it had when hidden (default: 6 lines)."""
        if visible != self.console.isVisible():
            if visible:
                self.console.setVisible(True)
                self._apply_console_height(
                    self._console_height or self._console_default_height()
                )
            else:
                self._console_height = self.splitter.sizes()[1]
                self.console.setVisible(False)
        self._sync_console_button()

    def _sync_console_button(self):
        self.console_btn.setText(
            "Console ▴" if self.console.isVisible() else "Console ▾"
        )

    def _hover(self, lat, lon):
        self.coords_label.setText("%.3f°, %.3f°" % (lat, lon))

    def _update_zoom_label(self):
        self.zoom_label.setText(
            "z%.0f · %s" % (self.map.zoom_level(), self.map.display_code())
        )

    def _status(self, message):
        self.statusBar().showMessage(message, 8000)

    # ------------------------------------------------------------------
    def closeEvent(self, event):
        if self._building:
            answer = QMessageBox.question(
                self,
                "Build in progress",
                "A build is running. Stop it and quit?",
            )
            if answer != QMessageBox.Yes:
                event.ignore()
                return
            # Through the session, not the raw flag: a parallel run must
            # relay the cancel to its worker subprocesses — and quitting
            # must also TERMINATE them (this process dies before their
            # graceful step-end retirement; a child left behind keeps
            # building headless and races the next session's caches).
            self._session.shutdown()
            UI.red_flag = True
        tile = self.map.active_tile()
        if tile:
            self.prefs["last_lat"], self.prefs["last_lon"] = tile
        # An unresolved combo ("--", index -1) keeps the previous pref.
        if self.imagery_combo.currentIndex() >= 0:
            self.prefs["imagery"] = self.imagery_combo.currentText()
        if self.zl_combo.currentIndex() >= 0:
            self.prefs["zl"] = int(self.zl_combo.currentText())
        self.prefs["window_geometry"] = bytes(
            self.saveGeometry().toBase64()
        ).decode("ascii")
        self.prefs["splitter_state"] = bytes(
            self.splitter.saveState().toBase64()
        ).decode("ascii")
        self.prefs["console_visible"] = self.console.isVisible()
        save_prefs(self.prefs)
        event.accept()


def _fmt_date(mtime):
    if not mtime:
        return "—"
    import datetime

    return datetime.datetime.fromtimestamp(mtime).strftime("%d %b %Y %H:%M")


def _fmt_arc_seconds(resolution_arc_seconds):
    """Human text for a base-source posting, e.g. '1 arc-second (~30 m)'."""
    if not resolution_arc_seconds:
        return "unknown resolution"
    value = float(resolution_arc_seconds)
    if value < 1.0:
        text = "1/%d arc-second" % round(1.0 / value)
    elif value == int(value):
        text = "%d arc-second" % int(value)
    else:
        text = "%.2f arc-second" % value
    return "%s (~%d m)" % (text, round(value * 30))


def _elevation_row_texts(
    lat, lon, tile_custom_dem="", tile_elevation_level="auto"
):
    """The (base, airport lidar) strings for the tile-info elevation rows.

    Everything behind this is offline (registry, local files, the
    cached inset index) — see summarize_tile_elevation_sources — so it
    runs on every selection change without stalling the UI.
    ``tile_elevation_level`` steers the base-class preference so the row
    reports the same base source a build would pick.
    """
    import O4_DEM_Utils as DEM
    import O4_Airport_Elevation_Insets as ELEVATION_PROVIDERS

    summary = ELEVATION_PROVIDERS.summarize_tile_elevation_sources(
        lat,
        lon,
        DEM.base_elevation_source,
        elevation_level=tile_elevation_level,
    )
    if tile_custom_dem:
        # The tile config pins its own source; the first ";"-token is
        # the base, the rest are local insets.
        base_text = "custom: " + (
            os.path.basename(tile_custom_dem.split(";")[0])
            or tile_custom_dem
        )
    else:
        base_text = "%s, %s" % (
            summary["base_code"],
            _fmt_arc_seconds(summary["base_resolution_arc_seconds"]),
        )
        if summary["base_is_fallback"]:
            base_text += " (default)"
    if summary["fetched_airports"] is not None:
        pieces = []
        if summary["fetched_airports"]:
            pieces.append(
                "%d airport%s fetched"
                % (
                    summary["fetched_airports"],
                    "s" if summary["fetched_airports"] > 1 else "",
                )
            )
        if summary["no_coverage_airports"]:
            pieces.append(
                "%d without coverage" % summary["no_coverage_airports"]
            )
        lidar_text = " · ".join(pieces) if pieces else "no airports found"
    elif summary["inset_providers"]:
        # Sources a build WOULD fetch from (nothing downloaded yet) —
        # the fetched case above announces itself ("N airports
        # fetched"), so the bare list is unambiguous and the narrow
        # field spends its width on the source names.
        lidar_text = ", ".join(
            "%s (%s m)"
            % (code, ("%g" % resolution) if resolution else "?")
            for (code, resolution) in summary["inset_providers"]
        )
    else:
        lidar_text = "none for this region"
    return (base_text, lidar_text)


def _fmt_duration(seconds):
    seconds = int(seconds)
    if seconds < 60:
        return "%d s" % seconds
    if seconds < 3600:
        return "%d m %02d s" % (seconds // 60, seconds % 60)
    return "%d h %02d m" % (seconds // 3600, (seconds % 3600) // 60)


def _fmt_tile_clock(elapsed, remaining, finished):
    """One Activity row's clock text from a TileClocks entry.

    Finished: the final elapsed alone.  Active: "elapsed · ~remaining"
    (the estimate is the tile's OWN outstanding work).  Queued: "~est"
    alone.  A missing estimate is a dash on an active tile and empty on
    a queued one — a row of dashes before anything starts is noise.
    """
    if finished:
        return _fmt_duration(elapsed)
    if elapsed > 0:
        if remaining is not None:
            return "%s · ~%s" % (_fmt_duration(elapsed),
                                 _fmt_remaining(remaining))
        return "%s · —" % _fmt_duration(elapsed)
    if remaining is not None:
        return "~%s" % _fmt_remaining(remaining)
    return ""


def _compose_run_report(tiles, tile_results, progress_states,
                        total_seconds, stopped):
    """The end-of-run console report: ``(summary, detail_lines)``.

    One tile: a single summary line naming the tile and its build time
    (or its failure).  Several tiles: a whole-run summary line, then one
    detail line per tile — its build time, or why it failed.  A stopped
    run keeps the done/failed counts in the summary; tiles the stop (or
    a failure) prevented from finishing say so in their detail line.

    ``tile_results`` maps tile -> (ok, error, seconds) from BuildDone;
    ``seconds`` (and ``total_seconds``) may be None when no timing was
    observed (e.g. a run that never started a step).
    """
    total_text = (
        _fmt_duration(total_seconds) if total_seconds is not None else None)

    def _tile_outcome(tile):
        """(ok_or_None, phrase) — ok None means the tile never finished."""
        result = tile_results.get(tile)
        if result is None:
            (_state, label, _percent) = progress_states.get(
                tile, (None, None, 0))
            if label == "stopped":
                return (None, "stopped before finishing")
            return (None, "never started")
        (ok, error, seconds) = result
        duration = _fmt_duration(seconds) if seconds is not None else None
        if ok:
            return (True, "built in %s" % duration if duration else "built")
        reason = error or "failed (see the console log)"
        if duration:
            return (False, "failed after %s — %s" % (duration, reason))
        return (False, "failed — %s" % reason)

    if len(tiles) == 1 and not stopped:
        tile = tiles[0]
        name = FNAMES.short_latlon(*tile)
        result = tile_results.get(tile)
        if result is not None:
            (ok, _error, seconds) = result
            duration = (
                _fmt_duration(seconds) if seconds is not None
                else total_text)
            if ok:
                if duration:
                    return ("Tile %s finished in %s." % (name, duration), [])
                return ("Tile %s finished." % name, [])
            (_ok, phrase) = _tile_outcome(tile)
            return ("Tile %s %s." % (name, phrase), [])
        return ("Tile %s was not built." % name, [])

    ok_count = sum(
        1 for tile in tiles if tile_results.get(tile, (False,))[0])
    failed_count = sum(
        1 for tile in tiles
        if tile in tile_results and not tile_results[tile][0])
    if stopped:
        summary = "Build stopped%s: %d done, %d failed." % (
            " after %s" % total_text if total_text else "",
            ok_count, failed_count)
    elif failed_count:
        summary = "Build finished%s: %d ok, %d failed." % (
            " in %s" % total_text if total_text else "",
            ok_count, failed_count)
    else:
        summary = ("Build finished in %s." % total_text
                   if total_text else "Build finished.")
    detail_lines = [
        "  %s: %s" % (FNAMES.short_latlon(*tile), _tile_outcome(tile)[1])
        for tile in tiles
    ]
    return (summary, detail_lines)


def _fmt_remaining(seconds):
    """Remaining-time display: an ESTIMATE, so past two minutes it
    rounds to whole minutes — second-level digits on a figure that
    honestly drifts both ways read as a clock counting up."""
    seconds = int(seconds)
    if seconds < 120:
        return _fmt_duration(seconds)
    if seconds < 3600:
        return "%d m" % round(seconds / 60.0)
    return _fmt_duration(seconds)


def _fmt_size(nbytes):
    value = float(nbytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return "%.1f %s" % (value, unit)
        value /= 1024
