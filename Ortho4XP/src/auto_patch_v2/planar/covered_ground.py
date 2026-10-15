"""THE GROUND OVER A COVERED ROAD IS THE GROUND BESIDE IT (issue #714).

A mapped bore (``tunnel=yes``, spec §26's admitted values) that passes
UNDER airside pavement is a road the airport stands on.  A bare-earth DEM
(lidar ground classes drop bridge decks and cut-and-cover lids) carries
that road's FLOOR along the covered stretch: at KATL the freeway (I-285,
ways -2193 / -2190, five lanes each, ``covered=yes layer=-1``) under
runway 10/28 reads 282 m against the 304-305 m field either side, and the
runway's target profile (``constraints/runway_chord``'s trend over the
ridge's ``dem_z``) and every per-vertex DEM pull over the cover sank the
runway 9.9 m into the road.  The pack's own portal objects there
(``tunel_A`` / ``tunel_B`` / ``tunel_C``: a deck plate at the object's
zero with walls 23.7-25.0 m under it) say the same thing: the deck is at
the field's level and the road 23-25 m below it.

THE RULE.  Every such bore's CUT is read off the DEM across its axis,
every 5 m along its covered chain: from the floor under the carriageway
(``structure_approach.carriageway_width_m``), each side's RIM is where
the DEM first climbs ``[tunnel] covered_rim_rise_frac`` of the way to the
highest ground within ``[tunnel] covered_rim_search_m`` (a dual
carriageway's median and its twin bore sit inside one cut and are
crossed), and the ground BESIDE the cover there is the highest DEM within
``[tunnel] covered_side_probe_m`` past the rim.  The sections span the
COVERED FOOTPRINT (rim to rim, the mapped covered stretch long: the open
cut beyond the mouths is never touched) and clipped to the airside
pavement over it (the deck ends where its pavement ends: a portal the
mapped bore overshoots by a few metres leaves the open cut and its road
at the DEM); a vertex inside takes the
ground beside the cover, interpolated along the bore and across it.  It
LIFTS only (``max(dem, beside)``), and a side whose DEM never climbs
the MOUTH DEPTH (``Tunnel.mouth_depth_m``, 7.5 m: the least a real road
floor stands under the surface over it) reads no cut: where the DEM already stands
over the cover (a DSM, a true bored tunnel, lidar that kept the lid)
nothing moves, so an airport whose DEM sees the cover reads as before.

ONE derivation site (RULINGS 2026-08-30l): ``planar/build`` writes the
lifted value into ``Vertex.dem_z`` beside the tunnel ramps' own targets
(``ramp_targets``, which win on their vertices), and every solve-side
reader — the runway trend, the per-vertex fit, the ground band, the
zones — reads ``dem_z``.  Readers that ask ``airport.dem`` directly (the
object readers, the structure stage, the emitter's outside mesh) keep the
real ground: the trench beyond the mouths and the object seats are
unchanged.  The consumer census is in ``docs/briefs/katl714-notes.md``
(issue #714).

THE MOUTH IS A DECLARED STEP WHERE PACK WALLS BOUND IT (owner RULINGS
2026-10-15a (1)/(2), #714 residual): where a pack object whose solid
reaches at least the mouth depth under its own zero (a portal: KATL
``tunel_A`` / ``_B`` / ``_C``, walls 23.7-25.9 m deep) stands over the
deck's edge at the pavement's end, that stretch of the edge is published
(:attr:`CoveredGround.mouth_walls`, ``PlanarMap.mouth_walls``) as a wall
that retains its height — ``airport/road_ramp`` reads it like a pack
retaining wall: the road past the mouth is released from the deck's level
and runs at its own floor, and the step across the edge is declared."""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

import numpy as np
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union
from shapely.prepared import prep
from shapely.strtree import STRtree

from ..airport.dem import dem_z_many
from ..law import Law
from .structure_approach import (Bore, carriageway_width_m, chains, is_tunnel,
                                 standing_cover)
from .structure_service import airside_cut_roles

__all__ = ["CoveredGround", "covered_ground"]

#: the across-axis sampling step of a cut's section (metres)
_STEP_M = 1.0
#: the spacing of the sections along a bore's covered chain (metres)
_STATION_M = 5.0
#: the airside pavement's union is grown by this before it clips a cut, so
#: a vertex ON the pavement's edge (the identity grid) is inside (metres)
_PAVEMENT_TOL_M = 0.5


@_dc.dataclass
class CoveredGround:
    """The covered footprint and what it lifted (the build's report line)."""

    #: the covered footprint's exterior rings, frame metres (JSON-able:
    #: the build report carries this record through ``dataclasses.asdict``)
    rings: list[list[tuple[float, float]]] = _dc.field(default_factory=list)
    bores: list[str] = _dc.field(default_factory=list)
    area_m2: float = 0.0
    vertices_in: int = 0
    vertices_lifted: int = 0
    max_lift_m: float = 0.0
    max_lift_xy: tuple[float, float] | None = None
    #: the deck edge where pack walls bound it (owner RULINGS 2026-10-15a):
    #: ``(strip ring, wall depth m, resource)`` per walled stretch
    mouth_walls: list[tuple[list[tuple[float, float]], float, str]] = \
        _dc.field(default_factory=list)

    def line(self) -> str:
        if not self.rings:
            return ("covered ground (#714): no mapped bore under airside pavement runs in a "
                    "cut the mouth depth deep")
        at = (f" at ({self.max_lift_xy[0]:.0f}, {self.max_lift_xy[1]:.0f})"
              if self.max_lift_xy else "")
        return (f"covered ground (#714): {len(self.bores)} bore(s) under airside pavement "
                f"[{', '.join(self.bores[:8])}], footprint {self.area_m2:,.0f} m2; "
                f"{self.vertices_lifted} of {self.vertices_in} vertex(es) inside take the "
                f"ground beside the cover, max lift {self.max_lift_m:.2f} m{at}; "
                f"{len(self.mouth_walls)} walled mouth edge(s)")


def _served(bores: list[Bore], airside: list[Polygon], min_m: float) -> list[Bore]:
    """The bores whose plan line runs at least ``min_m`` under airside pavement."""
    if not airside:
        return []
    tree = STRtree(airside)
    out = []
    for b in bores:
        ln = b.line
        parts = [ln.intersection(airside[int(j)]) for j in tree.query(ln, predicate="intersects")]
        parts = [g for g in parts if not g.is_empty]
        if parts and unary_union(parts).length >= min_m:
            out.append(b)
    return out


@_dc.dataclass(frozen=True)
class _Section:
    """One across-axis reading of a bore's cut: the foot on the bore, the
    unit normal (+ = left), each rim's distance from the foot and the
    ground beside the cover there."""

    s: float
    foot: tuple[float, float]
    normal: tuple[float, float]
    dl: float
    dr: float
    zl: float
    zr: float


def _rim(d: np.ndarray, z: np.ndarray, floor: float, frac: float, probe: float, rise: float):
    """(rim distance, ground beside) on one side, or None where the DEM
    never climbs ``rise`` over the floor (the DEM already sees the cover)."""
    ok = np.isfinite(z)
    if not ok.any():
        return None
    top = float(np.nanmax(z))
    if top - floor < rise:
        return None
    target = floor + frac * (top - floor)
    k = int(np.argmax(np.where(ok, z, -np.inf) >= target))
    beyond = z[(d >= d[k]) & (d <= d[k] + probe) & ok]
    return float(d[k]), float(beyond.max())


def _sections(dem, bore: Bore, law: Law) -> list[_Section]:
    """The bore's cut, read every ``_STATION_M`` along its covered chain."""
    tn = law.tables.structures.tunnel
    reach, probe = float(tn.covered_rim_search_m), float(tn.covered_side_probe_m)
    # a DEM that sees the road FLOOR under the cover stands at least the
    # mouth depth (clearance + equipment + roof + cover) under the ground
    # beside it; a shallower dip is not the floor and is not read
    frac, rise = float(tn.covered_rim_rise_frac), float(tn.mouth_depth_m)
    half = 0.5 * max(carriageway_width_m(w.tags, law) for w in bore.ways)
    ln = bore.line
    d = np.arange(0.0, reach + probe + 1e-9, _STEP_M)
    out = []
    for s in np.append(np.arange(0.0, ln.length, _STATION_M), ln.length):
        a = ln.interpolate(max(0.0, s - 1.0))
        b = ln.interpolate(min(ln.length, s + 1.0))
        tx, ty = b.x - a.x, b.y - a.y
        n = math.hypot(tx, ty) or 1.0
        nx, ny = -ty / n, tx / n
        q = ln.interpolate(s)
        zl = dem_z_many(dem, q.x + nx * d, q.y + ny * d)
        zr = dem_z_many(dem, q.x - nx * d, q.y - ny * d)
        near = np.concatenate([zl[d <= half], zr[d <= half]])
        near = near[np.isfinite(near)]
        if near.size == 0:
            continue
        floor = float(near.min())
        inner = d <= reach
        left = _rim(d[inner], zl[inner], floor, frac, probe, rise)
        right = _rim(d[inner], zr[inner], floor, frac, probe, rise)
        if left is None and right is None:
            continue
        # a side whose DEM never climbs keeps the carriageway's own edge and
        # the other side's ground: the cover spans the cut it can see
        left = left or (half, right[1])
        right = right or (half, left[1])
        # the rim reading stops at the probe: the beside value is read
        # from the full probe window past the rim, not cut at ``reach``
        dl = max(left[0], half)
        dr = max(right[0], half)
        zl_b = float(np.nanmax(zl[(d >= dl) & (d <= dl + probe)]))
        zr_b = float(np.nanmax(zr[(d >= dr) & (d <= dr + probe)]))
        out.append(_Section(float(s), (q.x, q.y), (nx, ny), dl, dr,
                            max(left[1], zl_b), max(right[1], zr_b)))
    return out


def _ribbon(secs: list[_Section]):
    """The plan polygon a bore's sections span (rim to rim)."""
    if len(secs) < 2:
        return None
    left = [(c.foot[0] + c.normal[0] * c.dl, c.foot[1] + c.normal[1] * c.dl) for c in secs]
    right = [(c.foot[0] - c.normal[0] * c.dr, c.foot[1] - c.normal[1] * c.dr) for c in secs]
    poly = Polygon(left + right[::-1]).buffer(0)
    return poly if not poly.is_empty else None


def _ground_at(p: Point, ln: LineString, secs: list[_Section]) -> float | None:
    """The ground beside the cover at ``p``, interpolated along and across."""
    s = ln.project(p)
    ss = [c.s for c in secs]
    k = int(np.clip(np.searchsorted(ss, s), 1, len(ss) - 1))
    a, b = secs[k - 1], secs[k]
    w = 0.0 if b.s <= a.s else min(1.0, max(0.0, (s - a.s) / (b.s - a.s)))

    def lerp(u, v):
        return u + w * (v - u)
    q = ln.interpolate(s)
    nx, ny = lerp(a.normal[0], b.normal[0]), lerp(a.normal[1], b.normal[1])
    off = (p.x - q.x) * nx + (p.y - q.y) * ny
    dl, dr = lerp(a.dl, b.dl), lerp(a.dr, b.dr)
    t = min(1.0, max(0.0, (off + dr) / max(dl + dr, 1e-6)))
    zr, zl = lerp(a.zr, b.zr), lerp(a.zl, b.zl)
    return zr + t * (zl - zr)


#: half the width of a walled mouth edge's strip (metres): the identity
#: grid's own tolerance, so a vertex ON the pavement's edge stands in it
_EDGE_HALF_M = _PAVEMENT_TOL_M


def _mouth_walls(cuts, pav, objects, depth_min: float):
    """The walled mouths: per mouth (the deck's edge at the pavement's end)
    where a pack object reaching ``depth_min`` under its own zero (a
    portal) stands within the cut, ONE piece — that edge (a strip the
    identity tolerance wide: the deck's last vertices stand in it) and the
    OPEN CUT beyond it off the pavement, as wide as the cut's own section
    there (rim to rim, :class:`_Section`): the road in it runs at its
    floor.  ``[(ring, depth, resource)]``."""
    deep = []
    for o in objects or ():
        box = getattr(o, "plan_bbox", None)
        lo = getattr(o, "solid_min_z", None)
        if box is None or lo is None or getattr(o, "anchor_z", None) is None:
            continue
        depth = float(o.anchor_z) + float(getattr(o, "agl_m", 0.0) or 0.0) - float(lo)
        if depth >= depth_min:
            deep.append((box, depth, str(o.path)))
    if not deep:
        return []
    end = pav.boundary.buffer(0.1)
    out = []
    for _b, secs, rib, _pr in cuts:
        mouth = rib.boundary.intersection(end)
        for seg in getattr(mouth, "geoms", [mouth]):
            if seg.is_empty or seg.length < 1.0:
                continue
            sec = min(secs, key=lambda c: seg.distance(Point(c.foot))) if secs else None
            reach = max(sec.dl, sec.dr) if sec is not None else 0.0
            cut = seg.buffer(reach).difference(pav) if reach > 0.0 else None
            walls = [(d, p) for box, d, p in deep
                     if box.intersects(seg) or (cut is not None and box.intersects(cut))]
            if not walls:
                continue
            depth, path = max(walls)
            piece = unary_union([seg.buffer(_EDGE_HALF_M)] + ([cut] if cut is not None else []))
            for g in getattr(piece, "geoms", [piece]):
                if g.geom_type == "Polygon" and g.area > 0.0 and g.intersects(seg):
                    out.append(([(round(x, 2), round(y, 2)) for x, y in g.exterior.coords],
                                round(depth, 2), path))
    return out


def covered_ground(airport, classification, law: Law, xs: np.ndarray, ys: np.ndarray,
                   zs: np.ndarray, objects=()) -> tuple[np.ndarray, CoveredGround]:
    """``zs`` with every vertex inside the covered footprint lifted to the
    ground beside the cover (never lowered), and the report (with the
    walled mouth edges, :func:`_mouth_walls`, read off ``objects`` —
    ``planar/basins.read_objects``)."""
    rep = CoveredGround()
    dem = getattr(airport, "dem", None)
    tn = law.tables.structures.tunnel
    ways = [w for w in getattr(airport, "osm_ways", ())
            if is_tunnel(w, tn.admitted_values) and len(w.points) >= 2]
    if dem is None or not ways or not classification.cells:
        return zs, rep
    roles = set(airside_cut_roles(law))
    cells, _gap, polys = standing_cover(classification)
    airside = [p for p, c in zip(polys, cells) if c.role in roles]
    served = _served(chains(ways), airside, float(tn.terrain_cover_min_m))
    cuts = []
    for b in served:
        secs = _sections(dem, b, law)
        rib = _ribbon(secs)
        if rib is not None:
            cuts.append((b, secs, rib))
    if not cuts:
        return zs, rep
    # THE COVER ENDS WHERE ITS PAVEMENT ENDS: the cut's ribbon is clipped to
    # the airside pavement over it (grown by the identity grid), so the open
    # cut beyond the deck's edge — the road at its floor, the bank — keeps
    # the DEM even where the mapped bore ends a few metres past the portal
    pav = unary_union(airside).buffer(_PAVEMENT_TOL_M)
    cuts = [(b, secs, rib.intersection(pav)) for b, secs, rib in cuts]
    cuts = [(b, secs, rib, prep(rib)) for b, secs, rib in cuts if not rib.is_empty]
    if not cuts:
        return zs, rep
    fp = unary_union([c[2] for c in cuts])
    rep.area_m2 = float(fp.area)
    rep.rings = [[(round(x, 2), round(y, 2)) for x, y in g.exterior.coords]
                 for g in getattr(fp, "geoms", [fp]) if g.geom_type == "Polygon"]
    rep.bores = ["+".join(str(w.id) for w in b.ways) for b, *_r in cuts]
    rep.mouth_walls = _mouth_walls(cuts, pav, objects, float(tn.mouth_depth_m))
    out = np.array(zs, dtype=float, copy=True)
    minx, miny, maxx, maxy = fp.bounds
    box = (xs >= minx) & (xs <= maxx) & (ys >= miny) & (ys <= maxy)
    for v in np.nonzero(box)[0]:
        p = Point(float(xs[v]), float(ys[v]))
        zs_in = [_ground_at(p, b.line, secs) for b, secs, _rib, pr in cuts if pr.contains(p)]
        zs_in = [z for z in zs_in if z is not None]
        if not zs_in:
            continue
        rep.vertices_in += 1
        z = max(zs_in)
        here = float(out[v])
        if math.isnan(here) or z > here:
            lift = z - (0.0 if math.isnan(here) else here)
            out[v] = z
            rep.vertices_lifted += 1
            if lift > rep.max_lift_m:
                rep.max_lift_m, rep.max_lift_xy = lift, (p.x, p.y)
    return out, rep
