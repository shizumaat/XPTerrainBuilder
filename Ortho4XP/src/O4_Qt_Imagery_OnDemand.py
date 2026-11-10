"""Imagery on demand in the Qt window (#1992 P4; the Mac app's
``ImageryFollowLine`` and ``TilePinRow``, same words —
``O4_Imagery_OnDemand_Text``).

* :class:`FollowStatusLine` -- the activity area's line while the follow
  job runs: every ``ImageryFollowStatus`` field (headline and detail),
  and "Follow X-Plane" / "Stop Following", so a flight needs no Terminal.
  Shown while the world switch is on or a job runs.
* :class:`TilePinRow` -- the tile pane's "Resolution" row on an on-demand
  or pinned tile: its state and "Always keep full resolution" / "Let it
  go low-res again" (engine ``imagery_pin``).
* :func:`pin_tile` -- the pin on a daemon thread (the Library uses it
  too); refused while a build runs, as the engine command is.
"""
from __future__ import annotations

import O4_Imagery_OnDemand_Text as TEXT
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

__all__ = ["FollowStatusLine", "TilePinRow", "pin_tile", "BUSY_PIN"]

NOTE_STYLE = "color: gray; font-size: 11px;"
BUSY_PIN = "A build is running; pin or unpin the tile when it ends."


def pin_tile(lat, lon, pinned, signal, busy=lambda: False, working_dir=""):
    """``imagery_pin`` for one tile on a daemon thread; its reply (or the
    error) is emitted on ``signal``."""
    from O4_Qt_Library import emit_from_thread  # it imports this module
    if busy():
        signal.emit(RuntimeError(BUSY_PIN))
        return

    def work():
        from o4_engine.imagery_ondemand import imagery_pin
        return imagery_pin(int(lat), int(lon), working_dir=working_dir,
                           pinned=bool(pinned))
    emit_from_thread(work, signal, "o4-qt-imagery-pin")


class FollowStatusLine(QWidget):
    """The follow job's line: headline, detail, and its Start/Stop."""

    #: True: start following; False: stop.
    toggle_requested = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        self.headline = QLabel(TEXT.FOLLOW_TEMPLATES["stopped"])
        self.headline.setWordWrap(True)
        top.addWidget(self.headline, 1)
        self.toggle_btn = QPushButton(TEXT.FOLLOW_START_TITLE)
        self.toggle_btn.clicked.connect(
            lambda: self.toggle_requested.emit(not self.running))
        top.addWidget(self.toggle_btn, 0)
        layout.addLayout(top)
        self.detail = QLabel("")
        self.detail.setWordWrap(True)
        self.detail.setStyleSheet(NOTE_STYLE)
        self.detail.setVisible(False)
        layout.addWidget(self.detail)
        self.running = False
        self.status = None

    def show_status(self, status) -> None:
        """One ``ImageryFollowStatus`` (the event, or its dict)."""
        fields = status if isinstance(status, dict) else vars(status)
        self.status = dict(fields)
        headline, detail = TEXT.follow_lines(fields)
        self.headline.setText(headline)
        self.detail.setText(detail)
        self.detail.setVisible(True)
        self.set_running(fields.get("state") not in ("stopped", "error"))

    def set_running(self, running: bool) -> None:
        self.running = bool(running)
        self.toggle_btn.setText(TEXT.FOLLOW_STOP_TITLE if self.running
                                else TEXT.FOLLOW_START_TITLE)


class TilePinRow(QWidget):
    """The tile pane's "Resolution" row of an on-demand or pinned tile."""

    #: (lat, lon, pinned) the user asked for.
    pin_requested = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        self.label = QLabel("—")
        self.label.setWordWrap(True)
        self.label.setToolTip(TEXT.PIN_HELP)
        layout.addWidget(self.label, 1)
        self.button = QPushButton(TEXT.PIN_TITLE)
        self.button.setToolTip(TEXT.PIN_HELP)
        self.button.clicked.connect(self._clicked)
        layout.addWidget(self.button, 0)
        self._tile = None
        self._pinned = False

    @staticmethod
    def applies(info) -> bool:
        """Does the row show for this tile (built on demand, or pinned)?"""
        return info is not None and bool(
            getattr(info, "on_demand", False) or getattr(info, "pinned", False))

    def show_tile(self, tile, info) -> None:
        """The active tile and its :class:`O4_Tile_Info.TileInfo`."""
        self._tile = tuple(tile) if tile and self.applies(info) else None
        self.set_pinned(bool(getattr(info, "pinned", False)))

    def set_pinned(self, pinned: bool) -> None:
        """Show the pin state (the tile's, or the engine's answer)."""
        self._pinned = bool(pinned)
        self.label.setText(TEXT.PINNED_STATE if self._pinned
                           else TEXT.LOW_RES_STATE)
        self.button.setText(TEXT.UNPIN_TITLE if self._pinned
                            else TEXT.PIN_TITLE)

    def _clicked(self) -> None:
        if self._tile is not None:
            self.pin_requested.emit((self._tile[0], self._tile[1],
                                     not self._pinned))
