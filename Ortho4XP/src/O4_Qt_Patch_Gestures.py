"""Edit mode on the Qt map (spec patch-editor-20261015 §4, §3.3; the Mac
app's ``PatchEditGestures`` and ``PatchEditKeys``).

Gestures (#1325: the same table as the Mac's ``PatchEditGestures``):

=====================  ===================================================
left click             select a node (8 px) or a line's whole shape
Shift-click            toggle a node or a shape
Shift-drag             box-select nodes
drag on a node         move the selection (snaps within 8 px, merges on
                       release while snapped)
left drag, open map    pan (the map's own rule, every map view)
click on a "+"         insert a node
right click            the context menu (never a pan)
scroll / pinch         zoom
Delete / Backspace     delete; Esc clears
=====================  ===================================================

The cursor (:func:`O4_Qt_Patch_ShapePick.pointer`) is a pointing hand
over a node, "+" handle or line, an open hand over open map and a closed
hand while panning.  A click on a LINE selects
its whole shape (#759, ``O4_Qt_Patch_ShapePick``; node > "+" > line > empty
map; a repeat click on the same spot cycles the shapes sharing that edge;
Shift-click toggles one), and a drag on a selected shape's line or nodes
moves the whole shape without snapping.  A drag never edits the
document per frame: the moved shapes are drawn here from the pointer
delta, and ONE edit commits on release.
"""
from __future__ import annotations

import math
import typing as _t

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QKeySequence, QPen, QShortcut

import O4_Qt_Patch_ShapePick as PICK
from O4_Qt_Patch_Geometry import SNAP_RADIUS_PX, below_grade, style_class
from O4_Qt_Patch_Overlay import NODE_FILL, SELECTION, STYLES, paint_styled

__all__ = ["PatchGestures", "DragSkip", "CLICK_SLOP_PX"]

#: Movement below this is a click.
CLICK_SLOP_PX = 3.0
HANDLE_STROKE = QColor("#C74078")


class DragSkip(_t.NamedTuple):
    """What the base layer leaves to the gesture layer during a node drag."""
    ways: frozenset
    nodes: frozenset


class PatchGestures:
    """The interaction state machine and its drawing."""

    IDLE, PENDING, PAN, NODES, BOX = "idle", "pending", "pan", "nodes", "box"

    def __init__(self, overlay):
        self.overlay = overlay
        self.model = overlay.model
        self.kind = self.IDLE
        self.start = QPointF()
        self.current = QPointF()
        self.last = QPointF()
        self.grabbed: int | None = None
        self.ids: list[int] = []
        self.dlat = self.dlon = 0.0
        self.snap_target: int | None = None
        self.hover_edge: tuple[int, int] | None = None
        self.pressed_handle: tuple[int, int] | None = None
        #: The line the press landed on (no node, no handle there).
        self.pressed_edge: tuple[int, int] | None = None
        self.skip: DragSkip | None = None
        overlay.gestures = self

    # ─── helpers ───────────────────────────────────────────────────────
    def _index(self):
        index = self.overlay.index
        if index is not None:
            index.project(self.overlay.transform())
        return index

    def _size(self) -> tuple[float, float]:
        vp = self.overlay.map.viewport().rect()
        return vp.width(), vp.height()

    def _handles(self, index, hover):
        return index.handles(self.model.selection, hover, *self._size(),
                             shapes=self.model.shape_selection)

    @staticmethod
    def _moved(a: QPointF, b: QPointF) -> bool:
        return math.hypot(b.x() - a.x(), b.y() - a.y()) >= CLICK_SLOP_PX

    # ─── mouse ─────────────────────────────────────────────────────────
    def press(self, event) -> bool:
        if event.button() != Qt.LeftButton:
            return False
        index = self._index()
        if index is None:
            return False
        p = event.position()
        self.start = self.current = self.last = QPointF(p)
        self.hover_edge = None
        if event.modifiers() & Qt.ShiftModifier:
            self.kind = self.BOX
            return True
        target, node, edge, best = self._target(index, p)
        m = self.model
        self.kind = self.PENDING
        if target[0] == "node":
            if node not in m.marked_nodes:
                m.select_node(node)
            self.grabbed, self.ids = node, sorted(m.marked_nodes)
            self.kind = self.NODES
        elif target[0] == "handle":
            self.pressed_handle = best[1]
        elif target[0] == "edge":
            self.pressed_edge = edge
            if m.shape_selection.intersection(PICK.shapes_on_edge(m.doc, *edge)):
                # a selected shape's line: drag the whole shape
                self.grabbed, self.ids = edge[0], sorted(m.marked_nodes)
                self.kind = self.NODES
        return True

    def _target(self, index, p: QPointF):
        """What a press at ``p`` lands on: ``(click_target, node, edge,
        (distance, handle edge) or None)``."""
        node = index.node_at(p.x(), p.y())
        edge = index.edge_at(p.x(), p.y()) if node is None else None
        best = None
        if node is None:
            handles = self._handles(index, None) + index.handles((), edge, *self._size())
            best = min(((math.hypot(x - p.x(), y - p.y()), e) for e, x, y in handles), default=None)
            if best is not None and best[0] > SNAP_RADIUS_PX:
                best = None
        return PICK.click_target(node, best is not None, edge is not None), node, edge, best

    def pointer_at(self, p: QPointF) -> str | None:
        """The cursor over ``p`` (#1325), or None to leave it to the map."""
        if not self.overlay._editing():
            return None
        if self.kind == self.BOX:
            return None
        if self.kind == self.PAN:
            return PICK.pointer(None, panning=True)
        if self.kind == self.NODES:
            return PICK.pointer(("node",))
        index = self._index()
        return PICK.pointer(self._target(index, p)[0] if index is not None else None)

    def move(self, event) -> bool:
        p = QPointF(event.position())
        if self.kind == self.IDLE:
            self._hover(p)
            return False                  # the map still reports the pointer
        moved = self._moved(self.start, p)
        if self.kind == self.PENDING and moved:
            self.model.last_shape_click = None
            self.kind = self.PAN
        if self.kind == self.PAN:
            d = p - self.last
            self.overlay.map.pan_by(d.x(), d.y())
        elif self.kind == self.NODES and (moved or self.skip is not None):
            index = self._index()
            if self.skip is None:
                ways = frozenset(w for n in self.ids for w in index.ways_by_node.get(n, ()))
                self.skip = DragSkip(ways, frozenset(self.ids))
            a = self.overlay.lat_lon(self.start)
            b = self.overlay.lat_lon(p)
            self.dlat, self.dlon = b[0] - a[0], b[1] - a[1]
            # a shape drag never snaps (#759)
            self.snap_target = (index.node_at(p.x(), p.y(), excluding=set(self.ids))
                                if not self.model.shape_selection else None)
        self.current = self.last = p
        self.overlay.update()
        return True

    def release(self, event) -> bool:
        if event.button() != Qt.LeftButton or self.kind == self.IDLE:
            return False
        p = QPointF(event.position())
        index = self._index()
        try:
            if index is None:
                return True
            if self.kind == self.NODES:
                if self.skip is not None:
                    merge = (self.grabbed, self.snap_target) if self.snap_target is not None else None
                    self.model.last_shape_click = None
                    self.model.move_selection(self.ids, self.dlat, self.dlon, merge)
                elif self.pressed_edge is not None:
                    self.model.click_edge(*self.pressed_edge, self.start.x(), self.start.y())
                else:
                    self.model.select_node(self.grabbed)
            elif self.kind == self.BOX:
                if self._moved(self.start, p):
                    found = index.nodes_in_rect(self.start.x(), self.start.y(), p.x(), p.y())
                    self.model.set_selection(self.model.selection | set(found))
                else:
                    node = index.node_at(self.start.x(), self.start.y())
                    edge = index.edge_at(self.start.x(), self.start.y())
                    if node is not None:
                        self.model.toggle(node)
                    elif edge is not None:
                        self.model.click_edge(*edge, self.start.x(), self.start.y(), toggle=True)
            elif self.kind == self.PENDING:
                if self.pressed_handle is not None:
                    self.model.insert_node(*self.pressed_handle)
                elif self.pressed_edge is not None:
                    self.model.click_edge(*self.pressed_edge, self.start.x(), self.start.y())
                else:
                    self.model.clear_selection()
            return True
        finally:
            self.reset()

    def reset(self) -> None:
        self.kind = self.IDLE
        self.snap_target = self.pressed_handle = self.pressed_edge = self.grabbed = None
        self.ids = []
        self.dlat = self.dlon = 0.0
        self.skip = None
        self.overlay.update()

    def _hover(self, p: QPointF) -> None:
        index = self._index()
        edge = index.edge_at(p.x(), p.y()) if index is not None else None
        if edge != self.hover_edge:
            self.hover_edge = edge
            self.overlay.update()

    # ─── keys ──────────────────────────────────────────────────────────
    def install_shortcuts(self, window) -> list:
        """Delete / Backspace and Esc on the window (a text field that has
        focus keeps its own Backspace through Qt's shortcut override)."""
        made = []
        for key in (QKeySequence.Delete, QKeySequence(Qt.Key_Backspace)):
            s = QShortcut(key, window)
            s.activated.connect(lambda: self.key("delete"))
            made.append(s)
        s = QShortcut(QKeySequence(Qt.Key_Escape), window)
        s.activated.connect(lambda: self.key("escape"))
        made.append(s)
        return made

    def key(self, which: str) -> bool:
        """Whether Edit mode consumed the key."""
        if not (self.overlay._editing() and self.model.has_selection):
            return False
        if which == "delete":
            return self.model.delete_selection()
        if which == "escape":
            self.model.clear_selection()
            return True
        return False

    # ─── drawing (viewport space) ──────────────────────────────────────
    def _at(self, nid: int) -> QPointF | None:
        index = self.overlay.index
        if nid not in index.row:
            return None
        x, y = index.screen(nid)
        if self.skip is None or nid not in self.skip.nodes:
            return QPointF(x, y)
        if nid == self.grabbed and self.snap_target is not None:
            return QPointF(*index.screen(self.snap_target))
        lat, lon = float(index.lat[index.row[nid]]), float(index.lon[index.row[nid]])
        return self.overlay.screen_of(lat + self.dlat, lon + self.dlon)

    def paint(self, painter) -> None:
        doc, index = self.model.doc, self.overlay.index
        if doc is None or index is None:
            return
        if self.skip is not None:
            shapes = []
            for w in self.skip.ways:
                if w < len(doc.ways):
                    way = doc.ways[w]
                    path = self.overlay.way_path(way.refs, self._at)
                    if path is not None:
                        shapes.append((style_class(way.tags), way.closed, path,
                                       below_grade(way.tags)))
            paint_styled(painter, shapes, self.overlay.hatch_phase())
        self._paint_shapes(painter, doc)
        width, height = self._size()
        painter.setPen(QPen(NODE_FILL, 1))
        painter.setBrush(SELECTION)
        for nid in self.model.marked_nodes:
            p = self._at(nid)
            if p is not None and -8 <= p.x() <= width + 8 and -8 <= p.y() <= height + 8:
                painter.drawRect(QRectF(p.x() - 4, p.y() - 4, 8, 8))
        if self.skip is not None and self.snap_target is not None:
            p = QPointF(*index.screen(self.snap_target))
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(SELECTION, 2))
            painter.drawEllipse(p, 10, 10)
        if self.kind in (self.IDLE, self.PENDING):
            for _edge, x, y in self._handles(index, self.hover_edge):
                self._paint_handle(painter, QPointF(x, y))
        if self.kind == self.BOX and self._moved(self.start, self.current):
            rect = QRectF(self.start, self.current).normalized()
            painter.setBrush(QColor(255, 255, 255, 20))
            pen = QPen(QColor(255, 255, 255, 204), 1)
            pen.setDashPattern([4, 3])
            painter.setPen(pen)
            painter.drawRect(rect)

    def _paint_shapes(self, painter, doc) -> None:
        """Selected shapes: the full outline in the selection colour at
        twice the stroke width, over a light selection tint (#759)."""
        tint = QColor(SELECTION)
        tint.setAlpha(46)
        for way in doc.ways:
            if way.id not in self.model.shape_selection:
                continue
            path = self.overlay.way_path(way.refs, self._at)
            if path is None:
                continue
            if way.closed:
                painter.fillPath(path, tint)
            pen = QPen(SELECTION, 2 * STYLES[style_class(way.tags)][2])
            pen.setJoinStyle(Qt.RoundJoin)
            painter.strokePath(path, pen)

    @staticmethod
    def _paint_handle(painter, p: QPointF) -> None:
        painter.setBrush(QColor(0x23, 0x27, 0x2F, 230))
        painter.setPen(QPen(HANDLE_STROKE, 1.4))
        painter.drawEllipse(p, 7, 7)
        painter.setPen(QPen(QColor("#FFFFFF"), 1.4))
        painter.drawLine(QPointF(p.x() - 3, p.y()), QPointF(p.x() + 3, p.y()))
        painter.drawLine(QPointF(p.x(), p.y() - 3), QPointF(p.x(), p.y() + 3))
