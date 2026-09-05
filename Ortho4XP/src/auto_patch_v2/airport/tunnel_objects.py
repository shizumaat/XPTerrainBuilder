"""TUNNEL WALL OBJECTS AS THE TUNNEL AUTHORITY (RULINGS 2026-09-05k-1;
spec ``docs/specs/auto-patch-v2/tunnel-wall-objects-spec.md``; law
``structures.toml [tunnel.object]``).

The owner's reading, confirmed in the sim (OTHH 1.0.284): the pack's
tunnel wall objects define a tunnel's SHAPE, LENGTH and DEPTH wherever
one stands — the placement SEAT is the tunnel floor, the object's top
PLATE is the wall crest, its plan HULL the footprint; OSM bores stand
only where no object does.

THE SIGNATURE (§3.1), per resource, over the geometry the basin pass
already parsed (``obj8.ResourceCache`` — never a second parse):

* a WALL SKIRT: genuine solids (thickness-gated, the basin gate) reach
  ``skirt_min_depth_m`` or more BELOW the seat plane (authored y = 0);
* a CREST PLATE: near-horizontal solid faces (``plate_normal_y_min``) at
  or above the seat, binned ``plate_bin_m`` coarse — the largest-area bin
  is the crest plane; it carries ``plate_min_area_m2`` and stands
  ``plate_min_height_m`` above the seat (a kerb is not a wall);
* NO FLOOR PLATE below the seat (``floor_plate_max_m2``): an object the
  basin pass witnessed a floor in, or whose near-horizontal faces below
  the seat run along the axis, is a basin — ``planar/basins.py`` owns
  it, never this reader; and NO ROOF: near-horizontal faces running
  along the axis at any height worth a plate (``plate_min_area_m2``) make
  it a building or a deck (measured OTHH: the skirt + plate + hull
  signature alone admitted a terminal, a duty-free hall and three
  terminal road slabs);
* per PLACEMENT, the SEAT lies ``basin.admission_depth_m`` or more under
  the ground at the placement — a tunnel floor is below grade; a wall
  seated at grade is a fence (OTHH: a fuel-farm wall, a kerb wall).

THE FOOTPRINT (§3.2): the plan hull of the genuine solid vertices, its
minimum rotated rectangle (``model.frame.rotated_rectangle``) — length
and width are the rectangle's sides, the corridor AXIS its long axis —
placed by ``obj8.placement_affine``.  An END is OPEN when the solids
within ``end_cap_open_m`` of its end line leave the end line's CENTRE
uncovered (two side slabs, no wall across: a mouth); CLOSED when a solid
spans it (a dead wall).  Two hulls whose open ends face within
``merge_gap_m`` are ONE corridor.

THE DATUMS (§3.3): ``floor = seat`` (``OBJECT_MSL`` absolute; ``OBJECT``
/ ``OBJECT_AGL`` = the production DEM at the placement + the elevation);
``crest = floor + plate height``; depth = the plate height.

Every number is a law-table value; nothing here reads the environment.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import os
import time
import typing as _t

import numpy as np
from shapely import affinity as _affinity
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union

from ..law import Law
from ..model.airport import Airport
from ..model.frame import XY, rotated_rectangle
from . import obj8 as _obj8

__all__ = ["WallSignature", "Corridor", "TunnelObjectStats", "signature",
           "read_corridors", "ID_PREFIX"]

ID_PREFIX = "tunnel-object"


@_dc.dataclass(frozen=True)
class WallSignature:
    """One resource's reading in the AUTHORED frame (x east, z south,
    y up; the seat plane is y = 0): the crest plate height and area,
    the skirt depth, the plan rectangle and its long axis' end-line
    centres ``a`` / ``b``, and whether each end is open."""

    path: str
    plate_y: float
    plate_area_m2: float
    skirt_depth_m: float
    rect: tuple[XY, XY, XY, XY]
    length_m: float
    width_m: float
    a: XY
    b: XY
    open_a: bool
    open_b: bool


@_dc.dataclass(frozen=True)
class Corridor:
    """One tunnel corridor in the AIRPORT frame: the hull rectangle, its
    end-line centres ``a`` / ``b`` (open or closed each), the floor and
    crest.  ``objects`` are the placement ids it is read from (two after
    a merge)."""

    id: str
    resource: str
    objects: tuple[str, ...]
    rect: Polygon
    a: XY
    b: XY
    open_a: bool
    open_b: bool
    length_m: float
    width_m: float
    floor_z: float
    crest_z: float
    depth_m: float
    notes: tuple[str, ...] = ()

    @property
    def ends(self) -> str:
        return f"{'open' if self.open_a else 'closed'}/{'open' if self.open_b else 'closed'}"


@_dc.dataclass
class TunnelObjectStats:
    """What the reader saw, admitted and refused (every refusal names
    its reason and the resource)."""

    placements: int = 0
    resources: int = 0
    signatures: int = 0
    corridors: int = 0
    merged: int = 0
    refused: list[str] = _dc.field(default_factory=list)
    signature_s: float = 0.0


# ── the signature ────────────────────────────────────────────────────────

def _faces(v: np.ndarray, tris: np.ndarray):
    """``(|n_y|, plan area, centroid y, max y)`` per triangle."""
    p0, p1, p2 = v[tris[:, 0]], v[tris[:, 1]], v[tris[:, 2]]
    nrm = np.cross(p1 - p0, p2 - p0)
    ln = np.linalg.norm(nrm, axis=1)
    ok = ln > 1e-12
    ny = np.zeros(tris.shape[0])
    ny[ok] = np.abs(nrm[ok, 1] / ln[ok])
    area = 0.5 * np.abs((p1[:, 0] - p0[:, 0]) * (p2[:, 2] - p0[:, 2])
                        - (p2[:, 0] - p0[:, 0]) * (p1[:, 2] - p0[:, 2]))
    cy = (p0[:, 1] + p1[:, 1] + p2[:, 1]) / 3.0
    ymax = np.maximum(np.maximum(p0[:, 1], p1[:, 1]), p2[:, 1])
    return ny, area, cy, ymax


def _rect_axis(poly: Polygon) -> tuple[tuple[XY, XY, XY, XY], float, float, XY, XY] | None:
    """``(corners, length, width, a, b)`` of the minimum rotated
    rectangle: ``a`` / ``b`` the centres of the two SHORT sides (the
    end lines), ``a`` canonicalised on +x (tie on +z)."""
    rect = rotated_rectangle(poly)
    if rect.geom_type != "Polygon":
        return None
    c = list(rect.exterior.coords)[:4]
    if len(c) < 4:
        return None
    edges = [(c[i], c[(i + 1) % 4]) for i in range(4)]
    lens = [math.hypot(q[0] - p[0], q[1] - p[1]) for p, q in edges]
    li = max(range(4), key=lambda i: lens[i])
    length, width = lens[li], min(lens)
    if length <= 0.0:
        return None
    # the short sides are the two edges NOT parallel to the long one
    shorts = [edges[(li + 1) % 4], edges[(li + 3) % 4]]
    mids = [((p[0] + q[0]) / 2.0, (p[1] + q[1]) / 2.0) for p, q in shorts]
    a, b = mids
    if (b[0], b[1]) < (a[0], a[1]):
        a, b = b, a
    corners = tuple((float(x), float(z)) for x, z in c)
    return corners, float(length), float(width), (float(a[0]), float(a[1])), \
        (float(b[0]), float(b[1]))       # type: ignore[return-value]


def _end_open(v: np.ndarray, tris: np.ndarray, a: XY, b: XY, width: float,
              reach: float, at_a: bool) -> bool:
    """§3.2: the end at ``a`` (or ``b``) is OPEN when the solid faces
    within ``reach`` of its end line, projected across the corridor,
    leave the end line's centre uncovered."""
    L = math.hypot(b[0] - a[0], b[1] - a[1]) or 1.0
    ux, uz = (b[0] - a[0]) / L, (b[1] - a[1]) / L
    s0, s1 = (0.0, reach) if at_a else (L - reach, L)
    cover: list[tuple[float, float]] = []
    for t in tris.tolist():
        pts = [((v[i][0] - a[0]) * ux + (v[i][2] - a[1]) * uz,
                -(v[i][0] - a[0]) * uz + (v[i][2] - a[1]) * ux) for i in t]
        if max(p[0] for p in pts) < s0 or min(p[0] for p in pts) > s1:
            continue
        # the face's transverse extent inside the end band: clip the
        # triangle's plan to s in [s0, s1] (a vertical face is a line)
        band = Polygon([(s0, -width), (s1, -width), (s1, width), (s0, width)])
        tri = Polygon(pts)
        geom = tri if tri.area > 1e-9 else LineString(pts + [pts[0]])
        x = geom.intersection(band)
        if x.is_empty:
            continue
        cover.append((float(x.bounds[1]), float(x.bounds[3])))
    # ``a`` / ``b`` are the end lines' CENTRES, so the axis is the
    # rectangle's centre line and the centre's transverse coordinate is 0
    return not any(lo - 1e-9 <= 0.0 <= hi + 1e-9 for lo, hi in cover)


def _axis_crossing_area(v: np.ndarray, tris: np.ndarray, area: np.ndarray, a: XY, b: XY,
                        wall_m: float) -> float:
    """The plan area of the faces whose plan RUNS ALONG the axis segment
    ``a``–``b`` (authored x, z) for more than ``wall_m``: a floor does,
    an end wall's underside (a slab ``end_cap_open_m`` thick at most)
    does not."""
    if tris.shape[0] == 0:
        return 0.0
    axis = LineString([a, b])
    total = 0.0
    for t, ar in zip(tris.tolist(), area.tolist()):
        pts = [(float(v[i][0]), float(v[i][2])) for i in t]
        tri = Polygon(pts)
        if tri.area > 1e-9 and tri.intersection(axis).length > wall_m:
            total += ar
    return float(total)


def signature(geom: _obj8.ObjGeometry, genuine: _t.Sequence[_obj8.Component], law: Law
              ) -> WallSignature | str:
    """The resource's wall signature, or the REASON it is not a tunnel
    wall object (a string; every refusal names its numbers)."""
    ob = law.tables.structures.tunnel.object
    if not genuine:
        return "no genuine solid component"
    tris = np.concatenate([c.tris for c in genuine])
    v = geom.vertices
    ny, area, cy, ymax = _faces(v, tris)
    skirt = -min(c.min_y for c in genuine)
    if skirt < ob.skirt_min_depth_m:
        return (f"no wall skirt: genuine solids reach only {skirt:.2f} m under the seat "
                f"(< skirt_min_depth_m {ob.skirt_min_depth_m})")
    horiz = ny >= ob.plate_normal_y_min
    pts = v[np.unique(tris.reshape(-1))]
    hull = Polygon([(float(x), float(z)) for x, z in zip(pts[:, 0], pts[:, 2])]).convex_hull
    if hull.geom_type != "Polygon":
        return "the solids' plan hull is degenerate (a line)"
    ra = _rect_axis(hull)
    if ra is None:
        return "the solids' plan hull has no rectangle"
    corners, length, width, a, b = ra
    if length < ob.hull_min_length_m:
        return (f"a stub: the hull's long side is {length:.1f} m "
                f"(< hull_min_length_m {ob.hull_min_length_m})")
    above = horiz & (cy >= 0.0)
    if not above.any():
        return "no crest plate: no near-horizontal solid face at or above the seat"
    bins: dict[int, float] = {}
    for y, ar in zip(cy[above].tolist(), area[above].tolist()):
        k = int(math.floor(y / ob.plate_bin_m))
        bins[k] = bins.get(k, 0.0) + ar
    best = max(bins, key=lambda k: bins[k])
    plate_area = bins[best]
    in_bin = above & (np.floor(cy / ob.plate_bin_m).astype(int) == best)
    plate_y = float(ymax[in_bin].max())
    if plate_area < ob.plate_min_area_m2:
        return (f"not a wall: crest plate {plate_area:.0f} m2 at {plate_y:.2f} m "
                f"(< plate_min_area_m2 {ob.plate_min_area_m2:.0f})")
    if plate_y < ob.plate_min_height_m:
        return (f"a kerb, not a tunnel wall: crest plate at {plate_y:.2f} m above the seat "
                f"(< plate_min_height_m {ob.plate_min_height_m})")
    # NO FLOOR PLATE (``floor_plate_max_m2``): a near-horizontal face
    # below the seat that runs ALONG the corridor's axis is a floor (a
    # slab's own underside at the flank never reaches the centre; an end
    # wall's crosses it only over its thickness)
    below = horiz & (ymax < 0.0)
    floor_area = _axis_crossing_area(v, tris[below], area[below], a, b, ob.end_cap_open_m)
    if floor_area > ob.floor_plate_max_m2:
        return (f"a floor plate below the seat ({floor_area:.0f} m2 along the axis > "
                f"floor_plate_max_m2 {ob.floor_plate_max_m2:.0f}): a basin, basins.py owns it")
    # ...and OPEN ALONG ITS AXIS at every height: a near-horizontal face
    # running along the axis above the seat is a roof or a deck — a
    # building or a road slab, whose reader is its own (measured OTHH:
    # the spec's skirt + plate + hull signature alone admitted the
    # Emiri terminal, a fuel building and three terminal road slabs)
    roof_area = _axis_crossing_area(v, tris[horiz], area[horiz], a, b, ob.end_cap_open_m)
    if roof_area >= ob.plate_min_area_m2:
        return (f"roofed along its axis ({roof_area:.0f} m2 of near-horizontal faces run "
                f"along the corridor axis, a plate's worth: >= plate_min_area_m2 "
                f"{ob.plate_min_area_m2:.0f}): a building or a deck, not a wall skirt")
    open_a = _end_open(v, tris, a, b, width, ob.end_cap_open_m, True)
    open_b = _end_open(v, tris, a, b, width, ob.end_cap_open_m, False)
    return WallSignature(geom.path, plate_y, float(plate_area), float(skirt), corners,
                         length, width, a, b, open_a, open_b)


# ── placements → corridors ───────────────────────────────────────────────

def _seat(o: _obj8.PlacedObject, msl: _t.Mapping[str, float]) -> float:
    """§3.3 ``floor_datum = "seat"``: MSL absolute, else DEM(placement)
    + the AGL elevation (``PlacedObject.agl_m`` is 0 for a plain
    ``OBJECT``)."""
    if o.kind == "OBJECT_MSL":
        return float(msl.get(o.id, o.anchor_z))
    return float(o.anchor_z + o.agl_m)


def _place(sig: WallSignature, o: _obj8.PlacedObject, seat: float, k: int) -> Corridor:
    mat = _obj8.placement_affine(o.xy, o.heading_deg)
    rect = _affinity.affine_transform(Polygon(sig.rect), mat)
    pa = _affinity.affine_transform(Point(sig.a), mat)
    pb = _affinity.affine_transform(Point(sig.b), mat)
    a, b = (float(pa.x), float(pa.y)), (float(pb.x), float(pb.y))
    name = os.path.basename(o.path)
    return Corridor(f"{ID_PREFIX}:{name}@{k}", o.path, (o.id,), rect, a, b, sig.open_a,
                    sig.open_b, sig.length_m, sig.width_m, seat, seat + sig.plate_y,
                    sig.plate_y)


def _merge(cs: list[Corridor], law: Law, stats: TunnelObjectStats) -> list[Corridor]:
    """§3.2: two hulls whose OPEN ends face within ``merge_gap_m`` are one
    corridor (the far ends stay; the hull is the union's rectangle);
    floors must agree within the materiality floor."""
    gap = law.tables.structures.tunnel.object.merge_gap_m
    tol = law.tables.emit.materiality.elevation_m
    cs = list(cs)
    changed = True
    while changed:
        changed = False
        for i in range(len(cs)):
            for j in range(i + 1, len(cs)):
                ci, cj = cs[i], cs[j]
                ends_i = [(ci.a, ci.open_a, "a"), (ci.b, ci.open_b, "b")]
                ends_j = [(cj.a, cj.open_a, "a"), (cj.b, cj.open_b, "b")]
                pair = None
                for pi, oi, ki in ends_i:
                    for pj, oj, kj in ends_j:
                        if oi and oj and math.hypot(pi[0] - pj[0], pi[1] - pj[1]) <= gap:
                            pair = (ki, kj)
                if pair is None:
                    continue
                if abs(ci.floor_z - cj.floor_z) > tol:
                    stats.refused.append(
                        f"{ci.id} + {cj.id}: open ends meet within merge_gap_m but the floors "
                        f"differ ({ci.floor_z:.2f} vs {cj.floor_z:.2f}); kept apart")
                    continue
                ra = _rect_axis(unary_union([ci.rect, cj.rect]).convex_hull)
                if ra is None:
                    continue
                corners, length, width, a, b = ra
                far_i = (ci.b, ci.open_b) if pair[0] == "a" else (ci.a, ci.open_a)
                far_j = (cj.b, cj.open_b) if pair[1] == "a" else (cj.a, cj.open_a)
                # the far ends, in the merged rectangle's a/b order
                ends = sorted([far_i, far_j], key=lambda e: math.hypot(e[0][0] - a[0], e[0][1] - a[1]))
                merged = Corridor(ci.id, ci.resource, ci.objects + cj.objects, Polygon(corners),
                                  a, b, ends[0][1], ends[1][1], length, width, ci.floor_z,
                                  ci.crest_z, ci.depth_m,
                                  ci.notes + (f"merged with {cj.id} at the open ends "
                                              f"(merge_gap_m {gap})",))
                cs = [c for n, c in enumerate(cs) if n not in (i, j)] + [merged]
                stats.merged += 1
                changed = True
                break
            if changed:
                break
    return cs


def read_corridors(airport: Airport, objects: _t.Sequence[_obj8.PlacedObject],
                   cache: _obj8.ResourceCache, law: Law
                   ) -> tuple[list[Corridor], TunnelObjectStats]:
    """Every tunnel corridor the pack's wall objects state, in the
    airport frame, merged; the stats name every refusal by resource."""
    t0 = time.perf_counter()
    stats = TunnelObjectStats()
    msl = {o.id: o.y_offset_m for o in airport.dsf_objects if o.kind == "OBJECT_MSL"}
    admission = law.tables.structures.basin.admission_depth_m
    sigs: dict[str, WallSignature | str] = {}
    counts: dict[str, int] = {}
    out: list[Corridor] = []
    k_by_res: dict[str, int] = {}
    for o in objects:
        if o.resolved is None or _obj8.is_stock_library_resource(o.path):
            continue
        stats.placements += 1
        counts[o.path] = counts.get(o.path, 0) + 1
        if o.witnesses:
            sigs.setdefault(o.path, "the basin pass witnessed a floor in it (basins.py owns it)")
            continue
        if o.path not in sigs:
            stats.resources += 1
            g = cache.geometry(o.resolved)
            sigs[o.path] = signature(g, cache.genuine(o.resolved), law) if g is not None \
                else "unreadable OBJ8"
        sig = sigs[o.path]
        if isinstance(sig, str):
            continue
        seat = _seat(o, msl)
        # THE SEAT IS BELOW GRADE (the basin family's admission depth): a
        # tunnel floor lies under the ground it is cut into; a wall
        # object seated AT grade is a fence or a compound wall (measured
        # OTHH: a fuel-farm wall and a terminal kerb wall carried the
        # skirt + plate signature with their seats on the DEM)
        if seat > o.anchor_z - admission:
            stats.refused.append(f"{o.id} {os.path.basename(o.path)}: seat {seat:.2f} is not "
                                 f"{admission:.1f} m (basin.admission_depth_m) under the ground "
                                 f"at the placement ({o.anchor_z:.2f}) — a wall at grade, not a "
                                 f"tunnel floor")
            continue
        k = k_by_res.get(o.path, 0)
        k_by_res[o.path] = k + 1
        out.append(_place(sig, o, seat, k))
    stats.signatures = sum(1 for s in sigs.values() if not isinstance(s, str))
    for path, sig in sigs.items():
        if isinstance(sig, str) and not sig.startswith("no wall skirt") \
                and not sig.startswith("no genuine") and not sig.startswith("no crest plate"):
            # only the NEAR MISSES are worth a line: a building with no
            # skirt or no plate is every other object in the pack
            stats.refused.append(f"{os.path.basename(path)} x{counts[path]}: {sig}")
    out = _merge(out, law, stats)
    out.sort(key=lambda c: c.id)
    stats.corridors = len(out)
    stats.signature_s = time.perf_counter() - t0
    return out, stats
