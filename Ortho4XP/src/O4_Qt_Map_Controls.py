"""The map's top-right controls (#2016): zoom out, zoom in and "Center on
aircraft", as the Mac map's ``zoomControls`` (``MapCanvasView.swift``) and
``CenterOnAircraftButton`` (``MapCenterOnAircraft.swift``) show them.

"Center on aircraft" pans to the position Fly's ``aircraft_watch`` last
reported and keeps the zoom; it is disabled, with
:data:`O4_Fly_Text.NO_AIRCRAFT_POSITION` as its tooltip, while no position
is current (:func:`O4_Fly_Text.aircraft_is_current`).  A viewport child of
:class:`O4_Qt_Map.MapView`, re-pinned top-right on resize and scroll.
"""

from __future__ import annotations

import math
import time

from PySide6.QtCore import QPointF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap, QPolygonF
from PySide6.QtWidgets import QFrame, QHBoxLayout, QToolButton, QWidget

import O4_Fly_Text as TEXT

__all__ = ["MapControls", "ZOOM_STEP"]

#: One zoom click, in slippy levels: the Mac's factor 1.5.
ZOOM_STEP = math.log2(1.5)
_MARGIN = 8


def _location_icon(size: int = 16) -> QIcon:
    """SF Symbols ``location``: an arrow pointing up and to the right."""
    pixmap = QPixmap(size * 2, size * 2)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(QColor("#E8EAED"))
    s = size * 2
    painter.drawPolygon(QPolygonF([QPointF(s * 0.88, s * 0.12),
                                   QPointF(s * 0.12, s * 0.45),
                                   QPointF(s * 0.50, s * 0.50),
                                   QPointF(s * 0.55, s * 0.88)]))
    painter.end()
    pixmap.setDevicePixelRatio(2.0)
    return QIcon(pixmap)


class MapControls(QWidget):
    """``zoom_out_btn``, ``zoom_in_btn`` and ``center_btn`` in one pill."""

    def __init__(self, view, clock=time.monotonic):
        super().__init__(view.viewport())
        self._view = view
        self._clock = clock
        self._aircraft = None        # (lat, lon)
        self._seen_at = None
        self.setStyleSheet(
            "QWidget#mapControls { background: rgba(0,0,0,115); border-radius: 6px; }"
            "QToolButton { color: #E8EAED; border: none; background: transparent;"
            " font-size: 15px; }"
            "QToolButton:disabled { color: rgba(232,234,237,90); }")
        self.setObjectName("mapControls")
        self.setAttribute(Qt.WA_StyledBackground, True)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.zoom_out_btn = self._button("−", "Zoom out")
        self.zoom_in_btn = self._button("+", "Zoom in (drag the map to pan)")
        self.center_btn = self._button("", TEXT.NO_AIRCRAFT_POSITION)
        self.center_btn.setIcon(_location_icon())
        self.center_btn.setIconSize(QSize(16, 16))
        self.center_btn.setAccessibleName(TEXT.CENTER_ON_AIRCRAFT)
        self.zoom_out_btn.clicked.connect(lambda: view.zoom_step(-ZOOM_STEP))
        self.zoom_in_btn.clicked.connect(lambda: view.zoom_step(ZOOM_STEP))
        self.center_btn.clicked.connect(self.center_on_aircraft)
        for i, button in enumerate((self.zoom_out_btn, self.zoom_in_btn,
                                    self.center_btn)):
            if i:
                layout.addWidget(self._divider())
            layout.addWidget(button)
        # X-Plane going quiet sends nothing: re-checked every second.
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self.refresh)
        self._timer.start()
        self.refresh()

    def _button(self, text, tip):
        button = QToolButton(self)
        button.setText(text)
        button.setToolTip(tip)
        button.setFixedSize(30, 24)
        button.setCursor(Qt.ArrowCursor)
        return button

    def _divider(self):
        line = QFrame(self)
        line.setFrameShape(QFrame.VLine)
        line.setFixedHeight(16)
        line.setStyleSheet("color: rgba(255,255,255,60);")
        return line

    def show_aircraft(self, lat, lon):
        """An ``AircraftPosition`` arrived."""
        self._aircraft = (float(lat), float(lon))
        self._seen_at = self._clock()
        self.refresh()

    def aircraft_is_current(self):
        return TEXT.aircraft_is_current(self._seen_at, self._clock())

    def refresh(self):
        current = self.aircraft_is_current()
        self.center_btn.setEnabled(current)
        self.center_btn.setToolTip(TEXT.CENTER_ON_AIRCRAFT if current
                                   else TEXT.NO_AIRCRAFT_POSITION)

    def center_on_aircraft(self):
        """Pan to the aircraft; the zoom stays."""
        if self._aircraft is not None and self.aircraft_is_current():
            self._view.center_on_point(*self._aircraft)

    def place(self):
        """Pin top-right in the viewport (Mac: ``.topTrailing``, padding 8)."""
        self.adjustSize()
        self.move(self._view.viewport().width() - self.width() - _MARGIN, _MARGIN)
        self.raise_()
