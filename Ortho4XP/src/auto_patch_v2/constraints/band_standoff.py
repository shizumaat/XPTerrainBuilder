"""THE BAND'S WALL BESIDE A ROAD PAGE (owner 2026-10-19 answers to the #951
spec, Q12: walls stand beside DSF road pages too, not only OSM ribbons; Q11:
at the wall the top of the band holds its own graded level; spec
``docs/specs/band-road-wall-joint-spec.md`` §7).

A road page that is not a mapped-road ribbon (a DSF road page, a classified
road cell) is a groundside CELL: the zone band is already cut back from it
by ``zones.adjacent_ground.groundside_cutback_m`` (the stand-off every
groundside cell gets), so the band's edge and the road's kerb are two rings
about one weld spacing apart with no face between them — the riser the
ribbons need ``planar/band_riser`` to cut is already there.  This module
reads it: :func:`band_standoffs` pairs each runway / taxi band ring vertex
with the nearest road-page vertex across the stand-off, and
:func:`band_wall_vertices` is the set of band vertices at a wall (these and
the riser's band line) whose band row holds the band's graded level
(``zones.zone_bands``)."""
from __future__ import annotations

from ..law import Law
from ..model.band_riser import band_risers
from ..model.planar import PlanarMap, is_osm_ribbon_ref

__all__ = ["band_standoffs", "band_wall_vertices", "is_band_zone_ref"]

#: the zone families that are a SAFETY-AREA band (19a)
_BAND_FAMILIES = ("runway", "taxi")


def is_band_zone_ref(ref) -> bool:
    """A runway / taxi adjacent-ground zone face's ref."""
    parts = str(ref or "").split(":")
    return len(parts) > 2 and parts[0] == "adjacent_ground" and parts[1] in _BAND_FAMILIES


def band_standoffs(planar: PlanarMap, law: Law
                   ) -> list[tuple[int, int, int, float, float]]:
    """``(band vertex, a, c, t, plan distance)`` for every runway / taxi band
    ring vertex whose nearest point on a road page's ring (a road-family
    face that is not an OSM ribbon) stands across the stand-off — within
    ``groundside_cutback_m`` + ``weld_spacing_m`` + the snap margin, never
    a shared vertex.  The nearest point is ``(1 - t) a + t c`` on the ring
    edge ``a``-``c``: the EDGE, not its nearest vertex (round 3, KBUR
    building9 corner 34.19628, -118.35023: the census's 1.12 m stand-off
    is to the road's edge; its nearest ring vertex is 2.69 m away, past the
    1.95 m horizon).  Sorted by band vertex."""
    from shapely.geometry import LineString, Point
    from shapely.strtree import STRtree

    from ..law.tables import family, snap_margin_m
    # the road family as ``constraints/roads.road_family_roles`` reads it
    # (the cross-section family's roles), without importing that generator
    roads = set(family(law, "road_cross_section").roles)
    edges: dict[tuple[int, int], None] = {}
    road_v: set[int] = set()
    band_v: set[int] = set()
    for f in planar.faces.values():
        if f.role in roads and not is_osm_ribbon_ref(f.ref):
            for cyc in (f.ring, *f.holes):
                vs = planar.ring_vertices(cyc)
                road_v.update(vs)
                for i, x in enumerate(vs):
                    y = vs[(i + 1) % len(vs)]
                    if x != y:
                        edges[(min(x, y), max(x, y))] = None
        elif f.role == "graded_strip" and is_band_zone_ref(f.ref):
            for cyc in (f.ring, *f.holes):
                band_v.update(planar.ring_vertices(cyc))
    band_v -= road_v
    if not edges or not band_v:
        return []
    keys = sorted(edges)
    lines = [LineString([planar.vertices[x].xy, planar.vertices[y].xy]) for x, y in keys]
    tree = STRtree(lines)
    ag = law.tables.zones.adjacent_ground
    ident = law.tables.emit.identity
    horizon = (float(ag.groundside_cutback_m) + float(ident.weld_spacing_m)
               + snap_margin_m(law))
    min_d = float(ident.min_distinct_spacing_m)
    out: list[tuple[int, int, int, float, float]] = []
    for bv in sorted(band_v):
        pt = Point(planar.vertices[bv].xy)
        j = tree.nearest(pt)
        if j is None:
            continue
        ln = lines[int(j)]
        d = float(ln.distance(pt))
        if not (min_d <= d <= horizon):
            continue
        t = float(ln.project(pt, normalized=True)) if ln.length > 0.0 else 0.0
        x, y = keys[int(j)]
        out.append((bv, x, y, t, d))
    return out


def band_wall_vertices(planar: PlanarMap, law: Law) -> frozenset[int]:
    """The band vertices standing at a wall beside a road: the band line of
    every riser (``model.band_riser``) and every stand-off band vertex
    (:func:`band_standoffs`).  A riser vertex closer to a ribbon than one
    weld spacing less the snap margin is no band line: it is a median or a
    sliver between carriageways (``planar/band_riser`` absorbs them), road
    ground that rides with the roads (MEASURED, round 2 iteration 1, KLAX
    33.94033, -118.39618: a median vertex 0.5 m off both carriageways held
    at the band's level stood 3.5 m over them)."""
    from shapely.geometry import Point, Polygon
    from shapely.strtree import STRtree

    from ..law.tables import snap_margin_m
    near_m = float(law.tables.emit.identity.weld_spacing_m) - snap_margin_m(law)
    ribs = []
    for f in planar.faces.values():
        if is_osm_ribbon_ref(f.ref):
            g = Polygon([planar.vertices[v].xy for v in planar.ring_vertices(f.ring)])
            ribs.append(g if g.is_valid else g.buffer(0.0))
    tree = STRtree(ribs) if ribs else None
    out: set[int] = set()
    from ..law.tables import riser_kerb_near_m
    for _fid, _lo, up in band_risers(planar, riser_kerb_near_m(law)):
        for v in up:
            p = Point(planar.vertices[v].xy)
            if tree is None or not len(tree.query(p, predicate="dwithin",
                                                   distance=near_m)):
                out.add(v)
    out.update(r[0] for r in band_standoffs(planar, law))
    return frozenset(out)
