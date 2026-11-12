"""The Build map's World states (Qt half; the Mac app's ``MapWorldStates``,
same colours — #2024): what the World pack draws on each tile.

Borders only, never a fill (#1256): a full tile is the built-tile green,
a mesh whose imagery streams is teal with its sharp fraction as a bar
along its bottom edge, a drape is pink, a placeholder a faint thin gray
outline; a tile with nothing is left unmarked.  Another tool's mesh is
dotted.  Painted in scene space under the built-tile borders.
"""
from __future__ import annotations

import O4_Tile_Info as TINFO
from o4_engine import world_state as WS
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPen

__all__ = ["FULL_COLOR", "MESH_COLOR", "DRAPE_COLOR", "PLACEHOLDER_COLOR",
           "PLACEHOLDER_ALPHA", "OTHER_TOOL_DASH", "STATE_COLORS", "from_wire",
           "paint_world"]

#: The built-tile green (O4_Qt_Map.BUILT_COLOR, MapCanvasView.builtTile).
FULL_COLOR = "#4CAF6E"
MESH_COLOR = "#30B0C7"
DRAPE_COLOR = "#FF6482"
PLACEHOLDER_COLOR = "#D9D9D9"
#: The placeholder outline's opacity (MapWorldStates.placeholderOpacity).
PLACEHOLDER_ALPHA = 0.30
#: Another tool's mesh: the border's dash (MapWorldStates.otherToolDash).
OTHER_TOOL_DASH = (2, 3)
STATE_COLORS = {WS.FULL: FULL_COLOR, WS.MESH_LOWRES: MESH_COLOR,
                WS.DRAPE: DRAPE_COLOR, WS.PLACEHOLDER: PLACEHOLDER_COLOR}


def from_wire(rows) -> dict:
    """``{(lat, lon): world_state.WorldTile}`` of ``ScanBatch.world`` rows."""
    out = {}
    for row in rows or ():
        if len(row) >= 7:
            out[(int(row[0]), int(row[1]))] = WS.WorldTile(
                row[2], row[3], float(row[4] or 0), row[5], row[6])
    return out


def _pen(color: str, alpha: float, width: float, dash=None) -> QPen:
    c = QColor(color)
    c.setAlphaF(alpha)
    pen = QPen(c)
    pen.setCosmetic(True)
    pen.setWidthF(width)
    if dash:
        pen.setDashPattern(list(dash))
    return pen


def paint_world(painter, world: dict, tiles, tile_rect, scale: float,
                skip=lambda tile: False) -> None:
    """Each visible tile's World state; ``tiles`` the visible (lat, lon),
    ``tile_rect(lat, lon)`` its scene rect, ``skip`` a tile being built."""
    if not world:
        return
    painter.save()
    painter.setBrush(Qt.NoBrush)
    placeholder = _pen(PLACEHOLDER_COLOR, PLACEHOLDER_ALPHA, 1)
    for tile in tiles:
        row = world.get(tile)
        if row is None or skip(tile):
            continue
        color = STATE_COLORS.get(row.state)
        if color is None:
            continue
        r = tile_rect(*tile)
        if row.state == WS.PLACEHOLDER:
            painter.setPen(placeholder)
            inset = 1.0 / max(scale, 1e-12)
            painter.drawRect(r.adjusted(inset, inset, -inset, -inset))
            continue
        painter.setPen(_pen(color, 0.85, 2,
                            OTHER_TOOL_DASH if row.origin == TINFO.ORIGIN_OTHER else None))
        painter.drawRect(r)
        px = r.width() * scale
        if row.state == WS.MESH_LOWRES and px > 24:
            _sharp_bar(painter, r, scale, row.sharp)
    painter.restore()


def _sharp_bar(painter, r: QRectF, scale: float, sharp: float) -> None:
    """The mesh tile's sharp fraction along its bottom edge."""
    unit = 1.0 / max(scale, 1e-12)
    h = min(max(r.height() * scale * 0.05, 3), 6) * unit
    bar = QRectF(r.left() + 3 * unit, r.bottom() - h - 3 * unit,
                 r.width() - 6 * unit, h)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(0, 0, 0, 89))
    painter.drawRect(bar)
    painter.setBrush(QColor(FULL_COLOR))
    painter.drawRect(QRectF(bar.left(), bar.top(),
                            bar.width() * min(max(sharp, 0.0), 1.0), h))
    painter.setBrush(Qt.NoBrush)
