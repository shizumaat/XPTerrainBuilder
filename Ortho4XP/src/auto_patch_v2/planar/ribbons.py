"""THE MAPPED-ROAD RIBBONS' PASS (RULINGS 2026-09-30aa rules 2, 9-10; issue
#100) and the polygonise-and-claim pass it shares with ``overlay.
build_arrangement`` — split out of ``planar/overlay.py`` for its line budget
(lane roadmint100b).  ``overlay`` imports this module lazily at its two call
sites; this module reads ``overlay``'s merge passes at import, so the cycle
never closes at import time."""
from __future__ import annotations

import dataclasses as _dc

import shapely
from shapely.geometry import Polygon
from shapely.ops import unary_union
from shapely.strtree import STRtree

from ..law import Law
from ..model.planar import is_osm_ribbon_ref
from ..law.tables import rolled_on_roles
from .pad_cut import _drop_rim_midpoints, airside_clip, build_rim
from . import overlay as _ov
from .overlay import (PAD_AIRSIDE, Region, _claiming_region, _node_coords,
                      absorb_enclosed_pavement, dissolve_degenerate_holes,
                      dissolve_sliver_zones, merge_slivers)
from .platform import merge_platform_faces

__all__ = ["_ribbons_pass_c", "_faces_of", "_grid_parts"]

def _ribbons_pass_c(ribbon_cells, noded, regions, bands, law: Law, keeps: bool,
                    grid: float, ring_lines_of, counts: dict):
    """RULINGS 2026-09-30aa rules 2, 9-10 (#100) — THE MAPPED-ROAD RIBBONS
    JOIN THE FINISHED AIRSIDE.  The arrangement WITHOUT them (pass A and
    the pads, ``noded``) is finished first — claimed, merged, absorbed and
    its zone slivers dissolved (``_faces_of``) — and its AIRSIDE FACES are
    the union each ribbon is clipped by and welded to (``pad_cut.
    airside_clip``, the pads' own clip: crossings quantised to that
    arrangement's rim NODES, no stand-off, no sliver).  Finishing first is
    what makes the airside the same with and without the ribbons: a zone
    sliver the airside absorbs (HECA 05L/23R's zone1#9, 110.9 m²) is
    airside to the ribbon too, so the ribbon never re-cuts it.  Returns the
    ribbon ring lines, the regions with the ribbons, the finished node set
    (a later sliver dissolve treats it as frozen) and that airside union."""
    from ..law.tables import rolled_on_roles
    hosts_seen: dict = {}
    got = _faces_of(noded, regions, bands, law, keeps, None, hosts_seen=hosts_seen)
    base_faces = got[0]
    base_order = ({shapely.normalize(g).wkb: k for k, g in enumerate(got[-1])},
                  hosts_seen)
    rolled = rolled_on_roles(law)
    air_raw = unary_union([p for p, r in base_faces if r.role in rolled])
    air_f = shapely.set_precision(air_raw, grid)
    nodes_b = _node_coords(noded)
    rim_f = build_rim(air_f, law, nodes_b)
    keep_out = unary_union([shapely.set_precision(r.polygon, 0.0) for r in regions
                            if r.source == "cell" and r.role not in rolled])
    ribs, rc = airside_clip(
        [Region(c.role, c.ref, Polygon(c.ring, c.holes), c.code_number,
                c.code_letter, c.side, "cell") for c in ribbon_cells],
        law, air=air_f, nodes=nodes_b, rim=rim_f, select=lambda r: True,
        near_m=rim_f.band, keep_out=keep_out)
    counts.update({f"ribbon_{k}": v for k, v in rc.items()})
    # ON THE IDENTITY GRID, as the noding will put its ring (the pad's own
    # rule, ``apron_cut_to_pads``): a raw ribbon overlaps its own face by
    # less than the zone it lies in does
    ribs = [_dc.replace(r, polygon=q) for r in ribs
            for q in _grid_parts(r.polygon, grid)]
    if not ribs:
        return [], regions, None, air_raw, None
    own = {(float(x), float(y)) for r in ribs
           for ring in (r.polygon.exterior, *r.polygon.interiors)
           for x, y in ring.coords}
    lines, mid = _drop_rim_midpoints(ring_lines_of(ribs), rim_f, set(nodes_b),
                                     own, grid if keeps else 0.0)
    counts["ribbon_rim_midpoints_dropped"] = mid
    # the claim guard reads the RAW union: the grid would erase a sub-cell
    # airside needle (HECA dsf:objpav402, 0.4 m) and its face with it
    return lines, regions + ribs, set(nodes_b), air_raw, base_order


def _faces_of(noded, regions, bands, law: Law, keeps: bool, frozen,
              air_f=None, order=None, hosts_seen=None):
    """Polygonise ``noded`` and give every face its region, then the
    derivation-site merges (§41 (1)/(4), 08d (4a), 10h (1)).  ``air_f``
    (30aa, the ribbons' pass): the FINISHED airside — a face outside it is
    never an aircraft pavement's (a strip between a ribbon and the rim the
    raw apron cell overlaps is not apron)."""
    if air_f is not None:
        from ..law.tables import rolled_on_roles
        rolled = rolled_on_roles(law)
        from shapely.prepared import prep
        air_p = prep(air_f.buffer(0.0))
    polys = [g for g in shapely.get_parts(shapely.polygonize([noded]))
             if g.geom_type == "Polygon" and not g.is_empty]
    if order is not None:
        big = len(order)
        polys.sort(key=lambda g: order.get(shapely.normalize(g).wkb, big))
    tree = STRtree([r.polygon for r in regions])
    faces: list[tuple[Polygon, Region]] = []
    dropped = 0
    dropped_seam = 0
    for poly in polys:
        if bands and any(b.contains(poly.representative_point()) for b in bands):
            dropped_seam += 1
            continue
        hits = tree.query(poly, predicate="intersects")
        if air_f is not None and not air_p.contains(poly.representative_point()):
            hits = [j for j in hits if regions[int(j)].role not in rolled]
        best, best_a = _claiming_region(poly, regions, hits, law)
        if best is None or best_a < 0.5 * poly.area:
            dropped += 1
            continue
        faces.append((poly, best))
    if keeps:
        # RULINGS 2026-09-29n (4), #94: ONE platform, ONE face — a foreign
        # ring edge noded through the pad is dropped at this derivation site
        from .platform import merge_platform_faces
        faces, _plat_merged = merge_platform_faces(faces)
        PAD_AIRSIDE["platform_faces_merged"] = _plat_merged
        from .platform import MERGE_READ
        if MERGE_READ:
            PAD_AIRSIDE["platform_merge_read"] = "; ".join(
                f"{r} {a}->{'refused' if b is None else b}"
                for r, (a, b) in sorted(MERGE_READ.items()))
    ident = law.tables.emit.identity.min_distinct_spacing_m
    faces, merged = merge_slivers(faces,
                                  (ident * law.tables.emit.terrace.sliver_area_factor) ** 2,
                                  law.tables.emit.identity.weld_spacing_m)
    # §41 (1): an enclosed pavement face is its host's hole — absorbed HERE,
    # at the single derivation site, so every consumer downstream reads one
    # body with one law (owner RULINGS 2026-08-30l: trim at the derivation
    # site, never per consumer)
    faces, absorbed, detached = absorb_enclosed_pavement(
        faces, tuple(law.tables.emit.terrace.shape_roles),
        mouth_m=law.tables.emit.terrace.narrow_mouth_max_m)
    # §41 (4): a sliver ZONE face is dissolved into the pavement it borders
    # HERE, before the host's hole is cut — the same single-derivation-site
    # discipline (owner RULINGS 2026-08-30l) the absorption above follows
    faces, zs_dissolved, zs_dropped, zs_area, zs_rows = dissolve_sliver_zones(
        faces, law.tables.emit.terrace.strip_min_m2,
        law.tables.emit.terrace.strip_min_width_m,
        tuple(law.tables.emit.terrace.shape_roles),
        tuple(r for r, spec in law.tables.precedence.roles.items()
              if spec.rigid),
        frozen=frozen, hosts_seen=hosts_seen)
    faces, holes_gone = dissolve_degenerate_holes(
        faces, law.tables.emit.terrace.separation_m, ident ** 2)
    return (faces, dropped, dropped_seam, merged, absorbed, detached,
            zs_dissolved, zs_dropped, zs_area, zs_rows, holes_gone, polys)


def _grid_parts(g, grid: float) -> list[Polygon]:
    """``g`` put on the identity grid, as its parts (a ribbon region)."""
    q = shapely.set_precision(g, grid)
    q = q if q.is_valid else q.buffer(0.0)
    return [p for p in shapely.get_parts(q) if isinstance(p, Polygon)
            and not p.is_empty and p.area > 0.0]
