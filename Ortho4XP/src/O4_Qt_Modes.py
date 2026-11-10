"""The three modes in the Qt window (RULINGS 2026-11-10j; spec
``docs/specs/flight-manager-and-world-20261110.md`` §14, lane U1).

The Mac app's ``AppMode.swift``, ``FlyPane.swift`` and ``LibraryPane.swift``
are the layout; ``tests/test_qt_layout_parity.py`` holds the two equal.

- :class:`ModeSwitch` — Build · Fly · Library, leading the toolbar.
- :class:`FlyOfferBanner` — "X-Plane has a flight loaded. Open Fly" above
  the side pane in Build and Library; never switches by itself.
- :class:`FlyPane` — Fly mode's pane: the follow line under a placeholder
  until the flight manager lands (lanes F1b/U2).
- :class:`LibraryPane` — Library mode's pane: the built tiles, Storage
  (moved from Settings) and the patch library.
"""

from __future__ import annotations

import O4_App_Modes as MODES
import O4_Glossary as GLOSSARY
import O4_Qt_Library as QTLIB
import O4_Qt_Settings_Storage as QTSTORAGE
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)


def mode_title(mode: str) -> str:
    """The segment's word (the glossary's ``mode_<mode>``)."""
    return GLOSSARY.TERMS["mode_" + mode]


class ModeSwitch(QWidget):
    """A segmented Build · Fly · Library control."""

    mode_changed = Signal(str)

    def __init__(self, mode=MODES.DEFAULT, parent=None):
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.buttons = {}
        for key in MODES.MODES:
            button = QToolButton()
            button.setText(mode_title(key))
            button.setCheckable(True)
            button.setToolTip("Show the %s pane" % mode_title(key))
            self.group.addButton(button)
            row.addWidget(button)
            self.buttons[key] = button
            button.toggled.connect(
                lambda on, k=key: on and self.mode_changed.emit(k))
        self.set_mode(mode)

    def mode(self) -> str:
        return next(k for k, b in self.buttons.items() if b.isChecked())

    def set_mode(self, mode: str):
        """Check ``mode``'s segment (emits :attr:`mode_changed` on a change)."""
        self.buttons[MODES.restore(mode)].setChecked(True)


class FlyOfferBanner(QFrame):
    """The offer to open Fly when X-Plane has a flight loaded."""

    open_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        self.offer = MODES.FlyOffer()
        row = QHBoxLayout(self)
        row.setContentsMargins(8, 6, 8, 6)
        self.text_label = QLabel(MODES.OFFER_TEXT)
        self.text_label.setWordWrap(True)
        row.addWidget(self.text_label, 1)
        self.open_btn = QPushButton(MODES.OFFER_OPEN)
        self.open_btn.clicked.connect(self._open)
        row.addWidget(self.open_btn)
        self.dismiss_btn = QPushButton(MODES.OFFER_DISMISS)
        self.dismiss_btn.clicked.connect(self._dismiss)
        row.addWidget(self.dismiss_btn)
        self.setVisible(False)

    def observe(self, event, mode):
        """One ``ImageryFollowStatus`` event, in the window's mode."""
        shown = self.offer.observe(
            getattr(event, "state", ""), getattr(event, "xplane", False),
            int(getattr(event, "flight_loads", 0) or 0), mode)
        self.setVisible(shown)

    def mode_changed(self, mode):
        if mode == "fly":
            self._dismiss()

    def _open(self):
        self._dismiss()
        self.open_requested.emit()

    def _dismiss(self):
        self.offer.dismiss()
        self.setVisible(False)


class FlyPane(QWidget):
    """Fly mode's pane: a placeholder and the follow line (``follow_line``,
    moved here from the Build pane)."""

    def __init__(self, follow_line, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        title = QLabel("<b>%s</b>" % mode_title("fly"))
        layout.addWidget(title)
        self.placeholder = QLabel(MODES.FLY_PLACEHOLDER)
        self.placeholder.setWordWrap(True)
        self.placeholder.setStyleSheet("color: gray;")
        layout.addWidget(self.placeholder)
        self.follow_line = follow_line
        layout.addWidget(follow_line)
        layout.addStretch(1)


class LibraryPane(QWidget):
    """Library mode's pane, top to bottom: the built tiles
    (``tiles_box``), Storage (``storage``, from Settings) and the patch
    library (``patch_box``)."""

    def __init__(self, working_dir, scenery_dir, building=lambda: False,
                 on_rebuild=None, on_changed=None, restore_pack=None, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.addWidget(QLabel("<b>%s</b>" % mode_title("library")))
        self.tiles_box = QTLIB.LibraryTilesSection(
            None, working_dir, scenery_dir, building=building,
            on_rebuild=on_rebuild, on_changed=on_changed,
            restore_pack=restore_pack)
        layout.addWidget(self.tiles_box, 1)
        self.storage = QTSTORAGE.StorageSection(busy=building)
        layout.addWidget(self.storage)
        self.patch_box = self.tiles_box.patch_box
        layout.addWidget(self.patch_box)

    def refresh(self, working_dir, scenery_dir):
        """Read the tiles folder, the caches and the data folder again
        (each time the pane is shown)."""
        self.tiles_box.working_dir = working_dir
        self.tiles_box.scenery_dir = scenery_dir
        self.patch_box.working_dir = working_dir
        self.tiles_box.refresh()
        self.storage.refresh()


class LibraryPointer(QWidget):
    """Settings ▸ Storage's pointer: the data folder's sizes, Clear and
    the disk budget's use moved to Library mode (Mac: ``StoragePointer``)."""

    def __init__(self, show_library, parent=None):
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 4, 0, 4)
        text = QLabel(MODES.STORAGE_POINTER)
        text.setWordWrap(True)
        row.addWidget(text, 1)
        self.show_btn = QPushButton(MODES.STORAGE_POINTER_BUTTON)
        self.show_btn.clicked.connect(show_library)
        row.addWidget(self.show_btn)

    @staticmethod
    def matches(query: str) -> bool:
        return any(word in query.lower() for word in (
            "storage", "disk", "space", "cache", "clear", "budget"))
