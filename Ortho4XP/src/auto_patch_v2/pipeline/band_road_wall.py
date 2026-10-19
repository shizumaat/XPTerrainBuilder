"""THE BAND'S WALL AGAINST A ROAD INSIDE IT, DECLARED AT THE SHARED KERB
(owner RULINGS 2026-10-19a / 19i / 19k / 19l, issues #951 / #947).

A mapped-road ribbon inside a safety-area band shares its kerb with the
band (spec-author 30e (4)); ``constraints/zones.zone_bands`` gives that
kerb vertex the nearest pavement's CEILING only, so a road at or below the
band's grade keeps its own level (19a, 19k) and the band holds its own.
The riser between them is the first band edge off the kerb: one vertex at
road height, the next at band height — the retaining wall 19i rules.

Nothing is cut: no stand-off strip, no second edge beside the kerb (the
stand-off of #988 minted an unmeshable hairline wherever its ring ran one
identity spacing from a ribbon or band edge).  The wall is DECLARED where
the mesh already carries it, through the declared-step register (sidecar
``terrace_joints``, ``kind`` ``wall_terrace`` — the record a pack
retaining wall publishes, ``publication.wall_terrace_joints``), so both
instruments forgive exactly the declared riser across that line and price
any excess, and the census exempts it (19l).

The riser edges are :func:`band_kerb_risers`.  The line crosses each
riser edge at :data:`AT` of the way from the kerb vertex, perpendicular to
it, :data:`HALF_M` to each side.  Only a road
BELOW the band is a wall: a kerb at or above its band neighbour declares
nothing (the band leads there, 13ar / 29r)."""
from __future__ import annotations

import math
import typing as _t

from ..law import Law
from ..model.planar import PlanarMap, is_osm_ribbon_ref

__all__ = ["band_road_wall_joints", "band_kerb_risers", "AT", "HALF_M", "LABEL"]

#: where the declared line crosses the riser edge, from the kerb vertex
AT = 0.25
#: half-length of the declared line across the riser edge (metres)
HALF_M = 0.25
#: the patch writes elevations to the centimetre (``publication``'s own)
_EMIT_Z_ROUND_M = 0.01
#: the shape label the record carries: a wall of this family
LABEL = "band_road_wall"


def band_road_wall_joints(planar: PlanarMap, law: Law,
                          z: _t.Sequence[float] | None = None
                          ) -> list[dict[str, _t.Any]]:
    """One ``wall_terrace`` record per band riser edge off an in-band road's
    kerb where the road stands below the band (module docstring).  Empty
    before a solve."""
    if z is None:
        return []
    floor = float(law.tables.emit.materiality.elevation_m)
    out: list[dict[str, _t.Any]] = []
    for a, b in band_kerb_risers(planar, law):
        step = float(z[b]) - float(z[a])
        if step > floor:
            out.append(_record(planar, a, b, step))
    return out


def band_kerb_risers(planar: PlanarMap, law: Law) -> list[tuple[int, int]]:
    """``(kerb, band)`` for every ``graded_strip`` ring edge from a band
    kerb vertex (``PlanarMap.band_kerb_vertices``, never a pavement rim) to
    a vertex no OSM ribbon carries — sorted, each once."""
    from ..law.tables import airside_stage_roles
    kerb = planar.band_kerb_vertices(airside_stage_roles(law))
    if not kerb:
        return []
    rib: set[int] = set()
    for f in planar.faces.values():
        if is_osm_ribbon_ref(f.ref):
            for cyc in (f.ring, *f.holes):
                rib.update(planar.ring_vertices(cyc))
    out: set[tuple[int, int]] = set()
    for f in planar.faces.values():
        if f.role != "graded_strip":
            continue
        for cyc in (f.ring, *f.holes):
            vs = planar.ring_vertices(cyc)
            for i, p in enumerate(vs):
                q = vs[(i + 1) % len(vs)]
                for a, b in ((p, q), (q, p)):
                    if a in kerb and b not in rib and a != b:
                        out.add((a, b))
    return sorted(out)


def _record(planar: PlanarMap, a: int, b: int, step: float) -> dict[str, _t.Any]:
    """The declared line across the riser edge ``a`` (kerb) – ``b`` (band),
    in the vertices' own canonical lat/lon keys (an affine plan->lat/lon fit
    misplaced it by 0.3 m on a large patch — KLAX — and the census chord
    then missed it)."""
    (la, lo), (lb, mb) = planar.vertices[a].key, planar.vertices[b].key
    m_lat = 111_320.0
    m_lon = m_lat * math.cos(math.radians(la))
    ex, ey = (mb - lo) * m_lon, (lb - la) * m_lat
    d = math.hypot(ex, ey) or 1.0
    pla, plo = la + AT * (lb - la), lo + AT * (mb - lo)
    dla, dlo = ex / d * HALF_M / m_lat, -ey / d * HALF_M / m_lon
    declared = round(step + _EMIT_Z_ROUND_M, 4)
    return {"points": [[pla - dla, plo - dlo], [pla + dla, plo + dlo]],
            "step_m": declared, "declared_step_m": declared, "faced": False,
            "kind": "wall_terrace", "faces": [], "shapes": [LABEL],
            "gap": False, "roles": [], "pairs": 1,
            "length_m": round(2.0 * HALF_M, 2), "height_m": round(step, 3),
            "emitted_step_m": round(step, 3), "agreement_m": 0.0}
