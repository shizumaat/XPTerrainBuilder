"""THE WELD SPANS THE DECK'S FULL END EDGE (#2239 / #2241; owner sim read
2026-11-26T15:02Z on 1.0.585: "the deck-to-taxiway weld does not cover the
full bridge width: one shoulder still has a gap.  The weld must span the
deck's full width including shoulders").

A pack deck's end line is held flush by its STATION vertices
(``constraints/edge_deck._station_rows``): each station's nearest airside
vertex (``constraints/deck_lines.end_lines``) -- for a walled deck the
nearest one off the cut a step outside its rim.  Every OTHER vertex on the
deck's edge took no flush row: an airside one only a ceiling from the
deck's zero, a ground one the bank or the DEM.  MEASURED (CYYZ, replay at
4126b4276): the M deck's end line A seated on ONE vertex, the taxiway along
the rest of its 68 m edge +0.44 .. -0.79 m off the slab; the T deck's
shoulder (no pavement outside 9.5 m of its edge) on the DEM, 0.58-1.44 m
under the deck as X-Plane drew it.

THE RULE: every map vertex ON a deck's end EDGE (``geom/deck_end_edge``:
the ring's side the end line lies on, corner to corner), within half the
arrangement's least ring separation (``[cutout] ring_floor_m``: nearer than
that it is no ring of its own), is a station of that end line: its depth is
the end line's, read along the edge where the slab falls along it (#2241,
``EndLine.tops``: a straight fit over the stations', carried to the
corners).  A trench floor vertex never is (the cut's own level), nor a
runway's (its rows are senior, ``constraints/edge_deck``).  Pure plan
reading; ``constraints/edge_deck`` writes the rows.  Nothing here names a
pack or an airport.
"""
from __future__ import annotations

import typing as _t

from ..geom.deck_end_edge import end_edge, on_edge

__all__ = ["edge_vertices"]


def _slab_depths(planar, e) -> list[tuple[tuple[float, float], float]]:
    """``[(xy, depth), ...]`` along end line ``e``: each seat STATION's slab
    top less the frame's bottom (``DeckBridge.station_tops``, #2241) where
    the deck reads one per station, else each seat VERTEX's own
    (``EndLine.tops``), else ``[]``."""
    db = e.deck
    sts = getattr(db, "station_tops", ()) or ()
    line = tuple(tuple(q) for q in e.line)
    for k, seats in enumerate((getattr(db, "seats_a", ()), getattr(db, "seats_b", ()))):
        if len(sts) == 2 and tuple(tuple(q) for q in seats) == line and len(sts[k]) == len(line):
            return [(q, float(t) - float(db.bottom_y)) for q, t in zip(line, sts[k], strict=True)]
    return [(planar.vertices[v].xy, float(d)) for v, d in (getattr(e, "tops", ()) or ())]


def _depth_along(planar, e, edge) -> _t.Callable[[tuple[float, float]], float]:
    """``depth(xy)``: the end line's depth at ``xy`` -- its one depth, or
    (#2241) the least-squares line through its slab's depths
    (:func:`_slab_depths`) against their run along ``edge``."""
    pts = _slab_depths(planar, e)
    if len(pts) < 2:
        return lambda _p, d=float(e.depth): d
    from shapely.geometry import LineString, Point
    ln = LineString(edge)
    ss = [ln.project(Point(q)) for q, _d in pts]
    ds = [d for _q, d in pts]
    n = len(ss)
    ms, md = sum(ss) / n, sum(ds) / n
    var = sum((s - ms) * (s - ms) for s in ss)
    slope = 0.0 if var <= 1e-12 else sum((s - ms) * (d - md)
                                         for s, d in zip(ss, ds, strict=True)) / var
    return lambda p: md + slope * (ln.project(Point(p)) - ms)


def edge_vertices(planar, es: _t.Sequence, tol: float, skip: _t.AbstractSet[str],
                  stations: _t.AbstractSet[int], apron: float = 0.0,
                  keep: _t.AbstractSet[str] = frozenset()) -> dict[int, tuple[int, float]]:
    """``{vertex: (end line index, depth there)}`` (module doc) over one
    object's end lines ``es`` (``constraints/deck_lines.EndLine``), every
    vertex once -- the first end line naming it -- ``stations`` and any
    vertex carrying a ``skip`` role left out.  THE APRON'S RUN-ON BAND
    (#2239 R4, ``planar/deck_apron``): a vertex of the deck's own apron
    faces within ``apron`` of its edge is flush with it too, save one
    carrying a ``keep`` role (a neighbour whose law it keeps)."""
    from ..model.structures import DECK_APRON_REF
    out: dict[int, tuple[int, float]] = {}
    reach = max(tol, apron + tol)
    for k, e in enumerate(es):
        ring = getattr(e.deck, "ring", ())
        edge = end_edge(ring, e.line) if len(ring) >= 3 else []
        if len(edge) < 2:
            continue
        depth = _depth_along(planar, e, edge)
        own = f"{DECK_APRON_REF}:{getattr(e.deck, 'object_id', '')}"
        xs, ys = [p[0] for p in edge], [p[1] for p in edge]
        x0, x1, y0, y1 = min(xs) - reach, max(xs) + reach, min(ys) - reach, max(ys) + reach
        for v, vx in planar.vertices.items():
            x, y = vx.xy
            if not (x0 <= x <= x1 and y0 <= y <= y1) or v in stations or v in out:
                continue
            roles = set(planar.roles_at(v))
            if skip & roles:
                continue
            if on_edge(vx.xy, edge, tol) or (
                    apron > 0.0 and not keep & roles and on_edge(vx.xy, edge, reach)
                    and any(str(planar.faces[f].ref).split("#")[0] == own
                            for f in vx.incident_faces if f in planar.faces)):
                out[v] = (k, depth(vx.xy))
    return out
