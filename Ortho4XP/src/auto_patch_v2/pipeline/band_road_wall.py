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
the in-band ROADS' OUTLINE half a weld spacing off the kerb
(:func:`_kerb_records`, round 6), so every chord from the road to the band
crosses it, and both instruments forgive the declared step and price any
excess; the
census exempts it from CRITICAL visual (19l) and from the runway-strip
wall check (19i: lawful in the safety area) by its shape label
:data:`LABEL`.  A road at or above the band (the band's cap holds it there,
13ar / 29r) declares nothing."""
from __future__ import annotations

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
    """The ``wall_terrace`` records of the band's walls against the roads
    inside it: per part of the in-band roads' outline, and per road-page
    stand-off pair, where the band stands above the road by more than the
    elevation materiality floor (module docstring).  Empty before a solve."""
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
    out: list[dict[str, _t.Any]] = _standoff_records(planar, standoffs, z, floor, to_ll)
    if risers:
        out.extend(_kerb_records(planar, law, risers, z, floor, to_ll))
    return out


def _kerb_records(planar: PlanarMap, law: Law, risers, z, floor: float, to_ll
                  ) -> list[dict[str, _t.Any]]:
    """THE WALL IS DECLARED AT THE KERB, ACROSS THE WHOLE BAND (#951 round
    6).  The line is the in-band ribbons' outline grown by half a weld
    spacing, with the same reach around every riser vertex within the
    kerb-weld reach (``law.tables.riser_kerb_near_m``) that is off the
    ribbon (``constraints/band_riser`` holds it at road level): every kerb
    vertex stands inside it and every band vertex outside, so EVERY chord from the
    road to the band crosses it — past a riser's ends, between a ribbon's
    split pieces, into a median's band tip — where the riser's midline
    (rounds 2-5) was crossed only by the chords through the riser face
    (MEASURED round 4, KLAX taxiway F 33.9403, -118.3962: 3.5-4.5 m chords
    from the band tip between two carriageways touched no declared line).
    Clipped to the runway / taxi bands (the owner's "for roads in safety
    area, wall is correct"); one record per connected part, declared at the
    largest step of a road-to-band (or road-to-other-road) pair within the
    census's pairing reach whose chord crosses that part — the wall's
    actual height there."""
    import shapely
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    from shapely.strtree import STRtree

    from ..model.planar import is_osm_ribbon_ref

    def poly(f):
        ring = [planar.vertices[v].xy for v in planar.ring_vertices(f.ring)]
        holes = [[planar.vertices[v].xy for v in planar.ring_vertices(h)]
                 for h in f.holes]
        g = Polygon(ring, holes)
        return g if g.is_valid else g.buffer(0.0)
    from ..constraints.band_standoff import is_band_zone_ref
    band_faces = [f for f in planar.faces.values()
                  if f.role == "graded_strip" and is_band_zone_ref(f.ref)]
    w = float(law.tables.emit.identity.weld_spacing_m)
    area = unary_union([poly(f) for f in band_faces]).buffer(w, **_MITRE)
    road_of: dict[int, set[str]] = {}
    rib_polys = []
    for f in planar.faces.values():
        if is_osm_ribbon_ref(f.ref):
            g = poly(f)
            if not g.intersects(area):
                continue
            rib_polys.append(g)
            for c in (f.ring, *f.holes):
                for v in planar.ring_vertices(c):
                    road_of.setdefault(v, set()).add(str(f.ref).split("#", 1)[0])
    if not rib_polys:
        return []
    kerb = set(road_of).union(*(lo for _f, lo, _u in risers))
    # HALF A WELD SPACING, offset as the riser is: the emit snaps every
    # vertex to the identity lattice (up to ``snap_margin_m``, 0.35 m), so
    # the line keeps that margin from the kerb (0 m) and from the riser's
    # band line (1 m) — MEASURED iteration 2, KLAX 33.945963, -118.436316:
    # a line at 0.93 m stood beyond the band line the emit snapped to
    # 0.84 m off the kerb, and the 3.9 m riser chords crossed nothing.  A
    # kerb vertex off the ribbon (within the kerb-weld reach) brings its
    # own reach into the outline, so it stays on the road side.
    grow = 0.5 * w
    off = sorted(set().union(*(lo for _f, lo, _u in risers)) - set(road_of))
    outline = unary_union([g.buffer(grow, **_MITRE) for g in rib_polys]
                          + [shapely.Point(planar.vertices[v].xy).buffer(grow)
                             for v in off]).boundary
    cut = outline.intersection(area)
    merged = shapely.line_merge(cut) if cut.geom_type == "MultiLineString" else cut
    parts = [p for p in shapely.get_parts(merged)
             if p.geom_type == "LineString" and len(p.coords) >= 2]
    if not parts:
        return []
    import numpy as np
    from scipy.spatial import cKDTree
    kerb_ids = sorted(v for v in kerb if area.contains(shapely.Point(planar.vertices[v].xy)))
    band_ids = sorted({v for f in band_faces for c in (f.ring, *f.holes)
                       for v in planar.ring_vertices(c)} - kerb)
    if not kerb_ids:
        return []
    ids = kerb_ids + band_ids
    xy = np.array([planar.vertices[v].xy for v in ids], dtype=float)
    zz = np.array([float(z[v]) for v in ids], dtype=float)
    nk = len(kerb_ids)
    reach = _PAIR_REACH_W * w
    pr = cKDTree(xy).query_pairs(reach, output_type="ndarray")
    pr = pr[(pr[:, 0] < nk) | (pr[:, 1] < nk)]        # band to band: no wall
    i, j = np.minimum(pr[:, 0], pr[:, 1]), np.maximum(pr[:, 0], pr[:, 1])
    d = np.where(j < nk, np.abs(zz[i] - zz[j]), zz[j] - zz[i])
    keep = d > floor
    i, j, d = i[keep], j[keep], d[keep]
    # road to road only between two different roads (the next road across
    # a narrow band: both walls, round 5)
    ok = [jj >= nk or (ids[ii] in road_of and ids[jj] in road_of
                       and not road_of[ids[ii]] & road_of[ids[jj]])
          for ii, jj in zip(i.tolist(), j.tolist(), strict=True)]
    i, j, dz = i[ok], j[ok], d[ok]
    pa, pb = i, j
    step = [0.0] * len(parts)
    if len(pa):
        segs = shapely.linestrings(np.stack([xy[pa], xy[pb]], axis=1))
        hit = STRtree(parts).query(segs, predicate="intersects")
        for s_i, p_i in zip(hit[0], hit[1], strict=True):
            if dz[int(s_i)] > step[int(p_i)]:
                step[int(p_i)] = dz[int(s_i)]
    out: list[dict[str, _t.Any]] = []
    for line, s in zip(parts, step, strict=True):
        if s <= floor:
            continue
        declared = round(s + _EMIT_Z_ROUND_M, 4)
        out.append({
            "points": [list(to_ll(x, y)) for x, y in line.coords],
            "step_m": declared, "declared_step_m": declared, "faced": False,
            "kind": "wall_terrace", "faces": [], "shapes": [LABEL],
            "gap": False, "roles": ["graded_strip"], "pairs": 0,
            "length_m": round(float(line.length), 2),
            "height_m": round(s, 3), "emitted_step_m": round(s, 3),
            "agreement_m": 0.0})
    return out


_MITRE = dict(join_style="mitre", mitre_limit=2.0)
#: how far (in weld spacings) a kerb vertex reads its band partners: the
#: census pairs strip nodes up to 6 m apart (``strip_seam_tear``)
_PAIR_REACH_W = 6.0
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
