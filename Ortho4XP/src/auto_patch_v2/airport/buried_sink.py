"""A SINK THAT BURIES ITS BUILDING ON EVERY SIDE IS NOT A STATEMENT ABOUT
OUR GROUND (#2293; owner sim read 2026-11-27T00:04Z, app 1.0.585: "the
hangar ... is sunken, probably expecting a level pad, as it is cut into
the hill there with a retaining wall").

Owner RULINGS 2026-10-14g (1) keeps an ``OBJECT_AGL`` row as authored: its
height over the ground is the author's statement about OUR terrain.  An
unsplit SINK (``authored_landing.is_sink``, a negative column) is kept
the same way (``dsf_write.conversions_for_dump``, #1214 round 3 R2): an
author sinks a building into a slope so its low side meets the grade.

A sink sized for ANOTHER terrain says something else.  Where the author's
mesh carried a hill over a site that real ground has cut level -- a pad
under a retaining wall -- the author sank the building by that hill's
height at his anchor.  On our ground the same column puts the building's
floor under the surface on EVERY side: no wall meets the grade, its doors
and floor are buried.  Our ground requires the change (14g), so the row
converts and is seated on our surface like any other on-ground row.

THE RULE (:func:`buried_rows`), a witness in the geometry and the design
surface, never a pack, an airport or a coordinate:

* the row is ``OBJECT_AGL`` with a column at or under ``-bar_m``
  (a shallower sink can bury nothing by more than the bar);
* its resource is a STOCK one -- it resolves through the library index,
  not inside the pack (a pack's own object is the split's to seat: "the
  split seats a sink", #1214 R2; the census of the owner's built tiles
  flipped a KMCI road bridge at -7 m and LFPG decks at -2 m until this) --
  to an OBJ8 with STATIC solid geometry (``msl_feet.static_vertices``);
* its FLOOR -- the drape at the row, plus the column, plus the higher of
  0 and its lowest static vertex (a skirt under ``y = 0`` is meant to be
  buried; geometry standing above ``y = 0`` is the author's own lift) --
  stands more than ``bar_m`` under the design surface at EVERY station of
  its plan outline (the convex hull of its static vertices: its corners
  and a station every ``STEP_M`` along its edges).  One station within the
  bar -- a low side that meets the grade -- keeps the author's row;
* its plan covers at least ``MIN_PLAN_M2`` (a building: a pole, a column
  or a lamp is sunk to shorten it, never for a hill);
* THE HILL IS THERE (:func:`_hill_beside`): somewhere within ``REACH_M``
  outside its outline our surface stands at least the sink's depth over
  the drape at the row -- the rise the author's mesh smoothed over the
  site.  A sink on open ground (a canopy or a tank lowered on a flat
  apron: the height trick) keeps the author's row.

The caller hands the rows it has SETTLED (split, kept, a terrain feature)
in ``skip``: their seats are another rule's.  Pure geometry over a
surface callable; nothing is written here.
"""
from __future__ import annotations

import math
import os
import typing as _t

import numpy as np

from ..model.placement import KIND_AGL

__all__ = ["buried_rows", "outline_stations",
           "sinks_box", "STEP_M", "REACH_M", "MIN_PLAN_M2", "BOX_PAD_M"]

Surface = _t.Callable[[float, float], "float | None"]

#: outline stations are taken this far apart along the hull (m)
STEP_M = 2.0
#: the hill is looked for this far outside the outline (m): a retaining
#: wall's crest stands within a few metres of the building it was cut for
REACH_M = 10.0
#: a candidate's mesh is read this far about its row (m): the half-span
#: of a large hangar plus ``REACH_M``
BOX_PAD_M = 80.0
#: the smallest plan a buried building covers (m2): a 4 m x 5 m site office
MIN_PLAN_M2 = 20.0


def outline_stations(v: np.ndarray, step_m: float = STEP_M) -> np.ndarray:
    """``(n, 2)`` OBJ8 ``(x, z)`` stations of the plan outline of static
    vertices ``v`` (``(m, 3)``): the corners of their convex hull and a
    station every ``step_m`` along each hull edge (a degenerate hull, a
    line or a point, gives its own points)."""
    from shapely import MultiPoint
    hull = MultiPoint([(float(x), float(z)) for x, _y, z in v]).convex_hull
    ring = getattr(hull, "exterior", None)
    if ring is None:
        return np.asarray(list(hull.coords), float).reshape(-1, 2)
    pts = np.asarray(ring.coords, float)
    out = []
    for (x0, z0), (x1, z1) in zip(pts[:-1], pts[1:], strict=True):
        n = max(1, int(math.ceil(math.hypot(x1 - x0, z1 - z0) / step_m)))
        out.extend((x0 + (x1 - x0) * k / n, z0 + (z1 - z0) * k / n) for k in range(n))
    return np.asarray(out, float)


def _placer(row: _t.Any) -> _t.Callable[[float, float], tuple[float, float]]:
    """OBJ8 ``(x, z)`` -> ``(lat, lon)`` for ``row`` (``msl_feet._foot_needs``'
    convention: ``east = x cos h - z sin h``, ``north = -(x sin h + z cos h)``)."""
    from .anchor_rule import _m_per_deg
    lat, lon = float(row.lat), float(row.lon)
    h = math.radians(float(row.heading_deg))
    c, s = math.cos(h), math.sin(h)
    ml, mo = _m_per_deg(lat)

    def to(x: float, z: float) -> tuple[float, float]:
        return lat - (x * s + z * c) / ml, lon + (x * c - z * s) / mo
    return to


def _hill_beside(row: _t.Any, v: np.ndarray, surface: Surface,
                reach_m: float = REACH_M, step_m: float = STEP_M) -> bool:
    """Does our surface rise, somewhere within ``reach_m`` outside the
    outline of static vertices ``v``, at least the row's sink depth over
    the drape at the row?  Read at each outline station pushed out from
    the hull's centre by ``reach_m / 2`` and by ``reach_m``."""
    drape = surface(float(row.lat), float(row.lon))
    stations = outline_stations(v, step_m)
    if drape is None or not len(stations):
        return False
    need = float(drape) - float(row.elevation or 0.0)
    to = _placer(row)
    cx, cz = stations.mean(axis=0)
    for x, z in stations:
        d = math.hypot(x - cx, z - cz) or 1.0
        for r in (0.5 * reach_m, reach_m):
            g = surface(*to(x + (x - cx) / d * r, z + (z - cz) / d * r))
            if g is not None and float(g) >= need:
                return True
    return False


def _is_buried(row: _t.Any, v: np.ndarray, surface: Surface, bar_m: float,
              step_m: float = STEP_M) -> bool:
    """Is the building of ``row`` (static vertices ``v``) more than
    ``bar_m`` under ``surface`` at every outline station at its AUTHORED
    seat?  ``False`` where the drape at the row or at any station does not
    read (nothing is guessed)."""
    drape = surface(float(row.lat), float(row.lon))
    stations = outline_stations(v, step_m)
    if drape is None or not len(stations):
        return False
    floor = float(drape) + float(row.elevation or 0.0) + max(0.0, float(v[:, 1].min()))
    to = _placer(row)
    for x, z in stations:
        g = surface(*to(x, z))
        if g is None or float(g) - floor <= bar_m:
            return False
    return True


def _candidates(dump: _t.Any, bar_m: float, pack_root: "str | None",
                skip: _t.AbstractSet[int] = frozenset()) -> list[int]:
    """The rows a buried sink can be: stock ``OBJECT_AGL`` ``.obj`` rows
    sunk by at least ``bar_m``, not in ``skip``."""
    rows = list(getattr(dump, "placements", ()) or ())
    return [i for i, p in enumerate(rows)
            if i not in skip and p.kind == KIND_AGL
            and float(p.elevation or 0.0) <= -bar_m
            and str(p.def_path).lower().endswith(".obj")
            and not _in_pack(pack_root, str(p.def_path))]


def _in_pack(pack_root: "str | None", res: str) -> bool:
    """Does ``res`` resolve inside the pack (``deck_riders_of_pack``'s
    test)?  Such a row is the split's, never a stock sink."""
    return bool(pack_root) and os.path.isfile(os.path.join(pack_root, res.lstrip("/")))


def sinks_box(dump: _t.Any, bar_m: float = 1.0, pack_root: "str | None" = None
              ) -> "tuple[float, float, float, float] | None":
    """``(min_lon, min_lat, max_lon, max_lat)`` the candidates' outline and
    hill stations read (each row grown by ``BOX_PAD_M``), or ``None`` with
    none -- the box the placement stage widens its mesh reading to (a stock
    row is in no rebake plan's bounds)."""
    rows = list(getattr(dump, "placements", ()) or ())
    pts = [(float(rows[i].lon), float(rows[i].lat)) for i in _candidates(dump, bar_m, pack_root)]
    if not pts or bar_m <= 0.0:
        return None
    lons, lats = zip(*pts, strict=True)
    dlat = BOX_PAD_M / 111320.0
    dlon = dlat / max(math.cos(math.radians(max(abs(v) for v in lats))), 1e-6)
    return min(lons) - dlon, min(lats) - dlat, max(lons) + dlon, max(lats) + dlat


def buried_rows(dump: _t.Any, pack_root: str | None, surface: Surface, *,
                bar_m: float, skip: _t.AbstractSet[int] = frozenset(),
                index: "_t.Mapping[str, str] | None" = None,
                counts: "dict[str, int] | None" = None) -> frozenset[int]:
    """The rows of ``dump`` whose sink buries their building on every side
    (module docstring).  ``index`` is the library index (``None`` reads the
    install's, read-only); ``bar_m`` 0 disarms.  ``counts`` gains
    ``buried_sinks_seated`` when any row qualifies."""
    if bar_m <= 0.0:
        return frozenset()
    rows = list(getattr(dump, "placements", ()) or ())
    cand = _candidates(dump, bar_m, pack_root, skip)
    if not cand:
        return frozenset()
    if index is None:
        index = _library_index(pack_root)
    from . import obj8 as _obj8
    from .msl_feet import static_vertices
    from .pack import authored_source
    memo: dict[str, "np.ndarray | None"] = {}
    out = set()
    for i in cand:
        res = str(rows[i].def_path)
        if res not in memo:
            phys = _obj8.resolve_resource(res, pack_root, index)
            path = authored_source(phys, pack_root)[0] if phys else None
            try:
                memo[res] = static_vertices(_obj8.parse_obj8(path)) if path else None
            except (OSError, ValueError):
                memo[res] = None
        v = memo[res]
        if (v is not None and _plan_m2(v) >= MIN_PLAN_M2
                and _is_buried(rows[i], v, surface, bar_m)
                and _hill_beside(rows[i], v, surface)):
            out.add(i)
    if counts is not None and out:
        counts["buried_sinks_seated"] = len(out)
    return frozenset(out)


def _plan_m2(v: np.ndarray) -> float:
    """The area of the convex hull of static vertices ``v`` in plan (m2)."""
    from shapely import MultiPoint
    return float(MultiPoint([(float(x), float(z)) for x, _y, z in v]).convex_hull.area)


def _library_index(pack_root: str | None) -> "_t.Mapping[str, str] | None":
    """The install's library index, read-only (never rebuilt here; the
    ``sibling_stage`` reading); ``None`` when it cannot be read -- a stock
    resource then does not resolve and its row is kept."""
    if not pack_root:
        return None
    try:
        import O4_File_Names as FNAMES

        from . import obj8 as _obj8
        xplane = os.path.dirname(os.path.dirname(os.path.normpath(pack_root)))
        return _obj8.read_library_index(_obj8.library_index_path(
            FNAMES.airport_mod_cache_root(), xplane))
    except Exception:                        # no engine frame: nothing resolves
        return None
