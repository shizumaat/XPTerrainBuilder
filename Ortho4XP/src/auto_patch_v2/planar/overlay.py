"""The ONE planar subdivision (plan §1 row 4; M0 §4 step 3).

Every region (a classified pavement cell, a pad, a road corridor, a zone
region) contributes its rings; every breakline source (runway profile
stations, taxi / road centrelines) its line.  All of it is noded in ONE
``unary_union`` at full precision, snapped ONCE to the identity grid
(``law.emit.identity.min_distinct_spacing_m`` — two distinct vertices
never closer than that, so the near-parallel / sub-micron class the mesh
pays for cannot exist), and polygonised.  Each face takes the region with
the largest overlap; a face no region claims (a hole beyond zone 2) is
dropped — the DEM owns it.

Shared boundaries exist once BY CONSTRUCTION: two regions that share a
boundary contribute the same coordinates, the union merges them, and the
face on each side references the same noded segment.  No annuli, no
T-vertices.  Boundaries that MERELY NEARLY coincide (two sources a
sub-metre apart) are welded first (``weld.py``, RULINGS 2026-09-04u) so
the sliver between them never becomes a face.
"""
from __future__ import annotations

import dataclasses as _dc
import math

import shapely
from shapely.geometry import LineString, MultiLineString, Polygon
from shapely.ops import unary_union
from shapely.strtree import STRtree

from ..classify.roles import Classification
from ..law import Law
from ..law.tables import chord_cap_m, role_side
from ..model.airport import Airport
from .chords import densify, ring_lines, stations
from .terrain_edge import EdgeReport, road_lines
from .weld import WeldStats, weld_cells
from .zones import zone_regions

__all__ = ["Region", "SourceLine", "Arrangement", "build_arrangement", "seam_bands",
           "merge_slivers", "dissolve_degenerate_holes",
           "absorb_enclosed_pavement", "ENCLOSED_MIN_FRAC"]

#: §41 (1): the fraction of its OWN area a pavement face must have inside
#: another pavement face's exterior ring to be that face's hole.
ENCLOSED_MIN_FRAC = 0.95


@_dc.dataclass(frozen=True)
class Region:
    """A face source: what a face inside it becomes."""

    role: str
    ref: str
    polygon: Polygon
    code_number: int | None
    code_letter: str | None
    side: str
    source: str            # "cell" | "zone"
    zone: int | None = None
    #: THE TERRAIN EDGE (owner RULINGS 2026-09-10b/10c; spec §19.3 C12):
    #: which rule ended this region — ``"crest"``, ``"road"``, ``"none"``.
    edge_kind: str = "none"


@_dc.dataclass(frozen=True)
class SourceLine:
    """A breakline source, before noding."""

    kind: str              # runway_profile | taxi_centerline | road_centerline
    ref: str
    line: LineString
    code_letter: str | None = None   # the taxi chain's letter (04t-3)


@_dc.dataclass
class Arrangement:
    """The noded, polygonised subdivision."""

    faces: list[tuple[Polygon, Region]]
    noded: MultiLineString
    sources: list[SourceLine]
    regions: list[Region]
    dropped_faces: int
    grid_m: float
    #: The tile-seam bands (``law.emit.seam``, user 2026-05-10) cut out of
    #: the arrangement, one per integer lat/lon line the regions cross;
    #: faces inside them are dropped (``dropped_seam_faces``) — the DEM
    #: owns the band, each tile's patch stops ``half_width_m`` short.
    seam_bands: list[Polygon] = _dc.field(default_factory=list)
    dropped_seam_faces: int = 0
    #: The sliver weld (``weld.py``, RULINGS 2026-09-04u) applied to the
    #: cells BEFORE the zones are derived and the rings noded.
    weld: WeldStats = _dc.field(default_factory=WeldStats)
    #: RULINGS 2026-09-08d (4a): same-region faces under the sliver area
    #: merged into their neighbour (``merge_slivers``).
    slivers_merged: int = 0
    #: THE TERRAIN EDGE (owner RULINGS 2026-09-10b/10c; spec §19): the edge
    #: SEGMENTS the zone clip made, in the frame — the boundary beyond
    #: which there is no patch and no bank — and what the clip did.
    terrain_edges: tuple = ()
    edge_report: EdgeReport = _dc.field(default_factory=EdgeReport)
    #: RULINGS 2026-09-10h (1): degenerate hole rings dissolved into their
    #: own face (``dissolve_degenerate_holes``) — never a vertex set.
    holes_dissolved: int = 0
    #: §41 (1) (owner RULINGS 2026-09-13co item 2; RULINGS 2026-09-13cs
    #: item 2): pavement faces enclosed by another pavement face's ring
    #: and absorbed into it (``absorb_enclosed_pavement``).
    enclosed_absorbed: int = 0
    #: The same rule's REFUSALS: an enclosed face that shares NO boundary
    #: with its enclosing body, so the union would not be one face — an
    #: island in the middle of a loop, not a notch cut into a body.
    enclosed_detached: int = 0


def build_arrangement(airport: Airport, classification: Classification,
                      law: Law, grid_m: float | None = None) -> Arrangement:
    """Regions + breakline sources -> ONE noded arrangement."""
    grid = grid_m if grid_m is not None else \
        law.tables.emit.identity.min_distinct_spacing_m
    cells, weld = weld_cells(classification.cells, law)
    regions: list[Region] = []
    for c in cells:
        regions.append(Region(c.role, c.ref, Polygon(c.ring, c.holes),
                              c.code_number, c.code_letter, c.side, "cell"))
    # THE TERRAIN EDGE (owner RULINGS 2026-09-10b/10c; spec §19): the zones
    # are clipped at their own derivation site, against the airport's DEM
    # and the tile's OSM road centrelines
    erep = EdgeReport()
    edge_lines: list[LineString] = []
    for z in zone_regions(cells, law, classification.keepouts,
                          getattr(airport, "dem", None),
                          road_lines(getattr(airport, "osm_ways", ())), erep):
        regions.append(Region("graded_strip", z.ref, z.polygon, z.code_number,
                              z.code_letter, role_side(law, "graded_strip"),
                              "zone", z.zone, z.edge_kind))
        edge_lines.extend(z.edge_lines)

    lines: list[LineString] = []
    for r in regions:
        cap = chord_cap_m(law, r.role)
        for ring in ring_lines(tuple(r.polygon.exterior.coords)[:-1],
                               [tuple(h.coords)[:-1] for h in r.polygon.interiors],
                               cap):
            if len(ring) >= 2:
                lines.append(LineString(ring))

    sources: list[SourceLine] = []
    spacing = law.tables.emit.chords.station_spacing_m
    cap_pav = law.tables.emit.chords.pavement_max_chord_m
    for rw in airport.runways:
        a, b = rw.ends
        (ax, ay), (bx, by) = a.xy, b.xy
        L = ((bx - ax) ** 2 + (by - ay) ** 2) ** 0.5
        if L < 1.0:
            continue
        ux, uy = (bx - ax) / L, (by - ay) / L
        p0 = (ax - ux * a.overrun_m, ay - uy * a.overrun_m)
        p1 = (bx + ux * b.overrun_m, by + uy * b.overrun_m)
        sources.append(SourceLine("runway_profile", rw.id,
                                  LineString(stations([p0, p1], spacing))))
    for cl in classification.cut_lines:
        if len(cl.points) >= 2:
            sources.append(SourceLine(cl.kind, cl.ref,
                                      LineString(densify(cl.points, cap_pav)),
                                      cl.code_letter))
    lines.extend(s.line for s in sources)
    bands = seam_bands(airport, regions, law.tables.emit.seam.half_width_m)
    lines.extend(LineString(b.exterior.coords) for b in bands)

    # Node at full precision, snap the ONE result to the grid, then node
    # AGAIN under the grid's precision model: snap-rounding can create new
    # crossings between previously noded segments, and polygonize needs a
    # fully noded set.
    noded = shapely.unary_union(unary_union(lines), grid_size=grid)
    if noded.geom_type == "LineString":
        noded = MultiLineString([noded])
    polys = [g for g in shapely.get_parts(shapely.polygonize([noded]))
             if g.geom_type == "Polygon" and not g.is_empty]

    tree = STRtree([r.polygon for r in regions])
    faces: list[tuple[Polygon, Region]] = []
    dropped = 0
    dropped_seam = 0
    for poly in polys:
        if bands and any(b.contains(poly.representative_point()) for b in bands):
            dropped_seam += 1
            continue
        best: Region | None = None
        best_a = 0.0
        for j in tree.query(poly, predicate="intersects"):
            r = regions[int(j)]
            a = poly.intersection(r.polygon).area
            if a > best_a:
                best, best_a = r, a
        if best is None or best_a < 0.5 * poly.area:
            dropped += 1
            continue
        faces.append((poly, best))
    ident = law.tables.emit.identity.min_distinct_spacing_m
    faces, merged = merge_slivers(faces, (ident * law.tables.emit.terrace.sliver_area_factor) ** 2)
    # §41 (1): an enclosed pavement face is its host's hole — absorbed HERE,
    # at the single derivation site, so every consumer downstream reads one
    # body with one law (owner RULINGS 2026-08-30l: trim at the derivation
    # site, never per consumer)
    faces, absorbed, detached = absorb_enclosed_pavement(
        faces, tuple(law.tables.emit.terrace.shape_roles))
    faces, holes_gone = dissolve_degenerate_holes(
        faces, law.tables.emit.terrace.separation_m, ident ** 2)
    return Arrangement(faces, noded, sources, regions, dropped, grid,
                       bands, dropped_seam, weld, merged,
                       tuple(edge_lines), erep, holes_gone,
                       absorbed, detached)


def dissolve_degenerate_holes(faces: list[tuple[Polygon, Region]], sep_m: float,
                              area_min_m2: float
                              ) -> tuple[list[tuple[Polygon, Region]], int]:
    """THE DEGENERATE HOLE (RULINGS 2026-09-10h (1)): a face's interior ring
    that is NOWHERE as wide as ``terrace.separation_m`` — the width at which
    a gap is still one shape, so a hole under it is not a gap at all — or
    under ``area_min_m2`` (``identity.min_distinct_spacing_m²``, the smallest
    area two distinct vertices can bound) is DEGENERATE GEOMETRY, dissolved
    into its own face here.  It never becomes a vertex set.

    WHY, measured at LEMD (RULINGS 2026-09-10h): way −10892, a 35 m × 0.5 m,
    3-vertex hole in apron ``pav16``, emitted 16.3 m BELOW the apron it sits
    inside (582.7 against a DEM of 599.0) and coned to over 265 × 240 m of
    mesh — the owner's "large apron dip".  Such a ring's vertices bound no
    face law and no design target, and every triangle the face's
    triangulation gives them is obtuse enough that the cotangent Laplacian
    CLAMPS its weight (``solve/rows._cotangent_laplacian``): the columns
    reach the least-squares solve carrying no row at all, so their value is
    whatever the min-norm solution leaves there — which is why the same
    three vertices, at byte-identical coordinates, moved 7.6 m between two
    arms that changed nothing near them.

    A hole is dissolved only when NO kept face lies inside it: a real inner
    face (a pad, a trench floor) keeps its hole however thin the ring, and
    the two faces never overlap.  ``buffer(-sep/2)`` empty is the width
    test — the ring cannot hold a disc of diameter ``sep_m`` anywhere, i.e.
    it is nowhere as wide as the separation.  Returns the faces and the
    number of holes dissolved."""
    if not faces or (sep_m <= 0.0 and area_min_m2 <= 0.0):
        return faces, 0
    inner = STRtree([p for p, _r in faces])
    out: list[tuple[Polygon, Region]] = []
    gone = 0
    for i, (poly, region) in enumerate(faces):
        if not poly.interiors:
            out.append((poly, region))
            continue
        keep: list = []
        for h in poly.interiors:
            hp = Polygon(h)
            if not hp.is_valid:
                hp = hp.buffer(0)
            degenerate = (hp.is_empty or hp.area < area_min_m2
                          or (sep_m > 0.0 and hp.buffer(-0.5 * sep_m).is_empty))
            if degenerate and not _holds_a_face(hp, faces, inner, i):
                gone += 1
                continue
            keep.append(h)
        out.append((poly if len(keep) == len(poly.interiors)
                    else Polygon(poly.exterior, keep), region))
    return out, gone


def _holds_a_face(hole: Polygon, faces: list[tuple[Polygon, Region]],
                  tree: STRtree, self_i: int) -> bool:
    """A kept face other than ``faces[self_i]`` lies inside ``hole``."""
    if hole.is_empty:
        return False
    for j in tree.query(hole, predicate="intersects"):
        j = int(j)
        if j == self_i:
            continue
        if hole.contains(faces[j][0].representative_point()):
            return True
    return False


def merge_slivers(faces: list[tuple[Polygon, Region]], area_max: float
                  ) -> tuple[list[tuple[Polygon, Region]], int]:
    """THE SLIVER MERGE (RULINGS 2026-09-08d (4a); spec heca-v1-parity §4 /
    §6.3): a face under ``area_max`` (``(identity.min_distinct_spacing_m ×
    terrace.sliver_area_factor)²``) whose ring shares a boundary run with a
    face of the SAME region (same role, same ref — one cell the noding cut
    twice) is a classification artefact, never a cell of its own: it is
    unioned into that neighbour (the largest sharing one).  HECA pav131
    face 269 (3 nodes, 9.8 m², 47 m along face 215's edge) became a
    terrace joint of 6.2 m at the owner's site.  Returns the faces and
    the number merged."""
    if area_max <= 0.0 or len(faces) < 2:
        return faces, 0
    polys = [p for p, _r in faces]
    tree = STRtree(polys)
    keep = list(faces)
    merged = 0
    for i, (poly, region) in enumerate(faces):
        if keep[i] is None or poly.area >= area_max:
            continue
        best = None
        best_len = 0.0
        for j in tree.query(poly, predicate="intersects"):
            j = int(j)
            if j == i or keep[j] is None:
                continue
            pj, rj = keep[j]
            if rj.role != region.role or rj.ref != region.ref:
                continue
            shared = poly.boundary.intersection(pj.boundary).length
            if shared > best_len:
                best, best_len = j, shared
        if best is None or best_len <= 0.0:
            continue
        pj, rj = keep[best]
        u = pj.union(poly)
        if u.geom_type != "Polygon":
            u = max(shapely.get_parts(u), key=lambda g: g.area)
        keep[best] = (u, rj)
        keep[i] = None
        merged += 1
    return [f for f in keep if f is not None], merged


def absorb_enclosed_pavement(faces: list[tuple[Polygon, Region]],
                             roles: tuple[str, ...],
                             min_frac: float = ENCLOSED_MIN_FRAC
                             ) -> tuple[list[tuple[Polygon, Region]], int, int]:
    """§41 (1) — A PAVEMENT FACE INSIDE A PAVEMENT FACE IS A HOLE OF IT
    (owner RULINGS 2026-09-13co item 2; attributed RULINGS 2026-09-13cs
    item 2; spec §41).  A pavement face at least ``min_frac`` of whose own
    area lies inside another, LARGER pavement face's EXTERIOR RING is that
    face's hole: it contributes no rows of its own and the outer face's law
    governs every vertex in it.  A cross-connector inside a parallel is the
    parallel.  Implemented as an absorption into the host face, so there is
    one face, one role, one ref and one law — no boundary between them for
    a step to stand on.

    THE FRAME IS THE HOST'S EXTERIOR RING, NOT ITS SOLID, and that is the
    whole reading.  The enclosed face sits in a HOLE of the host (the
    arrangement is a partition: a face never overlaps another), so the
    hole-aware intersection of the two is 0 m² BY CONSTRUCTION and a
    solid-frame test finds nothing.  Measured on the owner's 1.0.329 HECA
    patch: 22 faces stand at ≥ 95 % inside another pavement face's ring,
    every one of them at 0.000 solid fraction; 21 of the 22 share that
    face's boundary.

    WHY IT IS A DEFECT (the owner's site 30.1312203, 31.3983896).
    ``cross_connector:pav77`` (895 m²) is a notch in ``primary_parallel:
    pav73``'s ring, pinned at 65.5 m while the parallel around it holds
    68–69.5 m: the parallel's OWN surface has to ramp 65.7 → 68.05 m over
    21 m — 11 % across a code-F taxiway against a 1.5 % cap — and the
    census sees no row, because each face is lawful on its own.

    THE ONE NARROWING (reported, RULINGS 2026-09-13cs): a face that shares
    NO boundary run with its host is NOT absorbed — the union would be two
    disjoint pieces, which no face can be.  That is an island in the middle
    of a taxiway loop (HECA ``apron:pav5``, 2,362 m², 12.97 m off
    ``cross_connector:pav67``'s solid), not a notch cut into a body; it is
    counted as ``enclosed_detached`` and left alone.

    Smallest first, so a chain of nested notches folds into the outermost
    body.  Returns the faces, how many were absorbed and how many enclosed
    faces were refused for being detached."""
    if len(faces) < 2 or not roles:
        return faces, 0, 0
    role_set = set(roles)
    polys = [p for p, _r in faces]
    tree = STRtree(polys)
    keep: list[tuple[Polygon, Region] | None] = list(faces)
    #: union-find: which face each original index now lives in
    home = list(range(len(faces)))

    def root(i: int) -> int:
        while home[i] != i:
            home[i] = home[home[i]]
            i = home[i]
        return i

    absorbed = detached = 0
    for i in sorted(range(len(faces)), key=lambda k: polys[k].area):
        if keep[i] is None or faces[i][1].role not in role_set:
            continue
        poly = keep[i][0]
        if poly.area <= 0.0:
            continue
        best = None
        best_shared = 0.0
        saw_host = False
        # a BOUNDING-BOX query, not ``intersects``: the enclosed face lies
        # in the host's HOLE, so the two are disjoint as solids
        for j in tree.query(poly):
            j = root(int(j))
            if j == i or keep[j] is None:
                continue
            pj, rj = keep[j]
            if rj.role not in role_set or pj.area <= poly.area:
                continue
            try:
                inside = poly.intersection(Polygon(pj.exterior)).area
            except Exception:                             # pragma: no cover
                continue
            if inside < min_frac * poly.area:
                continue
            saw_host = True
            shared = poly.boundary.intersection(pj.boundary).length
            if shared > best_shared:
                best, best_shared = j, shared
        if best is None:
            detached += 1 if saw_host else 0
            continue
        pj, rj = keep[best]
        u = pj.union(poly)
        if u.geom_type != "Polygon":
            u = max(shapely.get_parts(u), key=lambda g: g.area)
        keep[best] = (u, rj)
        keep[i] = None
        home[i] = best
        absorbed += 1
    return [f for f in keep if f is not None], absorbed, detached


def _degree_offset(to_xy, lon: float, lat: float, along_lon: bool,
                   metres: float) -> float:
    """Degrees of ``lon`` (or ``lat``) that measure ``metres`` in the frame
    at ``(lat, lon)`` — the local scale, read from the frame's OWN forward
    transformer so the band is offset in the same map the patch is emitted
    in.  ``1.0`` degrees where the scale cannot be read (a degenerate
    frame): the caller then buffers as before."""
    eps = 1.0e-4
    x0, y0 = to_xy(lon, lat)
    x1, y1 = (to_xy(lon + eps, lat) if along_lon else to_xy(lon, lat + eps))
    d = math.hypot(x1 - x0, y1 - y0)
    return metres * eps / d if d > 1.0e-12 else 1.0


def seam_bands(airport: Airport, regions: list[Region], half_width_m: float
               ) -> list[Polygon]:
    """One band per integer latitude / longitude line crossing the
    regions' extent: the graticule line sampled every 25 m in the frame
    (a tmerc image of a parallel is not straight).

    THE BAND IS SYMMETRIC ABOUT THE GRATICULE LINE IN THE EMITTED FRAME
    (§38 (3)/13an (b); owner RULINGS 2026-09-13an).  Until 13an the band
    was ``LineString(pts).buffer(half_width_m)`` — a buffer of the tmerc
    IMAGE of the line, offset by ``half_width_m`` of frame metre.  Measured
    at SPLP that band's edges came back at **+5.0228 / −4.9754 m** of
    emitted longitude (centre 0.0237 m east, growing to 0.0287 m over
    1.1 km of latitude): the ``pyproj`` round trip is not the identity on
    the line itself.  The two 5.0 m bank collars then met at +0.0229 and
    +0.0245 m and left a ~1.6 mm HAIRLINE CRACK, the bank foot followed
    it, and Triangle4XP split that segment 16,298 times against the
    unsplittable tile border — the SPLP texture tear.

    So each edge is built as its OWN polyline, at the graticule value
    ± the DEGREES that measure ``half_width_m`` there
    (:func:`_degree_offset`), and the band is the polygon between them:
    the round trip carries both edges equally, so the emitted band is
    symmetric to the frame's own scale error rather than to none of it.
    """
    if not regions or half_width_m <= 0.0:
        return []
    to_xy, to_ll = airport.frame.transformers()
    xmin, ymin, xmax, ymax = unary_union([r.polygon for r in regions]).bounds
    margin = 2.0 * half_width_m
    xmin, ymin, xmax, ymax = xmin - margin, ymin - margin, xmax + margin, ymax + margin
    corners = [to_ll(x, y) for x in (xmin, xmax) for y in (ymin, ymax)]
    lat_lo, lat_hi = min(c[0] for c in corners), max(c[0] for c in corners)
    lon_lo, lon_hi = min(c[1] for c in corners), max(c[1] for c in corners)
    out: list[Polygon] = []
    n = max(2, int((max(xmax - xmin, ymax - ymin)) / 25.0) + 1)

    def _xy_at(lon: float, lat: float) -> tuple[float, float]:
        """The frame point that COMES BACK as ``(lat, lon)``.

        ``to_ll(to_xy(...))`` is not the identity — measured at SPLP the
        meridian round-trips 0.0237 m east, growing to 0.0287 m over 1.1 km
        of latitude (13an).  The band's edges are a statement about the
        EMITTED frame (the mesh's tile border sits at the exact graticule
        value), so they are specified there: one Newton step against the
        round trip, which the smoothness of the bias closes to well under a
        millimetre.
        """
        x, y = to_xy(lon, lat)
        la2, lo2 = to_ll(x, y)
        return to_xy(lon - (lo2 - lon), lat - (la2 - lat))

    def _band(pairs: list[tuple[float, float]], along_lon: bool) -> Polygon:
        """``pairs`` are the (lon, lat) samples ON the graticule line."""
        lo_side, hi_side = [], []
        for lon, lat in pairs:
            d = _degree_offset(to_xy, lon, lat, along_lon, half_width_m)
            if along_lon:
                lo_side.append(_xy_at(lon, lat - d))
                hi_side.append(_xy_at(lon, lat + d))
            else:
                lo_side.append(_xy_at(lon - d, lat))
                hi_side.append(_xy_at(lon + d, lat))
        return Polygon(lo_side + hi_side[::-1]).buffer(0)

    for L in range(math.ceil(lat_lo), math.floor(lat_hi) + 1):
        # a PARALLEL: the offset is in latitude
        out.append(_band([(lon_lo + (lon_hi - lon_lo) * k / (n - 1), float(L))
                          for k in range(n)], True))
    for L in range(math.ceil(lon_lo), math.floor(lon_hi) + 1):
        # a MERIDIAN: the offset is in longitude
        out.append(_band([(float(L), lat_lo + (lat_hi - lat_lo) * k / (n - 1))
                          for k in range(n)], False))
    return [b for b in out if not b.is_empty and b.geom_type == "Polygon"]
