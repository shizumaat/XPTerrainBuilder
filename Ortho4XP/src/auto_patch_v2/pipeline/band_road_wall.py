"""THE BAND'S WALL AGAINST A ROAD INSIDE IT, DECLARED (owner RULINGS
2026-10-19a / 19i / 19k / 19l, issues #951 / #949; spec
``docs/specs/band-road-wall-joint-spec.md``).

``planar/band_riser`` gives a runway / taxi safety-area band a RISER face
one weld spacing wide beside every mapped-road ribbon inside it; the solve
neither bends nor caps across it (``solve/wall_cut.riser_cut_edges``,
``constraints/band_riser.riser_release``).  Where the road stands BELOW the
band the riser is the retaining wall 19i rules, and this module declares
it: ``terrace_joints`` records (``kind`` ``wall_terrace``, the record a
pack retaining wall publishes, ``publication.wall_terrace_joints``) along
the riser's MIDLINE — half a weld spacing off the ribbon, strictly between
the kerb and the band line, so every chord across the riser crosses it
exactly once and
both instruments forgive the declared step and price any excess; the
census exempts it from CRITICAL visual (19l) and from the runway-strip
wall check (19i: lawful in the safety area) by its shape label
:data:`LABEL`.  A road at or above the band (the band's cap holds it there,
13ar / 29r) declares nothing."""
from __future__ import annotations

import math
import typing as _t

from ..law import Law
from ..model.band_riser import band_risers
from ..model.planar import PlanarMap

__all__ = ["band_road_wall_joints", "LABEL"]

#: the shape label the record carries (``tools/check_grade`` quotes it)
LABEL = "band_road_wall"
#: the patch writes elevations to the centimetre (``publication``'s own)
_EMIT_Z_ROUND_M = 0.01


def band_road_wall_joints(planar: PlanarMap, law: Law,
                          z: _t.Sequence[float] | None = None
                          ) -> list[dict[str, _t.Any]]:
    """One ``wall_terrace`` record per riser face whose band side stands
    above its road kerb by more than the elevation materiality floor
    (module docstring).  Empty before a solve."""
    if z is None:
        return []
    from ..law.tables import riser_kerb_near_m
    risers = band_risers(planar, riser_kerb_near_m(law))
    from ..constraints.band_standoff import band_standoffs
    standoffs = band_standoffs(planar, law)
    if not risers and not standoffs:
        return []
    from .ribbon_steps import _to_ll
    to_ll = _to_ll(planar)
    floor = float(law.tables.emit.materiality.elevation_m)
    reach_w = float(law.tables.emit.identity.weld_spacing_m)
    band_ids, band_tree = _band_vertices(planar)
    out: list[dict[str, _t.Any]] = _standoff_records(planar, standoffs, z, floor, to_ll)
    for fid, lower, upper in risers:
        if not lower or not upper:
            continue
        # the LARGEST pair within a few weld spacings, not the nearest
        # partner's — and the band's vertices just beyond the riser count:
        # the census's chords run from them across the riser to the road
        # (round 3/4, KLAX 33.945963, -118.436316 and 33.94031, -118.39618:
        # 3.5-4.5 m chords stood 0.05-0.35 m over the riser-only step)
        lo_xy = [(planar.vertices[w].xy, float(z[w])) for w in lower]
        step = 0.0
        for l in lower:
            lx, ly = planar.vertices[l].xy
            zl = float(z[l])
            for b_ in band_tree.query_ball_point((lx, ly), _PAIR_REACH_W * reach_w):
                step = max(step, float(z[band_ids[b_]]) - zl)
        for v in upper:
            vx, vy = planar.vertices[v].xy
            _p, zl = min(lo_xy, key=lambda t: math.hypot(t[0][0] - vx, t[0][1] - vy))
            step = max(step, float(z[v]) - zl)
        if step <= floor:
            continue
        declared = round(step + _EMIT_Z_ROUND_M, 4)
        for line in _midlines(planar, law, fid, lower):
            out.append({
                "points": [list(to_ll(x, y)) for x, y in line],
                "step_m": declared, "declared_step_m": declared, "faced": False,
                "kind": "wall_terrace", "faces": [fid], "shapes": [LABEL],
                "gap": False, "roles": ["graded_strip"], "pairs": len(lower),
                "length_m": round(sum(math.dist(line[i], line[i + 1])
                                      for i in range(len(line) - 1)), 2),
                "height_m": round(step, 3), "emitted_step_m": round(step, 3),
                "agreement_m": 0.0})
    return out


def _midlines(planar: PlanarMap, law: Law, fid: int, lower) -> list[list]:
    """The riser face's midline parts: the boundary of its ribbons grown by
    half a weld spacing, inside the face (plan coordinates)."""
    import shapely
    from shapely.geometry import Polygon
    from shapely.ops import unary_union

    from ..model.planar import is_osm_ribbon_ref

    def poly(f):
        ring = [planar.vertices[v].xy for v in planar.ring_vertices(f.ring)]
        holes = [[planar.vertices[v].xy for v in planar.ring_vertices(h)]
                 for h in f.holes]
        g = Polygon(ring, holes)
        return g if g.is_valid else g.buffer(0.0)
    low = set(lower)
    ribs = [poly(f) for f in planar.faces.values() if is_osm_ribbon_ref(f.ref)
            and low & {v for c in (f.ring, *f.holes) for v in planar.ring_vertices(c)}]
    if not ribs:
        return []
    half = 0.5 * float(law.tables.emit.identity.weld_spacing_m)
    mid = unary_union(ribs).buffer(half, join_style="mitre", mitre_limit=2.0).boundary
    # THROUGH THE END EDGES (round 3, KLAX 33.945963, -118.436316): clipped
    # at the riser's own ring, the line stopped ON its end edge and a census
    # chord along that edge touched it without crossing it
    cut = mid.intersection(poly(planar.faces[fid]).buffer(half, join_style="mitre",
                                                          mitre_limit=2.0))
    return [list(p.coords) for p in shapely.get_parts(shapely.line_merge(cut)
                                                       if cut.geom_type == "MultiLineString"
                                                       else cut)
            if p.geom_type == "LineString" and len(p.coords) >= 2]


#: how far (in weld spacings) a riser's band vertex reads its kerb partners
_PAIR_REACH_W = 4.0
#: half-length of the declared line across one road page's stand-off pair
_STANDOFF_HALF_M = 0.5


def _standoff_records(planar: PlanarMap, standoffs, z, floor: float, to_ll
                      ) -> list[dict[str, _t.Any]]:
    """THE ROAD PAGE'S WALL (#951 spec Q12): per stand-off pair
    (``constraints/band_standoff``) whose band point stands above its road
    point by more than ``floor``, a short line across the pair's chord at
    its middle, perpendicular to it — the chord the census reads crosses
    it."""
    out: list[dict[str, _t.Any]] = []
    for band, road, d in standoffs:
        zb = sum(w * float(z[v]) for v, w in band)
        zg = sum(w * float(z[v]) for v, w in road)
        step = zb - zg
        if step <= floor or d <= 0.0:
            continue
        bx = sum(w * planar.vertices[v].xy[0] for v, w in band)
        by = sum(w * planar.vertices[v].xy[1] for v, w in band)
        gx = sum(w * planar.vertices[v].xy[0] for v, w in road)
        gy = sum(w * planar.vertices[v].xy[1] for v, w in road)
        mx, my = 0.5 * (bx + gx), 0.5 * (by + gy)
        nx, ny = -(gy - by) / d * _STANDOFF_HALF_M, (gx - bx) / d * _STANDOFF_HALF_M
        declared = round(step + _EMIT_Z_ROUND_M, 4)
        out.append({
            "points": [list(to_ll(mx - nx, my - ny)), list(to_ll(mx + nx, my + ny))],
            "step_m": declared, "declared_step_m": declared, "faced": False,
            "kind": "wall_terrace", "faces": [], "shapes": [LABEL],
            "gap": False, "roles": ["graded_strip"], "pairs": 1,
            "length_m": round(2.0 * _STANDOFF_HALF_M, 2), "height_m": round(step, 3),
            "emitted_step_m": round(step, 3), "agreement_m": 0.0})
    return out


def _band_vertices(planar: PlanarMap):
    """``(ids, KD-tree)`` of every runway / taxi band ring vertex that no
    OSM ribbon carries."""
    from scipy.spatial import cKDTree

    from ..constraints.band_standoff import is_band_zone_ref
    from ..model.planar import is_osm_ribbon_ref
    rib = {v for f in planar.faces.values() if is_osm_ribbon_ref(f.ref)
           for c in (f.ring, *f.holes) for v in planar.ring_vertices(c)}
    ids = sorted({v for f in planar.faces.values()
                  if f.role == "graded_strip" and is_band_zone_ref(f.ref)
                  for c in (f.ring, *f.holes) for v in planar.ring_vertices(c)} - rib)
    pts = [planar.vertices[v].xy for v in ids] or [(0.0, 0.0)]
    return ids, cKDTree(pts)
