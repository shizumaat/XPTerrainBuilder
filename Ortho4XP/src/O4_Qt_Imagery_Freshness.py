"""The tile pane's "Imagery check" row (Qt half; the Mac app's
``TileImageryFreshnessRow``, same words — the engine writes them).

Whether the provider still serves the imagery the active tile was built
from (:mod:`O4_Imagery_Freshness`, #1666): "Up to date", "Newer imagery
available", "Unknown" or "Not checked yet", the reason in the tooltip.
With newer imagery an "Update Imagery" button asks the window to discard
the tile's downloaded imagery and rebuild it.  The check may send a few
requests to the provider, so it runs on a latest-wins background probe
(:class:`O4_Qt_Latest_Probe.LatestProbe`); an answer for a tile no longer
active is dropped.
"""
from __future__ import annotations

import O4_Imagery_Freshness as FRESH
import O4_Qt_Latest_Probe as QTPROBE
from o4_engine import imagery_commands as CMDS
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

__all__ = ["ImageryFreshnessRow", "UPDATE_TITLE", "UPDATE_HELP"]

UPDATE_TITLE = "Update Imagery"
UPDATE_HELP = ("Download this tile's imagery again from its source and "
               "rebuild the tile with it.")
NEWER_COLOR = "#D9822B"


def _check(tile, info, should_stop):
    return tile, CMDS.freshness_for_info(info, should_stop=should_stop)


class ImageryFreshnessRow(QWidget):
    """The status line, and "Update Imagery" when newer imagery exists."""

    #: (lat, lon) of the tile whose imagery the user asked to update.
    update_requested = Signal(object)
    #: (tile, answer) from the probe thread.
    _checked = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        self.label = QLabel("—")
        self.label.setWordWrap(True)
        layout.addWidget(self.label, 1)
        self.update_button = QPushButton(UPDATE_TITLE)
        self.update_button.setToolTip(UPDATE_HELP)
        self.update_button.clicked.connect(self._update)
        self.update_button.setVisible(False)
        layout.addWidget(self.update_button, 0)
        self._tile = None
        self._checked.connect(self._show)
        self._probe = QTPROBE.LatestProbe(_check, self._deliver,
                                          name="o4-imagery-freshness")
        self.destroyed.connect(self._probe.close)

    def check(self, tile, info) -> None:
        """Check ``tile`` (its :class:`O4_Tile_Info.TileInfo`, None when
        not built); the row updates when the answer lands."""
        self._tile = tuple(tile) if tile and info is not None else None
        self.update_button.setVisible(False)
        self.label.setStyleSheet("")
        self.label.setToolTip("")
        if self._tile is None:
            self.label.setText("—")
            return
        self.label.setText("Checking…")
        self._probe.submit(self._tile, info)

    def close_probe(self) -> None:
        """Stop the probe (the window is closing)."""
        self._probe.close()

    def _deliver(self, delivered) -> None:
        try:
            self._checked.emit(delivered)
        except RuntimeError:
            pass  # the window was destroyed meanwhile

    def _show(self, delivered) -> None:
        tile, answer = delivered
        if tile != self._tile:
            return
        newer = answer.get("status") == FRESH.NEWER
        self.label.setText(str(answer.get("label") or "—"))
        self.label.setToolTip(str(answer.get("detail") or ""))
        self.label.setStyleSheet("color: %s;" % NEWER_COLOR if newer else "")
        self.update_button.setVisible(newer)

    def _update(self) -> None:
        if self._tile is not None:
            self.update_requested.emit(self._tile)
