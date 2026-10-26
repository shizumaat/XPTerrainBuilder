"""The map's bottom-left cursor readout (issue #1308): ``lat, lon`` in the
node format (``O4_Qt_Patch_Panel.node_lat_lon``) and, once the cursor
rests 150 ms, the elevation under it from ``cursor_elevation`` —
``123.4 m``, ``(DEM)`` appended when the tile has no built mesh there —
and, over a pack outline, its label (``pack: terminal.obj``, #1316).
The Mac app's twin is ``MapCanvasView.cursorReadout``."""
from __future__ import annotations

import math

from O4_Qt_Patch_Panel import node_lat_lon
from PySide6.QtCore import QObject, QTimer

__all__ = ["CursorReadout", "elevation_text", "readout_text"]

REST_MS = 150
PENDING_MS = 400


def elevation_text(reply) -> str | None:
    """The readout's suffix for a ``cursor_elevation`` reply, or None."""
    if not reply or reply.get("elevation_m") is None:
        return None
    text = "%.1f m" % reply["elevation_m"]
    return text + " (DEM)" if reply.get("source") == "dem" else text


def readout_text(lat: float, lon: float, elevation: str | None = None,
                 pack: str | None = None) -> str:
    """``lat, lon[ · elevation][ · pack: label]``."""
    parts = [node_lat_lon(lat, lon)] + ([elevation] if elevation else []) \
        + (["pack: " + pack] if pack else [])
    return " · ".join(parts)


class CursorReadout(QObject):
    """Drives ``label`` from the map's hover; ``engine`` is the window's
    ``PatchEngine``, ``built()`` the scan's ``{(lat, lon): info}``,
    ``pack_label(lat, lon)`` the pack outline under the cursor (or None)."""

    def __init__(self, label, engine, built, parent=None,
                 pack_label=lambda _lat, _lon: None):
        super().__init__(parent)
        self._label, self._engine, self._built = label, engine, built
        self._pack_label = pack_label
        self._pack = None
        self._at = None
        self._gen = 0
        self._tries = 0
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._ask)

    def hover(self, lat: float, lon: float) -> None:
        self._at = (lat, lon)
        self._gen += 1
        self._tries = 0
        self._pack = self._pack_label(lat, lon)
        self._label.setText(readout_text(lat, lon, pack=self._pack))
        if self._engine is not None and self._engine.has("cursor_elevation"):
            self._timer.start(REST_MS)

    def _ask(self) -> None:
        lat, lon = self._at
        gen = self._gen
        info = (self._built() or {}).get((math.floor(lat), math.floor(lon)))
        build_dir = getattr(info, "build_dir", None) or None

        def answered(reply, error):
            if gen != self._gen or error is not None:
                return
            self._label.setText(readout_text(lat, lon, elevation_text(reply), self._pack))
            self._tries += 1
            if reply.get("pending") and self._tries < 20:
                self._timer.start(PENDING_MS)

        self._engine.call("cursor_elevation", answered, lat=lat, lon=lon,
                          build_dir=build_dir)
