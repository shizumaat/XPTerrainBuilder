"""THE GENERATED DECK'S STRUCTURE: a real taxiway bridge under the slab
(#2132, spec ``sim-review/2132-design.md`` section 4; owner 2026-11-17:
"kerb only (0.30 x 0.40 m, side edges), no blast screen").

Pure plan geometry.  A deck ring (``(x, z)`` in the object frame of
``deck_obj8``, the carried route along ``-z``), its END edges (where the
pavement runs on) and the roads under it go in; the PARTS come out, each
a plan polygon with the depths of its top and bottom under the deck top
(``deck_obj8`` writes them, :class:`Part`):

* the SLAB: the whole ring, ``slab_m`` deep -- its top is the hard deck;
* the EDGE BEAM: a band ``edge_beam_m`` wide inside the ring, at the
  full depth ``thickness_m`` (today's fascia: it hides the beam ends);
* the BEAMS: ``beam_width_m`` prisms along the route, one every
  ``beam_spacing_m`` across it, from the slab soffit to the full depth;
* the KERBS: ``kerb_w_m`` x ``kerb_h_m`` on the SIDE edges and round the
  holes, never across an end (aircraft roll on there);
* the PIERS, only on a deck longer than ``pier_min_span_m`` along its
  route that knows its roads: per road a row each side at the floor's
  edge (carriageway half width + ``shoulder_m``), octagonal columns
  ``pier_col_m`` across at most ``pier_gap_m`` apart under a cap beam,
  from ``pier_foot_m`` below the floor to the beams.

Everything but the piers stays inside the slab's ``thickness_m``
envelope, so the cut, the floor and the solve read nothing new.  Nothing
here names an airport.

Build-time impact: shapely on a handful of polygons per deck, at write time.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union

__all__ = ["Part", "Road", "end_edges", "structure_parts", "length_along_route"]

XY = tuple[float, float]


@_dc.dataclass(frozen=True)
class Part:
    """A prism: ``poly`` in ``(x, z)``; its top ``top_m`` and bottom
    ``bottom_m`` metres ABOVE the deck top there (negative: below);
    ``faces`` the faces drawn (``"top"``, ``"bottom"``, ``"sides"``) --
    a face against another part is left out.  ``floor_y`` (a column):
    the bottom is this ``y`` of the object frame, not ``bottom_m``."""

    name: str
    poly: Polygon
    top_m: float
    bottom_m: float
    faces: tuple[str, ...] = ("top", "bottom", "sides")
    floor_y: "float | None" = None


class Road(_t.NamedTuple):
    """A road under the deck: its centreline ``(x, z)`` and carriageway
    half width (m)."""

    line: tuple[XY, ...]
    half_m: float


def end_edges(ring: Polygon, ends: _t.Sequence[_t.Sequence[XY]], tol_m: float,
              angle_deg: float = 25.0) -> list[tuple[XY, XY]]:
    """The ring's exterior edges at an END (``ends``: the end lines'
    stations): its midpoint within ``tol_m`` of an end line, and turned
    more than ``angle_deg`` off the route (``z``) -- a side edge runs
    along the route, an end edge across it (ESSA 2026-11-17: the end
    lines stand ~2.4 m inside the ring's ends, which run oblique to them)."""
    lines = [LineString(e) if len(e) >= 2 else Point(e[0]) for e in ends if len(e)]
    cos_max = math.cos(math.radians(angle_deg))
    pts = list(ring.exterior.coords)
    out = []
    for a, b in zip(pts[:-1], pts[1:], strict=True):
        d = math.dist(a, b)
        if d < 1e-6 or abs(b[1] - a[1]) / d > cos_max:
            continue
        mid = Point((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)
        if any(ln.distance(mid) <= tol_m for ln in lines):
            out.append((a, b))
    return out


def length_along_route(ring: Polygon) -> float:
    """The deck's extent along its route (``z``: the route runs along ``-z``)."""
    _x0, z0, _x1, z1 = ring.bounds
    return z1 - z0


def _parts_of(geom) -> list[Polygon]:
    return [q for q in getattr(geom, "geoms", [geom])
            if q.geom_type == "Polygon" and q.area > 1e-3]


def _kerbs(ring: Polygon, ends: list[tuple[XY, XY]], g) -> list[Polygon]:
    """The kerb band on every edge but the ends (and round every hole)."""
    w = float(g.kerb_w_m)
    band = ring.difference(ring.buffer(-w, join_style="mitre"))
    endset = {(a, b) for a, b in ends}
    sides = []
    for ring_ in (ring.exterior, *ring.interiors):
        pts = list(ring_.coords)
        for a, b in zip(pts[:-1], pts[1:], strict=True):
            if (a, b) not in endset and math.dist(a, b) > 1e-6:
                sides.append(LineString([a, b]).buffer(w * 1.01, cap_style="flat"))
    if not sides:
        return []
    return _parts_of(band.intersection(unary_union(sides)))


def _beams(ring: Polygon, g) -> list[Polygon]:
    """Beam footprints along ``z`` every ``beam_spacing_m`` across ``x``,
    centred on the ring, inside the edge beam."""
    inner = ring.buffer(-float(g.edge_beam_m), join_style="mitre")
    if inner.is_empty:
        return []
    x0, z0, x1, z1 = inner.bounds
    step, hw = float(g.beam_spacing_m), float(g.beam_width_m) / 2.0
    n = max(0, int((x1 - x0 - 2 * hw) // step))
    xc = 0.5 * (x0 + x1)
    out = []
    for k in range(n + 1):
        x = xc + (k - n / 2.0) * step
        rect = Polygon([(x - hw, z0 - 1), (x + hw, z0 - 1), (x + hw, z1 + 1), (x - hw, z1 + 1)])
        out += _parts_of(rect.intersection(inner))
    return out


def _octagon(c: XY, r: float) -> Polygon:
    return Polygon([(c[0] + r * math.cos(math.pi / 8 + k * math.pi / 4),
                     c[1] + r * math.sin(math.pi / 8 + k * math.pi / 4)) for k in range(8)])


def _piers(ring: Polygon, roads: _t.Sequence[Road], floor_y: float, g
           ) -> list[Part]:
    """Column rows at each road's floor edge, with their cap beams: no
    column and no cap over any covered road's floor (two roads side by
    side share the row between them), no two columns closer than two
    widths."""
    col, gap = float(g.pier_col_m), float(g.pier_gap_m)
    depth, cap_w, cap_h = float(g.thickness_m), float(g.pier_cap_w_m), float(g.pier_cap_h_m)
    inner = ring.buffer(-float(g.edge_beam_m) - col / 2.0, join_style="mitre")
    floors = unary_union([LineString(r.line).buffer(r.half_m + float(g.shoulder_m),
                                                    cap_style="flat")
                          for r in roads if len(r.line) >= 2])
    cols: list[Point] = []
    caps = []
    for r in roads:
        if len(r.line) < 2:
            continue
        line = LineString(r.line)
        off = r.half_m + float(g.shoulder_m) + col / 2.0
        for side in ("left", "right"):
            row = line.parallel_offset(off, side, join_style="mitre")
            row = row.intersection(inner) if not row.is_empty else row
            for seg in getattr(row, "geoms", [row]):
                if seg.is_empty or seg.geom_type != "LineString" or seg.length < col:
                    continue
                n = max(1, math.ceil(seg.length / gap))
                here = [p for p in (seg.interpolate(k / n, normalized=True) for k in range(n + 1))
                        if not floors.contains(p) and all(p.distance(q) >= 2 * col for q in cols)]
                if here:
                    cols += here
                    caps.append(seg.buffer(cap_w / 2.0, cap_style="flat"))
    if not cols:
        return []
    cap = unary_union(caps).difference(floors).intersection(
        ring.buffer(-float(g.edge_beam_m), join_style="mitre"))
    # a sliver of cap between two floors carries nothing: no cap, no column
    caps_ = [q for q in _parts_of(cap) if not q.buffer(-0.3 * cap_w).is_empty]
    held = unary_union(caps_) if caps_ else None
    out = [Part("cap", q, -depth, -depth - cap_h, ("bottom", "sides")) for q in caps_]
    return out + [Part("column", _octagon((p.x, p.y), col / 2.0), -depth - cap_h, 0.0,
                       ("sides",), floor_y - float(g.pier_foot_m))
                  for p in cols if held is not None and held.contains(p)]


def structure_parts(ring: Polygon, ends: _t.Sequence[_t.Sequence[XY]], g, *,
                    roads: _t.Sequence[Road] = (), floor_y: "float | None" = None
                    ) -> list[Part]:
    """The deck's parts (module doc), ``g`` the ``[deck_gen]`` law; the
    slab first (its top is the hard deck)."""
    slab, depth = float(g.slab_m), float(g.thickness_m)
    e_edges = end_edges(ring, ends, float(g.end_tol_m), float(g.end_angle_deg))
    band = ring.difference(ring.buffer(-float(g.edge_beam_m), join_style="mitre"))
    parts = [Part("slab", ring, 0.0, -slab)]
    parts += [Part("edge_beam", q, -slab, -depth, ("bottom", "sides")) for q in _parts_of(band)]
    parts += [Part("beam", q, -slab, -depth, ("bottom", "sides")) for q in _beams(ring, g)]
    parts += [Part("kerb", q, float(g.kerb_h_m), 0.0, ("top", "sides"))
              for q in _kerbs(ring, e_edges, g)]
    if roads and floor_y is not None and length_along_route(ring) > float(g.pier_min_span_m):
        parts += _piers(ring, roads, floor_y, g)
    return parts
