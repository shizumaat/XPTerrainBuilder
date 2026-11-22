"""A HIDDEN BRIDGE'S OWN DRAPES (owner 2026-11-21T06:47Z, KMCO 1.0.570:
"remnants of the pack bridge objects still visible, causing shadows,
semi-transparent floating planes, etc. around the bridges").

A pack bridge the generated deck replaces is hidden (``dsf_row_hide``, the
decks' ``hides``), but its author also DRAPED art for it on the ground:
shadow lines along the old deck, pages under it.  Those are the bridge's
companions and leave with it.  A draped page or painted line is one when

* every point of it lies within a hidden bridge's PLAN BOX (the OBJ's
  authored x/z extent, placed at its row) -- drawn for that bridge, not a
  taxiway line or a pavement page running on past it; and
* ``[deck_gen] hide_inside_share`` of it (length for a line, area for a
  page) lies over the crossing: between a generated deck's END lines,
  across the bridge's whole plan (:func:`_span_band`; a shadow line along
  the old, wider deck's edge falls beside ours) -- never the approach
  pavement (the same share a hidden bridge's co-placed mate
  needs, owner 2026-11-20T22:39Z, ``planar/deck_takeover._rides``).

A building is never a drape, so none is touched (RULINGS 2026-11-20u).
The companions ride the recipe's ``hides`` (``companion`` rows, named by
their first point as ``dsf_row_hide`` names a polygon), so the record
keeps them and Restore originals brings them back; the pack write drops
them before it clips the pages (the clip moves a line's first point).
Nothing here names an airport, a pack or a page.

Build-time impact: the object stage only -- one OBJ read per hidden
bridge and a containment test per page near it.
"""
from __future__ import annotations

import typing as _t

from shapely.geometry import Polygon
from shapely.ops import unary_union

__all__ = ["placements", "plan_box", "companions", "rows"]

_OBJECT_ROWS = ("OBJECT", "OBJECT_MSL", "OBJECT_AGL")


def placements(text: str) -> dict[str, list[tuple[float, float, float]]]:
    """``{definition: [(lon, lat, heading)]}``: the OBJECT rows of a DSF
    text dump."""
    defs: list[str] = []
    out: dict[str, list[tuple[float, float, float]]] = {}
    for ln in text.split("\n"):
        if ln.startswith("OBJECT_DEF "):
            defs.append(ln.split(None, 1)[1].strip())
            continue
        t = ln.split()
        if len(t) < 5 or t[0] not in _OBJECT_ROWS:
            continue
        try:
            k, row = int(t[1]), (float(t[2]), float(t[3]), float(t[4]))
        except ValueError:
            continue
        if 0 <= k < len(defs):
            out.setdefault(defs[k], []).append(row)
    return out


def plan_box(phys: str, lon: float, lat: float, hdg: float) -> "Polygon | None":
    """The OBJ at ``phys`` placed at ``(lon, lat, hdg)``: its authored plan
    box (every solid and draped triangle's x/z extent) as a lon/lat ring;
    ``None`` when it draws no triangle."""
    import numpy as np

    from .deck_obj8 import DeckFrame
    from .obj8 import parse_obj8
    try:
        g = parse_obj8(phys)
    except (OSError, ValueError):
        return None
    used = np.concatenate([g.solid.reshape(-1), g.draped.reshape(-1)]).astype(int)
    if not used.size:
        return None
    v = g.vertices[np.unique(used)]
    x0, x1 = float(v[:, 0].min()), float(v[:, 0].max())
    z0, z1 = float(v[:, 2].min()), float(v[:, 2].max())
    f = DeckFrame(lon, lat, hdg)
    return Polygon([f.to_lonlat(x, z) for x, z in ((x0, z0), (x1, z0), (x1, z1), (x0, z1))])


def _span_band(ring: Polygon, route, reach: Polygon) -> "Polygon | None":
    """The crossing a deck spans: the strip between its END lines (where
    its carried ``route``, lon/lat points, enters and leaves ``ring``),
    across as far as ``reach`` (a hidden bridge's plan) runs; ``None``
    when the route does not cross the ring."""
    import math

    from shapely.geometry import LineString, Point
    if route is None or len(route) < 2:
        return None
    L = LineString(route)
    on = L.intersection(ring)
    s = [L.project(Point(c)) for g in getattr(on, "geoms", [on])
         if g.geom_type == "LineString" for c in g.coords]
    if not s or max(s) <= min(s):
        return None
    a, b = L.interpolate(min(s)), L.interpolate(max(s))
    x0, y0, x1, y1 = reach.bounds
    w = math.hypot(x1 - x0, y1 - y0) + math.hypot(b.x - a.x, b.y - a.y)
    n = math.hypot(b.x - a.x, b.y - a.y)
    px, py = -(b.y - a.y) / n * w, (b.x - a.x) / n * w
    return Polygon([(a.x + px, a.y + py), (b.x + px, b.y + py),
                    (b.x - px, b.y - py), (a.x - px, a.y - py)])


def _over(geom, decks, is_line: bool) -> float:
    """The share of ``geom`` lying over ``decks`` (a lon/lat union)."""
    if is_line:
        return geom.intersection(decks).length / geom.length if geom.length > 0 else 0.0
    return geom.intersection(decks).area / geom.area if geom.area > 0 else 0.0


def companions(pages: _t.Sequence, plans: _t.Sequence[Polygon],
               decks: _t.Sequence[tuple[Polygon, _t.Any]], share: float
               ) -> list[tuple[int, int]]:
    """``[(page index, plan index)]``: the hidden bridges' companions among
    ``pages`` (``deck_author_art.PackPage``; module doc), each wholly
    within its plan of ``plans`` and ``share`` of it over the crossing of
    the ``decks`` (each ``(ring, route)``)."""
    out = []
    for i, plan in enumerate(plans):
        bands = [b for b in (_span_band(r, q, plan) for r, q in decks) if b is not None]
        if not bands:
            continue
        over = unary_union(bands).intersection(plan)
        for k, pg in enumerate(pages):
            if any(k == j for j, _i in out) or not plan.covers(pg.geom):
                continue
            if _over(pg.geom, over, pg.is_line) >= share:
                out.append((k, i))
    return out


def rows(pages: _t.Sequence, found: _t.Iterable[tuple[int, int]],
         owners: _t.Sequence[str]) -> list[dict]:
    """The recipe's ``hides`` rows of the companions ``found``
    (:func:`companions`), each naming the hidden placement it leaves with
    (``owners``: object ids by plan index)."""
    return [{"object_id": f"{owners[i]}~drape{k}", "resource": pages[k].path,
             "lon": pages[k].anchor[0], "lat": pages[k].anchor[1], "companion": True}
            for k, i in found if pages[k].anchor]
