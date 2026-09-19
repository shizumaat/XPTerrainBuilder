"""TUNNEL WALL OBJECTS AS THE TUNNEL AUTHORITY (RULINGS 2026-09-05k-1;
round 2 2026-09-05n; specs ``docs/specs/auto-patch-v2/tunnel-wall-
objects-spec.md`` §3.1 and ``…-round2-spec.md``; law ``structures.toml
[tunnel.object]``).

The owner's five laws (05n), all of them read here or in
``planar/object_corridor.py``: (1) the ramp's MOUTH is at the full depth
of the wall object and the other end reaches GROUND at the end of the
wall — or beyond where ``ramp_max_grade`` needs the length; (2) the
trench never extends beyond the outside of the walls and follows their
CURVES; (3) an OSM tunnel ramp is still built wherever OSM says there is
one, objects or not (precedence PER MOUTH); (4) the top of the wall
object is FLUSH with the ground (the object is re-seated to it).

THE SIGNATURE (round-1 §3.1), per resource, over the geometry the basin
pass already parsed (``obj8.ResourceCache`` — never a second parse): a
WALL SKIRT (genuine solids ``skirt_min_depth_m`` or more below the seat
plane), a CREST PLATE (near-horizontal faces at the largest-area
``plate_bin_m`` bin at or above the seat, ``plate_min_area_m2``,
``plate_min_height_m`` above the seat), NO FLOOR PLATE below the seat
and NO ROOF along the axis, and per placement a seat
``basin.admission_depth_m`` or more under the ground.  THE EDGE WALL
(RULINGS 2026-09-06c (2) / 06f): a crest under ``edge_wall_max_plate_m``
— the TOP BAND wherever it lies against the seat (LEMD's Bridge4.obj:
y −2.88 … −0.86, wholly below its seat; the seat is the author's
handle, 05n-4 re-seats the crest flush at grade) — over a skirt of
``edge_wall_min_skirt_m`` below that crest gives the ramp its PLAN; the
depth is the bore law's (``tunnel.bore_datum_m`` at a BORE mouth).

THE WALLS (round 2 §3.1; ``tunnel_walls.py``): the crest plate's plan
union IS the walls' footprint — a U / an O / two bands (measured OTHH:
one welded component per object, the plate ring the only thin band per
wall) — read into the two side walls' inner faces, the end walls and
the free ends; the corridor AXIS is the midline between the inner
faces; the wall band is each wall's own footprint.  NO rectangle.

THE ENDS (§3.2, ``mouth_end = "bore"``): the MOUTH is the end an OSM
tunnel way continues into — a bore END standing inside the corridor
nearer that end, or the bore LINE crossing that end's line; else the
end facing the other placement of the same resource; else the closed
end.  Two bore ends (a box on the bore: OTHH ``tunnel west 1``) are two
mouths and the trench is FLAT at the mouth depth.

THE DATUMS (RULINGS 2026-09-08l / 08o, ``mouth_depth = "floor_slab"``):
the trench depth is the object's FLOOR SLAB when it carries one (a near-
horizontal plate below the crest running along the axis, ``plate_min_
area_m2``: depth = crest − slab), else ``tunnel.bore_datum_m`` for EVERY
mouth kind (bore / closed / family) — never the crest's height above the
ANCHOR (``plate_y`` is the author's origin handle: OTHH's two mouths of
ONE bore read 5.0 and 10.0 m by it, both crests +2 m over ground, both
skirts to −18 m).  ``plate_y`` stays the crest for the SEAT (05n-4).  A
bore END within ``bore_end_tolerance_m`` of the plate makes the object
that bore's mouth (the OSM mouth pairs with it, ``bore_ways``); a
closed-end fallback with no mapped road through the trench is refused by
name.  Floor at the mouth = ground(mouth) − depth; the ramp climbs inside
the walls (``planar/object_corridor.py``).

Every number is a law-table value; nothing here reads the environment.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import os
import time
import typing as _t

import numpy as np
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union
from shapely.strtree import STRtree

from ..law import Law
from ..model.airport import Airport
from ..model.frame import XY, rotated_rectangle
from . import frame_entry as _fe
from . import obj8 as _obj8
from . import object_cut as _object_cut
from .deck_signature import is_tunnel_way
from .tunnel_walls import Station, WallLines, midline, read_wall_lines, stations_along

__all__ = ["WallSignature", "Corridor", "TunnelObjectStats", "signature",
           "read_corridors", "shell_corridor", "ID_PREFIX"]

ID_PREFIX = "tunnel-object"
#: Facing test for the family rule: the other placement lies within this
#: half-angle of the end's outward direction.
_FACING_COS = math.cos(math.radians(45.0))


@_dc.dataclass(frozen=True)
class WallSignature:
    """One resource's reading in the AUTHORED frame (x east, z south,
    y up; the seat plane is y = 0): the crest plate height and area, the
    skirt depth, the plate's plan polygon (the walls' footprint) and the
    plan rectangle's sides (a reading, never a footprint)."""

    path: str
    plate_y: float
    plate_area_m2: float
    skirt_depth_m: float
    plate: Polygon
    length_m: float
    width_m: float
    #: RULINGS 2026-09-06c (2): the crest stands under ``edge_wall_max_
    #: plate_m`` — an EDGE WALL: the plan is the walls', the depth the
    #: bore law's (``tunnel.bore_datum_m`` at the mouth).
    edge_wall: bool = False
    #: RULINGS 2026-09-08l: the FLOOR SLAB's top (authored y, below the
    #: crest) when the model carries one along its axis — the depth is
    #: ``plate_y − floor_y``; ``None`` for a skirt (the bore law's depth).
    floor_y: float | None = None


@_dc.dataclass(frozen=True)
class Corridor:
    """One tunnel corridor in the AIRPORT frame (round 2).  ``axis`` runs
    from the MOUTH (s = 0; ``cutout.floor_overlap_m`` OUTSIDE a closed
    end's inner face — the floor overlaps the end wall's footprint,
    2026-09-06b) to the far end; ``stations`` give the inner faces left / right
    of it and the walls' thickness by station; ``trench`` is the region
    between the inner faces, ``walls`` the walls' plan footprint,
    ``footprint`` their union (what a bore mouth is INSIDE of)."""

    id: str
    resource: str
    objects: tuple[str, ...]
    plate_y: float
    axis: tuple[XY, ...]
    stations: tuple[Station, ...]
    length_m: float
    width_m: float
    mouth_closed: bool
    far_closed: bool
    mouth_thickness_m: float
    far_thickness_m: float
    mouth_kind: str
    flat: bool
    mouth_dem_z: float
    floor_z: float
    walls: Polygon
    trench: Polygon
    footprint: Polygon
    anchor_xy: XY
    anchor_dem_z: float
    agl_m: float
    notes: tuple[str, ...] = ()

    def stations_inner(self) -> "tuple[list[XY], list[XY]]":
        """The corridor's two INNER FACES as polylines in the airport
        frame, reconstructed from the axis and its stations — the line
        §33 (6) C2' asks an emitted ring to follow (the object's own wall
        curve, never a chord between distant stations)."""
        import math as _m
        ln = LineString(self.axis)
        left: list[XY] = []
        right: list[XY] = []
        L = ln.length
        for st in self.stations:
            s = min(max(st.s, 0.0), L)
            p = ln.interpolate(s)
            a = ln.interpolate(max(0.0, s - 1.0))
            b = ln.interpolate(min(L, s + 1.0))
            ux, uy = b.x - a.x, b.y - a.y
            m = _m.hypot(ux, uy) or 1.0
            nx, ny = -uy / m, ux / m
            left.append((p.x + nx * st.half_l, p.y + ny * st.half_l))
            right.append((p.x - nx * st.half_r, p.y - ny * st.half_r))
        return left, right

    @property
    def ends(self) -> str:
        a = "closed" if self.mouth_closed else "open"
        b = "closed" if self.far_closed else "open"
        return f"{a}/{b}"

    @property
    def ground_kind(self) -> str:
        return "bore" if self.flat else ("closed" if self.far_closed else "open")

    #: The trench DEPTH at the mouth (RULINGS 2026-09-08l/08o, ``mouth_depth
    #: = "floor_slab"``): crest − floor slab when the model carries one,
    #: else ``tunnel.bore_datum_m`` — ``plate_y`` stays the crest's height
    #: for the seat (crest flush at grade, 05n-4).
    depth_m: float = 0.0
    edge_wall: bool = False
    #: The floor slab's authored y under the crest (``None`` = a skirt).
    floor_y: float | None = None
    #: The OSM tunnel way ids whose END stands at a mouth of this corridor
    #: (08o: those mouths PAIR with the corridor in ``planar/structures``).
    bore_ways: tuple[int, ...] = ()


@_dc.dataclass
class TunnelObjectStats:
    """What the reader saw, admitted and refused (every refusal names
    its reason and the resource)."""

    placements: int = 0
    resources: int = 0
    signatures: int = 0
    corridors: int = 0
    merged: int = 0
    #: spec §33 (1): resources the 06f cheap gate skipped before the
    #: pre-screen (no skirt under the seat, no mapped bore in the plan) —
    #: never READ, so never a verdict: counted, never enumerated.
    not_screened: int = 0
    #: spec §33 (2): THIN-PLATE wall objects read (``airport/thin_plates``).
    plates: int = 0
    #: spec §33 (6) B: SHELL + flush hard cover object cuts admitted, and
    #: the placements they CLAIM out of the basin intake ("the shell is
    #: never a basin").
    shells: int = 0
    shell_claimed: tuple[str, ...] = ()
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


def _rect_axis(poly: Polygon) -> tuple[float, float, XY, XY] | None:
    """``(length, width, a, b)`` of the minimum rotated rectangle — a
    READING of the hull's sides for the stub gate and the roof / floor
    axis tests, never a footprint (05n-2)."""
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
    shorts = [edges[(li + 1) % 4], edges[(li + 3) % 4]]
    mids = [((p[0] + q[0]) / 2.0, (p[1] + q[1]) / 2.0) for p, q in shorts]
    a, b = mids
    return float(length), float(width), (float(a[0]), float(a[1])), (float(b[0]), float(b[1]))


def _axis_crossing_mask(v: np.ndarray, tris: np.ndarray, a: XY, b: XY, wall_m: float
                        ) -> np.ndarray:
    """Per triangle: its plan RUNS ALONG the axis segment ``a``–``b``
    (authored x, z) for more than ``wall_m`` — a floor does, an end
    wall's underside (a slab ``end_cap_open_m`` thick at most) does not."""
    out = np.zeros(tris.shape[0], dtype=bool)
    if tris.shape[0] == 0:
        return out
    axis = LineString([a, b])
    for k, t in enumerate(tris.tolist()):
        pts = [(float(v[i][0]), float(v[i][2])) for i in t]
        tri = Polygon(pts)
        if tri.area > 1e-9 and tri.intersection(axis).length > wall_m:
            out[k] = True
    return out


def _axis_crossing_area(v: np.ndarray, tris: np.ndarray, area: np.ndarray, a: XY, b: XY,
                        wall_m: float) -> float:
    """The plan area of the faces :func:`_axis_crossing_mask` selects."""
    if tris.shape[0] == 0:
        return 0.0
    return float(area[_axis_crossing_mask(v, tris, a, b, wall_m)].sum())


def _skirt_perimeter_fraction(v: np.ndarray, tris: np.ndarray, ny: np.ndarray,
                              plate, plate_y: float, need_m: float, ref_y: float,
                              ob) -> float:
    """THE WALL SIGNATURE (RULINGS 2026-09-09w (2)): the share of the crest
    plate's PERIMETER — every ring of every plate polygon, sampled every
    ``wall_sample_m`` — with a near-vertical solid face standing under it
    (within ``wall_face_max_thickness_m`` in plan, its top in the crest's
    band) that descends to ``ref_y − need_m``.  A tunnel wall's crest is
    the top of its walls, so its skirt stands under all of it; a terminal
    SLAB has a skirt under a corner at most — it is a roof."""
    vert = ny < ob.plate_normal_y_min
    vt = tris[vert]
    if vt.shape[0] == 0:
        return 0.0
    p = v[vt.reshape(-1)].reshape(-1, 3, 3)
    # only the faces hanging FROM the crest (a facade's top is its own
    # crest; a floor slab's walls stand above it, never under it)
    at_crest = p[:, :, 1].max(axis=1) >= plate_y - ob.plate_bin_m
    if not at_crest.any():
        return 0.0
    p = p[at_crest]
    y_low = p[:, :, 1].min(axis=1)
    deep = y_low <= ref_y - need_m
    if not deep.any():
        return 0.0
    p = p[deep]
    faces = [LineString([(float(q[0]), float(q[2])) for q in t] +
                        [(float(t[0][0]), float(t[0][2]))]) for t in p]
    tree = STRtree(faces)
    polys = list(plate.geoms) if plate.geom_type == "MultiPolygon" else [plate]
    rings = [r for pg in polys for r in [pg.exterior, *pg.interiors]]
    total = covered = 0
    for ring in rings:
        n = max(1, int(round(ring.length / ob.wall_sample_m)))
        for k in range(n):
            q = ring.interpolate(k * ring.length / n)
            total += 1
            if len(tree.query(q.buffer(ob.wall_face_max_thickness_m),
                              predicate="intersects")):
                covered += 1
    return covered / total if total else 0.0


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
    y_low = min(c.min_y for c in genuine)
    skirt = -y_low                        # a FULL wall's skirt: below the seat
    horiz = ny >= ob.plate_normal_y_min
    pts = v[np.unique(tris.reshape(-1))]
    hull = Polygon([(float(x), float(z)) for x, z in zip(pts[:, 0], pts[:, 2])]).convex_hull
    if hull.geom_type != "Polygon":
        return "the solids' plan hull is degenerate (a line)"
    ra = _rect_axis(hull)
    if ra is None:
        return "the solids' plan hull has no rectangle"
    length, width, a, b = ra
    if length < ob.hull_min_length_m:
        return (f"a stub: the hull's long side is {length:.1f} m "
                f"(< hull_min_length_m {ob.hull_min_length_m})")
    # THE CREST.  A FULL wall (skirt_min_depth_m of skirt below the seat:
    # the seat is its datum, the plate height its depth) reads the
    # largest-area bin of near-horizontal faces at or above the seat
    # (round 1).  With a shallower skirt the seat is the author's HANDLE,
    # not a datum (2026-09-06f: LEMD's Bridge4.obj is authored y 0 … 2.02
    # and was baked to −2.88 … −0.86 by v1): the crest is the TOP BAND
    # wherever it lies — the topmost bin holding plate_min_area_m2 of
    # near-horizontal faces — and the wall is an EDGE WALL when its skirt
    # below THAT crest reaches edge_wall_min_skirt_m.
    full_skirt = skirt >= ob.skirt_min_depth_m
    binned = np.floor(cy / ob.plate_bin_m).astype(int)
    above = horiz & (cy >= 0.0)
    bins: dict[int, float] = {}
    for k, ar in zip(binned[above].tolist(), area[above].tolist()):
        bins[k] = bins.get(k, 0.0) + ar
    best = max(bins, key=lambda k: bins[k]) if bins else None
    if full_skirt and best is not None and bins[best] >= ob.plate_min_area_m2:
        in_bin = above & (binned == best)
        plate_area = bins[best]
    else:
        all_bins: dict[int, float] = {}
        for k, ar in zip(binned[horiz].tolist(), area[horiz].tolist()):
            all_bins[k] = all_bins.get(k, 0.0) + ar
        tops = [k for k, ar in all_bins.items() if ar >= ob.plate_min_area_m2]
        if not tops:
            if best is None:
                return ("no crest plate: no near-horizontal solid face at or above the seat, "
                        f"none of plate_min_area_m2 {ob.plate_min_area_m2:.0f} below it")
            plate_y = float(ymax[above & (binned == best)].max())
            return (f"not a wall: crest plate {bins[best]:.0f} m2 at {plate_y:.2f} m "
                    f"(< plate_min_area_m2 {ob.plate_min_area_m2:.0f})")
        best = max(tops)
        in_bin = horiz & (binned == best)
        plate_area = all_bins[best]
    plate_y = float(ymax[in_bin].max())
    edge_wall = False
    if not full_skirt:
        edge_skirt = plate_y - y_low
        if edge_skirt < ob.edge_wall_min_skirt_m:
            return (f"no wall skirt: genuine solids reach only {skirt:.2f} m under the seat "
                    f"(< skirt_min_depth_m {ob.skirt_min_depth_m}) and {edge_skirt:.2f} m under "
                    f"the crest at {plate_y:+.2f} m (< edge_wall_min_skirt_m "
                    f"{ob.edge_wall_min_skirt_m})")
        edge_wall = True
    elif plate_y < ob.plate_min_height_m:
        # THE EDGE WALL over a full skirt (2026-09-06c (2)): a low crest
        # states the ramp's PLAN; the depth is the bore law's
        if plate_y < ob.edge_wall_max_plate_m:
            edge_wall = True
        else:
            return (f"a kerb, not a tunnel wall: crest plate at {plate_y:.2f} m above the "
                    f"seat (< plate_min_height_m {ob.plate_min_height_m}, not under "
                    f"edge_wall_max_plate_m {ob.edge_wall_max_plate_m})")
    # THE FLOOR SLAB (RULINGS 2026-09-08l, ``mouth_depth = "floor_slab"``):
    # near-horizontal faces below the crest's band that run ALONG the
    # corridor's axis, a plate's worth (plate_min_area_m2), are the
    # model's floor — its TOP (the largest-area bin's ceiling) states the
    # depth under the crest.  Less than a plate's worth is a skirt: the
    # bore law's depth.  (A floor the basin pass witnessed never reaches
    # this reader: ``read_corridors`` routes it to basins.py by witness.)
    below = horiz & (ymax < min(0.0, plate_y - ob.plate_bin_m))
    floor_y: float | None = None
    if below.any():
        b_idx = np.nonzero(below)[0]
        on_axis = b_idx[_axis_crossing_mask(v, tris[below], a, b, ob.end_cap_open_m)]
        if on_axis.size and float(area[on_axis].sum()) >= ob.plate_min_area_m2:
            fb: dict[int, float] = {}
            for k, ar in zip(binned[on_axis].tolist(), area[on_axis].tolist()):
                fb[k] = fb.get(k, 0.0) + ar
            fbest = max(fb, key=lambda k: fb[k])
            floor_y = float(ymax[on_axis[binned[on_axis] == fbest]].max())
    # ...and OPEN ALONG ITS AXIS above the floor: a near-horizontal face
    # running along the axis at or above the crest's band is a roof or a
    # deck (measured OTHH: the skirt + plate + hull signature alone
    # admitted the Emiri terminal, a fuel building and three terminal road
    # slabs); the floor slab below it is depth evidence, never a roof
    roof_sel = horiz & ~below
    roof_area = _axis_crossing_area(v, tris[roof_sel], area[roof_sel], a, b, ob.end_cap_open_m)
    if roof_area >= ob.plate_min_area_m2:
        return (f"roofed along its axis ({roof_area:.0f} m2 of near-horizontal faces run "
                f"along the corridor axis, a plate's worth: >= plate_min_area_m2 "
                f"{ob.plate_min_area_m2:.0f}): a building or a deck, not a wall skirt")
    # THE PLATE IN PLAN (round 2 §3.1): the walls' footprint
    faces = [Polygon([(float(v[i][0]), float(v[i][2])) for i in t])
             for t in tris[in_bin].tolist()]
    plate = _fe.union([f for f in faces if f.area > 1e-9], "tunnel_objects.crest").buffer(0)
    if plate.is_empty:
        return "the crest plate has no plan area"
    # A CREST NEEDS A WALL UNDER IT (RULINGS 2026-09-09w (2)): the very
    # skirt that admitted this reading — ``skirt_min_depth_m`` under the
    # SEAT for a full wall, ``edge_wall_min_skirt_m`` under the CREST for
    # a shallow-seat edge wall (06f: the seat is the author's handle
    # there) — must stand under at least ``skirt_perimeter_min_fraction``
    # of the plate's perimeter.  A slab at +9 m over a terminal floor has
    # its deep solids somewhere else in the file: it is a ROOF.
    need, ref = (ob.skirt_min_depth_m, 0.0) if full_skirt \
        else (ob.edge_wall_min_skirt_m, plate_y)
    frac = _skirt_perimeter_fraction(v, tris, ny, plate, plate_y, need, ref, ob)
    if frac < ob.skirt_perimeter_min_fraction:
        return (f"roof, not a crest: skirt under {frac:.0%} of the perimeter "
                f"(< skirt_perimeter_min_fraction "
                f"{ob.skirt_perimeter_min_fraction:.0%}; a wall face reaching "
                f"{need:.1f} m under {'the seat' if full_skirt else 'the crest'})")
    # skirt_depth_m: below the seat for a full-skirt wall (round 1, 06c's
    # edge wall included); below the CREST for a shallow-seat edge wall
    # (06f: the seat is no datum there)
    return WallSignature(geom.path, plate_y, float(plate_area),
                         float(plate_y - y_low if (edge_wall and not full_skirt) else skirt),
                         plate, length, width, edge_wall, floor_y)


# ── placements → corridors ───────────────────────────────────────────────

def _seat(o: _obj8.PlacedObject, msl: _t.Mapping[str, float]) -> float:
    """The rendered seat plane: MSL absolute, else DEM(placement) + the
    AGL elevation (``PlacedObject.agl_m`` is 0 for a plain ``OBJECT``)."""
    if o.kind == "OBJECT_MSL":
        return float(msl.get(o.id, o.anchor_z))
    return float(o.anchor_z + o.agl_m)


def _bore_near(o: _obj8.PlacedObject, cache: _obj8.ResourceCache, tree: STRtree | None,
               tol: float) -> bool:
    """A mapped tunnel way touches the placement's plan bounding box
    (``tol`` around) — the edge-wall candidate's cheap discriminator."""
    if tree is None:
        return False
    _vmin, _vmax, x0, x1, z0, z1 = cache.y_range(o.resolved)
    if x0 == math.inf or x1 == -math.inf:
        return False
    corners = [_obj8._to_frame(o.xy, o.heading_deg, x, z) for x in (x0, x1) for z in (z0, z1)]
    box = Polygon(corners).convex_hull.buffer(tol)
    return len(tree.query(box, predicate="intersects")) > 0


def _bore_ends_at(walls: WallLines, axis: list[XY], tunnel_ways, tol: float
                  ) -> tuple[list[int], list[int]]:
    """Per end ``(0, 1)``: the ids of the OSM tunnel ways whose mapped END
    stands inside the corridor ⊕ ``tol`` nearer that end (the bore dips
    under the ground there: OTHH's bores end 3–20 m inside the closed
    end, and 4.1–4.5 m OUTSIDE the deep object's plate — RULINGS
    2026-09-08o: ``tol`` = ``bore_end_tolerance_m``), or — for a bore
    with NO end inside, one passing through — whose LINE crosses that
    end's line (a box on the bore)."""
    # EVERY POLYGON BUILT FROM WALL BANDS IS REPAIRED FIRST (the LGAV
    # crash, 2026-09-15): the inner faces are AUTHORED polylines, and a
    # wall that crosses itself makes this ring self-intersecting — GEOS
    # then raises ``TopologyException: side location conflict`` inside
    # ``unary_union`` and the whole structure replay dies.
    inner = _object_cut.valid_polygon(
        Polygon(list(walls.inner_a) + list(reversed(walls.inner_b))))
    # §51 (4) row 15: the belt STAYS for the wall-BAND ring above (it is
    # BUILT from authored polylines, never placed, so Law A never sees
    # it — the LGAV crash); it is REMOVED for the plate, which entered
    # the frame through ``frame_entry.enter`` and is valid by Law A.
    plate = walls.plate
    parts = [g for g in (plate, inner) if g is not None]
    if not parts:
        return ([], [])
    region = _object_cut.valid_polygon(_fe.union(parts, "tunnel_objects.region"))
    if region is None:
        return ([], [])
    region = region.buffer(tol)
    ln = LineString(axis)
    out: tuple[list[int], list[int]] = ([], [])
    for w in tunnel_ways:
        line = LineString(w.points)
        inside = [e for e in (w.points[0], w.points[-1]) if region.contains(Point(e))]
        for e in inside:
            k = 0 if ln.project(Point(e)) < ln.length / 2.0 else 1
            if w.id not in out[k]:
                out[k].append(w.id)
        if inside:
            continue
        for k in (0, 1):
            a, b = walls.end_line(k)
            if line.intersects(LineString([a, b]).buffer(tol)) and w.id not in out[k]:
                out[k].append(w.id)
    return out


def _rotated_box(w: WallLines) -> WallLines:
    """The O read the other way round: the end walls become the side
    walls (``inner_a`` = the wall at end 0, from ``inner_b``'s start to
    ``inner_a``'s start; ``inner_b`` = the wall at end 1, in the same
    direction) and the side walls the end walls."""
    a = [w.inner_b[0], w.inner_a[0]]
    b = [w.inner_b[-1], w.inner_a[-1]]
    # the former side walls' thickness at their middles
    la, lb = LineString(w.inner_a), LineString(w.inner_b)
    pa, pb = la.interpolate(0.5, normalized=True), lb.interpolate(0.5, normalized=True)
    mid_ab = ((pa.x + pb.x) / 2.0, (pa.y + pb.y) / 2.0)
    from .tunnel_walls import _dir, _thickness_at
    ua = _dir(mid_ab, (pa.x, pa.y))
    ub = _dir(mid_ab, (pb.x, pb.y))
    ta = _thickness_at((pa.x, pa.y), ua, w.plate, 3.0 * max(w.thickness_m, 0.5))
    tb = _thickness_at((pb.x, pb.y), ub, w.plate, 3.0 * max(w.thickness_m, 0.5))
    return WallLines(w.plate, a, b, (True, True), (ta or w.thickness_m, tb or w.thickness_m),
                     w.thickness_m, "O")


def _faces_other(axis: list[XY], k: int, others: _t.Sequence[Polygon]) -> bool:
    """End ``k``'s outward direction points at another placement of the
    same resource (within ``_FACING_COS``)."""
    e = axis[0] if k == 0 else axis[-1]
    nxt = axis[1] if k == 0 else axis[-2]
    u = (e[0] - nxt[0], e[1] - nxt[1])
    L = math.hypot(*u) or 1.0
    u = (u[0] / L, u[1] / L)
    for p in others:
        c = p.centroid
        d = (c.x - e[0], c.y - e[1])
        D = math.hypot(*d) or 1.0
        if (d[0] * u[0] + d[1] * u[1]) / D >= _FACING_COS:
            return True
    return False


def _oriented(walls: WallLines, axis: list[XY], sts: list[Station], mouth: int,
              overlap: float, sample: float) -> tuple[list[XY], list[Station]]:
    """The axis and stations re-based with s = 0 at the MOUTH end, the
    stations resampled every ``sample`` (the last ON the far end), a
    closed end's station standing ``overlap`` OUTSIDE its inner face
    (the trench floor overlaps the end wall, ``cutout.floor_overlap_m``)."""
    ln = LineString(axis)
    s0, s1 = sts[0].s, sts[-1].s
    if mouth == 1:
        s0, s1 = s1, s0
    closed_m, closed_f = walls.closed[mouth], walls.closed[1 - mouth]
    sign = 1.0 if mouth == 0 else -1.0
    start = s0 - sign * (overlap if closed_m else 0.0)
    end = s1 + sign * (overlap if closed_f else 0.0)
    total = abs(end - start)
    ss = [sample * k for k in range(int(total // sample) + 1)]
    if total - ss[-1] > 1e-6:
        ss.append(total)
    by_s = [(st.s, st) for st in sts]

    def interp(s_orig: float) -> Station:
        lo = max((t for t in by_s if t[0] <= s_orig + 1e-9), key=lambda t: t[0], default=by_s[0])
        hi = min((t for t in by_s if t[0] >= s_orig - 1e-9), key=lambda t: t[0], default=by_s[-1])
        if hi[0] - lo[0] < 1e-9:
            return lo[1]
        f = (s_orig - lo[0]) / (hi[0] - lo[0])
        g = lambda a, b: a + (b - a) * f     # noqa: E731
        return Station(s_orig, g(lo[1].half_l, hi[1].half_l), g(lo[1].half_r, hi[1].half_r),
                       g(lo[1].thick_l, hi[1].thick_l), g(lo[1].thick_r, hi[1].thick_r))

    out_axis: list[XY] = []
    out_st: list[Station] = []
    for s in ss:
        so = start + sign * s
        # beyond the midline's ends (the overlap into an end wall) the
        # axis continues straight along its end direction
        if so < 0.0 or so > ln.length:
            e = ln.interpolate(0.0 if so < 0.0 else ln.length)
            q = ln.interpolate(min(ln.length, 1.0) if so < 0.0 else max(0.0, ln.length - 1.0))
            ux, uy = e.x - q.x, e.y - q.y
            L = math.hypot(ux, uy) or 1.0
            d = (-so) if so < 0.0 else (so - ln.length)
            out_axis.append((e.x + ux / L * d, e.y + uy / L * d))
        else:
            p = ln.interpolate(so)
            out_axis.append((p.x, p.y))
        st = interp(so)
        if mouth == 1:          # travelling the other way: left and right swap
            st = Station(s, st.half_r, st.half_l, st.thick_r, st.thick_l)
        else:
            st = Station(s, st.half_l, st.half_r, st.thick_l, st.thick_r)
        out_st.append(st)
    return out_axis, out_st


def _road_through(trench: Polygon, ways) -> list[int]:
    """The mapped highway / railway ways (tunnel or not) whose line runs
    through the trench — a closed-end fallback needs one (2026-09-08o)."""
    out = []
    for w in ways:
        if ("highway" in w.tags or "railway" in w.tags) and len(w.points) >= 2 \
                and LineString(w.points).intersects(trench):
            out.append(w.id)
    return out


def _corridor(sig: WallSignature, o: _obj8.PlacedObject, k: int, airport: Airport,
              tunnel_ways, others: _t.Sequence[Polygon], law: Law) -> Corridor | str:
    """The placement's corridor, or the reason it has none."""
    ob = law.tables.structures.tunnel.object
    tn = law.tables.structures.tunnel
    grid = law.tables.emit.identity.min_distinct_spacing_m
    mat = _obj8.placement_affine(o.xy, o.heading_deg)
    # §51 (4) row 15 — ENTRY
    plate = _fe.enter([sig.plate], mat, _fe.quantum(law))[0]
    if plate is None:
        return "the placed deck plate repairs to nothing (§51 (2))"
    walls = read_wall_lines(plate, law)
    if isinstance(walls, str):
        return walls
    axis = midline(walls, ob.wall_sample_m)
    bores = _bore_ends_at(walls, axis, tunnel_ways, ob.bore_end_tolerance_m)
    notes: list[str] = []
    if walls.kind == "O" and not (bores[0] or bores[1]):
        # A BOX reads its long sides as the side walls; a near-square box
        # on a bore (OTHH tunnel west 1: 35 × 40 m inside) orients itself
        # ALONG the bore — the walls the bore crosses are its end walls
        alt = _rotated_box(walls)
        axis_alt = midline(alt, ob.wall_sample_m)
        bores_alt = _bore_ends_at(alt, axis_alt, tunnel_ways, ob.bore_end_tolerance_m)
        if bores_alt[0] or bores_alt[1]:
            walls, axis, bores = alt, axis_alt, bores_alt
            notes.append("box oriented along the bore that passes through it")
    sts = stations_along(axis, walls, ob.wall_sample_m, grid)
    if len(sts) < 2:
        return "the inner faces leave no station (the walls do not face each other)"
    if bores[0] and bores[1]:
        mouth, flat, kind = 0, True, "bore"
        notes.append(f"bores at both ends ({bores[0]} / {bores[1]}): two mouths, the trench "
                     f"flat at the mouth depth")
    elif bores[0] or bores[1]:
        mouth, flat, kind = (0 if bores[0] else 1), False, "bore"
        notes.append(f"mouth = the bore end (ways {bores[mouth]})")
    elif _faces_other(axis, 0, others) != _faces_other(axis, 1, others):
        mouth, flat, kind = (0 if _faces_other(axis, 0, others) else 1), False, "family"
        notes.append("mouth = the end facing the other placement of the resource")
    elif walls.closed[0] != walls.closed[1]:
        mouth, flat, kind = (0 if walls.closed[0] else 1), False, "closed"
        notes.append("mouth = the closed end")
    else:
        return (f"the mouth is undetermined: no bore at either end, no facing placement, "
                f"ends {walls.kind} {'closed' if walls.closed[0] else 'open'}/"
                f"{'closed' if walls.closed[1] else 'open'}")
    axis2, sts2 = _oriented(walls, axis, sts, mouth,
                            law.tables.structures.cutout.floor_overlap_m, ob.wall_sample_m)
    if len(axis2) < 2:
        return "the corridor is shorter than one station"
    far = 1 - mouth
    # THE MOUTH GROUND is the ground AT THE MOUTH WALL (09-03b: "the mouth
    # wall node stands bore_datum_m above the ramp's mouth node"; 05n-4:
    # the crest is flush with the ground at the wall): the MEDIAN DEM
    # along the mouth end's inner faces — the end wall's polyline and the
    # side walls' ends — never the axis sample.  LEMD's Bridge4 stands in
    # a cutting the SPAIN5M DEM already carries: the axis sample reads
    # 585.2 and the cap centre 590.5 against the walls' 593.7-594.6
    # (2026-09-06f); on flat ground (OTHH) every reading is the same.
    a_end, b_end = walls.end_line(mouth)
    pts = list(walls.end_walls[mouth]) + [a_end, b_end]
    samples = [float(airport.dem.z(*q)) for q in pts]
    samples = [z for z in samples if not math.isnan(z)]
    if not samples:
        return "no DEM at the mouth"
    mouth_dem = float(np.median(samples))
    # the trench closes along the END WALLS' inner faces (2026-09-06f:
    # Bridge4's three-segment far end), never along the side walls' chord
    trench = Polygon(walls.trench_ring())
    if not trench.is_valid:
        trench = trench.buffer(0)
    if trench.geom_type != "Polygon":
        trench = max((g for g in trench.geoms if g.geom_type == "Polygon"), key=lambda g: g.area)
    # THE DEPTH (RULINGS 2026-09-08l / 08o, ``mouth_depth = "floor_slab"``):
    # the model's floor slab under the crest when it carries one, else the
    # bore law's bore_datum_m for every mouth kind — never the crest's
    # height above the anchor.  A CLOSED-end fallback (no bore, no facing
    # placement) needs a mapped road through the trench, else it is a
    # wall around nothing and is refused by name.
    if sig.floor_y is not None:
        depth = float(sig.plate_y - sig.floor_y)
        notes.append(f"depth {depth:.2f} m = crest {sig.plate_y:.2f} − floor slab "
                     f"{sig.floor_y:.2f} (2026-09-08l)")
    else:
        depth = float(tn.bore_datum_m)
        notes.append(f"depth {depth:.2f} m = tunnel.bore_datum_m (no floor slab: a skirt; "
                     f"crest {sig.plate_y:.2f} is the seat's handle, 2026-09-08l/08o)")
    if kind == "closed":
        roads = _road_through(trench, airport.osm_ways)
        if not roads:
            return (f"the closed-end fallback has no mapped road through the trench: a wall "
                    f"around nothing, not a tunnel mouth (2026-09-08o)")
        notes.append(f"closed-end mouth with road(s) {roads} through the trench")
    if sig.edge_wall:
        notes.append(f"edge wall (2026-09-06c (2)): crest {sig.plate_y:.2f} m flush at grade")
    floor = mouth_dem - depth
    footprint = _fe.union([walls.plate, trench], "tunnel_objects.footprint")
    if footprint.geom_type != "Polygon":
        footprint = footprint.convex_hull
    width = 2.0 * sum((s.half_l + s.half_r) / 2.0 for s in sts2) / len(sts2)
    name = os.path.basename(o.path)
    notes.append(f"walls {walls.kind}: {len(walls.inner_a)} + {len(walls.inner_b)} inner-face "
                 f"vertices, band {walls.thickness_m:.2f} m thick")
    return Corridor(f"{ID_PREFIX}:{name}@{k}", o.path, (o.id,), sig.plate_y, tuple(axis2),
                    tuple(sts2), float(sts2[-1].s), width, walls.closed[mouth], walls.closed[far],
                    walls.end_thickness_m[mouth], walls.end_thickness_m[far], kind, flat,
                    mouth_dem, floor, walls.plate, trench, footprint, o.xy, float(o.anchor_z),
                    float(o.agl_m), tuple(notes), depth, bool(sig.edge_wall), sig.floor_y,
                    tuple(sorted(set(bores[0]) | set(bores[1]))))


def shell_corridor(cut, airport: Airport, tunnel_ways, law: Law) -> "Corridor | str":
    """A SIGNATURE-B object cut (spec §33 (6) B; ``airport/object_cut.py``)
    as a :class:`Corridor` — the SAME product every other object corridor
    enters, so ``planar/object_corridor.object_groups`` and the 05n-3
    per-mouth precedence read it unchanged (the §33 (6) consumer census,
    rows 14/15: no new argument, no re-ordering, no edit in
    ``planar/structures.py``).

    Three things are the OBJECT'S and not the law's: the TRENCH is the
    shell's own interior (never a hull, never the chords between the wall
    lines); the two inner chains are its ring cut at its two portals; and
    the DEPTH IS AUTHORED — ``floor_z`` is the floor plate's level in the
    SEATED frame, which overrides ``bore_datum_m`` (the law for
    UNAUTHORED bores only)."""
    ob = law.tables.structures.tunnel.object
    grid = law.tables.emit.identity.min_distinct_spacing_m
    band = _object_cut.valid_polygon(cut.wall_line)
    if band is None:
        return "the shell's wall band has no valid plan area"
    mean_t = 2.0 * band.area / max(band.length, 1e-9)
    walls = WallLines(band, list(cut.inner_a), list(cut.inner_b), (False, False),
                      (0.0, 0.0), float(mean_t), "II")
    axis = midline(walls, ob.wall_sample_m)
    if len(axis) < 2:
        return "the shell's inner faces leave no axis"
    sts = stations_along(axis, walls, ob.wall_sample_m, grid)
    if len(sts) < 2:
        return "the shell's inner faces leave no station"
    bores = _bore_ends_at(walls, axis, tunnel_ways, ob.bore_end_tolerance_m)
    notes = list(cut.notes)
    if not (bores[0] or bores[1]):
        # the bore may pass THROUGH without ending at a portal (a covered
        # stretch): the trench holding a mapped tunnel way is the same
        # evidence, read the way ``_road_through`` reads it
        through = [w.id for w in tunnel_ways
                   if LineString(w.points).intersects(cut.outline)]
        if through:
            bores = ([through[0]], [])
            notes.append(f"mapped tunnel way(s) {through} run through the trench")
    if bores[0] and bores[1]:
        mouth, flat, kind = 0, True, "bore"
        notes.append(f"bores at both portals ({bores[0]} / {bores[1]}): the trench is flat "
                     f"at the AUTHORED floor")
    elif bores[0] or bores[1]:
        mouth, flat, kind = (0 if bores[0] else 1), False, "bore"
        notes.append(f"mouth = the portal the bore reaches (ways {bores[0] or bores[1]})")
    else:
        # §33 (6) OPENS WITH "WHERE AN OBJECT … COVERS A BORE OR A
        # CROSSING": an object that covers neither is not a cut, whatever
        # its floor plate says.  MEASURED at VHHH — without this gate the
        # sea barrier ``sea_X.obj`` (a 402 m2 plate 28.20 m under its
        # zero) paired with ``sea.obj``'s 112,376 m2 flush hard deck (the
        # SEA SURFACE) and read as a 104.9 m wide, 22.88 m deep "tunnel"
        # 177 m long off the north shore.
        return ("a SHELL with a flush hard cover but no mapped bore at either portal and no "
                "mapped tunnel way through its trench: §33 (6) reads an object that covers a "
                "BORE or a CROSSING, and this covers neither")
    axis2, sts2 = _oriented(walls, axis, sts, mouth,
                            law.tables.structures.cutout.floor_overlap_m, ob.wall_sample_m)
    if len(axis2) < 2:
        return "the shell is shorter than one station"
    far = 1 - mouth
    a_end, b_end = walls.end_line(mouth)
    samples = [z for z in (float(airport.dem.z(*q)) for q in (a_end, b_end))
               if not math.isnan(z)]
    if not samples:
        return "no DEM at the shell's mouth"
    mouth_dem = float(np.median(samples))
    trench = _object_cut.largest_polygon(cut.outline)
    if trench is None:
        return "the shell's trench has no valid plan area"
    footprint = _object_cut.largest_polygon(_fe.union([band, trench], "tunnel_objects.band"))
    if footprint is None:
        return "the shell's footprint has no valid plan area"
    depth = float(mouth_dem - cut.floor_z)
    width = 2.0 * sum((s.half_l + s.half_r) / 2.0 for s in sts2) / len(sts2)
    notes.append(f"depth {depth:.2f} m = ground {mouth_dem:.2f} − the AUTHORED floor "
                 f"{cut.floor_z:.2f} (§33 (6) B: it overrides bore_datum_m "
                 f"{law.tables.structures.tunnel.bore_datum_m})")
    return Corridor(cut.id, cut.resource, (cut.object_id,), 0.0, tuple(axis2), tuple(sts2),
                    float(sts2[-1].s), width, False, False, mean_t, mean_t, kind, flat,
                    mouth_dem, float(cut.floor_z), band, trench, footprint,
                    cut.ends[mouth], mouth_dem, 0.0, tuple(notes), depth, False,
                    cut.floor_y, tuple(sorted(set(bores[0]) | set(bores[1]))))


def read_corridors(airport: Airport, objects: _t.Sequence[_obj8.PlacedObject],
                   cache: _obj8.ResourceCache, law: Law
                   ) -> tuple[list[Corridor], TunnelObjectStats]:
    """Every tunnel corridor the pack's wall objects state, in the
    airport frame; the stats name every refusal by resource."""
    t0 = time.perf_counter()
    stats = TunnelObjectStats()
    msl = {o.id: o.y_offset_m for o in airport.dsf_objects if o.kind == "OBJECT_MSL"}
    ob = law.tables.structures.tunnel.object
    admission = law.tables.structures.basin.admission_depth_m
    least_skirt = min(ob.skirt_min_depth_m, ob.edge_wall_min_skirt_m)
    tunnel_ways = [w for w in airport.osm_ways
                   if is_tunnel_way(w.tags, law.tables.structures.tunnel.admitted_values)
                   and len(w.points) >= 2]
    bore_tree = STRtree([LineString(w.points) for w in tunnel_ways]) if tunnel_ways else None
    # THE SHELL + FLUSH HARD COVER (spec §33 (6) B; owner RULINGS
    # 2026-09-15g).  Read FIRST, because this class falls through every
    # reader below it: the witness hand-off further down sends any floor
    # witness straight to basins.py, the crest-plate rule needs a plate
    # ABOVE the seat and ``thin_plates`` takes 1.0-1.5 m of solids only.
    # Its placements are then skipped here AND claimed out of the basin
    # intake ("the shell is never a basin"), one derivation
    # (``object_cut.cut_placement_ids``).
    cuts, cstats = _object_cut.read_shells(airport, objects, cache, law)
    shell_ids: set[str] = set()
    claimed_ids: set[str] = set()
    shell_corridors: list[Corridor] = []
    for cut in cuts:
        c = shell_corridor(cut, airport, tunnel_ways, law)
        if isinstance(c, str):
            stats.refused.append(f"{cut.object_id} {os.path.basename(cut.resource)}: "
                                 f"a signature-B shell, but {c}")
            continue
        shell_corridors.append(c)
        shell_ids.add(cut.object_id)
        claimed_ids.add(cut.object_id)
        if cut.cover_object_id:
            claimed_ids.add(cut.cover_object_id)
    stats.shells = len(shell_corridors)
    stats.shell_claimed = tuple(sorted(claimed_ids))
    stats.refused.extend(cstats.refused)
    sigs: dict[str, WallSignature | str] = {}
    counts: dict[str, int] = {}
    admitted: list[tuple[WallSignature, _obj8.PlacedObject]] = []
    no_bore: set[str] = set()
    #: spec §33 (1): the resources the pre-screen actually READ — every one
    #: of them is named with its verdict (the no-bore skip below never
    #: screened its resource and is counted, not enumerated).
    screened: set[str] = set()
    # THE INTAKE IS SORTED (``object_cut.placement_key``, the one
    # derivation site): this loop's order decides which placement of a
    # resource is the one SCREENED (``sigs`` / ``stats.resources``), the
    # insertion order of every refusal line, and the ``@k`` index below.
    # Measured on the signature fixture: six of eight input shuffles
    # re-bound ``tunnel-object:wall_long.obj@0`` to another placement
    # while the corridor SET stayed identical (lane v2othhdet).
    for o in _object_cut.placement_order(objects):
        if o.resolved is None or _obj8.is_stock_library_resource(o.path):
            continue
        stats.placements += 1
        counts[o.path] = counts.get(o.path, 0) + 1
        if o.id in shell_ids:
            sigs.setdefault(o.path, "a signature-B SHELL (§33 (6) B): its own cut geometry")
            continue
        if o.witnesses:
            sigs.setdefault(o.path, "the basin pass witnessed a floor in it (basins.py owns it)")
            continue
        if o.path not in sigs and cache.y_range(o.resolved)[0] > -ob.skirt_min_depth_m:
            # A SHALLOW-SEAT resource is an edge-wall candidate only around a
            # BORE (06c: the bore mouth inside it is its discriminator; 06f):
            # its signature is read once a placement's plan holds a mapped
            # tunnel way — OTHH: 1,350 resources, 219 signatures otherwise
            # (21 s), the 8 corridors all full-skirt
            if not _bore_near(o, cache, bore_tree, ob.bore_end_tolerance_m):
                no_bore.add(o.path)
                continue
        if o.path not in sigs:
            stats.resources += 1
            screened.add(o.path)
            # THE PRE-SCREEN (the basin reader's O(n) step): a wall's skirt
            # spans at least the lesser of skirt_min_depth_m (a full wall,
            # below the seat) and edge_wall_min_skirt_m (an edge wall, below
            # ITS crest wherever that lies — 2026-09-06f), and its plan is
            # hull_min_length_m long, so a resource whose authored extent
            # has neither is refused before its components are built
            # (OTHH: 1,350 resources, 7 tunnels)
            vmin, vmax, x0, x1, z0, z1 = cache.y_range(o.resolved)
            if vmax - vmin < least_skirt:
                sigs[o.path] = (f"no wall skirt: the solids span only {vmax - vmin:.2f} m "
                                f"vertically (< {least_skirt} = the lesser of skirt_min_depth_m "
                                f"and edge_wall_min_skirt_m)")
                continue
            if max(x1 - x0, z1 - z0) < ob.hull_min_length_m:
                sigs[o.path] = (f"a stub: the plan extent is {max(x1 - x0, z1 - z0):.1f} m "
                                f"(< hull_min_length_m {ob.hull_min_length_m})")
                continue
            g = cache.geometry(o.resolved)
            sigs[o.path] = signature(g, cache.genuine(o.resolved), law) if g is not None \
                else "unreadable OBJ8"
        sig = sigs[o.path]
        if isinstance(sig, str):
            continue
        seat = _seat(o, msl)
        # THE SEAT IS BELOW GRADE (the basin family's admission depth): a
        # wall object seated AT grade is a fence or a compound wall
        # (measured OTHH: a fuel-farm wall and a terminal kerb wall).  An
        # EDGE WALL (2026-09-06c (2)) is placed with its low crest at the
        # ground — its seat stands one crest under grade, never the
        # admission depth; its discriminator is the BORE mouth inside it
        # (read in _corridor), and the re-seat puts the crest flush.
        if not sig.edge_wall and seat > o.anchor_z - admission:
            stats.refused.append(f"{o.id} {os.path.basename(o.path)}: seat {seat:.2f} is not "
                                 f"{admission:.1f} m (basin.admission_depth_m) under the ground "
                                 f"at the placement ({o.anchor_z:.2f}) — a wall at grade, not a "
                                 f"tunnel floor")
            continue
        admitted.append((sig, o))
    for path in no_bore - set(sigs):
        sigs[path] = ("no wall skirt under the seat and no mapped bore within the plan: not an "
                      "edge-wall candidate (2026-09-06f)")
    stats.signatures = sum(1 for s in sigs.values() if not isinstance(s, str))
    # EVERY SCREENED RESOURCE IS NAMED (spec §33 (1); RULINGS 2026-09-13i).
    # The four suppressed prefixes — "no wall skirt", "no genuine", "no
    # crest plate", "a stub: the plan extent" — hid the pre-screen's own
    # verdicts from every report, so LEMD's Bridge3 (1.03 m of solids over
    # the whole of bore -5931) and Bridge2 (1.31 m over two decks) were
    # refused INVISIBLY and the OSM corridor stood alone.  A resource the
    # reader never screened (no skirt under the seat AND no mapped bore in
    # its plan — the 06f cheap gate, OTHH's ~1,100 library resources) is
    # not a verdict and is COUNTED, not enumerated.
    for path, sig in sorted(sigs.items()):
        if isinstance(sig, str) and path in screened:
            stats.refused.append(f"{os.path.basename(path)} x{counts[path]}: {sig}")
    stats.not_screened = len(no_bore - screened)
    # the other placements of each resource (the family rule reads them)
    plates: dict[str, list[tuple[str, Polygon]]] = {}
    for sig, o in admitted:
        placed = _fe.enter([sig.plate],                       # §51 row 15 — ENTRY
                           _obj8.placement_affine(o.xy, o.heading_deg), _fe.quantum(law))[0]
        if placed is not None:
            plates.setdefault(o.path, []).append((o.id, placed))
    out: list[Corridor] = []
    k_by_res: dict[str, int] = {}
    for sig, o in admitted:
        k = k_by_res.get(o.path, 0)
        k_by_res[o.path] = k + 1
        others = [p for oid, p in plates[o.path] if oid != o.id]
        c = _corridor(sig, o, k, airport, tunnel_ways, others, law)
        if isinstance(c, str):
            stats.refused.append(f"{o.id} {os.path.basename(o.path)}: {c}")
            continue
        out.append(c)
    out.extend(shell_corridors)
    out.sort(key=lambda c: c.id)
    # the report is order-free too: a refusal LIST whose order depends on
    # the read order cannot be diffed between two arms (lane v2othhdet)
    stats.refused.sort()
    stats.corridors = len(out)
    stats.signature_s = time.perf_counter() - t0
    return out, stats
