"""Edit mode on the Qt map (spec patch-editor-20261015 §4, §3.3; the Mac
app's ``PatchEditGestures`` and ``PatchEditKeys``).

Gestures (#1325: the same table as the Mac's ``PatchEditGestures``):

=====================  ===================================================
left click             select a node (8 px) or a line's whole shape
Shift-click            toggle a node or a shape
Shift-drag             box-select nodes
drag on a node         move the selection (snaps within 8 px, merges on
                       release while snapped; else snaps to a pack
                       object's corner or edge middle and asks Top /
                       Bottom / Keep current, #1703)
left drag, open map    pan (the map's own rule, every map view)
click on a "+"         insert a node
Alt-drag on a node     rotate its shape about the centre (#1746; Option
                       on a Mac keyboard)
click on a pack object select it: the object inspector (#1702)
right click            the context menu (never a pan)
scroll / pinch         zoom
Delete / Backspace     delete; Esc clears
=====================  ===================================================

The cursor (:func:`O4_Qt_Patch_ShapePick.pointer`) is a pointing hand
over a node, "+" handle or line, an open hand over open map and a closed
hand while panning, a rotate arrow over a node while Alt is held.  An
Alt-drag on a node turns :func:`O4_Qt_Patch_ShapePick.rotation_shapes`
about their centre (``o4_engine.patch_rotate``) and commits ONE
"Rotate Shape" edit on release (undoable; elevations kept).  A click on a
LINE selects
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

import O4_Qt_Object_Seat as SEAT
import O4_Qt_Patch_ShapePick as PICK
from o4_engine import patch_rotate as ROT
from O4_Qt_Patch_Geometry import SNAP_RADIUS_PX, below_grade, style_class
from O4_Qt_Patch_Overlay import NODE_FILL, SELECTION, STYLES, paint_styled
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QGuiApplication, QKeySequence, QPen, QPolygonF, QShortcut
from PySide6.QtWidgets import QApplication, QLineEdit

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

    IDLE, PENDING, PAN, NODES, BOX, ROTATE = "idle", "pending", "pan", "nodes", "box", "rotate"

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
        #: No node there: ``(outline, lat, lon)`` of the object snap point (#1703)
        self.object_snap: tuple | None = None
        self.hover_edge: tuple[int, int] | None = None
        self.pressed_handle: tuple[int, int] | None = None
        #: The line the press landed on (no node, no handle there).
        self.pressed_edge: tuple[int, int] | None = None
        self.skip: DragSkip | None = None
        #: An Alt-drag (#1746): the shapes turning, their centre, the angle.
        self.rotate_ways: set[int] = set()
        self.pivot: tuple[float, float] | None = None
        self.angle = 0.0
        overlay.gestures = self
        # #1693: a selection takes keyboard focus off a text field (the
        # search box) so Delete / Backspace reach the selection.
        self.model.selection_changed.connect(self.focus_map_on_selection)

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
        m = self.model
        if event.modifiers() & Qt.AltModifier and self._press_rotate(index, p):
            return True
        target, node, edge, best = self._target(index, p)
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

    def _press_rotate(self, index, p: QPointF) -> bool:
        """Alt-press on a node: select the shapes it turns and start."""
        node = index.node_at(p.x(), p.y())
        if node is None:
            return False
        m = self.model
        ways = PICK.rotation_shapes(m.doc, node, m.shape_selection)
        pivot = ROT.centre(m.doc.nodes, [w.refs for w in m.doc.ways if w.id in ways])
        if pivot is None:
            return False
        m.select_shapes(ways)
        self.rotate_ways, self.pivot = ways, pivot
        self.ids = sorted(m.marked_nodes)
        self.kind = self.ROTATE
        return True

    @staticmethod
    def rotation(start: QPointF, p: QPointF, pivot: QPointF) -> float:
        """The pointer angle since the press, degrees counter-clockwise on
        the ground (screen y points down, so the screen angle flips)."""
        d = -math.degrees(math.atan2(p.y() - pivot.y(), p.x() - pivot.x())
                          - math.atan2(start.y() - pivot.y(), start.x() - pivot.x()))
        return d - 360.0 if d > 180.0 else d + 360.0 if d < -180.0 else d

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
        if self.kind == self.ROTATE:
            return "rotate"
        index = self._index()
        alt = bool(QGuiApplication.queryKeyboardModifiers() & Qt.AltModifier)
        return PICK.pointer(self._target(index, p)[0] if index is not None else None, rotate=alt)

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
            self.object_snap = self._object_snap(p) if self.snap_target is None \
                and not self.model.shape_selection else None
        elif self.kind == self.ROTATE and (moved or self.skip is not None):
            if self.skip is None:
                index = self._index()
                ways = frozenset(w for n in self.ids for w in index.ways_by_node.get(n, ()))
                self.skip = DragSkip(ways, frozenset(self.ids))
            self.angle = self.rotation(self.start, p, self.overlay.screen_of(*self.pivot))
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
                if self.skip is not None and self.object_snap is not None:
                    self.model.last_shape_click = None
                    self._drop_on_object(event)
                elif self.skip is not None:
                    merge = (self.grabbed, self.snap_target) if self.snap_target is not None else None
                    self.model.last_shape_click = None
                    self.model.move_selection(self.ids, self.dlat, self.dlon, merge)
                elif self.pressed_edge is not None:
                    self.model.click_edge(*self.pressed_edge, self.start.x(), self.start.y())
                else:
                    self.model.select_node(self.grabbed)
            elif self.kind == self.ROTATE:
                if self.skip is not None:
                    self.model.rotate_shapes(self.rotate_ways, self.angle)
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
                    # open map: a pack object under the click, else nothing
                    self.model.clear_selection()
                    inspector = getattr(self.overlay, "inspector", None)
                    if inspector is not None:
                        inspector.clear()
                        inspector.select_at(*self.overlay.lat_lon(self.start))
            return True
        finally:
            self.reset()

    def _object_snap(self, p: QPointF):
        """The pack object snap point under the pointer (#1703), or None."""
        outlines = self.overlay.outlines
        if outlines is None or not outlines.enabled:
            return None

        def to_screen(lat: float, lon: float) -> tuple[float, float]:
            q = self.overlay.screen_of(lat, lon)
            return q.x(), q.y()
        return SEAT.vertex_at(outlines.footprints, to_screen, p.x(), p.y(), SNAP_RADIUS_PX)

    def _drop_on_object(self, event) -> None:
        """The grabbed node onto the object's point exactly (one step), then
        Top / Bottom / Keep current when the object has a height."""
        outline, lat, lon = self.object_snap
        node = self.model.doc.nodes.get(self.grabbed)
        if node is None:
            return
        done = self.model.move_selection(self.ids, lat - node[1], lon - node[2], None,
                                         name="Move to Object")
        inspector = getattr(self.overlay, "inspector", None)
        if done and inspector is not None:
            view = self.overlay.map.viewport()
            inspector.offer_top_or_bottom(self.grabbed, outline.object, view,
                                          view.mapToGlobal(event.position().toPoint()))

    def reset(self) -> None:
        self.kind = self.IDLE
        self.snap_target = self.pressed_handle = self.pressed_edge = self.grabbed = None
        self.object_snap = None
        self.ids = []
        self.dlat = self.dlon = self.angle = 0.0
        self.skip = self.pivot = None
        self.rotate_ways = set()
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

    def focus_map_on_selection(self) -> None:
        """Move focus from a text field to the map when Edit mode selects
        something (#1693)."""
        if not (self.overlay._editing() and self.model.has_selection):
            return
        if isinstance(QApplication.focusWidget(), QLineEdit):
            self.overlay.map.setFocus(Qt.OtherFocusReason)

    def key(self, which: str) -> bool:
        """Whether Edit mode consumed the key."""
        inspector = getattr(self.overlay, "inspector", None)
        if (which == "escape" and self.overlay._editing() and not self.model.has_selection
                and inspector is not None and inspector.selected is not None):
            inspector.clear()                   # Esc drops a selected pack object (#1702)
            return True
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
        lat, lon = float(index.lat[index.row[nid]]), float(index.lon[index.row[nid]])
        if self.kind == self.ROTATE:
            return self.overlay.screen_of(*ROT.rotate_point(lat, lon, self.pivot, self.angle))
        if nid == self.grabbed and self.snap_target is not None:
            return QPointF(*index.screen(self.snap_target))
        if nid == self.grabbed and self.object_snap is not None:
            return self.overlay.screen_of(*self.object_snap[1:])
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
        elif self.skip is not None and self.object_snap is not None:
            # the object snap: a diamond on the footprint point (#1703)
            p = self.overlay.screen_of(*self.object_snap[1:])
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(SELECTION, 2))
            painter.drawPolygon(QPolygonF([QPointF(p.x(), p.y() - 10), QPointF(p.x() + 10, p.y()),
                                           QPointF(p.x(), p.y() + 10), QPointF(p.x() - 10, p.y())]))
        if self.kind == self.ROTATE and self.skip is not None:
            c = self.overlay.screen_of(*self.pivot)      # the rotation's centre
            painter.setPen(QPen(SELECTION, 2))
            painter.drawLine(QPointF(c.x() - 6, c.y()), QPointF(c.x() + 6, c.y()))
            painter.drawLine(QPointF(c.x(), c.y() - 6), QPointF(c.x(), c.y() + 6))
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
