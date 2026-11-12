"""The map's tile legend (Qt half; the Mac app's ``MapTileLegend``, same
words, colors and order — #1958, #2024).

What the World pack draws on each tile (``O4_Qt_Map_World``, words from
``O4_World_State_Text``), which border is a tile this app built, which is
"some ortho" another tool made (``TileInfo.origin``), which tile's airport
pack changed since its build (``O4_Tile_Staleness``), which lives on
another drive (#1987), and what the orange custom-patch band means
(#1229).  Only the kinds on the map now are listed.  Painted in viewport
space, bottom-right above the zoom badge.
"""
from __future__ import annotations

import O4_Qt_Map_World as QTWORLD
import O4_Tile_Info as TINFO
import O4_World_State_Text as WORLD_TEXT
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPen

__all__ = ["WORLD_FULL", "WORLD_MESH", "WORLD_DRAPE", "WORLD_PLACEHOLDER",
           "WORLD_NOTHING", "WORLD_OTHER_TOOL", "BUILT", "OTHER", "STALE",
           "EXTERNAL", "CUSTOM_PATCH", "LEGEND_LABELS",
           "STALE_COLOR", "OTHER_ORTHO_COLOR", "CUSTOM_PATCH_COLOR",
           "legend_kinds", "stale_label", "paint_legend"]

WORLD_FULL, WORLD_MESH, WORLD_DRAPE = "world_full", "world_mesh", "world_drape"
WORLD_PLACEHOLDER, WORLD_NOTHING = "world_placeholder", "world_nothing"
WORLD_OTHER_TOOL = "world_other_tool"
BUILT, OTHER, STALE, EXTERNAL = "built", "other", "stale", "external"
CUSTOM_PATCH = "custom_patch"

#: kind -> words (MapTileLegend.Kind.label), in the legend's order.
LEGEND_LABELS = {
    WORLD_FULL: WORLD_TEXT.LEGEND_FULL,
    WORLD_MESH: WORLD_TEXT.LEGEND_MESH,
    WORLD_DRAPE: WORLD_TEXT.LEGEND_DRAPE,
    WORLD_PLACEHOLDER: WORLD_TEXT.LEGEND_PLACEHOLDER,
    WORLD_NOTHING: WORLD_TEXT.LEGEND_NOTHING,
    WORLD_OTHER_TOOL: WORLD_TEXT.LEGEND_OTHER_TOOL,
    BUILT: "XPTerrainBuilder tile",
    OTHER: "Other ortho",
    STALE: "Airport pack changed",
    EXTERNAL: "On another drive",
    CUSTOM_PATCH: WORLD_TEXT.LEGEND_CUSTOM_PATCH,
}

#: A tile whose airport pack changed (MapCanvasView.staleTile).
STALE_COLOR = "#BF5AF2"
#: A tile another tool built: the other packs' outline gray
#: (MapCanvasView.otherOrthoTile = regionOutline).
OTHER_ORTHO_COLOR = QColor(158, 158, 158, 217)
#: The custom-patch band (O4_Qt_Map.CUSTOM_PATCH_COLOR).
CUSTOM_PATCH_COLOR = "#FF9F0A"
_WORLD_KINDS = ((WORLD_FULL, "full"), (WORLD_MESH, "mesh_lowres"),
                (WORLD_DRAPE, "drape"), (WORLD_PLACEHOLDER, "placeholder"))


def built_elsewhere(info) -> bool:
    """Another tool built it (an engine before ``origin`` says nothing)."""
    return getattr(info, "origin", "") == TINFO.ORIGIN_OTHER


def legend_kinds(built: dict, stale: dict, world: dict | None = None,
                 custom_patch: bool = False) -> list:
    """The kinds present on the map now, in the legend's order."""
    world = world or {}
    states = {row.state for row in world.values()}
    infos = list(built.values())
    present = {kind: state in states for kind, state in _WORLD_KINDS}
    present.update({
        WORLD_NOTHING: bool(world),
        WORLD_OTHER_TOOL: any(row.origin == TINFO.ORIGIN_OTHER
                              for row in world.values()),
        BUILT: any(not built_elsewhere(i) for i in infos),
        OTHER: any(built_elsewhere(i) for i in infos),
        STALE: bool(infos) and bool(stale),
        EXTERNAL: any(getattr(i, "volume", "") for i in infos),
        CUSTOM_PATCH: bool(custom_patch),
    })
    return [kind for kind in LEGEND_LABELS if present[kind]]


def stale_label(verdict: dict) -> str:
    """The map's pill: "Stale: EGKK", "Stale: EGKK +2" (O4StaleTile.label)."""
    airports = verdict.get("airports") or []
    if not airports:
        return ""
    first = airports[0]["icao"]
    return ("Stale: %s +%d" % (first, len(airports) - 1) if len(airports) > 1
            else "Stale: %s" % first)


def _pen(kind: str, built_color: str, external_color: str):
    """The swatch's pen (MapTileLegend.Kind color / dash / lineWidth);
    None for the empty swatch of an unmarked tile."""
    if kind == WORLD_NOTHING:
        return None
    color = {
        WORLD_FULL: QColor(QTWORLD.FULL_COLOR),
        WORLD_MESH: QColor(QTWORLD.MESH_COLOR),
        WORLD_DRAPE: QColor(QTWORLD.DRAPE_COLOR),
        WORLD_PLACEHOLDER: QColor(QTWORLD.PLACEHOLDER_COLOR),
        WORLD_OTHER_TOOL: QColor(OTHER_ORTHO_COLOR),
        BUILT: QColor(built_color), OTHER: QColor(OTHER_ORTHO_COLOR),
        STALE: QColor(STALE_COLOR), EXTERNAL: QColor(external_color),
        CUSTOM_PATCH: QColor(CUSTOM_PATCH_COLOR),
    }[kind]
    if kind == WORLD_PLACEHOLDER:
        color.setAlphaF(QTWORLD.PLACEHOLDER_ALPHA)
    pen = QPen(color)
    pen.setWidthF({CUSTOM_PATCH: 3, WORLD_PLACEHOLDER: 1}.get(kind, 2))
    if kind == STALE:
        pen.setDashPattern([2, 1])
    elif kind == WORLD_OTHER_TOOL:
        pen.setDashPattern([1, 1.5])
    return pen


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
        pen = _pen(kind, built_color, external_color)
        if pen is not None:
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(QRectF(box.left() + 9, top + (line - 10) / 2, 14, 10))
        painter.setPen(QColor(235, 238, 245, 220))
        painter.drawText(QRectF(box.left() + 30, top, width - 34, line),
                         Qt.AlignVCenter | Qt.AlignLeft, LEGEND_LABELS[kind])
    painter.restore()
