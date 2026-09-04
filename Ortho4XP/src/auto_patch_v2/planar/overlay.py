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
face on each side references the same noded segment.  No welds, no
annuli, no T-vertices.
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
from .zones import zone_regions

__all__ = ["Region", "SourceLine", "Arrangement", "build_arrangement"]


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


@_dc.dataclass(frozen=True)
class SourceLine:
    """A breakline source, before noding."""

    kind: str              # runway_profile | taxi_centerline | road_centerline
    ref: str
    line: LineString


@_dc.dataclass
class Arrangement:
    """The noded, polygonised subdivision."""

    faces: list[tuple[Polygon, Region]]
    noded: MultiLineString
    sources: list[SourceLine]
    regions: list[Region]
    dropped_faces: int
    grid_m: float


def build_arrangement(airport: Airport, classification: Classification,
                      law: Law, grid_m: float | None = None) -> Arrangement:
    """Regions + breakline sources -> ONE noded arrangement."""
    grid = grid_m if grid_m is not None else \
        law.tables.emit.identity.min_distinct_spacing_m
    regions: list[Region] = []
    for c in classification.cells:
        regions.append(Region(c.role, c.ref, Polygon(c.ring, c.holes),
                              c.code_number, c.code_letter, c.side, "cell"))
    for z in zone_regions(classification.cells, law):
        regions.append(Region("graded_strip", z.ref, z.polygon, z.code_number,
                              z.code_letter, role_side(law, "graded_strip"),
                              "zone", z.zone))

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
                                      LineString(densify(cl.points, cap_pav))))
    lines.extend(s.line for s in sources)

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
    for poly in polys:
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
    return Arrangement(faces, noded, sources, regions, dropped, grid)
