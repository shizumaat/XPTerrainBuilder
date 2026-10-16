"""The pack reference outlines on the Qt patch layer (spec
patch-editor-20261015 §2 as amended before L4, A4; mockup "Pack outlines").

Two engine reads, drawn dashed under the patch when the map toolbar's
"Pack outlines" box is ticked:

* ``pack_outlines {tile, icao}`` — the pack's apt.dat pavement (row 110)
  and boundary (row 130) rings (an engine without the command is skipped).
* building footprints from the ``pack_objects`` result — the plan outline
  of each placed model (the convex hull of its grey-massing vertices,
  turned by the placement's heading) and each facade's ring.
  Buildings are read once, by one command; the request box is the 3D
  preview's (patch bbox + 500 m, A9), so the engine's session cache serves
  both.
"""
from __future__ import annotations

import base64
import math
import typing as _t

import numpy as np
from PySide6.QtCore import QObject, QPointF, Qt, Signal
from PySide6.QtGui import QColor, QPainterPath, QPen, QPolygonF

from O4_Qt_Patch_Geometry import scene_xy

__all__ = ["PackOutlines", "request_bbox", "model_footprint", "placed_ring",
           "footprints_from_pack_objects", "MARGIN_M", "OUTLINE_COLOR", "TOGGLE_HELP"]

#: The 3D preview's margin round the patch bbox (A9).
MARGIN_M = 500.0
#: The engine's local plane (``emit/osm_adapter._local_metres``).
METRES_PER_DEG_LAT = 111_320.0

#: The mockup's dashed grey (#9AA4B5 at 0.7), 1.2 px, dash 5 4.
OUTLINE_COLOR = QColor(0x9A, 0xA4, 0xB5, 178)
TOGGLE_HELP = ("Show the airport pack's own pavement, boundary and building outlines "
               "(dashed) under the patch, for reference.")


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


def footprints_from_pack_objects(result: _t.Mapping) -> list[list[tuple[float, float]]]:
    """Every footprint ring ``[(lat, lon), …]`` of a ``pack_objects``
    result: one per drawn placement (a model with fewer than three distinct
    plan points has none), then one per facade."""
    hulls = {m["key"]: model_footprint(m["vertices_f32_b64"]) for m in result.get("models") or ()}
    out: list[list[tuple[float, float]]] = []
    for p in result.get("placements") or ():
        hull = hulls.get(p["model"])
        if hull and len(hull) >= 3:
            out.append(placed_ring(hull, float(p["lat"]), float(p["lon"]),
                                   float(p.get("heading_deg") or 0.0)))
    for f in result.get("facades") or ():
        if len(f["ring"]) >= 3:
            out.append([(float(la), float(lo)) for la, lo in f["ring"]])
    return out


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
    the toggle is on (remembered per user, on by default), drawn in scene
    units under a cosmetic dashed pen."""

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
        self._pavement = QPainterPath()
        self._footprints = QPainterPath()
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
        self._pavement, self._footprints, self.missing = QPainterPath(), QPainterPath(), []
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
                rings = [r for item in reply.get("pavement") or () for r in item.get("rings") or ()]
                self._pavement = _path(rings, self.zoomlevel)
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
                self._footprints = _path(footprints_from_pack_objects(result), self.zoomlevel)
            self.changed.emit()
        # The 3D window's box (A9), so the engine's cache serves both.
        self.engine.pack_objects(tile, icao, request_bbox(m.doc.nodes.values()), objects)

    def paint(self, painter, view_transform) -> None:
        """The dashed grey layer, under the patch (painter in viewport space)."""
        if not self.enabled:
            return
        painter.save()
        painter.setTransform(view_transform)
        painter.setBrush(Qt.NoBrush)
        pen = QPen(OUTLINE_COLOR)
        pen.setCosmetic(True)
        pen.setWidthF(1.2)
        pen.setDashPattern([5 / 1.2, 4 / 1.2])      # in pen widths: 5 px on, 4 off
        painter.setPen(pen)
        painter.drawPath(self._pavement)
        painter.drawPath(self._footprints)
        painter.restore()
