"""The pack reference outlines on the Qt patch layer (spec
patch-editor-20261015 §2 as amended before L4, A4; mockup "Pack outlines").

Two engine reads, drawn under the patch when the map toolbar's "Pack
outlines" box is ticked: a dark long-dash stroke over a light translucent
fill, and from ZL 18 a label on each outline that has room (#1316):

* ``pack_outlines {tile, icao}`` — the pack's apt.dat pavement (row 110)
  and boundary (row 130) rings (an engine without the command is skipped).
* building footprints from the ``pack_objects`` result — the plan outline
  of each placed model (the convex hull of its grey-massing vertices,
  turned by the placement's heading) and each facade's ring.  Asked
  ``footprints_only`` (#797): the engine sends each model's plan hull and
  no massing (OTHH's full answer is 47 MB, the outlines a few points
  each).  The request box is the 3D preview's (patch bbox + 500 m, A9).

A label is the pavement row's description (``pack_outlines`` ``label``)
or the object's file name; :meth:`PackOutlines.label_at` reports the same
text for the map's cursor readout.  The look is the ``STROKE_*`` /
``FILL_*`` / ``LINE_WIDTH`` / ``DASH`` / ``LABEL_*`` constants below, the
Mac app's ``PackOutlineStyle`` (``tests/test_qt_pack_outline_style.py``
holds the two equal).  Tile overlays are NOT filled (#1256): only these.
"""
from __future__ import annotations

import base64
import math
import typing as _t

import numpy as np
from O4_Qt_Patch_Geometry import scene_xy
from PySide6.QtCore import QObject, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainterPath, QPen, QPolygonF

__all__ = ["PackOutlines", "Outline", "request_bbox", "model_footprint", "placed_ring",
           "footprints_from_pack_objects", "labelled_footprints", "pavement_outlines",
           "file_label", "ring_contains", "place_labels", "MARGIN_M", "OUTLINE_COLOR",
           "FILL_COLOR", "LEGEND_FILL", "TOGGLE_HELP"]

#: The 3D preview's margin round the patch bbox (A9).
MARGIN_M = 500.0
#: The engine's local plane (``emit/osm_adapter._local_metres``).
METRES_PER_DEG_LAT = 111_320.0

# The look (#1316: "a bit darker and heavier stroke … a light translucent
# color"); the Mac app's ``PackOutlineStyle`` has the same values.
STROKE_RGB = 0x3D4757
STROKE_ALPHA = 0.9
LINE_WIDTH = 1.8
#: Long dash, in px: 10 on, 4 off.
DASH = (10.0, 4.0)
FILL_RGB = 0xC8D0DC
FILL_ALPHA = 0.12
#: Labels show from this zoom level, at this point size, on a dark pill.
LABEL_MIN_ZL = 18.0
LABEL_POINT_SIZE = 10.0
LABEL_BACK_ALPHA = 0.55
#: Labels closer than this (px) to a drawn one are skipped.
LABEL_GAP = 4.0


def _rgba(rgb: int, alpha: float) -> QColor:
    return QColor((rgb >> 16) & 0xFF, (rgb >> 8) & 0xFF, rgb & 0xFF, round(alpha * 255))


OUTLINE_COLOR = _rgba(STROKE_RGB, STROKE_ALPHA)
FILL_COLOR = _rgba(FILL_RGB, FILL_ALPHA)
#: The legend swatch's fill: the same colour, opaque enough to read on
#: the legend's dark panel.
LEGEND_FILL = _rgba(FILL_RGB, 0.6)
TOGGLE_HELP = ("Show the airport pack's own pavement, boundary and building outlines "
               "under the patch, for reference; zoom in to read their names.")


def _m_per_deg_lon(lat: float) -> float:
    return METRES_PER_DEG_LAT * max(math.cos(math.radians(lat)), 1e-6)


def request_bbox(nodes: _t.Iterable[tuple]) -> list[float] | None:
    """``[min_lat, min_lon, max_lat, max_lon]`` of the nodes + 500 m."""
    rows = list(nodes)
    if not rows:
        return None
    lats = [n[1] for n in rows]
    lons = [n[2] for n in rows]
    mid = (min(lats) + max(lats)) / 2
    d_lat, d_lon = MARGIN_M / METRES_PER_DEG_LAT, MARGIN_M / _m_per_deg_lon(mid)
    return [min(lats) - d_lat, min(lons) - d_lon, max(lats) + d_lat, max(lons) + d_lon]


def model_footprint(vertices_b64: str) -> list[tuple[float, float]]:
    """A model's plan outline in its authored frame, ``(x, z)`` metres at
    heading 0 (OBJ8: x east, z south): the 2-D convex hull of all its
    grey-massing vertices (the Mac app's ``PackFootprints.planHull``)."""
    from scipy.spatial import ConvexHull, QhullError
    v = np.frombuffer(base64.b64decode(vertices_b64), dtype="<f4").reshape(-1, 3)
    pts = np.unique(np.column_stack([v[:, 0], v[:, 2]]).astype(np.float64), axis=0)
    if len(pts) < 3:
        return []
    try:
        return [(float(pts[k][0]), float(pts[k][1])) for k in ConvexHull(pts).vertices]
    except QhullError:                  # all collinear: no area, no outline
        return []


def placed_ring(hull: _t.Sequence[tuple[float, float]], lat: float, lon: float,
                heading_deg: float) -> list[tuple[float, float]]:
    """An authored plan hull at a placement, turned clockwise from north by
    the heading (as the 3D window turns the model), as ``(lat, lon)``."""
    h = math.radians(heading_deg)
    c, s = math.cos(h), math.sin(h)
    m_lon = _m_per_deg_lon(lat)
    return [(lat - (s * x + c * z) / METRES_PER_DEG_LAT, lon + (c * x - s * z) / m_lon)
            for (x, z) in hull]


def file_label(path: str | None, fallback: str) -> str:
    """An object's label: its file name (``lib/terminal.obj`` →
    ``terminal.obj``), or ``fallback`` when the engine sent none."""
    name = (path or "").replace("\\", "/").rstrip("/").rsplit("/", 1)[-1]
    return name or fallback


def footprints_from_pack_objects(result: _t.Mapping) -> list[list[tuple[float, float]]]:
    """Every footprint ring ``[(lat, lon), …]`` of a ``pack_objects``
    result (:func:`labelled_footprints` without the labels)."""
    return [ring for _label, ring in labelled_footprints(result)]


def labelled_footprints(result: _t.Mapping) -> list[tuple[str, list[tuple[float, float]]]]:
    """``(label, ring)`` per footprint of a ``pack_objects`` result: one
    per drawn placement (a model with fewer than three distinct plan points
    has none), labelled by the model's file name, then one per facade
    (its ``.fac`` name).  A model carries its plan hull (a
    ``footprints_only`` answer) or its massing vertices."""
    hulls = {m["key"]: model_footprint(m["vertices_f32_b64"]) if "plan_hull_f32_b64" not in m
             else [(float(x), float(z)) for x, z in np.frombuffer(
                 base64.b64decode(m["plan_hull_f32_b64"]), dtype="<f4").reshape(-1, 2)]
             for m in result.get("models") or ()}
    out: list[tuple[str, list[tuple[float, float]]]] = []
    for p in result.get("placements") or ():
        hull = hulls.get(p["model"])
        if hull and len(hull) >= 3:
            out.append((file_label(str(p["model"]), "object"),
                        placed_ring(hull, float(p["lat"]), float(p["lon"]),
                                    float(p.get("heading_deg") or 0.0))))
    for f in result.get("facades") or ():
        if len(f["ring"]) >= 3:
            out.append((file_label(f.get("def"), "facade"),
                        [(float(la), float(lo)) for la, lo in f["ring"]]))
    return out


def pavement_outlines(reply: _t.Mapping) -> list[tuple[str, list]]:
    """``(label, rings)`` per ``pack_outlines`` item (exterior first, then
    holes); an engine without labels names it by its kind."""
    return [(str(item.get("label") or item.get("kind") or "pavement"), list(item["rings"]))
            for item in reply.get("pavement") or () if item.get("rings")]


def ring_contains(ring: _t.Sequence, lat: float, lon: float) -> bool:
    """Whether ``(lat, lon)`` is inside the closed ``[(lat, lon), …]`` ring
    (even-odd ray cast; the Mac app's ``PackOutlineGeometry.contains``)."""
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        (ai, oi), (aj, oj) = ring[i][:2], ring[j][:2]
        if (ai > lat) != (aj > lat) and lon < (oj - oi) * (lat - ai) / (aj - ai) + oi:
            inside = not inside
        j = i
    return inside


def _area(ring: _t.Sequence) -> float:
    """The ring's plan area in square degrees (to rank, not to measure)."""
    a = 0.0
    for (la0, lo0), (la1, lo1) in zip(ring, list(ring[1:]) + [ring[0]], strict=True):
        a += lo0 * la1 - lo1 * la0
    return abs(a) / 2


class Outline(_t.NamedTuple):
    """One pack outline: the label, ``(lat, lon)`` rings (exterior first,
    then holes), its path in map scene units (odd-even, so holes stay
    open), the path's bounds, its area rank and the label's scene anchor
    (the exterior's vertex mean)."""

    label: str
    rings: tuple
    path: QPainterPath
    bounds: QRectF
    area: float
    anchor: QPointF


def _outline(label: str, rings: _t.Sequence[_t.Sequence], zoomlevel: int) -> Outline | None:
    rings = tuple(tuple((float(p[0]), float(p[1])) for p in r) for r in rings if len(r) >= 3)
    if not rings:
        return None
    path = _path(rings, zoomlevel)
    ext = np.asarray(rings[0], dtype=np.float64)
    ax, ay = scene_xy(ext[:, 0].mean(), ext[:, 1].mean(), zoomlevel)
    return Outline(label, rings, path, path.boundingRect(), _area(rings[0]),
                   QPointF(float(ax), float(ay)))


def _outlines(labelled: _t.Iterable[tuple[str, _t.Sequence]], zoomlevel: int) -> list[Outline]:
    return [o for o in (_outline(label, rings, zoomlevel) for label, rings in labelled)
            if o is not None]


def place_labels(candidates: _t.Iterable[tuple[str, QRectF]],
                 within: QRectF) -> list[tuple[str, QRectF]]:
    """The labels that fit: ``candidates`` (text, screen box) in priority
    order, each kept unless it leaves ``within`` or comes nearer than
    ``LABEL_GAP`` to one already kept."""
    kept: list[tuple[str, QRectF]] = []
    for text, box in candidates:
        if not within.contains(box):
            continue
        grown = box.adjusted(-LABEL_GAP, -LABEL_GAP, LABEL_GAP, LABEL_GAP)
        if any(grown.intersects(k) for _, k in kept):
            continue
        kept.append((text, box))
    return kept


def _path(rings: _t.Iterable[_t.Sequence], zoomlevel: int) -> QPainterPath:
    """Closed ``[(lat, lon), …]`` rings as one path in map scene units."""
    path = QPainterPath()
    for ring in rings:
        if len(ring) < 2:
            continue
        arr = np.asarray(ring, dtype=np.float64)
        xs, ys = scene_xy(arr[:, 0], arr[:, 1], zoomlevel)
        path.addPolygon(QPolygonF([QPointF(x, y) for x, y in zip(xs, ys)]))
        path.closeSubpath()
    return path


class PackOutlines(QObject):
    """The "Pack outlines" layer: follows the loaded patch, asks only while
    the toggle is on (remembered per user, on by default), filled and drawn
    in scene units under a cosmetic dashed pen, labelled from ZL 18."""

    changed = Signal()

    def __init__(self, engine, model, zoomlevel: int, enabled: bool = True,
                 remember: _t.Callable[[bool], None] = lambda _on: None, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.model = model
        self.zoomlevel = zoomlevel
        self.enabled = bool(enabled)
        self._remember = remember
        #: The engine's sentences about what could not be read.
        self.missing: list[str] = []
        self._loaded = None                 # (generation, tile, icao)
        #: The apt.dat pavement and boundary, and the building footprints.
        self.pavement: list[Outline] = []
        self.footprints: list[Outline] = []
        model.document_changed.connect(self._reload_if_needed)

    @property
    def help_text(self) -> str:
        """The toggle's tooltip: what it does, then what could not be read."""
        return TOGGLE_HELP + ("\n\n" + "\n".join(self.missing) if self.missing else "")

    def set_enabled(self, on: bool) -> None:
        if bool(on) == self.enabled:
            return
        self.enabled = bool(on)
        self._remember(self.enabled)
        if self.enabled:
            self._reload_if_needed()
        self.changed.emit()

    def _key(self):
        """Which open this is: a load bumps ``generation``; a save moves
        ``path`` (auto → edited file) but is the same open, so it never
        asks again (owner 1.0.398: saves re-fetched ``pack_objects``)."""
        p = self.model.patch
        return None if p is None else (self.model.generation, p.tile, p.icao)

    def _reload_if_needed(self) -> None:
        """Every edit announces the document; only a new one reloads."""
        if self.model.doc is None:
            self._clear()
        elif self._key() != self._loaded:
            self._reload()

    def _clear(self) -> None:
        self._loaded = None
        self.pavement, self.footprints, self.missing = [], [], []
        self.changed.emit()

    def _reload(self) -> None:
        self._clear()
        m = self.model
        if not self.enabled or m.doc is None:
            return
        key = self._loaded = self._key()
        tile, icao = m.patch.tile, m.patch.icao

        def outlines(reply, error):
            if self._loaded != key:
                return
            if error is not None:
                self.missing.append(error)
            else:
                self.pavement = _outlines(pavement_outlines(reply), self.zoomlevel)
                self.missing += list(reply.get("missing") or ())
            self.changed.emit()
        if self.engine.has("pack_outlines"):
            self.engine.call("pack_outlines", outlines, tile=tile, icao=icao)

        def objects(result, error):
            if self._loaded != key:
                return
            if error is not None:
                self.missing.append("Pack buildings: %s" % error)
            else:
                self.footprints = _outlines(((label, [ring]) for label, ring
                                             in labelled_footprints(result)), self.zoomlevel)
            self.changed.emit()
        # The 3D window's box (A9); the outlines only (#797)
        self.engine.pack_objects(tile, icao, request_bbox(m.doc.nodes.values()), objects,
                                 footprints_only=True)

    def label_at(self, lat: float, lon: float) -> str | None:
        """The label of the smallest outline under ``(lat, lon)`` (inside
        its exterior, not in a hole), or None; nothing while it is off."""
        if not self.enabled:
            return None
        best = None
        for o in self.pavement + self.footprints:
            if best is not None and o.area >= best.area:
                continue
            if ring_contains(o.rings[0], lat, lon) and not any(
                    ring_contains(h, lat, lon) for h in o.rings[1:]):
                best = o
        return None if best is None else best.label

    def paint(self, painter, view_transform) -> None:
        """The filled, long-dashed layer under the patch, then its labels
        from ZL 18 (painter in viewport space)."""
        if not self.enabled:
            return
        vp = QRectF(painter.viewport())
        visible = view_transform.inverted()[0].mapRect(vp)
        shown = [o for o in self.pavement + self.footprints if o.bounds.intersects(visible)]
        painter.save()
        painter.setTransform(view_transform)
        pen = QPen(OUTLINE_COLOR)
        pen.setCosmetic(True)
        pen.setWidthF(LINE_WIDTH)
        pen.setDashPattern([d / LINE_WIDTH for d in DASH])     # in pen widths
        for o in shown:
            painter.fillPath(o.path, FILL_COLOR)
        painter.setBrush(Qt.NoBrush)
        painter.setPen(pen)
        for o in shown:
            painter.drawPath(o.path)
        painter.restore()
        zl = self.zoomlevel + math.log2(max(view_transform.m11(), 1e-9))
        if zl >= LABEL_MIN_ZL - 1e-9:
            self._paint_labels(painter, view_transform, shown, vp)

    def _paint_labels(self, painter, view_transform, shown: list[Outline], vp: QRectF) -> None:
        """Smallest outline first, so a building names itself before the
        apron under it; a label that would collide is skipped."""
        painter.save()
        font = QFont(painter.font())
        font.setPointSizeF(LABEL_POINT_SIZE)
        painter.setFont(font)
        fm = painter.fontMetrics()
        h = fm.height() + 2

        def box(o: Outline) -> tuple[str, QRectF]:
            c = view_transform.map(o.anchor)
            w = fm.horizontalAdvance(o.label) + 8
            return o.label, QRectF(c.x() - w / 2, c.y() - h / 2, w, h)
        kept = place_labels((box(o) for o in sorted(shown, key=lambda o: o.area)), vp)
        back = QColor(0, 0, 0, round(LABEL_BACK_ALPHA * 255))
        for text, r in kept:
            painter.setPen(Qt.NoPen)
            painter.setBrush(back)
            painter.drawRoundedRect(r, h / 2, h / 2)
            painter.setPen(QColor(255, 255, 255, 230))
            painter.drawText(r, Qt.AlignCenter, text)
        painter.restore()
