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


def band_standoffs(planar: PlanarMap, law: Law) -> list[tuple[int, int, float]]:
    """``(band vertex, road vertex, plan distance)`` for every runway / taxi
    band ring vertex whose nearest road-page vertex (a road-family face that
    is not an OSM ribbon) stands across the stand-off — within
    ``groundside_cutback_m`` + ``weld_spacing_m`` + the snap margin, never a
    shared vertex.  Sorted by band vertex."""
    from ..law.tables import family, snap_margin_m
    # the road family as ``constraints/roads.road_family_roles`` reads it
    # (the cross-section family's roles), without importing that generator
    roads = set(family(law, "road_cross_section").roles)
    road_v: set[int] = set()
    band_v: set[int] = set()
    for f in planar.faces.values():
        if f.role in roads and not is_osm_ribbon_ref(f.ref):
            tgt = road_v
        elif f.role == "graded_strip" and is_band_zone_ref(f.ref):
            tgt = band_v
        else:
            continue
        for cyc in (f.ring, *f.holes):
            tgt.update(planar.ring_vertices(cyc))
    band_v -= road_v
    if not road_v or not band_v:
        return []
    from scipy.spatial import cKDTree
    ids = sorted(road_v)
    tree = cKDTree([planar.vertices[v].xy for v in ids])
    ag = law.tables.zones.adjacent_ground
    ident = law.tables.emit.identity
    horizon = (float(ag.groundside_cutback_m) + float(ident.weld_spacing_m)
               + snap_margin_m(law))
    min_d = float(ident.min_distinct_spacing_m)
    out: list[tuple[int, int, float]] = []
    for b in sorted(band_v):
        d, j = tree.query(planar.vertices[b].xy)
        if min_d <= d <= horizon:
            out.append((b, ids[int(j)], float(d)))
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
    for _fid, _lo, up in band_risers(planar):
        for v in up:
            p = Point(planar.vertices[v].xy)
            if tree is None or not len(tree.query(p, predicate="dwithin",
                                                   distance=near_m)):
                out.add(v)
    out.update(b for b, _g, _d in band_standoffs(planar, law))
    return frozenset(out)
