"""The map's tile legend (Qt half; the Mac app's ``MapTileLegend``, same
words, colors and order — #1958).

Which border is a tile this app built, which is "some ortho" another tool
made (``TileInfo.origin``), which tile's airport pack changed since its
build (``O4_Tile_Staleness``), and which lives on another drive (#1987).
Only the kinds on the map now are listed; with no built tile there is no
legend.  Painted in viewport space, bottom-right above the zoom badge.
"""
from __future__ import annotations

import O4_Tile_Info as TINFO
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPen

__all__ = ["BUILT", "OTHER", "STALE", "EXTERNAL", "LEGEND_LABELS",
           "STALE_COLOR", "OTHER_ORTHO_COLOR", "legend_kinds", "stale_label",
           "paint_legend"]

BUILT, OTHER, STALE, EXTERNAL = "built", "other", "stale", "external"

#: kind -> words (MapTileLegend.Kind.label), in the legend's order.
LEGEND_LABELS = {
    BUILT: "XPTerrainBuilder tile",
    OTHER: "Other ortho",
    STALE: "Airport pack changed",
    EXTERNAL: "On another drive",
}

#: A tile whose airport pack changed (MapCanvasView.staleTile).
STALE_COLOR = "#BF5AF2"
#: A tile another tool built: the other packs' outline gray
#: (MapCanvasView.otherOrthoTile = regionOutline).
OTHER_ORTHO_COLOR = QColor(158, 158, 158, 217)


def built_elsewhere(info) -> bool:
    """Another tool built it (an engine before ``origin`` says nothing)."""
    return getattr(info, "origin", "") == TINFO.ORIGIN_OTHER


def legend_kinds(built: dict, stale: dict) -> list:
    """The kinds present among the built tiles, in the legend's order."""
    if not built:
        return []
    infos = list(built.values())
    present = {
        BUILT: any(not built_elsewhere(i) for i in infos),
        OTHER: any(built_elsewhere(i) for i in infos),
        STALE: bool(stale),
        EXTERNAL: any(getattr(i, "volume", "") for i in infos),
    }
    return [kind for kind in LEGEND_LABELS if present[kind]]


def stale_label(verdict: dict) -> str:
    """The map's pill: "Stale: EGKK", "Stale: EGKK +2" (O4StaleTile.label)."""
    airports = verdict.get("airports") or []
    if not airports:
        return ""
    first = airports[0]["icao"]
    return ("Stale: %s +%d" % (first, len(airports) - 1) if len(airports) > 1
            else "Stale: %s" % first)


def _color(kind: str, built_color: str, external_color: str) -> QColor:
    return {BUILT: QColor(built_color), OTHER: QColor(OTHER_ORTHO_COLOR),
            STALE: QColor(STALE_COLOR), EXTERNAL: QColor(external_color)}[kind]


def paint_legend(painter, viewport: QRectF, kinds: list, bottom: float,
                 built_color: str, external_color: str) -> None:
    """The legend box, its bottom-right corner ``bottom`` px above the
    viewport's bottom edge, 10 px in from its right."""
    if not kinds:
        return
    metrics = painter.fontMetrics()
    line = metrics.height() + 3
    width = max(metrics.horizontalAdvance(LEGEND_LABELS[k]) for k in kinds) + 40
    height = line * len(kinds) + 10
    box = QRectF(viewport.right() - width - 10, viewport.bottom() - bottom - height,
                 width, height)
    painter.save()
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(20, 22, 28, 175))
    painter.drawRoundedRect(box, 8, 8)
    for row, kind in enumerate(kinds):
        top = box.top() + 5 + row * line
        pen = QPen(_color(kind, built_color, external_color))
        pen.setWidthF(2)
        if kind == STALE:
            pen.setDashPattern([2, 1])
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(QRectF(box.left() + 9, top + (line - 10) / 2, 14, 10))
        painter.setPen(QColor(235, 238, 245, 220))
        painter.drawText(QRectF(box.left() + 30, top, width - 34, line),
                         Qt.AlignVCenter | Qt.AlignLeft, LEGEND_LABELS[kind])
    painter.restore()
