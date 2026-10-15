"""The patch editor's map geometry for the Qt app (spec
patch-editor-20261015 §3.3, §4; mockup ``docs/mockups/patch-editor-20261015.html``).

Pure functions and one numpy index, no widgets, so every rule here is
tested headless:

* :func:`style_class` — how a way is drawn (the legend's classes; the Mac
  app's ``PatchStyleClass``, same mapping).
* :func:`snap_target` — the drag snap's choice of target: the POINTER within
  8 px on screen of a non-dragged node; nearest wins, ties by the engine's
  ``survivor_key``, then the lowest id (the fixture's ``ui_snap_reference``).
* :class:`PatchScreenIndex` — the document's nodes and edges in map scene
  units (web-mercator pixels at the map's ``SCENE_ZL``), projected to the
  viewport per frame with one numpy multiply-add: node hits, the hovered
  edge, the "+" handles, box selection and the ≥ 6 px node thinning.
"""
from __future__ import annotations

import math
import typing as _t

import numpy as np

from o4_engine import patch_edit as PE

__all__ = ["SNAP_RADIUS_PX", "NODE_SPACING_PX", "MIN_HANDLE_EDGE_PX",
           "DRAW_ORDER", "style_class", "role_name", "snap_target", "scene_xy",
           "PatchScreenIndex"]

#: The click and snap radius (owner A10, 2026-10-15): 8 points on screen,
#: at any zoom.
SNAP_RADIUS_PX = 8.0
#: Node squares closer than this on screen are thinned out.
NODE_SPACING_PX = 6.0
#: Edges shorter than this on screen get no "+" (it would sit on a node).
MIN_HANDLE_EDGE_PX = 24.0
#: Selected nodes above this count draw no "+" handles (the Mac's cap).
MAX_HANDLE_SELECTION = 200

#: Lower first: graded ground under pavement, buildings and roads on top.
DRAW_ORDER = ("ground", "apron", "taxiway", "runway", "building", "road")

_ROLE_CLASSES = {
    "runway": "runway",
    "taxiway": "taxiway",
    "apron": "apron", "groundside_pavement": "apron",
    "building": "building",
    "service_road": "road", "service_junction": "road", "road": "road",
    "graded_strip": "ground", "runway_clearance": "ground", "ols_cut": "ground",
    "retaining_wall": "ground", "adjacent_ground": "ground",
}
_AEROWAY_CLASSES = {
    "runway": "runway", "taxiway": "taxiway", "apron": "apron",
    "building": "building", "aerodrome": "ground",
}


def style_class(tags: _t.Mapping[str, str]) -> str:
    """The legend class of a way: ``role`` wins over ``aeroway`` (the
    engine tags a graded strip and a building ``aeroway=apron`` too);
    taxiway-family roles fall through to their ``aeroway=taxiway``."""
    mapped = _ROLE_CLASSES.get(tags.get("role", ""))
    if mapped:
        return mapped
    mapped = _AEROWAY_CLASSES.get(tags.get("aeroway", ""))
    if mapped:
        return mapped
    if "highway" in tags:
        return "road"
    if "building" in tags:
        return "building"
    return "ground"


def role_name(tags: _t.Mapping[str, str]) -> str | None:
    """The name the inspector's "Used by" shows for a way."""
    return tags.get("role") or tags.get("aeroway") or tags.get("highway")


def snap_target(px: float, py: float,
                candidates: _t.Iterable[tuple[int, float, float, float, float]],
                identity_dp: int, radius: float = SNAP_RADIUS_PX) -> int | None:
    """The candidate ``(id, x, y, lat, lon)`` nearest the pointer within
    ``radius`` screen px (inclusive, as a click); equal distances go to the
    lowest ``survivor_key``, then the lowest id.  Callers pass only
    non-dragged nodes."""
    # The engine's own key (lazy: the emitter's import is not app start-up's).
    from auto_patch_v2.emit.osm_adapter import survivor_key
    best = None
    for (nid, x, y, lat, lon) in candidates:
        d = math.hypot(x - px, y - py)
        if d > radius:
            continue
        key = (d, survivor_key((lat, lon), identity_dp), nid)
        if best is None or key < best:
            best = key
    return None if best is None else best[2]


def scene_xy(lat, lon, zoomlevel: int):
    """Map scene coordinates of lat/lon arrays: ``O4_Geo_Utils.wgs84_to_pix``
    WITHOUT its rounding to whole pixels (at the map's scene zoom a pixel is
    ~0.3 m, too coarse for node editing)."""
    lat = np.asarray(lat, dtype=np.float64)
    lon = np.asarray(lon, dtype=np.float64)
    k = 2.0 ** (zoomlevel + 7)
    x = (lon / 180.0 + 1.0) * k
    y = (1.0 - np.log(np.tan((90.0 + lat) * math.pi / 360.0)) / math.pi) * k
    return x, y


class PatchScreenIndex:
    """A document's nodes and edges in scene units; ``project`` maps them
    into the viewport with the view's transform ``(sx, sy, dx, dy)``
    (screen = scene * s + d)."""

    def __init__(self, doc: PE.PatchDoc, identity_dp: int, zoomlevel: int):
        self.doc = doc
        self.identity_dp = identity_dp
        rows = list(doc.nodes.values())
        self.ids = np.array([n[0] for n in rows], dtype=np.int64)
        self.lat = np.array([n[1] for n in rows], dtype=np.float64)
        self.lon = np.array([n[2] for n in rows], dtype=np.float64)
        self.x, self.y = scene_xy(self.lat, self.lon, zoomlevel)
        self.row = {int(i): k for k, i in enumerate(self.ids)}
        edges = set()
        self.ways_by_node: dict[int, list[int]] = {}
        for w, way in enumerate(doc.ways):
            for a, b in zip(way.refs, way.refs[1:]):
                if a != b and a in self.row and b in self.row:
                    edges.add((min(a, b), max(a, b)))
            for r in set(way.refs):
                self.ways_by_node.setdefault(r, []).append(w)
        edges = sorted(edges)
        self.edge_a = np.array([self.row[a] for a, _ in edges], dtype=np.int64)
        self.edge_b = np.array([self.row[b] for _, b in edges], dtype=np.int64)
        self.edges = edges
        self.transform = (1.0, 1.0, 0.0, 0.0)
        self.sx = self.x
        self.sy = self.y

    def project(self, transform: tuple[float, float, float, float]) -> None:
        """Screen positions of every node for this frame."""
        self.transform = transform
        sx, sy, dx, dy = transform
        self.sx = self.x * sx + dx
        self.sy = self.y * sy + dy

    def screen(self, nid: int) -> tuple[float, float]:
        k = self.row[nid]
        return float(self.sx[k]), float(self.sy[k])

    # ─── hits ──────────────────────────────────────────────────────────
    def node_at(self, px: float, py: float, excluding: _t.Container[int] = (),
                radius: float = SNAP_RADIUS_PX) -> int | None:
        """The node the pointer is on (or snaps to): :func:`snap_target`
        over the nodes within ``radius`` px."""
        near = np.nonzero((np.abs(self.sx - px) <= radius)
                          & (np.abs(self.sy - py) <= radius))[0]
        return snap_target(px, py, ((int(self.ids[k]), float(self.sx[k]), float(self.sy[k]),
                                     float(self.lat[k]), float(self.lon[k]))
                                    for k in near if int(self.ids[k]) not in excluding),
                           self.identity_dp, radius)

    def edge_at(self, px: float, py: float,
                radius: float = SNAP_RADIUS_PX) -> tuple[int, int] | None:
        """The edge under the pointer for the hover "+" (none over a node)."""
        if not len(self.edge_a) or self.node_at(px, py) is not None:
            return None
        ax, ay = self.sx[self.edge_a], self.sy[self.edge_a]
        bx, by = self.sx[self.edge_b], self.sy[self.edge_b]
        vx, vy = bx - ax, by - ay
        ll = vx * vx + vy * vy
        t = np.clip(np.where(ll > 0, ((px - ax) * vx + (py - ay) * vy) / np.where(ll > 0, ll, 1), 0), 0, 1)
        d = np.hypot(ax + t * vx - px, ay + t * vy - py)
        k = int(np.argmin(d))
        return self.edges[k] if d[k] <= radius else None

    def handles(self, selection: _t.Collection[int], hover: tuple[int, int] | None,
                width: float, height: float) -> list[tuple[tuple[int, int], float, float]]:
        """"+" handles ``((a, b), x, y)``: every edge of the selected
        nodes' shapes (up to 200 selected nodes) and the hovered edge, long
        enough on screen and inside the view."""
        seen: set[tuple[int, int]] = set()
        out = []

        def add(a: int, b: int) -> None:
            key = (min(a, b), max(a, b))
            if a == b or key in seen or a not in self.row or b not in self.row:
                return
            seen.add(key)
            (xa, ya), (xb, yb) = self.screen(a), self.screen(b)
            mx, my = (xa + xb) / 2, (ya + yb) / 2
            if math.hypot(xb - xa, yb - ya) >= MIN_HANDLE_EDGE_PX \
                    and 0 <= mx <= width and 0 <= my <= height:
                out.append((key, mx, my))

        if len(selection) <= MAX_HANDLE_SELECTION:
            ways = sorted({w for n in selection for w in self.ways_by_node.get(n, ())})
            for w in ways:
                refs = self.doc.ways[w].refs
                for a, b in zip(refs, refs[1:]):
                    add(a, b)
        if hover:
            add(*hover)
        return out

    def nodes_in_rect(self, x0: float, y0: float, x1: float, y1: float) -> list[int]:
        """Nodes inside a screen rectangle (box select)."""
        lo_x, hi_x = min(x0, x1), max(x0, x1)
        lo_y, hi_y = min(y0, y1), max(y0, y1)
        inside = (self.sx >= lo_x) & (self.sx <= hi_x) & (self.sy >= lo_y) & (self.sy <= hi_y)
        return [int(i) for i in self.ids[inside]]

    def visible_nodes(self, width: float, height: float, skip: _t.Container[int] = (),
                      spacing: float = NODE_SPACING_PX) -> list[tuple[float, float]]:
        """Screen points of the node squares to draw: inside the view, not
        skipped, thinned so no two are closer than ``spacing`` px."""
        inside = np.nonzero((self.sx >= 0) & (self.sx <= width)
                            & (self.sy >= 0) & (self.sy <= height))[0]
        taken: dict[tuple[int, int], tuple[float, float]] = {}
        out = []
        for k in inside:
            if int(self.ids[k]) in skip:
                continue
            x, y = float(self.sx[k]), float(self.sy[k])
            i, j = int(x // spacing), int(y // spacing)
            if (i, j) in taken:
                continue
            clear = True
            for di in (-1, 0, 1):
                for dj in (-1, 0, 1):
                    q = taken.get((i + di, j + dj))
                    if q is not None and math.hypot(q[0] - x, q[1] - y) < spacing:
                        clear = False
                        break
                if not clear:
                    break
            if clear:
                taken[(i, j)] = (x, y)
                out.append((x, y))
        return out
