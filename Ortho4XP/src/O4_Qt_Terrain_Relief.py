"""The patch view's terrain layer for the Qt app (issue #1320, owner Q134:
hillshade plus contours; the Mac app's ``PatchTerrainRelief``).

While the "Terrain" toggle is on and the patch layer shows, the map's
visible box (clipped to the patch's tile by the engine) is asked of
``terrain_relief`` once the view rests, at the viewport's size (long side
at most :data:`MAX_SIDE` px); the reply's PNG is drawn into its box under
the patch at the slider's opacity.  ``pending`` replies are asked again.
The toggle and the opacity are remembered per user; the toggle is off by
default (the picture covers the imagery).
"""
from __future__ import annotations

import base64
import typing as _t

import O4_File_Names as FNAMES
import O4_Geo_Utils as GEO
import O4_Qt_Map as QTMAP
from O4_Qt_Patch_Geometry import scene_xy
from PySide6.QtCore import QObject, QPointF, QRectF, QTimer, Signal
from PySide6.QtGui import QColor, QImage

__all__ = ["CONTOUR_COLOR", "MAX_SIDE", "TOGGLE_HELP", "TerrainRelief", "legend_text"]

#: The legend swatch: the engine's minor contour colour (``o4_engine.relief``).
CONTOUR_COLOR = QColor(214, 120, 30)

#: The picture's long side, in pixels (the engine allows 1024).
MAX_SIDE = 640
REST_MS = 300
PENDING_MS = 400
MAX_TRIES = 60
TOGGLE_HELP = ("Show the terrain under the patch: hillshade (sun from the north-west) "
               "with contour lines, from the last build's mesh, else the elevation data.")


def legend_text(legend) -> str | None:
    """``1 m contours · 101–110 m`` for a reply's legend, or None."""
    if not legend or legend.get("contour_m") is None:
        return None
    step = "%g m contours" % legend["contour_m"]
    if legend.get("min_m") is None:
        return step
    return "%s · %.0f–%.0f m" % (step, legend["min_m"], legend["max_m"])


class TerrainRelief(QObject):
    """The "Terrain" layer: asks for the visible box once the view rests,
    drawn under the patch in scene units."""

    changed = Signal()

    def __init__(self, engine, model, map_view, built: _t.Callable[[], dict],
                 enabled: bool = False, opacity: float = 0.6,
                 remember: _t.Callable[[bool, float], None] = lambda _on, _o: None,
                 showing: _t.Callable[[], bool] = lambda: True, parent=None):
        super().__init__(parent)
        self.engine, self.model, self.map = engine, model, map_view
        self._built, self._remember, self._showing = built, remember, showing
        self.enabled = bool(enabled)
        self.opacity = min(max(float(opacity), 0.0), 1.0)
        self.error: str | None = None
        self.legend = None
        self._image: QImage | None = None
        self._box = None                    # (s, w, n, e) of the image
        self._gen = 0
        self._tries = 0
        self._ask_args = None
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._ask)
        view_changed = getattr(map_view, "view_changed", None)
        if view_changed is not None:
            view_changed.connect(self.view_changed)

    @property
    def help_text(self) -> str:
        return TOGGLE_HELP + ("\n\n" + self.error if self.error else "")

    @property
    def available(self) -> bool:
        return self.engine.has("terrain_relief")

    def set_enabled(self, on: bool) -> None:
        if bool(on) == self.enabled:
            return
        self.enabled = bool(on)
        self._remember(self.enabled, self.opacity)
        if not self.enabled:
            self._gen += 1
            self._image, self._box, self.legend, self.error = None, None, None, None
        self.view_changed()
        self.changed.emit()

    def set_opacity(self, value: float) -> None:
        self.opacity = min(max(float(value), 0.0), 1.0)
        self._remember(self.enabled, self.opacity)
        self.changed.emit()

    def view_changed(self) -> None:
        """The map moved or the patch changed: ask once it rests."""
        if self.enabled and self.available:
            self._timer.start(REST_MS)

    # ─── asking ────────────────────────────────────────────────────────
    def request(self):
        """``terrain_relief``'s arguments for the visible box, or None."""
        patch = self.model.patch
        if patch is None or not self._showing():
            return None
        vp = self.map.viewport().rect()
        if vp.width() < 2 or vp.height() < 2:
            return None
        inverse = self.map.viewportTransform().inverted()[0]
        corners = [inverse.map(QPointF(x, y)) for x, y in ((0, 0), (vp.width(), vp.height()))]
        (n, w), (s, e) = (GEO.pix_to_wgs84(p.x(), p.y(), QTMAP.SCENE_ZL) for p in corners)
        scale = min(1.0, MAX_SIDE / max(vp.width(), vp.height()))
        info = (self._built() or {}).get(FNAMES.parse_tile_key(patch.tile))
        build_dir = getattr(info, "build_dir", None) or None
        return {"tile": patch.tile, "bbox": [float(s), float(w), float(n), float(e)],
                "px_w": max(1, round(vp.width() * scale)),
                "px_h": max(1, round(vp.height() * scale)), "build_dir": build_dir}

    def _ask(self, again: bool = False) -> None:
        if not again:
            args = self.request()
            if args is None:
                return
            self._gen += 1
            self._tries = 0
            self._ask_args = args
        args, gen = self._ask_args, self._gen

        def answered(reply, error):
            if gen != self._gen:
                return
            if error is not None:
                self.error = error
                self.changed.emit()
                return
            if reply.get("pending"):
                self._tries += 1
                if self._tries < MAX_TRIES:
                    QTimer.singleShot(PENDING_MS,
                                      lambda: gen == self._gen and self._ask(again=True))
                return
            image = QImage.fromData(base64.b64decode(reply.get("png_b64") or ""), "PNG")
            self.error = None
            self._image = None if image.isNull() else image
            self._box = tuple(reply.get("bbox") or ())
            self.legend = reply.get("legend")
            self.changed.emit()
        self.engine.call("terrain_relief", answered, **args)

    # ─── drawing ───────────────────────────────────────────────────────
    def paint(self, painter, view_transform) -> None:
        """The picture in its box (painter in viewport space)."""
        if not self.enabled or self._image is None or len(self._box) != 4:
            return
        s, w, n, e = self._box
        x0, y0 = scene_xy(n, w, QTMAP.SCENE_ZL)
        x1, y1 = scene_xy(s, e, QTMAP.SCENE_ZL)
        painter.save()
        painter.setTransform(view_transform)
        painter.setOpacity(self.opacity)
        painter.drawImage(QRectF(float(x0), float(y0), float(x1 - x0), float(y1 - y0)), self._image)
        painter.restore()
