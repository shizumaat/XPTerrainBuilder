"""THE RISER IS THE STEP — the pair rows across a band's riser beside a
road inside it are released (owner RULINGS 2026-10-19a / 19i / 19k, #951;
spec ``docs/specs/band-road-wall-joint-spec.md``).

``planar/band_riser`` cuts the strip of a runway / taxi safety-area band
within one weld spacing of a mapped-road ribbon as its own face.  Between
§20b's stages (``constraints/road_ramp.reach_seed_rewrite``) every stage-2
pair row from a road ribbon vertex to a band vertex whose segment crosses
a riser face is withdrawn: a grade cap there would price the retaining
wall as a slope the road must climb (measured on the #715 twin, c951joint:
the shared kerb's rows held a road 7 m over its ground).

KEPT: a row that can only hold the road DOWN — a ceiling governing the
road vertex (``follows`` it, no floor), the kerb's band cap
(``zones.zone_bands``, 19a: the band leads where the road would stand
above it) — and every ``wall_terrace`` row.  The design energy across the
riser is ``solve/wall_cut.riser_cut_edges``.

ADDED: THE WALL STANDS ONLY WHERE THE BAND IS ABOVE THE ROAD.  One one-way
floor per riser band-line vertex, ``z[band] - z[kerb] >= 0`` against its
nearest kerb vertex (the band vertex follows): 19a / 19i make the riser a
retaining wall for a road BELOW the band; where the road stands above it,
inside the band the road grades WITH the zone (13ar / 29r) and the band
meets it level, as it did through the shared kerb before the cut.
MEASURED (KBUR iteration 1, no floor): a band island the cut decoupled
from a road 8 m above it fell to 202.6 m — 82 ``strip_seam_tear`` rows,
worst 8.35 m at 34.197845, -118.347643."""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

from ..law import Law
from ..model.band_riser import band_risers
from ..model.constraints import ConstraintSet, Linear, Source
from ..model.planar import PlanarMap, is_osm_ribbon_ref

__all__ = ["riser_release", "FLOOR_RULING"]

#: the ruling of the one-way floor that keeps the band from falling below
#: the road across a riser (module docstring)
FLOOR_RULING = ("band riser floor (owner RULINGS 2026-10-19a / 19i; "
                "13ar / 29r above the road)")


#: the generator name the floor rows carry
GEN = "band_riser"


def riser_release(planar: PlanarMap, law: Law, cs: ConstraintSet
                  ) -> tuple[ConstraintSet, dict[str, _t.Any]]:
    """``cs`` without the pair rows across a band riser (module docstring)
    and the count released."""
    risers = band_risers(planar)
    rep: dict[str, _t.Any] = {"risers": len(risers), "released": 0}
    if not risers:
        return cs, rep
    from shapely.geometry import LineString, Polygon
    from shapely.strtree import STRtree
    rib: set[int] = set()
    band: set[int] = set()
    for f in planar.faces.values():
        tgt = rib if is_osm_ribbon_ref(f.ref) else (
            band if f.role == "graded_strip" else None)
        if tgt is not None:
            for cyc in (f.ring, *f.holes):
                tgt.update(planar.ring_vertices(cyc))
    band -= rib
    polys = []
    for fid, _lo, _up in risers:
        ring = [planar.vertices[v].xy
                for v in planar.ring_vertices(planar.faces[fid].ring)]
        if len(ring) >= 3:
            g = Polygon(ring)
            polys.append(g if g.is_valid else g.buffer(0.0))
    tree = STRtree(polys)
    xy = {v: planar.vertices[v].xy for v in planar.vertices}

    def crosses(vs) -> bool:
        lo = [v for v in vs if v in rib]
        up = [v for v in vs if v in band]
        return any(len(tree.query(LineString([xy[a], xy[b]]), predicate="intersects"))
                   for a in lo for b in up)

    def holds_down(r) -> bool:
        if r.source.generator in ("wall_terrace", GEN):
            return True
        f = r.follows
        gov = {f} if isinstance(f, int) else set(f or ())
        return isinstance(r, Linear) and r.lo is None and bool(gov) and gov <= rib

    diffs = []
    for r in cs.diffs:
        if not holds_down(r) and crosses((r.a, r.b)):
            rep["released"] += 1
            continue
        diffs.append(r)
    linears = []
    for r in cs.linears:
        if len(r.terms) >= 2 and not holds_down(r) and \
                crosses([v for v, _c in r.terms]):
            rep["released"] += 1
            continue
        linears.append(r)
    floors = _floor_rows(planar, risers, xy)
    rep["floors"] = len(floors)
    return _dc.replace(cs, diffs=tuple(diffs),
                       linears=tuple(linears) + tuple(floors)), rep


def _floor_rows(planar: PlanarMap, risers, xy) -> list[Linear]:
    """One one-way floor per riser band-line vertex against its nearest
    kerb vertex (module docstring)."""
    import math
    out: list[Linear] = []
    seen: set[int] = set()
    for _fid, lower, upper in risers:
        lo = sorted(lower)
        if not lo:
            continue
        for v in sorted(upper):
            if v in seen:
                continue
            seen.add(v)
            x, y = xy[v]
            u = min(lo, key=lambda q: (math.hypot(xy[q][0] - x, xy[q][1] - y), q))
            out.append(Linear(((int(v), 1.0), (int(u), -1.0)), 0.0, None,
                              Source(GEN, FLOOR_RULING, (f"vertex:{v}",)),
                              follows=int(v)))
    return out
