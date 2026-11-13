"""A background airport-core sharpening's row in the Build panel's run
list (#2039, owner 2026-11-13T04:32Z): after a build in on-demand mode,
a World publish, a flight's kept endpoints or an adopt, the engine lands
each tile's airport cores (``o4_engine.imagery_core_rows``) and says so
with ``ImageryCoresProgress``.  The row shows the tile, "Sharpening
airport imagery · n of N squares", a bar, and a stop button while it
runs; then done, failed or stopped.  It is not a build row: no clock, no
steps, not selectable; once finished it moves to Completed (#2052,
``O4_Qt_Activity_List.ActivityList.place_cores``).

The Mac app's twin is ``ImageryCoresRow`` (``ImageryCoresRow.swift``);
both word it with ``O4_Imagery_OnDemand_Text.cores_row_status``.
"""

import O4_Activity_Order as ACTORDER
import O4_File_Names as FNAMES
import O4_Imagery_OnDemand_Text as TEXT
import O4_Qt_Text_Scale as QTTEXT
from O4_Qt_Widgets import ElidedRowLabel
from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QProgressBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

__all__ = ["CoreRow", "CoreRowSet"]


def _fraction(event):
    """The bar's share of the tile's squares finished, 0..1."""
    total = int(getattr(event, "total", 0) or 0)
    if total <= 0:
        return 0.0
    return (int(event.done) + int(event.failed)) / total


class CoreRow(QWidget):
    """One tile's row; :meth:`show_progress` repaints it from an
    ``ImageryCoresProgress``.  ``stop_icon``/``icon_pt``, ``tone_colors``
    (``O4_Activity_Order.status_tone`` -> colour), ``small_px`` and
    ``margins`` are the build rows' own, so the two kinds of row match."""

    #: The user pressed stop: ``(lat, lon)``.
    stop_requested = Signal(object)

    def __init__(self, tile, stop_icon, icon_pt, tone_colors, small_px,
                 margins=(0, 0, 0, 0), parent=None):
        super().__init__(parent)
        self.tile = (int(tile[0]), int(tile[1]))
        self._tones = tone_colors
        self.running = True
        layout = QVBoxLayout(self)
        layout.setContentsMargins(*margins)
        self.title = ElidedRowLabel(FNAMES.short_latlon(*self.tile))
        self.title.setObjectName("cores_title")
        layout.addWidget(self.title)
        self.bar = QProgressBar()
        self.bar.setRange(0, 1000)
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(6)
        layout.addWidget(self.bar)
        line = QHBoxLayout()
        line.setSpacing(6)
        self.status = ElidedRowLabel("")
        self.status.setObjectName("cores_status")
        QTTEXT.size_text(self.status, pixels=small_px)
        line.addWidget(self.status, 1)
        self.stop = QToolButton()
        self.stop.setAutoRaise(True)
        self.stop.setIcon(stop_icon)
        self.stop.setIconSize(QSize(icon_pt, icon_pt))
        self.stop.setFixedSize(icon_pt + 6, icon_pt + 6)
        self.stop.setToolTip(TEXT.CORES_ROW_STOP_HELP)
        self.stop.clicked.connect(
            lambda _checked=False: self.stop_requested.emit(self.tile))
        line.addWidget(self.stop, 0, Qt.AlignRight)
        layout.addLayout(line)

    def show_progress(self, event):
        """Paint ``event`` (an ``ImageryCoresProgress``) on the row."""
        state = event.state
        self.running = state == "active"
        self.status.setText(TEXT.cores_row_status(
            state, event.done, event.total, event.failed))
        self.status.setStyleSheet("color: %s;" % self._tones[
            ACTORDER.status_tone(state, state, False)])
        self.title.setStyleSheet("" if self.running else "color: gray;")
        self.bar.setValue(int(round(_fraction(event) * 1000)))
        self.stop.setVisible(self.running)


class CoreRowSet:
    """The run list's core rows, one per tile in the order they started:
    ``make(tile)`` builds a new tile's :class:`CoreRow`.  A finished row
    sits in Completed (#2052) until the next run begins (:meth:`drop_finished`), as the Mac
    app's ``BuildActivityModel.coreRows``."""

    def __init__(self, make):
        self._make = make
        self._rows = {}

    def rows(self):
        return list(self._rows.values())

    def show(self, event):
        """Paint ``event`` on its tile's row; True when the row is new or
        has just finished (it then moves to Completed, #2052)."""
        tile = (int(event.lat), int(event.lon))
        row = self._rows.get(tile)
        new = row is None
        if new:
            row = self._rows[tile] = self._make(tile)
        was_running = row.running
        row.show_progress(event)
        return new or was_running != row.running

    def drop_finished(self):
        """Forget the finished rows; True when one went."""
        gone = [tile for tile, row in self._rows.items() if not row.running]
        for tile in gone:
            self._rows.pop(tile).deleteLater()
        return bool(gone)
