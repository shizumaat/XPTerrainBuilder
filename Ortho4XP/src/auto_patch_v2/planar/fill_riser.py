"""THE FILL'S STEP AT THE ROAD'S FAR KERB (owner RULINGS 2026-10-20d, 2026-10-27i;
spec ``docs/specs/fill-step-at-road-kerb-spec.md`` §2 (3)-(4)).

The owner: the road "should be graded to road rules, and reach the high
terminals, and then allow a vertical drop on the low side so the buildings
on that side can be seated on the ground".  A pad fill that cannot bank
runs to the road (``planar/fill_road.extend_to_roads``, the LENS) and its
level ``L`` reaches the road's NEAR kerb.  The road (or, 27i, the lot
between the fill and its road, which keeps lot law) descends from there at
``[road_contact] ramp_grade``; where its FAR kerb then stands more than
``[cockpit] visual_m`` over the ground beside it, the step is DECLARED here,
at the fill's own derivation site, from the DEM alone:

* the RISER: a strip along the far kerb — ACROSS the road from the lens's
  contact with it, within the lens's span along the road — of the low-level riser's width ``max(identity spacing, 2 x grid)``
  (``planar/low_level``) — minted ``<landing>#strip``, a bank face every
  pad reader skips;
* the PREDICTED KERB LEVEL at a point of the riser's outer line is
  ``L - g * s``, ``s`` its distance from the lens's contact with the road
  (the route distance across it), and the riser stands only where that
  exceeds the DEM there by ``visual_m``; below, the terrain drapes;
* its WALL: ``height_m`` the largest predicted kerb level over the DEM on
  its outer line; the riser's ring and its far-kerb line, recorded on the
  landing (``Registries.landings[ref]["risers"]``) and read into one
  ``road_terrace['wall']`` record per riser by ``airport/riser_wall``.

No later stage derives a drop: this is the one site."""
from __future__ import annotations

import typing as _t

from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union

from ..geom.parts import nonempty_polygon_parts as _parts

__all__ = ["riser_width", "fill_risers"]


def riser_width(law, grid: float) -> float:
    """The riser's width: the low-level riser's (``planar/low_level``)."""
    return max(float(law.tables.emit.identity.min_distinct_spacing_m), 2.0 * float(grid))


def _lines(g) -> list[LineString]:
    if g is None or g.is_empty:
        return []
    if g.geom_type == "LineString":
        return [g]
    out: list[LineString] = []
    for q in getattr(g, "geoms", ()):
        out.extend(_lines(q))
    return [q for q in out if q.length > 0.0]


def _outer_samples(band: Polygon, road: Polygon, w: float, step: float) -> list[Point]:
    """Points along ``band``'s OUTER line — its boundary off the road."""
    off = band.boundary.difference(road.buffer(0.5 * w, join_style=2))
    out: list[Point] = []
    for ln in _lines(off):
        n = max(1, int(ln.length // step))
        out.extend(ln.interpolate(k * ln.length / n) for k in range(n + 1))
    return out


def _across(p: Point, contact, core) -> bool:
    """``p`` is ACROSS the road from the contact: its way to the nearest
    contact point runs through the road's interior (``core``)."""
    from shapely.ops import nearest_points
    q = nearest_points(contact, p)[0]
    return not core.is_empty and LineString([q, p]).intersects(core)


def _span(contact, depth: float):
    """The ground ACROSS the road from the contact, within ``depth``: the
    union of every contact segment's flat-capped band (a joined buffer
    would wrap the contact's corners onto the road beyond the lens)."""
    rects = []
    for ln in _lines(contact):
        c = list(ln.coords)
        rects.extend(LineString([a, b]).buffer(depth, cap_style=2)
                     for a, b in zip(c, c[1:]) if a != b)
    return unary_union(rects)


def fill_risers(lens: Polygon, level: float, roads: _t.Sequence[Polygon],
                keep_out, dem, law, grid: float, reach_m: float
                ) -> list[dict[str, _t.Any]]:
    """The risers of a fill whose LENS ``lens`` stands at ``level``
    (module docstring): per road polygon of ``roads`` the lens touches, the
    strip along its far kerb within the lens's span, less ``keep_out`` (what
    is held, every road strip), where the predicted kerb level stands over
    the DEM by ``visual_m``.  ``[{"polygon", "upper", "height_m",
    "road"}]``: ``upper`` the riser's line on the road's kerb, ``road``
    the index into ``roads``."""
    if dem is None or not roads or lens is None or lens.is_empty:
        return []
    w = riser_width(law, grid)
    g = float(law.tables.emit.road_contact.ramp_grade)
    visual = float(law.tables.emit.cockpit.visual_m)
    step = max(float(grid), w)
    out: list[dict[str, _t.Any]] = []
    near = lens.buffer(w, join_style=2)
    for k, road in enumerate(roads):
        if road.distance(lens) > grid:
            continue
        contact = unary_union(_lines(lens.boundary.intersection(road.buffer(grid))))
        if contact.is_empty or contact.length < step:
            continue
        span = _span(contact, reach_m)
        band = road.buffer(w, join_style=2).difference(road).difference(near)
        if keep_out is not None and not keep_out.is_empty:
            band = band.difference(keep_out)
        band = band.intersection(span)
        core = road.buffer(-0.25 * w)
        for piece in _parts(band):
            kept, top = [], None
            for p in _outer_samples(piece, road, w, step):
                if not _across(p, contact, core):
                    continue
                dz = level - g * contact.distance(p) - float(dem.z(p.x, p.y))
                if dz > visual:
                    kept.append(p)
                    top = dz if top is None else max(top, dz)
            if not kept:
                continue
            R = piece.intersection(unary_union([p.buffer(step + w) for p in kept]))
            for q in _parts(R):
                if q.area < max(grid * grid, 1.0):
                    continue
                upper = unary_union(_lines(q.boundary.intersection(road.buffer(0.25 * w))))
                if upper.is_empty:
                    continue
                out.append({"polygon": q, "upper": upper, "height_m": round(float(top), 3),
                            "road": k})
    return out
