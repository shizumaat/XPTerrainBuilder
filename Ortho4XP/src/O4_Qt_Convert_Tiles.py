"""Library ▸ Convert existing tiles in the Qt window (World spec §13 M1,
§14 ``convert_box``; the Mac app's ``ConvertTilesSection.swift``, the same
words): the per-tile ``zOrtho4XP_`` packs moved into the World pack by
``o4_engine.world_migrate`` -- Measure (the dry run), Convert…, Stop and
Undo….  The work runs on a daemon thread; the engine writes every result
sentence.
"""

from __future__ import annotations

from O4_Qt_Library import emit_from_thread
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

__all__ = ["ConvertTilesSection", "TITLE", "INTRO"]

# The words of SceneryKit's ``O4WorldMigrateText`` (WorldMigrate.swift).
TITLE = "Convert existing tiles"
INTRO = ("Moves your per-tile ortho packs (zOrtho4XP_…) into the World pack, "
         "so X-Plane can take new tiles while it runs. Tiles on another drive "
         "get a small local copy and their files stay where they are. Nothing "
         "is deleted: Undo puts every tile back.")
MEASURE, CONVERT, STOP, UNDO = "Measure", "Convert…", "Stop", "Undo…"
MEASURING = ("Measuring (a few tiles are converted into a temporary folder "
             "to time it)…")
CONVERTING = "Converting…"
CONFIRM_TITLE = "Move these tiles into the World pack?"
CONFIRM_TEXT = ("Quit X-Plane first. Each tile's own pack is turned off in "
                "scenery_packs.ini (a copy of the file is kept) and the World "
                "pack draws it. You can stop at any time and convert again "
                "later.")
UNDO_TITLE = "Put every converted tile back?"
UNDO_TEXT = ("Quit X-Plane first. Each tile's own pack is turned on again and "
             "the World pack gives the tile back.")
NOTE_STYLE = "color: gray; font-size: 11px;"


class ConvertTilesSection(QWidget):
    """Measure, Convert…, Stop and Undo… over ``world_migrate``."""

    finished = Signal(object)

    def __init__(self, scenery_dir: str = "", parent=None):
        super().__init__(parent)
        self.scenery_dir = scenery_dir
        self.measured = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(QLabel("<b>%s</b>" % TITLE))
        intro = QLabel(INTRO)
        intro.setWordWrap(True)
        intro.setStyleSheet(NOTE_STYLE)
        layout.addWidget(intro)
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
        for button in (self.measure_btn, self.convert_btn, self.stop_btn):
            row.addWidget(button)
        row.addStretch(1)
        row.addWidget(self.undo_btn)
        layout.addLayout(row)
        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet(NOTE_STYLE)
        layout.addWidget(self.status_label)
        self.finished.connect(self._on_finished)

    def _busy(self, on: bool, text: str = "") -> None:
        for button in (self.measure_btn, self.undo_btn):
            button.setEnabled(not on)
        self.convert_btn.setEnabled(not on and self._to_move() > 0)
        self.stop_btn.setVisible(on)
        if text:
            self.status_label.setText(text)

    def _to_move(self) -> int:
        acts = ((self.measured or {}).get("totals") or {}).get("by_action", {})
        return sum(acts.get(a, 0) for a in ("copy", "stage", "resume"))

    def run(self, dry_run: bool, revert: bool = False) -> None:
        """Start the dry run, the migration or (``revert``) its undo."""
        from o4_engine import world_migrate as MIGRATE
        self._busy(True, MEASURING if dry_run else CONVERTING)
        scenery = self.scenery_dir
        emit_from_thread(
            lambda: MIGRATE.run_command(dry_run, revert, None, scenery),
            self.finished, "o4-qt-world-migrate")

    def stop(self) -> None:
        from o4_engine import world_migrate as MIGRATE
        MIGRATE.stop()

    def ask_convert(self) -> None:
        if QMessageBox.question(self, CONFIRM_TITLE, CONFIRM_TEXT) == \
                QMessageBox.Yes:
            self.run(dry_run=False)

    def ask_undo(self) -> None:
        if QMessageBox.question(self, UNDO_TITLE, UNDO_TEXT) == QMessageBox.Yes:
            self.run(dry_run=False, revert=True)

    def _on_finished(self, result) -> None:
        if isinstance(result, Exception):
            self.measured = None
            self._busy(False, str(result))
            return
        self.measured = result if result.get("action") == "dry_run" else None
        self._busy(False, result.get("summary", ""))
