"""THE TERRAIN EDGE — adjacent ground ends at a rim road or a crest
(owner RULINGS 2026-09-10b/10c; spec ``auto-patch-v2/design-surface-spec.md``
§19).

The adjacent-ground rings are LAW surfaces with no DEM term (09b (3)), so
an end corridor 240 m long holds its designed level right over the lip of
a natural plateau and the bank behind it becomes a wall (CYXY, 19 m in
5.6 m).  The owner's law: the ring's EXTENT ends at the physical edge.

The clip happens at the SINGLE derivation site (``planar/zones.py``
``zone_regions``, which calls this module) so every downstream reader —
the arrangement, the zone bands, the strips, the census, the bank — sees
one trimmed polygon and nothing else changes (spec §19.3).

Construction, per region part:
  1. the part is rasterised at ``edge_grid_m``; a cell is CREST when the
     DEM's downhill slope read over ``edge_probe_m`` in the OUTWARD
     direction (away from the region's own pavement side) is steeper than
     ``bank_slope`` AND the drop over the probe exceeds ``edge_min_drop_m``;
  2. a ROAD whose line runs within ``edge_road_snap_m`` INSIDE that crest
     over at least ``edge_road_run_m`` governs: the barrier there is the
     road's OUTER EDGE (``road_profile.lane_width_m`` — the ribbon's own
     half-width — plus ``zones.adjacent_ground.groundside_cutback_m``,
     which every road already receives), so the region ends flush at it;
  3. what survives is the part connected to the pavement side without
     crossing a barrier, opened by the identity snap margin so the edge
     carries no sliver (04u).

A part with no crest cell and no governing road is returned UNCHANGED —
byte-identical to a build without this law.
"""
from __future__ import annotations

import dataclasses as _dc
import math

import numpy as np
import shapely
from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union
from shapely.strtree import STRtree

from ..airport.deck_signature import is_bridge_way, is_tunnel_way
from ..law import Law
from ..law.tables import snap_margin_m

__all__ = ["EdgeClip", "EdgeReport", "road_lines", "road_ribbons",
           "road_half_width_m", "clip_to_terrain_edge"]

_MITRE = dict(join_style="mitre", mitre_limit=2.0)


@_dc.dataclass(frozen=True)
class EdgeClip:
    """One region's trim: what is left, the EDGE segments the trim made
    (the boundary the DEM takes over from), and which rule made them."""

    kept: object                      # Polygon | MultiPolygon (may be empty)
    lines: tuple[LineString, ...] = ()
    kind: str = "none"                # "none" | "crest" | "road"


@_dc.dataclass
class EdgeReport:
    """What the terrain edge did, for the build log."""

    regions: int = 0
    trimmed_crest: int = 0
    trimmed_road: int = 0
    emptied: int = 0
    area_cut_m2: float = 0.0
    edge_length_m: float = 0.0
    roads_governing: int = 0

    def line(self) -> str:
        return (f"terrain edge: {self.trimmed_crest} region(s) cut at a CREST, "
                f"{self.trimmed_road} at a ROAD ({self.roads_governing} road run(s)), "
                f"{self.emptied} emptied; {self.area_cut_m2:,.0f} m² beyond the "
                f"edge given back to the DEM, {self.edge_length_m:,.0f} m of edge")


def road_lines(osm_ways=()) -> tuple[LineString, ...]:
    """The AT-GRADE OSM road centrelines in the frame: every way carrying
    a ``highway`` tag from the road feeds (``airport/osm.load_feed``'s
    ``airport_small_roads`` / ``big_roads``, already loaded into
    ``Airport.osm_ways``) that is neither a BORE nor a BRIDGE.

    ONE derivation for both consumers (§19 rule 2's rim road and §34 (4)'s
    band subtraction).  A ``tunnel`` or ``bridge`` way's centreline is not
    the surface: a bored road under the band neither ends the adjacent
    ground nor takes a ribbon out of it, and a viaduct over it is the
    deck's own law (the structure passes carry both, ``planar/structures``).
    """
    out: list[LineString] = []
    for w in osm_ways or ():
        tags = getattr(w, "tags", None) or {}
        if not tags.get("highway"):
            continue
        if is_tunnel_way(tags) or is_bridge_way(tags):
            continue
        pts = [(float(p[0]), float(p[1])) for p in getattr(w, "points", ())]
        if len(pts) >= 2:
            out.append(LineString(pts))
    return tuple(out)


def road_half_width_m(law: Law) -> float:
    """A mapped road's RIBBON half-width: the lane width plus the
    ``groundside_cutback_m`` every road already receives.  ONE reading
    for §19 rule 2's outer-edge barrier and §34 (4)'s band subtraction."""
    return (float(law.tables.emit.road_profile.lane_width_m)
            + float(law.tables.zones.adjacent_ground.groundside_cutback_m))


def road_ribbons(roads, law: Law):
    """ZONES YIELD TO ROADS (spec §34 (4); Fable 2026-09-13i, RULINGS
    2026-09-13i item 8): the mapped road ribbons a zone band subtracts —
    every at-grade centreline of ``road_lines`` grown by
    ``road_half_width_m`` ⊕ the identity snap, as ONE geometry.

    The band used to subtract CELLS only (``planar/zones.zone_regions``),
    so a mapped road the classifier gave no cell — LEMD's −6289 — ran
    straight through ``adjacent_ground:...:zone2#2`` and the band held its
    designed level 1.73 m over the road's own ground across 1.5 m, a step
    no law family prices (``graded_strip`` has no cap; the tear families
    are empty on v2).  The road keeps its own profile; the band stops at
    the ribbon and the gap between them terraces (the groundside terrace
    law), exactly as it already does beside a road that HAS a cell."""
    if not roads:
        return Polygon()
    half = road_half_width_m(law) + snap_margin_m(law)
    return unary_union([ln.buffer(half, **_MITRE) for ln in roads])


def _segments(geom) -> list[LineString]:
    segs: list[LineString] = []
    for g in getattr(geom, "geoms", [geom]):
        if g.is_empty:
            continue
        rings = [g.exterior, *g.interiors] if g.geom_type == "Polygon" else [g]
        for ring in rings:
            cs = list(ring.coords)
            segs.extend(LineString([cs[i], cs[i + 1]]) for i in range(len(cs) - 1))
    return segs


def _outward(px: np.ndarray, py: np.ndarray, seed) -> tuple[np.ndarray, np.ndarray]:
    """The unit vector from each point AWAY from the nearest point of the
    region's pavement side (zero where the point is on it)."""
    segs = _segments(seed)
    if not segs:
        return np.zeros(len(px)), np.zeros(len(px))
    tree = STRtree(segs)
    idx = np.asarray(tree.nearest(shapely.points(px, py)), dtype=int)
    ab = np.asarray([[s.coords[0], s.coords[1]] for s in segs], dtype=float)
    a = ab[idx, 0, :]
    b = ab[idx, 1, :]
    d = b - a
    L2 = (d ** 2).sum(axis=1)
    p = np.stack([px, py], axis=1)
    t = np.where(L2 > 0.0, ((p - a) * d).sum(axis=1) / np.where(L2 > 0.0, L2, 1.0), 0.0)
    q = a + np.clip(t, 0.0, 1.0)[:, None] * d
    u = p - q
    n = np.hypot(u[:, 0], u[:, 1])
    ok = n > 1.0e-9
    ux = np.where(ok, u[:, 0] / np.where(ok, n, 1.0), 0.0)
    uy = np.where(ok, u[:, 1] / np.where(ok, n, 1.0), 0.0)
    return ux, uy


def _dem_many(dem, xs: np.ndarray, ys: np.ndarray) -> np.ndarray:
    many = getattr(dem, "z_many", None)
    if many is not None:
        return np.asarray(many(xs, ys), dtype=float)
    return np.asarray([dem.z(float(x), float(y)) for x, y in zip(xs, ys)],
                      dtype=float)


def _crest_geometry(part: Polygon, seed, dem, law) -> tuple[object, int]:
    """The CREST cells of one region part (rule 1), as one geometry."""
    d = law.tables.emit.design
    g = float(d.edge_grid_m)
    probe = float(d.edge_probe_m)
    minx, miny, maxx, maxy = part.bounds
    nx = max(1, int((maxx - minx) / g) + 1)
    ny = max(1, int((maxy - miny) / g) + 1)
    gx = minx + (np.arange(nx) + 0.5) * g
    gy = miny + (np.arange(ny) + 0.5) * g
    X, Y = np.meshgrid(gx, gy)
    X, Y = X.ravel(), Y.ravel()
    inside = shapely.intersects_xy(part, X, Y)
    if not inside.any():
        return Polygon(), 0
    X, Y = X[inside], Y[inside]
    ux, uy = _outward(X, Y, seed)
    z0 = _dem_many(dem, X, Y)
    z1 = _dem_many(dem, X + ux * probe, Y + uy * probe)
    drop = z0 - z1
    crest = (np.isfinite(drop) & (drop > float(d.edge_min_drop_m))
             & (drop > float(d.bank_slope) * probe))
    if not crest.any():
        return Polygon(), 0
    h = g / 2.0
    boxes = shapely.box(X[crest] - h, Y[crest] - h, X[crest] + h, Y[crest] + h)
    return unary_union(list(boxes)), int(crest.sum())


def _road_barriers(part: Polygon, seed, crest, roads, law) -> tuple[list, list, int]:
    """Rule 2: the OUTER-EDGE barrier of every road that RUNS ALONG the
    crest — its line within ``edge_road_snap_m`` of the crest found in
    rule 1 over at least ``edge_road_run_m``.

    Two geometries per qualifying run: the BARRIER (a ring one grid thick
    at the road's outer edge — ``road_profile.lane_width_m``, the ribbon's
    own half-width, plus the ``groundside_cutback_m`` every road already
    receives) and the RELIEF (the crest within ``edge_road_snap_m`` of the
    run, which the road REPLACES: "without a road the crest of (1) is the
    edge", so with one the road is)."""
    d = law.tables.emit.design
    if not roads:
        return [], [], 0
    g = float(d.edge_grid_m)
    snap = float(d.edge_road_snap_m)
    run_min = float(d.edge_road_run_m)
    half = road_half_width_m(law)
    reach = part.buffer(half + g, **_MITRE)
    out: list = []
    relief: list = []
    n_runs = 0
    for road in roads:
        line = road.intersection(reach)
        if line.is_empty:
            continue
        for piece in getattr(line, "geoms", [line]):
            if piece.geom_type != "LineString" or piece.length < run_min:
                continue
            n = max(2, int(piece.length / g) + 1)
            ss = np.linspace(0.0, piece.length, n)
            pts = [piece.interpolate(float(s)) for s in ss]
            # RULE 2 RUNS WITHOUT A CREST (spec §34 (4); Fable
            # 2026-09-13i): the rim road ends the adjacent ground because
            # it is the physical edge of the graded ground, not because the
            # DEM happens to fall away beyond it.  Gated on the crest
            # (§19.2 (2) as first built) a road on flat ground governed
            # nothing, and LEMD's zone2#2 ran through −6289 unclipped.
            near = [True] * len(pts) if crest.is_empty \
                else [crest.distance(p) <= snap for p in pts]
            i = 0
            while i < len(near):
                if not near[i]:
                    i += 1
                    continue
                j = i
                while j + 1 < len(near) and near[j + 1]:
                    j += 1
                if ss[j] - ss[i] >= run_min:
                    sub = LineString([(p.x, p.y) for p in pts[i:j + 1]])
                    # ONE-SIDED: the barrier stands at the road's OUTER
                    # edge only — the side the pavement is not on — so the
                    # ground BETWEEN the pavement and the road is kept
                    mid = sub.interpolate(0.5, normalized=True)
                    ux, uy = _outward(np.array([mid.x]), np.array([mid.y]),
                                      seed)
                    probe = shapely.points(mid.x + float(ux[0]) * (half + g / 2.0),
                                           mid.y + float(uy[0]) * (half + g / 2.0))
                    far = None
                    for side in (half + g, -(half + g)):
                        slab = sub.buffer(side, single_sided=True)
                        if not slab.is_empty and slab.contains(probe):
                            far = slab
                            break
                    if far is None:
                        i = j + 1
                        continue
                    ring = far.difference(sub.buffer(half))
                    if not ring.is_empty:
                        out.append(ring)
                        relief.append(sub.buffer(snap))
                        n_runs += 1
                i = j + 1
    return out, relief, n_runs


def clip_to_terrain_edge(geom, seed, dem, roads, law: Law,
                         report: EdgeReport | None = None, ribbons=None) -> EdgeClip:
    """One region geometry clipped by the terrain edge (module docstring).
    ``seed`` is the region's PAVEMENT SIDE (the pavement union for zone 1,
    its lip offset for zone 2): what the kept part must stay connected to,
    and the reference the outward direction is measured from.
    ``ribbons`` is §34 (4)'s mapped road set (``road_ribbons``), a BARRIER
    like the crest: the band ends at it and does not resume beyond it."""
    rep = report if report is not None else EdgeReport()
    if geom is None or geom.is_empty or seed is None or seed.is_empty:
        return EdgeClip(geom)
    if dem is None and (ribbons is None or ribbons.is_empty):
        return EdgeClip(geom)
    tol = snap_margin_m(law)
    d = law.tables.emit.design
    g = float(d.edge_grid_m)
    kept_parts: list = []
    lines: list[LineString] = []
    kinds: set[str] = set()
    parts = [p for p in getattr(geom, "geoms", [geom]) if p.geom_type == "Polygon"]
    for part in parts:
        rep.regions += 1
        if part.is_empty or part.distance(seed) > max(tol, g):
            kept_parts.append(part)          # not this region's own ground
            continue
        crest, _cells = (_crest_geometry(part, seed, dem, law) if dem is not None
                         else (Polygon(), 0))
        rings, relief, n_runs = _road_barriers(part, seed, crest, roads, law)
        ribs = Polygon() if ribbons is None else ribbons.intersection(part)
        if crest.is_empty and not rings and ribs.is_empty:
            kept_parts.append(part)          # no edge: byte-identical
            continue
        rep.roads_governing += n_runs
        if relief:
            # the road REPLACES the crest it runs along (rule 2)
            crest = crest.difference(unary_union(relief))
        barrier = unary_union([crest, *rings, ribs])
        if barrier.is_empty:
            kept_parts.append(part)
            continue
        remainder = part.difference(barrier)
        keep = [p for p in getattr(remainder, "geoms", [remainder])
                if p.geom_type == "Polygon" and not p.is_empty
                and p.distance(seed) <= max(tol, g)]
        kept = unary_union(keep) if keep else Polygon()
        if not kept.is_empty:
            # the identity snap's own opening: the edge carries no sliver
            kept = kept.buffer(-tol, **_MITRE).buffer(tol, **_MITRE)
            kept = kept.intersection(part)
            kept = kept if kept.geom_type in ("Polygon", "MultiPolygon") else Polygon()
        if kept.is_empty:
            rep.emptied += 1
            rep.area_cut_m2 += part.area
            continue
        cut = part.area - kept.area
        if cut <= tol * part.length:         # nothing material was trimmed
            kept_parts.append(part)
            continue
        rep.area_cut_m2 += cut
        kind = "road" if (n_runs or not ribs.is_empty) else "crest"
        kinds.add(kind)
        rep.trimmed_road += int(kind == "road")
        rep.trimmed_crest += int(kind == "crest")
        # DENSIFYING THE TRIMMED BOUNDARY IS REFUTED (spec §34 (4) as
        # amended, RULINGS 2026-09-13ai; MEASURED by lane ``v2rampwalk``
        # round 2, one LEMD build, ledger 1498afa25daa).  The ruled remedy
        # was to space the trim's stations so no ring edge carries more
        # than ``visual_m`` of DEM change.  Built (``_densify_new_boundary``
        # below, kept for the record) it inserted 402 stations and turned
        # the ONE 8.50 m ``adjacent_ground_step`` row into 704
        # ``within_shape`` pairs on ``graded_strip|graded_strip`` at up to
        # 67.9 % — the base arm has ZERO.  The reason is geometric: the
        # region's OWN outer ring runs ALONG the contour (it parallels the
        # pavement, which is why its 155 nodes over an 11.4 m DEM range
        # carry no row at all), while the ribbon trim's chord runs ACROSS
        # it — every station added to a cross-contour chord is another
        # priced pair on the same slope.  Densifying moves the reading, not
        # the surface.  A trim that follows the contour is the open
        # question; not this lane's to rule (the builder is DELETED, not
        # kept gated: the measurement above and git are its record).
        new = kept.boundary.difference(part.boundary.buffer(tol))
        for ln in getattr(new, "geoms", [new]):
            if ln.geom_type == "LineString" and ln.length > tol:
                lines.append(ln)
                rep.edge_length_m += ln.length
        kept_parts.append(kept)
    out = unary_union(kept_parts) if kept_parts else Polygon()
    kind = "road" if "road" in kinds else ("crest" if "crest" in kinds else "none")
    return EdgeClip(out, tuple(lines), kind)
