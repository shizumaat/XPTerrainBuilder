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
from ..model.constraints import Band, ConstraintSet, Linear, Source
from ..model.planar import PlanarMap, is_osm_ribbon_ref

__all__ = ["riser_release", "FLOOR_RULING", "GRADED_RULING"]

#: the ruling of the one-way floor that keeps the band from falling below
#: the road across a riser (module docstring)
FLOOR_RULING = ("band riser floor (owner RULINGS 2026-10-19a / 19i; "
                "13ar / 29r above the road)")


#: the generator name the floor rows carry
GEN = "band_riser"


def riser_release(planar: PlanarMap, law: Law, cs: ConstraintSet,
                  levels: _t.Mapping[int, float] | None = None
                  ) -> tuple[ConstraintSet, dict[str, _t.Any]]:
    """``cs`` without the pair rows across a band riser (module docstring)
    and the count released."""
    from ..law.tables import riser_kerb_near_m
    risers = band_risers(planar, riser_kerb_near_m(law))
    from .band_standoff import band_standoffs
    standoffs = band_standoffs(planar, law)
    rep: dict[str, _t.Any] = {"risers": len(risers), "released": 0,
                              "standoffs": len(standoffs)}
    from .band_standoff import band_wall_vertices
    wall = band_wall_vertices(planar, law)
    graded = _graded_rows(planar, law, levels or {}, wall, cs)
    rep["graded"] = len(graded)
    if not risers:
        floors = _standoff_floors(standoffs, set())
        rep["floors"] = len(floors)
        return _dc.replace(cs, linears=tuple(cs.linears) + tuple(floors),
                           bands=tuple(cs.bands) + tuple(graded)), rep
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
    for _fid, lo, _up in risers:
        rib |= lo              # a riser vertex the emit welds onto a ribbon
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
    floors = [r for r in _floor_rows(planar, risers, xy) if r.terms[0][0] in wall]
    floors += _standoff_floors(standoffs, {r.terms[0][0] for r in floors})
    rep["floors"] = len(floors)
    return _dc.replace(cs, diffs=tuple(diffs),
                       linears=tuple(linears) + tuple(floors),
                       bands=tuple(cs.bands) + tuple(graded)), rep


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


def _standoff_floors(standoffs, seen: set[int]) -> list[Linear]:
    """The same one-way floor across a road page's stand-off
    (``constraints/band_standoff``, #951 spec Q12): the band's level at its
    point of the pair stands at or above the road's at its point; the band's
    vertices follow."""
    out = []
    for band, road, _d in standoffs:
        gov = tuple(v for v, _w in band)
        if len(band) == 1 and gov[0] in seen:
            continue
        terms: dict[int, float] = {}
        for v, w in band:
            terms[v] = terms.get(v, 0.0) + w
        for v, w in road:
            terms[v] = terms.get(v, 0.0) - w
        out.append(Linear(tuple((v, c) for v, c in terms.items() if c != 0.0), 0.0, None,
                          Source(GEN, FLOOR_RULING, (f"vertex:{gov[0]}",)),
                          follows=gov[0] if len(gov) == 1 else gov))
    return out


#: the ruling of the band's graded level at a wall (owner, #951 spec Q11)
GRADED_RULING = ("band graded level at a wall (owner 2026-10-19, #951 spec Q11: "
                 "the top of the band holds its own graded level)")


def _graded_rows(planar: PlanarMap, law: Law, levels: _t.Mapping[int, float],
                 wall: _t.AbstractSet[int], cs: ConstraintSet | None = None
                 ) -> list[Band]:
    """AT THE WALL THE BAND HOLDS ITS OWN GRADED LEVEL (owner 2026-10-19,
    #951 spec Q11: it does not fall to raw DEM).  Per band vertex at a wall
    (``constraints/band_standoff.band_wall_vertices``), a floor at the
    nearest stage-1 pavement vertex's solved level plus the zone's graded
    fall at that distance — its ceiling (``law.tables.zone_bounds``), never
    above the pavement — whichever generator shapes the band there (the zone
    rows, or the runway end's ``strips`` skirt: MEASURED KLAX 33.945963,
    -118.436316, the end skirt's chord bounds -7.2..+4.2 m let the band line
    sit at its DEM, a 2.55 m step inside the band over 7.1 m).  No row
    where the vertex stands beyond the zone (``zone_bounds`` is the DEM)."""
    if not wall or not levels:
        return []
    from ..law.tables import airside_stage_roles, zone_bounds
    air = airside_stage_roles(law)
    feet: dict[int, _t.Any] = {}
    for f in planar.faces.values():
        if f.role in air:
            for v in planar.ring_vertices(f.ring):
                if v in levels:
                    feet.setdefault(v, f)
    if not feet:
        return []
    from scipy.spatial import cKDTree
    ids = sorted(feet)
    tree = cKDTree([planar.vertices[v].xy for v in ids])
    end = _end_profile_levels(cs, levels, wall) if cs is not None else {}
    out: list[Band] = []
    for v in sorted(wall):
        if v in end:
            # IN A RUNWAY END AREA THE GRADED LEVEL IS THE END PROFILE'S
            # (round 5): the runway-end profile chord row the ``strips``
            # generator already states for this vertex is the one law there
            # — the lowest level it allows there, never the nearest
            # pavement zone's (MEASURED round 4: the zone's level lifted
            # end-area band vertices above the end profile, KBUR
            # ``runway_end_skirt`` 3 -> 16, worst 1.57 m)
            out.append(Band(int(v), end[v], None,
                            Source(GEN, GRADED_RULING, (f"vertex:{v}",))))
            continue
        d, j = tree.query(planar.vertices[v].xy)
        p = ids[int(j)]
        f = feet[p]
        _fl, ce = zone_bounds(law, f.role, float(d), f.code_number, f.code_letter)
        if ce is None:
            continue
        out.append(Band(int(v), float(levels[p]) + min(ce, 0.0), None,
                        Source(GEN, GRADED_RULING, (f"vertex:{v}",))))
    return out


#: ``constraints/strips``' generator name and its ``END_PROFILE_RULING``'s
#: head, quoted rather than imported: ``strips`` pulls the whole end-area
#: closure into every stage that rewrites the road (``stage_code``)
_STRIPS_GEN = "strips"
_END_CHORD = "rulesets.end_skirt runway-end profile chord"


def _end_profile_levels(cs: ConstraintSet, levels: _t.Mapping[int, float],
                        wall: _t.AbstractSet[int]) -> dict[int, float]:
    """``{vertex: level}`` for the wall vertices a runway-end profile chord
    row governs (``constraints/strips``' ``END_PROFILE_RULING``, ``z[v] -
    foot`` within its bounds, the foot on stage-1 levels): the level of the
    foot moved by the row's FLOOR: the lowest level the profile allows there
    — the band falls along the end profile as far as it lets it and no
    further, never to raw DEM below it (round 5 iteration 1 held it flush
    with the end instead: KLAX ``strip_seam_tear`` 4 -> 104, worst 6.6 m)."""
    out: dict[int, float] = {}
    for r in cs.linears:
        if r.source.generator != _STRIPS_GEN or not r.source.ruling.startswith(_END_CHORD) \
                or not isinstance(r.follows, int):
            continue
        v = r.follows
        if v not in wall or not r.terms or r.terms[0] != (v, 1.0):
            continue
        feet = r.terms[1:]
        if not feet or any(u not in levels for u, _c in feet):
            continue
        if r.lo is None:
            continue
        foot = -sum(c * float(levels[u]) for u, c in feet)
        lvl = foot + float(r.lo)
        out[v] = lvl if v not in out else max(out[v], lvl)
    return out
