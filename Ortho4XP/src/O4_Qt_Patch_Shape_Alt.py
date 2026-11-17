"""A patch shape's own elevation in the Qt editor (issue #2137; the Mac
app's ``PatchShapeAltitudeBox`` and ``PatchSlopeMarksLayer``).

An Ortho4XP patch way can carry ONE elevation for the whole shape
(``cst_alt_abs``, ``cst_alt_rel``, ``var_alt_rel``, the legacy
``altitude``) or be a sloping rectangle (``altitude_high`` /
``altitude_low``); ``o4_engine.patch_shape_alt`` reads and writes the tags.

* :class:`ShapeAltBox` — the shape inspector's rows: the value(s) as
  editable fields; Return writes them back, ONE undo step.
* :class:`SlopeLayer` — the map drawing (owner 2026-11-17 15:58Z): the
  high edge drawn thicker, a large outlined arrow pointing from the high
  side to the low side, a label at each end against its edge ("High
  172.4 m" / "Low 170.9 m").  In Edit mode a click on a label opens a field
  for that side's value.

The words are twin-checked against the Mac by
``tests/test_qt_layout_parity.py``.
"""
from __future__ import annotations

import typing as _t

from o4_engine import patch_shape_alt as SA
from O4_Qt_Patch_Elevation import parse_number
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QLineEdit, QVBoxLayout, QWidget

__all__ = ["ShapeAltBox", "SlopeLayer", "LEVEL_TITLE", "MEAN_OFFSET_TITLE",
           "GROUND_OFFSET_TITLE", "SLOPE_TITLE", "HIGH_TITLE", "LOW_TITLE"]

LEVEL_TITLE = "Shape elevation"
MEAN_OFFSET_TITLE = "Above mean ground"
GROUND_OFFSET_TITLE = "Above ground"
SLOPE_TITLE = "Sloping rectangle"
HIGH_TITLE = "High side"
LOW_TITLE = "Low side"
_TITLES = {SA.ABSOLUTE: LEVEL_TITLE, SA.MEAN_OFFSET: MEAN_OFFSET_TITLE,
           SA.GROUND_OFFSET: GROUND_OFFSET_TITLE}

HIGH_EDGE_WIDTH = 6.0
ARROW_LINE = 2.0
LINE = QColor("#F2F4F8")
HALO = QColor(11, 13, 18, 140)


def _metres(value: float | None) -> str:
    return "" if value is None else "%.2f" % value


def _note() -> QLabel:
    label = QLabel()
    label.setWordWrap(True)
    label.setStyleSheet("color: palette(mid); font-size: 11px;")
    return label


class _Field(QWidget):
    """One value in metres; Return applies it."""

    def __init__(self, apply: _t.Callable[[float], _t.Any]):
        super().__init__()
        h = QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        self.title = QLabel()
        self.title.setStyleSheet("color: palette(mid);")
        self.edit = QLineEdit()
        self.edit.setFixedWidth(90)
        h.addWidget(self.title)
        h.addStretch(1)
        h.addWidget(self.edit)
        h.addWidget(QLabel("m"))
        self._shown: tuple | None = None

        def go():
            v = parse_number(self.edit.text())
            if v is not None:
                apply(v)
        self.edit.returnPressed.connect(go)

    def show_value(self, title: str, key: tuple, value: float | None) -> None:
        """Refill only when the shape or its value changed, so a field being
        typed in keeps its text."""
        self.title.setText(title)
        if self._shown != (key, value):
            self._shown = (key, value)
            self.edit.setText(_metres(value))
            self.edit.setPlaceholderText("from the mesh" if value is None else "")


class ShapeAltBox(QWidget):
    """The inspector rows for one selected shape's own elevation tags."""

    def __init__(self, model):
        super().__init__()
        self.model = model
        self.way_id: int | None = None
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(4)
        self.slope_title = QLabel(SLOPE_TITLE)
        self.slope_title.setStyleSheet("font-weight: 600;")
        self.level = _Field(lambda x: model.set_shape_level(self.way_id, x))
        self.high = _Field(lambda x: model.set_slope(self.way_id, "high", x))
        self.low = _Field(lambda x: model.set_slope(self.way_id, "low", x))
        self.notes = _note()
        for w in (self.slope_title, self.level, self.high, self.low, self.notes):
            v.addWidget(w)
        self.setVisible(False)

    def refresh(self, way, nodes_with_elevation: int) -> None:
        """Show ``way``'s value(s), or hide when its tags state none."""
        found = SA.shape_alt(way.tags, way.refs) if way is not None else None
        self.setVisible(found is not None)
        if found is None:
            self.way_id = None
            return
        self.way_id = way.id
        slope = found["form"] == SA.SLOPE
        for w in (self.slope_title, self.high, self.low):
            w.setVisible(slope)
        self.level.setVisible(not slope)
        notes = []
        if slope:
            self.high.show_value(HIGH_TITLE, (way.id, "high"), found["high"])
            self.low.show_value(LOW_TITLE, (way.id, "low"), found["low"])
            if not found["valid"]:
                notes.append("Not four corners: the build skips this shape.")
            if (found["high"] is None) != (found["low"] is None):
                notes.append("The build takes both sides from the mesh until both are numbers.")
            notes.append("The arrow on the map points downhill; click its labels to edit.")
        else:
            self.level.show_value(_TITLES[found["form"]], (way.id, found["key"]), found["value"])
            notes.append("Tag %s" % found["key"] + ("" if found["form"] == SA.ABSOLUTE
                                                    else ": metres added to the ground under the shape."))
            if nodes_with_elevation > 0:
                notes.append("%s nodes carry their own elevation; the build uses theirs."
                             % format(nodes_with_elevation, ","))
        self.notes.setText("\n".join(notes))


def _slope_shapes(doc) -> list[tuple[int, dict, float | None, float | None]]:
    """``(way id, slope_marks, high, low)`` for every valid sloping rectangle."""
    out = []
    for way in doc.ways if doc is not None else ():
        found = SA.shape_alt(way.tags, way.refs)
        if not found or found["form"] != SA.SLOPE or not found["valid"]:
            continue
        corners = [doc.nodes[r][1:3] for r in way.refs[:4] if r in doc.nodes]
        marks = SA.slope_marks(corners)
        if marks is not None:
            out.append((way.id, marks, found["high"], found["low"]))
    return out


class _ValuePopup(QFrame):
    """The field a label opens (the Mac's popover)."""

    def __init__(self, parent, title: str, value: float | None, apply):
        super().__init__(parent, Qt.Popup)
        h = QHBoxLayout(self)
        h.addWidget(QLabel(title))
        self.edit = QLineEdit(_metres(value))
        self.edit.setPlaceholderText("from the mesh" if value is None else "")
        self.edit.setFixedWidth(90)
        h.addWidget(self.edit)
        h.addWidget(QLabel("m"))

        def go():
            v = parse_number(self.edit.text())
            if v is not None:
                apply(v)
                self.close()
        self.edit.returnPressed.connect(go)


class SlopeLayer:
    """The sloping rectangles on the patch overlay: drawn by
    :meth:`paint` (screen coordinates through ``overlay.screen_of``), the
    labels hit-tested by :meth:`press` in Edit mode."""

    def __init__(self, overlay):
        self.overlay = overlay
        self.shapes: list[tuple[int, dict, float | None, float | None]] = []
        self.labels: list[tuple[QRectF, int, str, float | None]] = []
        self.popup: _ValuePopup | None = None

    def rebuild(self, doc) -> None:
        self.shapes = _slope_shapes(doc)

    def paint(self, painter) -> None:
        self.labels = []
        if not self.shapes:
            return
        at = self.overlay.screen_of
        edges, arrows = QPainterPath(), QPainterPath()
        for _wid, m, _hi, _lo in self.shapes:
            a, b = (at(*p) for p in m["high_edge"])
            edges.moveTo(a)
            edges.lineTo(b)
            arrows.addPolygon(QPolygonF([at(*p) for p in m["arrow"]]))
            arrows.closeSubpath()
        painter.save()
        painter.setRenderHint(painter.RenderHint.Antialiasing, True)
        painter.setBrush(Qt.NoBrush)
        for width, color in ((HIGH_EDGE_WIDTH + 2, HALO), (HIGH_EDGE_WIDTH, LINE)):
            pen = QPen(color, width)
            pen.setCapStyle(Qt.RoundCap)
            painter.setPen(pen)
            painter.drawPath(edges)
        fill = QColor(HALO)
        fill.setAlpha(56)
        painter.fillPath(arrows, fill)
        for width, color in ((ARROW_LINE + 2, HALO), (ARROW_LINE, LINE)):
            pen = QPen(color, width)
            pen.setJoinStyle(Qt.RoundJoin)
            painter.setPen(pen)
            painter.drawPath(arrows)
        editing = self.overlay.model.mode == "Edit"
        fm = painter.fontMetrics()
        for wid, m, hi, lo in self.shapes:
            for side, value in (("high", hi), ("low", lo)):
                text = SA.slope_label(side, value)
                c = at(*m["%s_label" % side])
                w, h = fm.horizontalAdvance(text) + 12, fm.height() + 4
                box = QRectF(c.x() - w / 2, c.y() - h / 2, w, h)
                painter.setPen(QPen(QColor(255, 255, 255, 204 if editing else 77), 1))
                painter.setBrush(QColor(0, 0, 0, 153))
                painter.drawRoundedRect(box, h / 2, h / 2)
                painter.setPen(QColor("white"))
                painter.drawText(box, Qt.AlignCenter, text)
                self.labels.append((box, wid, side, value))
        painter.restore()

    def label_at(self, pos: QPointF) -> tuple[int, str, float | None] | None:
        for box, wid, side, value in self.labels:
            if box.contains(pos):
                return wid, side, value
        return None

    def press(self, pos: QPointF) -> bool:
        """A click on a label in Edit mode opens its field; True when taken."""
        hit = self.label_at(pos)
        if hit is None:
            return False
        wid, side, value = hit
        model = self.overlay.model
        view = self.overlay.map.viewport()
        self.popup = _ValuePopup(view, HIGH_TITLE if side == "high" else LOW_TITLE, value,
                                 lambda v: model.set_slope(wid, side, v))
        self.popup.move(view.mapToGlobal(pos.toPoint()))
        self.popup.show()
        self.popup.edit.setFocus()
        return True
