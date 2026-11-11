"""The start's World onboarding in the Qt window (#2007, RULINGS
2026-11-11a; the Mac app's ``WorldOnboardSheet.swift``, the same words as
SceneryKit's ``O4WorldOnboardText``).

When no World folder exists at the start, the engine makes it
(``world_commands.world_onboard``); when per-tile ortho packs could move
into it and were never offered (RULINGS 2026-11-11h (2): the engine
records the offer, Not now included), :class:`OnboardDialog` asks once what managing them gives and
offers Move… (Convert existing tiles, its dry run's numbers first) or Not
now (Library ▸ Convert existing tiles asks again).  Spec §13 M1 holds:
the packs' ``scenery_packs.ini`` rows are disabled, never removed.
"""

from __future__ import annotations

import O4_Qt_Convert_Tiles as QTCONVERT
from O4_Qt_Library import emit_from_thread
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

__all__ = ["TITLE", "INTRO", "ADVANTAGES", "NOTE", "MOVE", "NOT_NOW", "DONE",
           "OnboardDialog", "check_at_launch"]

TITLE = "Let XPTerrainBuilder manage your ortho tiles?"
INTRO = ("XPTerrainBuilder can move the {count} ortho tile(s) you already "
         "have into its World folder in Custom Scenery.")
ADVANTAGES = ("One disk budget: everything the app keeps fits the space you "
              "give it.|Low-res placeholders: fly anywhere, sharp imagery "
              "arrives as you fly.|Build-ahead and the flight manager make the "
              "scenery for your flights.|Safe give-back: nothing is deleted, "
              "and Undo puts every tile back.")
NOTE = ("Quit X-Plane first. Not now: ask again from Library ▸ Convert "
        "existing tiles.")
MOVE, NOT_NOW, DONE = "Move…", "Not now", "Done"
NOTE_STYLE = "color: gray; font-size: 11px;"


class OnboardDialog(QDialog):
    """What managing the tiles gives; Move… or Not now."""

    def __init__(self, offer: int, scenery_dir: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(TITLE)
        self.scenery_dir = scenery_dir
        self.convert_box = None
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<b>%s</b>" % TITLE))
        intro = QLabel(INTRO.format(count=offer))
        intro.setWordWrap(True)
        layout.addWidget(intro)
        for line in ADVANTAGES.split("|"):
            label = QLabel("✓ " + line)
            label.setWordWrap(True)
            layout.addWidget(label)
        note = QLabel(NOTE)
        note.setWordWrap(True)
        note.setStyleSheet(NOTE_STYLE)
        layout.addWidget(note)
        self.body = layout
        row = QHBoxLayout()
        row.addStretch(1)
        self.not_now_btn = QPushButton(NOT_NOW)
        self.not_now_btn.clicked.connect(self.reject)
        row.addWidget(self.not_now_btn)
        self.move_btn = QPushButton(MOVE)
        self.move_btn.setDefault(True)
        self.move_btn.clicked.connect(self.move)
        row.addWidget(self.move_btn)
        layout.addLayout(row)
        self.resize(520, 0)

    def move(self):
        """Convert existing tiles, measuring at once (the numbers first)."""
        if self.convert_box is None:
            self.convert_box = QTCONVERT.ConvertTilesSection(self.scenery_dir)
            self.body.insertWidget(self.body.count() - 1, self.convert_box)
            self.convert_box.run(dry_run=True)
        self.move_btn.setVisible(False)
        self.not_now_btn.setText(DONE)


class _Onboarding(QObject):
    """``world_onboard`` on a thread; the dialog when it asks."""

    ready = Signal(object)

    def __init__(self, window, scenery_dir: str):
        super().__init__(window)
        self.window = window
        self.scenery_dir = scenery_dir
        self.dialog = None
        self.ready.connect(self._ready)

    def start(self):
        from o4_engine import world_commands as WORLD
        scenery = self.scenery_dir
        emit_from_thread(lambda: WORLD.world_onboard(scenery), self.ready,
                         "o4-qt-world-onboard")

    def _ready(self, result):
        if isinstance(result, Exception) or not result.get("offer"):
            return
        self.dialog = OnboardDialog(int(result["offer"]), self.scenery_dir, self.window)
        self.dialog.show()


def check_at_launch(window, scenery_dir: str):
    """At the start: make the World folder when absent, then ask once."""
    if not scenery_dir:
        return None
    onboarding = _Onboarding(window, scenery_dir)
    onboarding.start()
    return onboarding
