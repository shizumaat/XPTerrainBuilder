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
"""

from __future__ import annotations

import contextlib

from O4_Qt_Library import emit_from_thread
from PySide6.QtCore import Signal
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

__all__ = ["ConvertTilesSection", "TITLE", "INTRO"]

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


def progress_line(phase: str, done: int, total: int, tile: str = "") -> str:
    """The count under the bar (SceneryKit ``O4WorldMigrateText.progressLine``)."""
    verb = "Measuring" if phase == "measure" else "Converting"
    line = "%s: %s of %s tiles" % (verb, format(done, ","), format(total, ","))
    return line + (" · " + tile if tile else "")


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
        self.choice_group.idToggled.connect(
            lambda _id, _on: self.convert_btn.setEnabled(
                not self.running and self._to_move() > 0))
        self.finished.connect(self._on_finished)
        self.progress.connect(self._on_progress)

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
        if on:
            self.has_result = False
        if text:
            self.status_label.setText(text)
        self.running_changed.emit(on)

    def _on_progress(self, event) -> None:
        if not self.running or not event.total:
            return
        self.bar.setRange(0, int(event.total))
        self.bar.setValue(int(event.done))
        self.status_label.setText(progress_line(
            event.phase, event.done, event.total, event.tile))

    def _to_move(self) -> int:
        """Tiles the chosen choice moves or makes dynamic (the last
        measure's figures)."""
        for row in (self.measured or {}).get("choices") or ():
            if row.get("id") == self.choice():
                return int(row.get("kept", 0)) + int(row.get("dynamic", 0))
        acts = ((self.measured or {}).get("totals") or {}).get("by_action", {})
        return sum(acts.get(a, 0) for a in ("copy", "stage", "resume"))

    def choice(self) -> str:
        """The chosen ``world_retire`` choice's id."""
        return CHOICES[max(0, self.choice_group.checkedId())][0]

    def run(self, dry_run: bool, revert: bool = False,
            purge: bool = False) -> None:
        """Start the dry run, the migration under the chosen choice,
        (``revert``) its undo, or (``purge``) Free space."""
        from o4_engine import world_migrate as MIGRATE
        self._busy(True, MEASURING if dry_run else CONVERTING,
                   cancel=not (revert or purge))
        scenery, choice = self.scenery_dir, self.choice()

        def counted(event):                 # on the worker: queued signal
            if type(event).__name__ == "WorldMigrateProgress":
                with contextlib.suppress(RuntimeError):   # window closed
                    self.progress.emit(event)
        emit_from_thread(
            lambda: MIGRATE.run_command(dry_run, revert, None, scenery,
                                        emit=counted, choice=choice,
                                        purge=purge),
            self.finished, "o4-qt-world-migrate")

    def stop(self) -> None:
        """Cancel: the engine stops after the tiles in hand."""
        from o4_engine import world_migrate as MIGRATE
        self.stop_btn.setEnabled(False)
        MIGRATE.stop()

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
        if isinstance(result, Exception):
            self.measured = None
            self.has_result = True
            self._busy(False, str(result))
            return
        self.measured = result if result.get("action") == "dry_run" else None
        for row in (self.measured or {}).get("choices") or ():
            if row.get("id") in self.choice_notes:
                self.choice_notes[row["id"]].setText(row.get("line", ""))
        self.has_result = True
        self._busy(False, result.get("summary", ""))
