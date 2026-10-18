"""The Qt map's labels (issue #817): tile and airport labels, painted.

The RULES are :mod:`O4_Map_Labels` (shared with the macOS app); this
module only paints them, in VIEWPORT coordinates (a label is
screen-sized by definition):

* :func:`paint_tile_labels` -- every visible tile's coordinate top-left
  and, where ortho is installed, its imagery bottom-left, on pills;
* :class:`AirportLayer` -- airport marks and labels by size, laid out once
  per viewport change (the plan is cached on the view's geometry) and
  painted every frame.

Mac twin: ``Sources/XPTerrainBuilder/MapCanvasLabels.swift``.
"""

import math
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Set, Tuple

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QFontMetricsF, QPen

import O4_Airport_Rank as RANK
import O4_Map_Labels as LABELS
import O4_Text_Scale as TS

__all__ = ["paint_tile_labels", "AirportLayer", "label_font"]

Tile = Tuple[int, int]
PointOf = Callable[[float, float], QPointF]

PILL_COLOR = QColor(0, 0, 0, 140)
TILE_TEXT_COLOR = QColor(255, 255, 255, 235)
DEFAULT_LABEL_COLOR = QColor(224, 224, 224)
CUSTOM_LABEL_COLOR = QColor(242, 140, 184)


def label_font(pixel_size: float, bold: bool = False) -> QFont:
    """The system fixed-width font at ``pixel_size`` px -- pixels, not
    points, so the box estimate in :mod:`O4_Map_Labels` holds on every
    display density."""
    font = QFontDatabase.systemFont(QFontDatabase.FixedFont)
    font.setPixelSize(max(1, int(round(pixel_size))))
    font.setBold(bold)
    return font


def _pill(painter, text: str, x: float, y: float, top: bool,
          font: QFont) -> None:
    """``text`` on a translucent pill whose top-left (``top``) or
    bottom-left corner is (x, y)."""
    metrics = QFontMetricsF(font)
    width = metrics.horizontalAdvance(text) + 8.0
    height = metrics.height() + 4.0
    rect = QRectF(x, y if top else y - height, width, height)
    painter.setPen(Qt.NoPen)
    painter.setBrush(PILL_COLOR)
    painter.drawRoundedRect(rect, height / 2.0, height / 2.0)
    painter.setFont(font)
    painter.setPen(TILE_TEXT_COLOR)
    painter.drawText(rect, Qt.AlignCenter, text)


def paint_tile_labels(painter, point_of: PointOf, scale: float,
                      bounds: Tuple[float, float, float, float],
                      tile_key: Callable[[int, int], str],
                      built: Optional[Dict[Tile, object]],
                      ortho_tiles: Optional[Set[Tile]],
                      text_scale: float = TS.DEFAULT) -> None:
    """Coordinate top-left on every visible tile; imagery bottom-left on
    a ``built`` tile (its ``provider``/``zl``/``has_zones``) or on one an
    installed ortho pack covers (``imagery ?``).  ``None`` for ``built``
    or ``ortho_tiles`` hides that layer (the scenery filter).
    ``text_scale`` is the apps' text size (#827)."""
    if scale < LABELS.TILE_LABEL_MIN_SCALE:
        return
    (lat_lo, lat_hi, lon_lo, lon_hi) = bounds
    font = label_font(TS.scaled(LABELS.TILE_LABEL_FONT, text_scale))
    for lat in range(max(int(math.floor(lat_lo)), -85),
                     min(int(math.floor(lat_hi)), 84) + 1):
        for lon in range(max(int(math.floor(lon_lo)), -180),
                         min(int(math.floor(lon_hi)), 179) + 1):
            top_left = point_of(lat + 1, lon)
            bottom_left = point_of(lat, lon)
            _pill(painter, tile_key(lat, lon), top_left.x() + 4,
                  top_left.y() + 4, True, font)
            info = built.get((lat, lon)) if built is not None else None
            if info is not None:
                text = LABELS.imagery_label(
                    getattr(info, "provider", ""), getattr(info, "zl", None),
                    bool(getattr(info, "has_zones", False)))
            elif ortho_tiles is not None and (lat, lon) in ortho_tiles:
                text = LABELS.imagery_label(None, None)
            else:
                continue
            _pill(painter, text, bottom_left.x() + 4, bottom_left.y() - 4,
                  False, font)


class AirportLayer:
    """Airport marks and labels by size (mac-app parity).

    :meth:`set_default` bins Global Airports by size class and 10-degree
    cell ONCE, so a frame walks only the classes its zoom marks and the
    cells it can see; :meth:`paint` lays the labels out only when the
    view's geometry changed since the last frame.
    """

    def __init__(self) -> None:
        # class -> {(lat_bin, lon_bin): [(code, lat, lon), ...]}
        self._bins: Dict[int, Dict[Tuple[int, int], list]] = {}
        self._custom: List[tuple] = []
        self._sizes: Dict[str, Tuple[int, int]] = {}
        self._plan_key = None
        self._plan = None

    def set_sizes(self, sizes: Dict[str, Tuple[int, int]]) -> None:
        """``code -> (size_class, runway_m)`` from the airport index."""
        self._sizes = dict(sizes)
        self._plan_key = None

    def size_of(self, code: str) -> Tuple[int, int]:
        return self._sizes.get(code, (RANK.UNKNOWN_SIZE_CLASS, 0))

    def set_default(self, rows: Iterable[tuple]) -> None:
        bins: Dict[int, Dict[Tuple[int, int], list]] = {}
        for row in rows:
            cls = self.size_of(row[0])[0]
            cell = (int(math.floor(row[1] / 10.0)),
                    int(math.floor(row[2] / 10.0)))
            bins.setdefault(cls, {}).setdefault(cell, []).append(row)
        self._bins = bins
        self._plan_key = None

    def set_custom(self, rows: Sequence[tuple]) -> None:
        self._custom = list(rows)
        self._plan_key = None

    def _candidates(self, scale, bounds, point_of):
        (lat_lo, lat_hi, lon_lo, lon_hi) = bounds
        candidates, dims = [], []

        def add(code, lat, lon, custom, dim):
            p = point_of(lat, lon)
            (cls, runway) = self.size_of(code)
            candidates.append(LABELS.LabelCandidate(
                code, p.x(), p.y(), cls, runway, custom))
            dims.append(dim)

        for cls in sorted(self._bins):
            if not LABELS.mark_visible(cls, False, scale):
                continue
            cells = self._bins[cls]
            for lat_bin in range(int(math.floor(lat_lo / 10.0)),
                                 int(math.floor(lat_hi / 10.0)) + 1):
                for lon_bin in range(int(math.floor(lon_lo / 10.0)),
                                     int(math.floor(lon_hi / 10.0)) + 1):
                    for (code, lat, lon) in cells.get((lat_bin, lon_bin), ()):
                        if lat_lo < lat < lat_hi and lon_lo < lon < lon_hi:
                            add(code, lat, lon, False, False)
        for (code, lat, lon, dim) in self._custom:
            if lat_lo < lat < lat_hi and lon_lo < lon < lon_hi:
                add(code, lat, lon, True, dim)
        return candidates, dims

    def plan(self, key, scale, bounds, point_of, text_scale=TS.DEFAULT):
        """``(candidates, dims, marks, labels, radius)`` for this view,
        rebuilt only when ``key`` (the view geometry and the text
        scale, #827) changed."""
        if key != self._plan_key or self._plan is None:
            # One-degree margin, as the mac app culls: a mark just
            # off-screen still owns a label that reaches into it.
            (lat_lo, lat_hi, lon_lo, lon_hi) = bounds
            margin = (lat_lo - 1, lat_hi + 1, lon_lo - 1, lon_hi + 1)
            candidates, dims = self._candidates(scale, margin, point_of)
            radius = LABELS.mark_radius(scale)
            marks, labels = LABELS.place_airport_labels(
                candidates, scale, radius, text_scale=text_scale)
            self._plan = (candidates, dims, marks, labels, radius)
            self._plan_key = key
        return self._plan

    def paint(self, painter, key, scale, bounds, point_of,
              default_color: QColor, custom_color: QColor,
              dim_alpha: int, text_scale: float = TS.DEFAULT) -> None:
        (candidates, dims, marks, labels, radius) = self.plan(
            (key, text_scale), scale, bounds, point_of, text_scale)
        if not candidates:
            return
        pen_width = max(1.4, radius * 0.4)
        painter.setBrush(Qt.NoBrush)
        # Default marks first under one pen, custom (magenta) on top.
        pen = QPen(default_color)
        pen.setWidthF(pen_width)
        painter.setPen(pen)
        for i in marks:
            c = candidates[i]
            if not c.custom:
                painter.drawEllipse(QPointF(c.x, c.y), radius, radius)
        for i in marks:
            c = candidates[i]
            if c.custom:
                color = QColor(custom_color)
                color.setAlpha(dim_alpha if dims[i] else 242)
                pen = QPen(color)
                pen.setWidthF(pen_width)
                painter.setPen(pen)
                painter.drawEllipse(QPointF(c.x, c.y), radius, radius)
        for (i, box) in labels:
            c = candidates[i]
            rect = QRectF(box.x, box.y, box.width, box.height)
            painter.setPen(Qt.NoPen)
            painter.setBrush(PILL_COLOR)
            painter.drawRoundedRect(rect, box.height / 2.0, box.height / 2.0)
            painter.setFont(label_font(box.font_size, bold=True))
            painter.setPen(CUSTOM_LABEL_COLOR if c.custom
                           else DEFAULT_LABEL_COLOR)
            painter.drawText(rect, Qt.AlignCenter, c.code)
        painter.setBrush(Qt.NoBrush)
