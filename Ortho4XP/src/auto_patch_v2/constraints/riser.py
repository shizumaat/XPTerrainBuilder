"""THE RISER OF A LOWER LEVEL IS A DECLARED STEP (#1214 round 6; owner
RULINGS 2026-10-19ai, 2026-10-23b/c).

A lower level ``<block>/p<k>`` (``planar/low_level``, kind ``low_level``)
is held rigid at ``z = D + y_lo`` by its landing rows; its riser strip
``<block>/p<k>#strip`` is the object's own storey between it and the block.
No OTHER row may span that storey: a row naming a vertex of the lower level
and a vertex of the block's side of the riser (the block's own faces and
the strip's far edge) is withdrawn here, at the one site every generator's
rows pass (``constraints.assembly``).  That is the pad's 1 % ceiling and
plane read across the strip, and a road ribbon's grade rows where a
landside road crosses the riser: the free-road / pad-road rule puts a road
inside the lower level on the lower level, and a road CROSSING the riser
has its step there, listed as a #1138 site (``riser_road_sites``), never
holding the level's edge up.  MEASURED KMCI ``building26/b1`` (A/B replay):
with the rows kept, 832 pad rows were relaxed in stage 2 and 112 of the
lower level's 622 vertices stood up to 2.04 m over it where ``big_roads``
ribbons crossed the riser.

TWO LOWER LEVELS AT TWO FLOORS (#1306, RULINGS 2026-10-27h): a level's
extension (``planar/low_extent``) stands at the bottom of the objects on it,
so two levels of one group may stand at different floors with a riser
between; a row naming vertices of both is withdrawn the same way.
"""
from __future__ import annotations

import typing as _t

from ..model.constraints import Row
from ..model.planar import STRIP_SUFFIX, PlanarMap, face_vertex_set

__all__ = ["riser_sets", "riser_exempt", "LANDING_INPUT_PREFIX", "STATS"]

#: the last run's #1138 sites: the road refs whose rows crossed a riser
STATS: dict[str, _t.Any] = {}

#: the input id a lower level's own landing row carries
#: (``constraints/platform.landing_rows``) -- the one row that spans it
LANDING_INPUT_PREFIX = "low_level:"


def riser_sets(planar: PlanarMap) -> "tuple[frozenset[int], frozenset[int], dict[int, str]]":
    """``(low, high, road)``: the vertices of every lower level's own faces,
    the vertices of its block's faces and its strip's far edge, and the
    road ref of every vertex a groundside road face carries (for the
    #1138 site list)."""
    lands = getattr(planar.registries, "landings", {}) or {}
    lows = {ref: rec["block"] for ref, rec in lands.items() if rec.get("kind") == "low_level"}
    if not lows:
        return frozenset(), frozenset(), {}
    blocks = set(lows.values())
    strips = {r + STRIP_SUFFIX for r in lows}
    low: set[int] = set()
    high: set[int] = set()
    strip: set[int] = set()
    road: dict[int, str] = {}
    for f in planar.faces.values():
        ref = str(f.ref)
        vs = face_vertex_set(planar, f)
        if ref in lows:
            low |= vs
        elif ref in blocks:
            high |= vs
        elif ref in strips:
            strip |= vs
        elif "road" in str(f.role):
            for v in vs:
                road.setdefault(v, ref)
    high |= strip - low
    return frozenset(low), frozenset(high - low), road


def riser_exempt(rows: list[Row], planar: PlanarMap, counts: dict) -> list[Row]:
    """``rows`` less every row spanning a lower level's riser (module
    docstring); the count and the road crossings go into ``counts``."""
    low, high, road = riser_sets(planar)
    if not low or not high:
        return rows
    floor = _level_floors(planar)
    out: list[Row] = []
    n = 0
    sites: set[str] = set()
    for r in rows:
        vs = _named(r)
        if len(vs) < 2:
            out.append(r)
            continue
        src = getattr(r, "source", None)
        ins = getattr(src, "inputs", ()) or ()
        if ins and str(ins[0]).startswith(LANDING_INPUT_PREFIX):
            out.append(r)
            continue
        if (any(v in low for v in vs) and any(v in high for v in vs)) \
                or len({floor[v] for v in vs if v in floor}) > 1:
            n += 1
            for v in vs:
                if v in road:
                    sites.add(road[v])
            continue
        out.append(r)
    counts["riser_rows_withdrawn"] = n
    counts["riser_road_sites"] = len(sites)
    STATS["riser_road_sites"] = sorted(sites)
    return out


def _level_floors(planar: PlanarMap) -> dict[int, float]:
    """``vertex -> its lower level's floor`` (``y_lo``) for the vertices of
    ONE floor only: a vertex two levels at different floors share (the
    riser's foot) is neither's."""
    lands = getattr(planar.registries, "landings", {}) or {}
    ys = {ref: round(float(rec["y_lo"]), 1) for ref, rec in lands.items()
          if rec.get("kind") == "low_level" and rec.get("y_lo") is not None}
    if len(set(ys.values())) < 2:
        return {}
    seen: dict[int, set] = {}
    for f in planar.faces.values():
        y = ys.get(str(f.ref))
        if y is None:
            continue
        for v in face_vertex_set(planar, f):
            seen.setdefault(v, set()).add(y)
    return {v: next(iter(s)) for v, s in seen.items() if len(s) == 1}


def _named(r: Row) -> tuple[int, ...]:
    """The vertices a row names, whatever its kind."""
    if hasattr(r, "terms"):
        return tuple(int(v) for v, _c in r.terms)
    if hasattr(r, "group"):
        return tuple(int(v) for v in r.group)
    if hasattr(r, "a"):
        return (int(r.a), int(r.b))
    return (int(r.v),) if hasattr(r, "v") else ()
