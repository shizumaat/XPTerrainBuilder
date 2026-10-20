"""THE BAND RISER RECORD (owner RULINGS 2026-10-19a / 19i, #951; spec
``docs/specs/band-road-wall-joint-spec.md``): the ref a band's riser face
carries (``planar/band_riser`` mints it) and the one reading of the map's
risers every consumer shares — the bending cut (``solve/wall_cut``), the row
release (``constraints/band_riser``) and the declared wall
(``pipeline/band_road_wall``)."""
from __future__ import annotations

import math

from .planar import is_osm_ribbon_ref

__all__ = ["RISER_SUFFIX", "is_band_riser_ref", "band_risers"]

#: owner RULINGS 2026-10-19a / 19i (#951): the ref suffix of a band's RISER
#: face — the strip of a runway / taxi safety-area band within one weld
#: spacing of a mapped-road ribbon inside it (``planar/band_riser``).
RISER_SUFFIX = ":riser"


def is_band_riser_ref(ref) -> bool:
    """A band riser face's ref (:data:`RISER_SUFFIX`)."""
    return str(ref or "").endswith(RISER_SUFFIX)


def band_risers(pm, near_m: float = 0.0
                ) -> list[tuple[int, frozenset[int], frozenset[int]]]:
    """``(face id, lower, upper)`` per band riser face: ``lower`` its ring
    vertices an OSM ribbon face carries (the road's kerb) — and, with
    ``near_m``, every other ring vertex within ``near_m`` of a ribbon's
    ring, which the emit welds onto that ring (round 4, KLAX 33.94047,
    -118.39619: a riser vertex 0.5 m off a second carriageway, held at the
    band's level, shipped inside that road's way and stood 2.9 m over it);
    ``upper`` the rest (the band line one weld spacing off).  Derived from
    the map, in face-id order; empty without a riser."""
    ids = [f.id for f in pm.faces.values()
           if getattr(f, "role", None) == "graded_strip" and is_band_riser_ref(f.ref)]
    if not ids:
        return []
    rib: set[int] = set()
    segs: list[tuple[tuple[float, float], tuple[float, float]]] = []
    for f in pm.faces.values():
        if is_osm_ribbon_ref(f.ref):
            for cyc in (f.ring, *f.holes):
                vs = pm.ring_vertices(cyc)
                rib.update(vs)
                if near_m > 0.0 and len(vs) >= 2:
                    segs += [(pm.vertices[vs[i]].xy, pm.vertices[vs[(i + 1) % len(vs)]].xy)
                             for i in range(len(vs))]
    near = _SegmentGrid(segs, near_m) if segs else None
    out = []
    for fid in sorted(ids):
        f = pm.faces[fid]
        vs = {v for cyc in (f.ring, *f.holes) for v in pm.ring_vertices(cyc)}
        low = vs & rib
        if near is not None:
            low |= {v for v in vs - rib if near.within(pm.vertices[v].xy)}
        out.append((fid, frozenset(low), frozenset(vs - low)))
    return out


class _SegmentGrid:
    """Is a point within ``reach`` of any of ``segs``?  Plain arithmetic on
    a bucket grid of cell ``reach`` — the model layer carries no geometry
    library (``test_model``, ``test_v2packmst``)."""

    def __init__(self, segs, reach: float) -> None:
        self.reach = float(reach)
        self.cells: dict[tuple[int, int], list] = {}
        c = self.reach
        for (ax, ay), (bx, by) in segs:
            seg = ((ax, ay), (bx, by))
            n = max(1, math.ceil(2.0 * math.hypot(bx - ax, by - ay) / c))
            keys: set[tuple[int, int]] = set()
            for k in range(n + 1):           # every half cell along it
                ci = math.floor((ax + (bx - ax) * k / n) / c)
                cj = math.floor((ay + (by - ay) * k / n) / c)
                keys.update((ci + di, cj + dj) for di in (-1, 0, 1) for dj in (-1, 0, 1))
            for key in keys:
                self.cells.setdefault(key, []).append(seg)

    def within(self, p) -> bool:
        x, y = p
        key = (math.floor(x / self.reach), math.floor(y / self.reach))
        for (ax, ay), (bx, by) in self.cells.get(key, ()):
            dx, dy = bx - ax, by - ay
            ll = dx * dx + dy * dy
            t = 0.0 if ll == 0.0 else max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / ll))
            if math.hypot(x - ax - t * dx, y - ay - t * dy) <= self.reach:
                return True
        return False
