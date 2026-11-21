"""THE PACK AUTHOR'S ART ON A GENERATED DECK (#2183 (2) and (3); owner
2026-11-19T14:31Z, "should apply to all bridges").

The pack write clips every draped page (``.pol``) and painted line
(``.lin``) of the pack's DSF out of a generated deck's ring
(``dsf_poly_clip``): the deck, an OBJ, stands where the author's ground
art was.  This module reads that art back so the deck carries the
AUTHOR'S look, never one of ours:

* (2) "Ground markings that add dirt, wear, tiremarks, etc. should match
  whatever the author applied to the taxiways on either end of the
  bridge, including nothing": the draped pages that hold the carried
  route's centreline just beyond BOTH end lines (:func:`end_pages`) --
  the taxiway's treatment on either side of the bridge -- each drawn
  over the deck as a film in its own art (``deck_objects``); a page on
  one end only, or none, draws nothing (no default tire marks);
* (3) the author's painted ``.lin`` lines inside the ring (a taxiway edge
  line drawn in the DSF, not in apt.dat): their pieces
  (:func:`deck_lines`), redrawn on the deck in the line page's own art --
  only a piece that runs along the TAXIWAY: one reaching an END line (the
  ring's edges the carried route crosses) or lying wholly inside; a piece
  that comes in and goes out across the deck's SIDES is the ground the
  structure spans (a ditch's water edge under the bridge, owner
  2026-11-21T06:47Z KMCO 1.0.570: "draping on top of the bridge"), and a
  hidden bridge's own drapes (``deck_companions``) are never carried.

A UV-mapped page (parameter 65535) is never read: the clip never cuts
one either.  Pages resolve in the pack first (a ``.pol`` / ``.lin`` the
pack ships), then through the caller's library lookup
(:func:`pack_first`).  Nothing here names an airport, a pack or a page.

Build-time impact: the object stage only -- one pass over the pack DSF's
text dump per tile (already dumped for the placement write) and a few
point-in-polygon reads per deck.
"""
from __future__ import annotations

import math
import os
import typing as _t

from shapely.geometry import LineString, Point, Polygon

from . import dsf_poly_clip as _clip

__all__ = ["PackPage", "pack_pages", "end_pages", "deck_lines", "pack_first",
           "draw_order", "layer_order", "END_REACH_M"]

#: where the taxiway on either side of a deck is read: these metres along
#: the carried route beyond each end line
END_REACH_M = (2.0, 5.0, 10.0)
#: a clipped piece's tip on the ring (degrees, ~1 cm: the clip's own
#: vertices sit on it to rounding)
_ON_EDGE_DEG = 1e-7
_M_PER_DEG = 111320.0


class PackPage(_t.NamedTuple):
    """One draped page or painted line of the pack DSF: its definition
    ``path``, ``geom`` (lon/lat polygon or line), ``is_line`` and
    ``anchor``, its FIRST point as written (the row ``dsf_row_hide``
    names it by)."""

    path: str
    geom: _t.Any
    is_line: bool
    anchor: tuple = ()


def pack_pages(text: str) -> list[PackPage]:
    """The draped ``.pol`` pages and ``.lin`` lines of a DSF text dump, in
    file order (``dsf_poly_clip``'s own reading); UV-mapped pages left out."""
    lines = text.split("\n")
    defs = [ln.split(None, 1)[1].strip() for ln in lines if ln.startswith("POLYGON_DEF ")]
    out: list[PackPage] = []
    for _s, _e, head, wind in _clip.blocks(lines):
        path = defs[int(head[1])]
        if not path.endswith((".pol", ".lin")) or not wind or not wind[0]:
            continue
        param, ncoords = int(head[2]), int(head[3])
        is_line = path.endswith(".lin")
        if param == _clip.UV_PARAM and not is_line:
            continue
        if is_line:
            pts = _clip.flatten(wind[0], param == 1, ncoords >= 4)
            g = LineString(pts + pts[:1] if param == 1 else pts) if len(pts) >= 2 else None
        else:
            rings = [_clip.flatten(w, True, ncoords >= 4) for w in wind]
            g = (Polygon(rings[0], [r for r in rings[1:] if len(r) >= 3])
                 if len(rings[0]) >= 3 else None)
            if g is not None and not g.is_valid:
                g = g.buffer(0)
        if g is not None and not g.is_empty:
            out.append(PackPage(path, g, is_line, (float(wind[0][0][1]), float(wind[0][0][2]))))
    return out


def _metric(lat: float):
    k = math.cos(math.radians(lat)) * _M_PER_DEG
    return (lambda lo, la: (lo * k, la * _M_PER_DEG)), \
        (lambda x, y: (x / k, y / _M_PER_DEG))


def _end_samples(ring_ll: Polygon, route) -> tuple[list[Point], list[Point]]:
    """The stations :data:`END_REACH_M` beyond each end of the carried
    ``route`` (lon/lat points) across ``ring_ll``; ``([], [])`` when the
    route does not cross it."""
    if route is None or len(route) < 2:
        return [], []
    to_m, to_ll = _metric(ring_ll.centroid.y)
    L = LineString([to_m(lo, la) for lo, la in route])
    R = Polygon([to_m(lo, la) for lo, la in ring_ll.exterior.coords])
    on = L.intersection(R)
    pieces = [g for g in getattr(on, "geoms", [on]) if g.geom_type == "LineString"]
    if not pieces:
        return [], []
    s0 = min(L.project(Point(g.coords[0])) for g in pieces)
    s1 = max(L.project(Point(g.coords[-1])) for g in pieces)
    s0, s1 = min(s0, s1), max(s0, s1)

    def at(s: float) -> "Point | None":
        if s < 0.0 or s > L.length:
            return None
        q = L.interpolate(s)
        return Point(*to_ll(q.x, q.y))
    a = [p for p in (at(s0 - d) for d in END_REACH_M) if p is not None]
    b = [p for p in (at(s1 + d) for d in END_REACH_M) if p is not None]
    return a, b


def end_pages(pages: _t.Sequence[PackPage], ring_ll: Polygon, route) -> list[str]:
    """The draped pages (paths, file order, each once) that hold the carried
    route's centreline beyond BOTH ends of the deck (module doc (2))."""
    a, b = _end_samples(ring_ll, route)
    if not a or not b:
        return []
    out: list[str] = []
    for pg in pages:
        if pg.is_line or pg.path in out:
            continue
        if any(pg.geom.contains(q) for q in a) and any(pg.geom.contains(q) for q in b):
            out.append(pg.path)
    return out


def _end_edges(ring_ll: Polygon, route) -> list[LineString]:
    """The ring's END lines: its edges the carried ``route`` crosses."""
    pts = list(ring_ll.exterior.coords)
    edges = [LineString([a, b]) for a, b in zip(pts, pts[1:], strict=False)]
    if route is None or len(route) < 2:
        return []
    r = LineString(route)
    return [e for e in edges if e.intersects(r)]


def _along_taxiway(piece: LineString, ring_ll: Polygon, ends: _t.Sequence[LineString]) -> bool:
    """A carried piece (module doc (3)): one of its ends on an END line, or
    neither on the ring's boundary (it lies wholly inside)."""
    edge = ring_ll.exterior
    tips = [Point(piece.coords[0]), Point(piece.coords[-1])]
    on_edge = [edge.distance(p) <= _ON_EDGE_DEG for p in tips]
    if not any(on_edge):
        return True
    return any(e.distance(p) <= _ON_EDGE_DEG for p, on in zip(tips, on_edge, strict=True) if on
               for e in ends)


def deck_lines(pages: _t.Sequence[PackPage], ring_ll: Polygon, route=None,
               skip: _t.AbstractSet[int] = frozenset()
               ) -> list[tuple[str, list[tuple[float, float]]]]:
    """``[(line path, lon/lat points)]``: the pieces of the pack's painted
    lines inside the deck's ring that run along the taxiway the deck
    carries (module doc (3); ``route`` its lon/lat axis, ``None`` keeps
    only the pieces wholly inside), file order; ``skip`` the indices in
    ``pages`` never carried (a hidden bridge's own drapes)."""
    ends = _end_edges(ring_ll, route)
    out = []
    for k, pg in enumerate(pages):
        if k in skip or not pg.is_line or not pg.geom.intersects(ring_ll):
            continue
        cut = pg.geom.intersection(ring_ll)
        out += [(pg.path, list(g.coords)) for g in getattr(cut, "geoms", [cut])
                if g.geom_type == "LineString" and len(g.coords) >= 2
                and _along_taxiway(g, ring_ll, ends)]
    return out


def pack_first(pack_root: str, resolve):
    """A resolver reading a page the pack ships (``<pack>/<path>``) first,
    then ``resolve`` (``deck_skin.Resolver``)."""
    def look(path: str, root: str) -> "str | None":
        own = os.path.join(pack_root, *path.replace("\\", "/").split("/")) if pack_root else ""
        if own and os.path.isfile(own):
            return own
        return resolve(path, root) if resolve is not None else None
    return look


#: the draw order of X-Plane's layer groups (``LAYER_GROUP name offset``)
_GROUPS = ("terrain", "beaches", "shoulders", "taxiways", "runways",
           "markings", "airports", "roads", "objects", "light_objects", "cars")


def layer_order(header: _t.Mapping[str, str]) -> float:
    """The draw order of a ``.pol`` (group rank, then offset; no or an
    unknown ``LAYER_GROUP`` reads as ``markings``); ``header`` its rows by
    keyword (``pack_drapes`` reads the pack's pages so too)."""
    toks = header.get("LAYER_GROUP", "").split()
    if not toks or toks[0].lower() not in _GROUPS:
        return float(_GROUPS.index("markings") * 100)
    try:
        off = float(toks[1]) if len(toks) > 1 else 0.0
    except ValueError:
        off = 0.0
    return _GROUPS.index(toks[0].lower()) * 100 + off


def draw_order(pol_path: str) -> float:
    """The draw order of the ``.pol`` file at ``pol_path`` among draped
    pages (:func:`layer_order` of its ``LAYER_GROUP``)."""
    try:
        with open(pol_path, encoding="utf-8", errors="replace") as fh:
            row = next((ln.split() for ln in fh if ln.split()[:1] == ["LAYER_GROUP"]), None)
    except OSError:
        row = None
    return layer_order({"LAYER_GROUP": " ".join(row[1:])} if row else {})
