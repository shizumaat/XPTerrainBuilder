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
           "merge_slivers", "dissolve_degenerate_holes"]


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
    faces, holes_gone = dissolve_degenerate_holes(
        faces, law.tables.emit.terrace.separation_m, ident ** 2)
    return Arrangement(faces, noded, sources, regions, dropped, grid,
                       bands, dropped_seam, weld, merged,
                       tuple(edge_lines), erep, holes_gone)


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


def seam_bands(airport: Airport, regions: list[Region], half_width_m: float
               ) -> list[Polygon]:
    """One band per integer latitude / longitude line crossing the
    regions' extent: the graticule line sampled every 25 m in the frame
    (a tmerc image of a parallel is not straight), buffered
    ``half_width_m`` with flat caps."""
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
    import math
    n = max(2, int((max(xmax - xmin, ymax - ymin)) / 25.0) + 1)
    for L in range(math.ceil(lat_lo), math.floor(lat_hi) + 1):
        pts = [to_xy(lon_lo + (lon_hi - lon_lo) * k / (n - 1), float(L)) for k in range(n)]
        out.append(LineString(pts).buffer(half_width_m, cap_style=2))
    for L in range(math.ceil(lon_lo), math.floor(lon_hi) + 1):
        pts = [to_xy(float(L), lat_lo + (lat_hi - lat_lo) * k / (n - 1)) for k in range(n)]
        out.append(LineString(pts).buffer(half_width_m, cap_style=2))
    return out
