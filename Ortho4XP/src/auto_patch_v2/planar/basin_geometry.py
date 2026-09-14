"""THE BASIN'S PLAN GEOMETRY — the rim, the floor faces and the ramp
corridor's ring (split out of ``planar/basins.py`` for lane ``v2othhfix``
so that file stays inside its line budget; the ADMISSION and the region
loop stay there).

The law these carry, with its rulings:

* THE CUT HUGS THE WALL (owner RULINGS 2026-09-11t, spec §24 (1)):
  :func:`_rim` is the admitted region set INWARD by the shell's measured
  thickness and nothing else, and the wall band's stand-off comes out of
  the FLOOR (:func:`_floors_inside`).
* THE FLOOR IS THE WHOLE ADMITTED REGION (owner RULINGS 2026-09-14n item 1
  / 2026-09-14p, spec §24 (7)): :func:`_region_floor` — the trench floor is
  the rim minus that stand-off, the ramp corridors carved out of it; the
  witnessed plate witnesses DEPTH and delimits nothing.
* A RAMP CORRIDOR IS RE-NODED AT ITS STATIONS (owner RULINGS 2026-09-14s,
  spec §24 (8)): :func:`_renode`, so §24 (5)'s per-station deck profile has
  vertices to land on.
"""
from __future__ import annotations

import math
import typing as _t

import shapely
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union

from ..model.frame import XY

__all__ = ["shell_thickness_m"]

_MITRE = dict(join_style="mitre", mitre_limit=2.0)


def _parts(geom) -> list[Polygon]:
    return [g for g in shapely.get_parts(geom) if g.geom_type == "Polygon" and not g.is_empty]

def _snap_ring(poly: Polygon, grid: float) -> Polygon | None:
    p = shapely.set_precision(poly, grid)
    if p.is_empty:
        return None
    if p.geom_type != "Polygon":
        parts = [g for g in shapely.get_parts(p) if g.geom_type == "Polygon"]
        if not parts:
            return None
        p = max(parts, key=lambda g: g.area)
    return Polygon(p.exterior.coords) if p.is_valid else None


def _floors(plates, overlap: float, close: float, grid: float) -> list[Polygon]:
    """The floor face(s): the plates ⊕ ``overlap``, closed at ``close``,
    snapped to the grid and widened by grid steps until every snapped
    part stands ≥ ``overlap`` outside the plates it covers (the overlap
    is a stand-off: never rounded under), largest first."""
    for k in range(4):
        g = plates.buffer(overlap + k * grid, **_MITRE)
        g = g.buffer(close, **_MITRE).buffer(-close, **_MITRE)
        out: list[Polygon] = []
        ok = True
        for fp in sorted(_parts(g), key=lambda q: -q.area):
            f = _snap_ring(fp.simplify(grid / 2.0), grid)
            if f is None or f.area < grid * grid:
                continue
            inside = plates.intersection(fp)
            if not inside.is_empty and (not f.contains(inside.buffer(-1e-6))
                                        or inside.distance(f.exterior) < overlap - 1e-6):
                ok = False
            out.append(f)
        if ok or k == 3:
            return out
    return []


def _snap_face(poly: Polygon, grid: float) -> Polygon | None:
    """``poly`` on the identity grid WITH ITS HOLES (the region floor of
    §24 (7) carries the ramp corridors as holes; :func:`_snap_ring` keeps
    only an exterior, which would refill them and put two floor faces on
    the same ground)."""
    p = shapely.set_precision(poly, grid)
    if p.is_empty:
        return None
    parts = [g for g in _parts(p) if g.is_valid and g.area >= grid * grid]
    return max(parts, key=lambda g: g.area) if parts else None


def _ramp_axis(faces) -> tuple[XY, XY] | None:
    """A ramp corridor's CLIMB AXIS: its lowest deck vertex to its highest
    (the same two points :func:`basin_witness.ramp_decks` measures the run
    between).  ``None`` for a deck with no faces or no rise in plan."""
    pts = [q for tri in faces for q in tri]
    if len(pts) < 3:
        return None
    lo = min(pts, key=lambda q: q[2])
    hi = max(pts, key=lambda q: q[2])
    if math.hypot(hi[0] - lo[0], hi[1] - lo[1]) < 1e-6:
        return None
    return (lo[0], lo[1]), (hi[0], hi[1])


def _renode(ring: Polygon, axis: tuple[XY, XY], step: float, grid: float) -> Polygon:
    """A BASIN'S RAMP CORRIDOR IS RE-NODED AT ITS STATIONS (spec §24 (8),
    owner RULINGS 2026-09-14s).  §24 (5) states the floor under a ramp
    corridor per station, but ``constraints/structures`` can only pin
    vertices that EXIST: VHHH's ``basin_floor:5#1`` — 2,794 m2 over 6.9 m
    of drop — carried four interior vertices, so the pins made a
    four-triangle fan with a 42 % step at its mouth.  The ring is cut at
    every ``step`` along the climb axis (the structures pass's stationed
    ramp is the model): each station line's crossings of the ring become
    vertices, on the identity grid, and a crossing that snaps onto a
    neighbour is dropped."""
    (x0, y0), (x1, y1) = axis
    L = math.hypot(x1 - x0, y1 - y0)
    if L <= step or ring.is_empty or ring.geom_type != "Polygon":
        return ring
    ux, uy = (x1 - x0) / L, (y1 - y0) / L
    ext = LineString(ring.exterior.coords)
    span = float(ring.length)
    ds = {ext.project(Point(c)) for c in ring.exterior.coords}
    t = step
    while t < L - 1e-9:
        cx, cy = x0 + ux * t, y0 + uy * t
        cut = LineString([(cx - uy * span, cy + ux * span), (cx + uy * span, cy - ux * span)])
        for g in shapely.get_parts(ext.intersection(cut)):
            if g.geom_type == "Point":
                ds.add(ext.project(g))
        t += step
    coords: list[XY] = []
    for d in sorted(ds):
        p = ext.interpolate(d)
        q = (round(p.x / grid) * grid, round(p.y / grid) * grid)
        if not coords or math.hypot(q[0] - coords[-1][0], q[1] - coords[-1][1]) > grid / 2.0:
            coords.append(q)
    if len(coords) < 4:
        return ring
    out = Polygon(coords)
    # the inserted vertices lie ON the ring, so the area may only move by
    # the grid snap; anything more means the walk folded the ring
    return out if out.is_valid and abs(out.area - ring.area) <= max(1.0, 0.05 * ring.area) \
        else ring


def _region_floor(rim: Polygon, standoff: float, carved: list[Polygon],
                  grid: float) -> list[Polygon]:
    """THE FLOOR IS THE WHOLE ADMITTED REGION (spec §24 (7), owner
    RULINGS 2026-09-14n item 1 / 2026-09-14p): once a region is admitted
    as a pit, the trench floor is the rim MINUS the wall band's stand-off
    — the witnessed plate delimits nothing, it witnesses depth.  Where no
    plate lies under part of the region the floor still takes ``floor_z``:
    a rim-level island inside a pit is terrain standing inside the
    object's walls, which is what the owner read at OTHH (the cut in two
    pieces either side of one Dewatering object, the middle 4,330 − 879 m2
    left at grade as a V-funnel 5.6 m above the floor).

    ``carved`` are the faces that govern their own ground and must keep it
    — the §24 (5) ramp corridors, whose terrain follows the deck per
    station — so they come OUT of the region floor rather than being
    buried under a second face at the one depth."""
    inner = rim.buffer(-standoff, **_MITRE) if standoff > 1e-9 else rim
    if inner.is_empty:
        return []
    if carved:
        inner = inner.difference(unary_union(carved))
    out: list[Polygon] = []
    for part in _parts(inner):
        g = _snap_face(part, grid)
        if g is None:
            continue
        # the snap may round a vertex back out (``_floors_inside``' law):
        # keep only what still clears the rim, one more grid step in when
        # it does not
        if not (rim.contains(g) and g.distance(rim.exterior) >= standoff - 1e-6):
            g2 = _snap_face(part.buffer(-grid, **_MITRE), grid)
            if g2 is None or not rim.contains(g2):
                continue
            g = g2
        out.append(g)
    return sorted(out, key=lambda q: -q.area)


def shell_thickness_m(region: Polygon, plates, step_m: float = 1.0,
                      max_m: float | None = None, exclude=None) -> float:
    """A basin shell's plan WALL thickness: the smallest distance from the
    floor ``plates``' edges (sampled every ``step_m``) to the shells'
    at-grade footprint ``region``'s edge — the thinnest wall between
    floor and footprint (OTHH's drainage shells: a plate inset 0.75 m
    all round reads 0.75).  A plate reaching the footprint's edge reads
    0 (no wall to hide the rim in); thicker than ``max_m``
    (``tunnel.object.wall_face_max_thickness_m``: a plan solid past it
    is a slab, not a wall) is capped there — an area ratio is NOT a
    thickness (LEMD basin:3, a 366 m² plate in a 452 m² region, read
    29 m by one).  Plate-edge samples inside ``exclude`` are not wall
    samples (RULINGS 2026-09-08b/c: a door well's sill line, where the
    plate leaves the well into the building)."""
    if plates.is_empty:
        return 0.0
    ext = region.exterior
    best = None
    for part in _parts(plates):
        ring = part.exterior
        n = max(4, int(math.ceil(ring.length / max(step_m, 1e-6))))
        for i in range(n):
            q = ring.interpolate(ring.length * i / n)
            if exclude is not None and exclude.intersects(q):
                continue
            d = float(ext.distance(q))
            best = d if best is None else min(best, d)
    t = best or 0.0
    return min(t, max_m) if max_m is not None else t


def _outer(w) -> Polygon:
    """THE REGION IS BUILT FROM THE SHELL'S OUTER PLAN FOOTPRINT (owner
    RULINGS 2026-09-13g, spec §24 (4)) — the wall face at the TOP of the
    walls, not ``FloorWitness.below``'s clip at the DEM under the
    component's centroid.  ``below`` is the ADMISSION's evidence (rule 1
    reads a floor under the ground); as the REGION it made the cut follow
    a contour of the terrain through the middle of the shell: at LEMD's
    T4S pit 11 of the 59 ring nodes stood 6–15 m from any wall, and the
    modelled road ramp — the shell's own deck, rising through that one
    plane — was cut out of the region as a 52 x 11 m notch that a
    building pad then filled 2.92 m over the ramp.  A record made before
    §24 (4) (a fixture) keeps ``below``."""
    return w.below if getattr(w, "outer", None) is None else w.outer


def _rim(region: Polygon, inset: float, grid: float) -> Polygon | None:
    """THE CUT HUGS THE WALL (owner RULINGS 2026-09-11t, spec §24 (1)):
    the at-grade rim is ``region`` — the shells' own footprint below the
    ground, i.e. THE OBJECT'S OUTER WALL FACE AT ITS TOP — set INWARD by
    ``inset`` (``cutout.rim_inset_fraction`` × the measured shell
    thickness, 2026-09-08a: the terrain drop happens inside the wall,
    hidden by the object) and snapped to the identity grid.  Nothing
    else: no buffer, no widening.

    WHAT WAS HERE BEFORE, AND WHY IT WENT (the owed 08e deviation (2)):
    the rim was widened OUTWARD by whole grid steps — every station, not
    the offending ones — until it contained every floor and cleared it by
    the stand-off.  A shell whose plate reaches its own footprint edge
    (LEMD's T4S pit reads shell 0.00 m thick) needs the floor's own
    ``floor_overlap_m`` plus the stand-off of room that the wall does not
    have, so the loop ran to k = 4 and put all 56 rim vertices 1.75–4.12 m
    (median 2.06) OUTSIDE the wall face — the owner's "gap between the
    outer edge and the apron" on 1.0.315, a shelf of pavement standing
    over nothing.  The stand-off is now taken from the FLOOR instead
    (:func:`_floors_inside`), at the region's ONE derivation site rather
    than by pushing the cut away from the object it is cutting for.
    ``None`` when the ring does not survive the grid."""
    return _snap_ring(region.buffer(-inset, **_MITRE) if inset > 1e-9 else region, grid)


def _floors_inside(floors: list[Polygon], rim: Polygon, standoff: float, grid: float
                   ) -> list[Polygon]:
    """The floor faces TRIMMED to stand ``standoff`` inside ``rim`` (§24
    (1)): the void the mesh makes the wall in is taken out of the FLOOR,
    never out of the cut's outline.  A floor already clear is returned
    unchanged (the identity case, and every basin whose shell has real
    thickness); one that survives the trim with no area at all is
    dropped, and an empty return refuses the basin exactly as a rim that
    could not clear used to."""
    inner = rim.buffer(-standoff, **_MITRE)
    if inner.is_empty:
        return []
    out: list[Polygon] = []
    for f in floors:
        if rim.contains(f) and f.distance(rim.exterior) >= standoff - 1e-6:
            out.append(f)
            continue
        for part in _parts(f.intersection(inner)):
            g = _snap_ring(part, grid)
            if g is None or g.area < grid * grid:
                continue
            # the snap may round a vertex back out: keep only what still
            # clears, taking one more grid step in when it does not
            if not (rim.contains(g) and g.distance(rim.exterior) >= standoff - 1e-6):
                g2 = _snap_ring(part.buffer(-grid, **_MITRE), grid)
                if g2 is None or g2.area < grid * grid or not rim.contains(g2):
                    continue
                g = g2
            out.append(g)
    return sorted(out, key=lambda q: -q.area)
