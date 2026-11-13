"""Settings ▸ Storage ▸ Convert existing tiles in the Qt window (World spec §13 M1,
§14 ``convert_box``; the Mac app's ``ConvertTilesSection.swift``, the same
words): the per-tile ``zOrtho4XP_`` packs moved into the World pack by
``o4_engine.world_migrate`` -- a choice of what to keep (owner
2026-11-11T15:32Z, ``world_retire``: keep all, keep the tiles with custom
airports, make everything dynamic; Measure shows each choice's figures
before anything moves), Measure (the dry run), Convert…, Stop, Undo… and
Free space… (removes the local tiles made dynamic).  The work runs on a
daemon thread; the engine writes every result
sentence.  While it runs (owner 2026-11-11T15:32Z) a bar counts the tiles
(``WorldMigrateProgress``: "Measuring: N of M tiles · <tile>"), Cancel
stops it cleanly, and :attr:`ConvertTilesSection.running_changed` lets
the window around it hold its Done until the step has a result line.

Owner 2026-11-12T19:08Z: Measure runs on its own process
(``o4_engine.world_measure``) and starts by itself -- the main window
calls :func:`auto_measure` at launch and before Settings opens, the
section after a move, undo or Free space -- when Custom Scenery holds
per-tile packs and the kept measure is missing or stale.  The section
shows the kept result at once with "Measured 12 min ago", follows a
measure already running (its count, read every second), and every count
carries the time since the step began.
"""

from __future__ import annotations

import contextlib
import time

from O4_Qt_Library import emit_from_thread
from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

__all__ = ["ConvertTilesSection", "TITLE", "INTRO", "auto_measure"]

# The words of SceneryKit's ``O4WorldMigrateText`` (WorldMigrate.swift).
TITLE = "Convert existing tiles"
INTRO = ("Moves your per-tile ortho packs (zOrtho4XP_…) into the World pack, "
         "so X-Plane can take new tiles while it runs. Choose what to keep; "
         "Measure shows what each choice frees and still needs before "
         "anything moves. The tile folders leave Custom Scenery for the "
         "World pack's keeping, files on another drive are never deleted, "
         "and Undo moves every tile back.")
#: ``world_retire.CHOICES``: (id, title, the line shown before a measure).
CHOICES = (
    ("keep_all", "Keep all existing tiles",
     "Every tile moves as it is; a tile another tool built is adopted: its "
     "mesh kept, its imagery low-res and sharpened as you fly."),
    ("keep_custom", "Keep tiles with custom airports, make the rest dynamic",
     "Tiles holding an installed airport pack are kept (a tile another tool "
     "built is adopted: its mesh kept); the rest are draped ahead in flight "
     "or built when you fly there."),
    ("dynamic", "Make everything dynamic",
     "Every tile is draped ahead in flight or built when you fly there; no "
     "other drive is needed."),
)
CONFIRM_DYNAMIC = ("Tiles made dynamic are drawn by the World pack, draped "
                   "or built when you fly there; tiles not built by "
                   "XPTerrainBuilder become our drape or build, not the same "
                   "tile. Their links to another drive are removed from "
                   "Custom Scenery (Undo puts them back).")
FREE_SPACE = "Free space…"
FREE_TITLE = "Remove the dynamic tiles from this Mac?"
FREE_TEXT = ("Quit X-Plane first. The folders of the tiles made dynamic "
             "are deleted from this Mac and Undo can no longer bring them "
             "back; they are draped or built when you fly there. Files on "
             "other drives are never touched.")
MEASURE, CONVERT, STOP, UNDO = "Measure", "Convert…", "Cancel", "Undo…"
MEASURING = ("Measuring (a few tiles are converted into a temporary folder "
             "to time it)…")
MEASURING_BACKGROUND = "Measuring in the background…"
SAMPLING = "Timing a sample"
ADOPTING = "Reading tiles made dynamic before"
ELAPSED = "{time} elapsed"
MEASURED_JUST_NOW = "Measured just now"
MEASURED_MINUTES = "Measured {n} min ago"
MEASURED_HOURS = "Measured {n} h ago"
MEASURED_DAYS = "Measured {n} days ago"
CONVERTING = "Converting…"
CONFIRM_TITLE = "Move these tiles into the World pack?"
CONFIRM_TEXT = ("Quit X-Plane first. Each tile folder on this Mac moves "
                "out of Custom Scenery into the World pack's keeping "
                "(XPTerrainBuilder_world_migrate, beside Custom Scenery) "
                "and the World pack draws it (a copy of scenery_packs.ini "
                "is kept). You can stop at any time and convert again "
                "later.")
UNDO_TITLE = "Put every converted tile back?"
UNDO_TEXT = ("Quit X-Plane first. Each tile folder moves back into Custom "
             "Scenery, turned on, and the World pack gives the tile back.")
NOTE_STYLE = "color: gray; font-size: 11px;"


def phase_verb(phase: str) -> str:
    """The words of a ``WorldMigrateProgress`` phase."""
    return {"measure": "Measuring", "sample": SAMPLING,
            "adopt": ADOPTING}.get(phase, "Converting")


def progress_line(phase: str, done: int, total: int, tile: str = "",
                  elapsed=None) -> str:
    """The count under the bar, with the time since the step began
    (SceneryKit ``O4WorldMigrateText.progressLine``)."""
    line = "%s: %s of %s tiles" % (phase_verb(phase), format(done, ","),
                                   format(total, ","))
    line += " · " + tile if tile else ""
    return line + (" · " + elapsed_text(elapsed) if elapsed is not None else "")


def elapsed_text(seconds: float) -> str:
    """``4:07 elapsed`` (h:mm:ss past an hour; ``elapsedText``)."""
    total = max(0, int(seconds))
    h, m, sec = total // 3600, total % 3600 // 60, total % 60
    clock = "%d:%02d:%02d" % (h, m, sec) if h else "%d:%02d" % (m, sec)
    return ELAPSED.replace("{time}", clock)


def measured_ago(seconds: float) -> str:
    """``Measured 12 min ago`` (``measuredAgo``)."""
    s = max(0, int(seconds))
    if s < 60:
        return MEASURED_JUST_NOW
    if s < 3600:
        return MEASURED_MINUTES.replace("{n}", str(s // 60))
    if s < 2 * 86400:
        return MEASURED_HOURS.replace("{n}", str(s // 3600))
    return MEASURED_DAYS.replace("{n}", str(s // 86400))


def auto_measure(scenery_dir: str) -> bool:
    """Start Measure in the background when the engine says so
    (``world_measure.start_auto``); never raises."""
    from o4_engine import world_measure as MEASURE
    try:
        return MEASURE.start_auto(scenery_dir)
    except Exception:
        return False


class ConvertTilesSection(QWidget):
    """Measure, Convert…, Stop and Undo… over ``world_migrate``."""

    finished = Signal(object)
    progress = Signal(object)
    #: True while a step runs; False when it ends with its result line.
    running_changed = Signal(bool)

    def __init__(self, scenery_dir: str = "", parent=None):
        super().__init__(parent)
        self.scenery_dir = scenery_dir
        self.measured = None
        self.running = False
        #: A step finished and its result line is shown.
        self.has_result = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(QLabel("<b>%s</b>" % TITLE))
        intro = QLabel(INTRO)
        intro.setWordWrap(True)
        intro.setStyleSheet(NOTE_STYLE)
        layout.addWidget(intro)
        self.choice_group = QButtonGroup(self)
        self.choice_notes = {}
        for number, (key, title, hint) in enumerate(CHOICES):
            button = QRadioButton(title)
            button.setChecked(number == 0)
            self.choice_group.addButton(button, number)
            note = QLabel(hint)
            note.setWordWrap(True)
            note.setStyleSheet(NOTE_STYLE)
            note.setContentsMargins(22, 0, 0, 0)
            self.choice_notes[key] = note
            layout.addWidget(button)
            layout.addWidget(note)
        row = QHBoxLayout()
        self.measure_btn = QPushButton(MEASURE)
        self.measure_btn.clicked.connect(lambda: self.run(dry_run=True))
        self.convert_btn = QPushButton(CONVERT)
        self.convert_btn.setEnabled(False)
        self.convert_btn.clicked.connect(self.ask_convert)
        self.stop_btn = QPushButton(STOP)
        self.stop_btn.setVisible(False)
        self.stop_btn.clicked.connect(self.stop)
        self.undo_btn = QPushButton(UNDO)
        self.undo_btn.clicked.connect(self.ask_undo)
        self.free_btn = QPushButton(FREE_SPACE)
        self.free_btn.clicked.connect(self.ask_free)
        for button in (self.measure_btn, self.convert_btn, self.stop_btn):
            row.addWidget(button)
        row.addStretch(1)
        row.addWidget(self.free_btn)
        row.addWidget(self.undo_btn)
        layout.addLayout(row)
        self.bar = QProgressBar()
        self.bar.setTextVisible(False)
        self.bar.setVisible(False)
        layout.addWidget(self.bar)
        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet(NOTE_STYLE)
        layout.addWidget(self.status_label)
        self.measured_label = QLabel("")
        self.measured_label.setStyleSheet(NOTE_STYLE)
        layout.addWidget(self.measured_label)
        self.choice_group.idToggled.connect(
            lambda _id, _on: self.convert_btn.setEnabled(
                not self.running and self._to_move() > 0))
        self.finished.connect(self._on_finished)
        self.progress.connect(self._on_progress)
        #: when the running step began; its last count; when the shown
        #: measure was taken; following a measure started elsewhere.
        self.started_at = None
        self.last_count = None
        self._words = ""
        self._step = "measure"
        self.measured_at = None
        self.following = False
        self.clock = QTimer(self)
        self.clock.setInterval(1000)
        self.clock.timeout.connect(self._tick)
        self.clock.start()
        self.sync_measure()

    def _busy(self, on: bool, text: str = "", cancel: bool = True) -> None:
        self.running = on
        for button in (self.measure_btn, self.undo_btn, self.free_btn):
            button.setEnabled(not on)
        for button in self.choice_group.buttons():
            button.setEnabled(not on)
        self.convert_btn.setEnabled(not on and self._to_move() > 0)
        self.stop_btn.setVisible(on and cancel)
        self.stop_btn.setEnabled(True)
        self.bar.setRange(0, 0)             # busy until the first count
        self.bar.setVisible(on)
        self.last_count = None
        self.started_at = time.time() if on else None
        self._words = text
        if on:
            self.has_result = False
        if text:
            self.status_label.setText(text)
        self.running_changed.emit(on)

    def _on_progress(self, event) -> None:
        if not self.running or not event.total:
            return
        self.last_count = (event.phase, int(event.done), int(event.total),
                           event.tile or "")
        self.bar.setRange(0, int(event.total))
        self.bar.setValue(int(event.done))
        self._show_line()

    def _show_line(self) -> None:
        """The count (or the step's words) with the time since it began."""
        if not self.running or self.started_at is None:
            return
        elapsed = time.time() - self.started_at
        if self.last_count:
            self.status_label.setText(progress_line(*self.last_count,
                                                    elapsed=elapsed))
        else:
            words = MEASURING_BACKGROUND if self.following else self._words
            self.status_label.setText(words + " " + elapsed_text(elapsed))

    def _tick(self) -> None:
        """Every second: the elapsed time, the measure followed, and how
        long ago the shown measure was taken."""
        if self.following:
            self._follow()
        self._show_line()
        self.measured_label.setText(
            measured_ago(time.time() - self.measured_at)
            if self.measured_at else "")

    def _show_measured(self, result) -> None:
        self.measured = result
        self.measured_at = (result or {}).get("measured_at")
        for row in (result or {}).get("choices") or ():
            if row.get("id") in self.choice_notes:
                self.choice_notes[row["id"]].setText(row.get("line", ""))

    def sync_measure(self) -> None:
        """The kept measure (``world_measure.state``) shown while nothing
        runs here, and a measure running elsewhere followed."""
        from o4_engine import world_measure as MEASURE
        if self.running:
            return
        try:
            state = MEASURE.state(self.scenery_dir)
        except Exception:                   # no folder: nothing kept
            return
        if state.get("result"):
            self._show_measured({**state["result"],
                                 "measured_at": state.get("measured_at")})
            self.status_label.setText(state["result"].get("summary", ""))
        if state.get("running"):
            self.following = True
            self._busy(True, MEASURING_BACKGROUND)
            self.started_at = state.get("started_at") or time.time()
            self._follow(state)
        self._tick()

    def _follow(self, state=None) -> None:
        """The followed measure's count (``world_measure.live``), or at
        its end the kept result."""
        from o4_engine import world_measure as MEASURE
        state = state or MEASURE.live()
        if not state.get("running"):
            try:
                state = MEASURE.state(self.scenery_dir)
            except Exception:
                state = {"running": False}
        if state.get("running"):
            count = state.get("progress") or {}
            if count.get("total"):
                self.last_count = (count["phase"], int(count["done"]),
                                   int(count["total"]), count.get("tile", ""))
                self.bar.setRange(0, int(count["total"]))
                self.bar.setValue(int(count["done"]))
            return
        self.following = False
        result = state.get("result")
        if result:
            self._show_measured({**result, "measured_at": state.get("measured_at")})
        self.has_result = True
        self._busy(False, (result or {}).get("summary", ""))

    def _to_move(self) -> int:
        """Tiles the chosen choice moves, adopts again or makes dynamic
        (the last measure's figures)."""
        for row in (self.measured or {}).get("choices") or ():
            if row.get("id") == self.choice():
                return sum(int(row.get(k) or 0)
                           for k in ("kept", "dynamic", "again"))
        acts = ((self.measured or {}).get("totals") or {}).get("by_action", {})
        return sum(acts.get(a, 0) for a in ("copy", "stage", "resume"))

    def choice(self) -> str:
        """The chosen ``world_retire`` choice's id."""
        return CHOICES[max(0, self.choice_group.checkedId())][0]

    def run(self, dry_run: bool, revert: bool = False,
            purge: bool = False) -> None:
        """Start the dry run, the migration under the chosen choice,
        (``revert``) its undo, or (``purge``) Free space."""
        from o4_engine import world_measure as MEASURE
        from o4_engine import world_migrate as MIGRATE
        if self.running:
            return
        self._busy(True, MEASURING if dry_run else CONVERTING,
                   cancel=not (revert or purge))
        scenery, choice = self.scenery_dir, self.choice()
        self._step = "measure" if dry_run and not purge else (
            "undo" if revert else "free" if purge else "convert")

        def counted(event):                 # on the worker: queued signal
            if type(event).__name__ == "WorldMigrateProgress":
                with contextlib.suppress(RuntimeError):   # window closed
                    self.progress.emit(event)
        if self._step == "measure":         # its own process (world_measure)
            work = lambda: MEASURE.measure(scenery, counted)   # noqa: E731
        else:
            MEASURE.stop()                  # a move outdates a measure
            work = lambda: MIGRATE.run_command(   # noqa: E731
                dry_run, revert, None, scenery, emit=counted, choice=choice,
                purge=purge)
        emit_from_thread(work, self.finished, "o4-qt-world-migrate")

    def stop(self) -> None:
        """Cancel: the engine stops after the tiles in hand."""
        from o4_engine import world_measure as MEASURE
        from o4_engine import world_migrate as MIGRATE
        self.stop_btn.setEnabled(False)
        MIGRATE.stop()
        MEASURE.stop()

    def ask_convert(self) -> None:
        text = CONFIRM_TEXT
        if self.choice() != CHOICES[0][0]:
            text += " " + CONFIRM_DYNAMIC
        if QMessageBox.question(self, CONFIRM_TITLE, text) == QMessageBox.Yes:
            self.run(dry_run=False)

    def ask_free(self) -> None:
        if QMessageBox.question(self, FREE_TITLE, FREE_TEXT) == QMessageBox.Yes:
            self.run(dry_run=False, purge=True)

    def ask_undo(self) -> None:
        if QMessageBox.question(self, UNDO_TITLE, UNDO_TEXT) == QMessageBox.Yes:
            self.run(dry_run=False, revert=True)

    def _on_finished(self, result) -> None:
        step = getattr(self, "_step", "measure")
        if isinstance(result, Exception):
            self.measured, self.measured_at = None, None
            self.has_result = True
            self._busy(False, str(result))
            return
        measured = result if result.get("action") == "dry_run" else None
        self._show_measured(measured)
        if measured and not self.measured_at:
            self.measured_at = time.time()
        self.has_result = True
        self._busy(False, result.get("summary", ""))
        self._tick()
        if step != "measure" and auto_measure(self.scenery_dir):
            self.sync_measure()             # Custom Scenery changed: follow
