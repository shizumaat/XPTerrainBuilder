"""THE CROSSING FRAMES AND THEIR SEAT, read ONCE at load (owner RULINGS
2026-11-20g / 20k; spec ``docs/specs/elevated-clearance-20g-spec.md`` §4).

20g: an elevated pack structure crossing a mapped road or rail keeps the
class minimum clearance over it -- first by seating its buildings high
enough, then by lowering the road on a graded ramp.  20k (KMCO): "a group is
lifted no higher than its own highest ground vote; the remaining clearance
comes from 20g (3) ramps".

The patch must know the seat BEFORE the mesh: it grades the roads under the
soffit.  So the patch DECIDES the seat and the object stage obeys it (the
road overpass precedent, ``planar/overpass_deck``): :func:`crossing_records`
reads, per pack frame (plan unit) of the partition --

* its CROSSINGS: every component of a member whose soffit over a mapped
  road's or rail's carriageway stands at least ``[road_gen] witness_share``
  of ``[bridge] clearance_minimum_m`` (2.1 m) over the frame's zero and
  SPANS it (``airport/elevated_crossing``, the one read, on the authored
  geometry placed in the airport frame) -- the share the generated road
  bridge reads as a crossing (RULINGS 16s/16t); a canopy or a roof the
  author built a storey under that over a road is no passage;
* the CROSSING GROUP: the frame's parts touching the crossing components,
  transitively (``[placement] touch_gap_m``, ``touch_graph.VETO_M`` -- the
  touch pass's own relation, read on the parts);
* its SEAT ``zero``: the area-weighted MEDIAN of the group's building parts'
  ground votes (each part: the median of ``DEM - y`` over its own ground
  feet).  The median, never the highest: the object stage seats the group at
  ``min(zero, its highest vote on the mesh)`` (``touch_seat``), so a zero over
  that vote would leave the road graded for a soffit that is not built.  A
  group whose votes SPREAD (area-weighted p10..p90) more than
  ``touch_seat.SEAT_MAX_M`` is no seat: the touch pass leaves its members on
  their own pads (16v), nothing here can say which zero the crossing hangs
  from, and its crossings are listed, never graded;
* every crossing still SHORT at that seat over the DEM: its least soffit
  ``y``, the cells' region and the class minimum, for the road ceiling
  (``constraints/elevated_clearance``) and the published seat.  A crossing
  whose soffit stands UNDER the road's own ground at that seat is no road
  passing under a structure (the road runs over it -- a cut box, a portal),
  and its group's seat says nothing of the others: the group's crossings are
  listed, never graded.

A frame the bridge law owns (a deck member, a free bridge) is not read here.
Nothing names an airport, a pack or a resource.
"""
from __future__ import annotations

import math
import statistics as _st
import typing as _t

import numpy as np

from . import elevated_crossing as _ec

__all__ = ["crossing_records", "published", "PUBLISHED", "CELL_PAD_M"]

#: the crossing cells' region is grown by this (a cell is ``STEP_M`` wide)
CELL_PAD_M = 0.5


def _placed(g, comp, o, heading_deg: float) -> np.ndarray:
    """One component's static solid faces ``(n, 3, 3)`` in the airport
    frame: x, y the plan (``obj8.placement_affine``), z the AUTHORED ``y``."""
    from .obj8 import placement_affine
    a, b, d, e, xo, yo = placement_affine(o, heading_deg)
    T = np.asarray(g.solid)[np.asarray(comp.idx)]
    V = np.asarray(g.vertices, dtype=np.float64)[T]
    x, y, z = V[:, :, 0], V[:, :, 1], V[:, :, 2]
    return np.stack([a * x + b * z + xo, d * x + e * z + yo, y], axis=-1)


def _owners(u, cache, to_xy, elev: float) -> list:
    """``((member id, comp), faces, floor)`` of every component of the unit
    that rises over ``elev`` (the bridge law's members left out)."""
    from .placement_family import member_is_deck
    out = []
    for m in u.members:
        if getattr(m, "scatter", False) or getattr(m, "free_bridge", "") or member_is_deck(m):
            continue
        path = m.authored_path or m.live_path
        g = cache.geometry(path) if path else None
        if g is None or not g.solid.shape[0]:
            continue
        la, lo = (m.origin or u.anchor)
        o = to_xy(float(lo), float(la))
        for ci, c in enumerate(cache.components(path)):
            if c.animated or c.max_y <= elev or c.idx is None:
                continue
            out.append(((m.id, ci), _placed(g, c, o, float(m.heading_deg)), elev))
    return out


def _part_polys(u, to_xy) -> list:
    """``(member id, part, frame polygon)`` of every non-line part ring."""
    from shapely.geometry import Polygon
    out = []
    for m in u.members:
        for p in m.parts:
            if p.line:
                continue
            for r in p.rings or ():
                if len(r) >= 3:
                    g = Polygon([to_xy(lo, la) for la, lo in r])
                    g = g if g.is_valid else g.buffer(0.0)
                    if not g.is_empty:
                        out.append((m.id, p, g))
    return out


def _group(polys: list, seeds: set, touch_m: float, veto_m: float) -> list:
    """The parts touching the ``seeds`` ``(member, comp)`` transitively."""
    from shapely.strtree import STRtree
    if not polys:
        return []
    tree = STRtree([g for _m, _p, g in polys])
    a, b = tree.query([g for _m, _p, g in polys], predicate="dwithin", distance=touch_m)
    adj: dict[int, list[int]] = {}
    for i, j in zip(a.tolist(), b.tolist(), strict=True):
        pi, pj = polys[i][1], polys[j][1]
        lo = max(float(pi.base_y), float(pj.base_y))
        hi = min(float(pi.base_y) + float(pi.height_m), float(pj.base_y) + float(pj.height_m))
        if i != j and lo - hi <= veto_m:
            adj.setdefault(i, []).append(j)
    todo = [k for k, (m, p, _g) in enumerate(polys) if (m, p.comp) in seeds]
    seen = set(todo)
    while todo:
        k = todo.pop()
        for j in adj.get(k, ()):
            if j not in seen:
                seen.add(j)
                todo.append(j)
    return [polys[k] for k in sorted(seen)]


def _vote(p, to_xy, dem) -> "float | None":
    """A part's ground vote: the median of ``DEM - y`` over its feet."""
    vs = []
    for la, lo, y in p.feet or ():
        try:
            z = float(dem.z(*to_xy(lo, la)))
        except Exception:  # noqa: BLE001 -- off the raster
            continue
        if math.isfinite(z):
            vs.append(z - float(y))
    return _st.median(vs) if vs else None


def _weighted(vs: list[tuple[float, float]], q: float) -> float:
    """The area-weighted ``q`` quantile of sorted ``(vote, area)``."""
    total = sum(max(w, 1e-6) for _v, w in vs)
    acc = 0.0
    for v, w in vs:
        acc += max(w, 1e-6)
        if acc >= q * total:
            return v
    return vs[-1][0]


def _seat(group: list, to_xy, dem, wall_m: float) -> "tuple[float, float] | None":
    """``(seat, spread)``: the area-weighted median of the group's BUILDING
    parts' votes (a footed part ``wall_m`` tall), else of every footed
    part's, and their p10..p90 spread."""
    seen: set = set()
    votes: list[tuple[float, float]] = []
    walled: list[tuple[float, float]] = []
    for mid, p, _g in group:
        if (mid, p.comp) in seen or not p.feet:
            continue
        seen.add((mid, p.comp))
        v = _vote(p, to_xy, dem)
        if v is None:
            continue
        votes.append((v, float(p.area_m2)))
        if float(p.height_m) >= wall_m:
            walled.append((v, float(p.area_m2)))
    use = sorted(walled or votes)
    if not use:
        return None
    return _weighted(use, 0.5), _weighted(use, 0.9) - _weighted(use, 0.1)


def _region(c) -> list:
    """The crossing cells' plan region (frame xy ring)."""
    from shapely.geometry import box
    from shapely.ops import unary_union
    xs, ys, _z = c.grid
    h = 0.5 * _ec.STEP_M + CELL_PAD_M
    g = unary_union([box(x - h, y - h, x + h, y + h) for x, y in zip(xs, ys, strict=True)])
    g = g.convex_hull if g.geom_type != "Polygon" else g
    return [[round(x, 3), round(y, 3)] for x, y in g.exterior.coords]


#: the keys of a record the graded surface publishes for the object stage
PUBLISHED = ("unit", "member", "comp", "way", "kind", "need", "zero", "soffit_y")


def published(records: _t.Iterable[_t.Mapping]) -> list[dict]:
    """The crossing records as the graded surface publishes them
    (``provenance.elevated_crossings``; ``placement_read.
    crossings_from_graded_doc`` reads them back)."""
    return [{k: r[k] for k in PUBLISHED} for r in records]


def crossing_records(airport, law, cache) -> tuple[tuple[dict, ...], list[str]]:
    """``(records, notes)``: every crossing still short at its frame's seat
    (module doc), one plain record each."""
    part = getattr(airport, "partition", None)
    dem = getattr(airport, "dem", None)
    if part is None or dem is None or cache is None:
        return (), []
    st = law.tables.structures
    floor = max(float(st.rebake.elevated_base_m),
                float(st.road_gen.witness_share) * float(st.bridge.clearance_minimum_m))
    touch_m = float(getattr(st.placement, "touch_gap_m", 0.0) or 0.0)
    wall_m = float(st.placement.chain_min_height_m)
    to_xy = airport.frame.entry()
    cways = _ec.carriageways(getattr(airport, "osm_ways", ()) or (),
                             lambda w: list(w.points), law)
    if not cways or touch_m <= 0.0:
        return (), []
    from .touch_graph import VETO_M
    from .touch_seat import SEAT_MAX_M

    def ground(xs, ys):
        return np.array([float(dem.z(float(x), float(y))) for x, y in zip(xs, ys, strict=True)])
    out: list[dict] = []
    notes: list[str] = []
    for u in part.units:
        owners = _owners(u, cache, to_xy, floor)
        if not owners:
            continue
        crossed = _ec.read_crossings(owners, cways, ground)
        if not crossed:
            continue
        group = _group(_part_polys(u, to_xy), {c.owner for c in crossed}, touch_m, VETO_M)
        got = _seat(group, to_xy, dem, wall_m)
        if got is None:
            notes.append(f"{u.id}: {len(crossed)} crossing(s), no ground vote: no seat")
            continue
        zero, spread = got
        buried = [c for c in crossed if zero + c.least_m < 0.0]
        short = [c for c in crossed if 0.0 <= zero + c.least_m < c.need_m]
        if buried:
            notes.append(f"{u.id}: {len(buried)} crossing(s) with the soffit under the "
                         f"road's ground at seat {zero:.2f} (worst "
                         f"{min(zero + c.least_m for c in buried):+.2f} m): the group "
                         f"stands in a cut the roads run over, its {len(short)} short "
                         f"crossing(s) listed")
            continue
        if spread > SEAT_MAX_M:
            notes.append(f"{u.id}: {len(crossed)} crossing(s), {len(short)} short at the "
                         f"median {zero:.2f}, but the group's votes spread {spread:.2f} m: "
                         f"no one seat, listed")
            continue
        notes.append(f"{u.id}: {len(crossed)} crossing(s) at seat {zero:.2f} (spread "
                     f"{spread:.2f}, {len(group)} group part(s)), {len(short)} short over "
                     f"the DEM")
        for c in short:
            mid, comp = c.owner
            out.append({"unit": str(u.id), "member": str(mid), "comp": int(comp),
                        "way": c.way, "kind": c.kind, "need": float(c.need_m),
                        "zero": round(float(zero), 3),
                        "soffit_y": round(float(np.min(c.grid[2])), 3),
                        "least_dem": round(float(zero + c.least_m), 3),
                        "at": [round(c.at[0], 3), round(c.at[1], 3)],
                        "region": _region(c)})
    return tuple(out), notes

