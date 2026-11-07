"""THE PACK SUPPLIES ITS OWN GROUND (issue #1362; spec
``docs/specs/pack-supplied-ground-spec.md``, ratified by the owner
2026-11-04, option A).

A pack may model the airport's GROUND as objects: an invisible
``ATTR_hard`` skin the aircraft rolls on, the textured ground and the
pavement decals over it, all authored in ONE frame (one anchor, one
heading).  Such a set is the surface authority, not a building: it is never
split into bodies, never read as a deck or a ramp, and our mesh stands just
under it.

THE WITNESS (geometry only, RULINGS 05e): the placements sharing one
origin and heading are the pack's ground when ONE of them carries
plan-bearing ``ATTR_hard`` triangles covering at least
:data:`RUNWAY_COVER_MIN` of the airport's runway area (apt.dat slabs).
X-Plane rolls aircraft only on its mesh or on a hard object surface, so a
hard surface under the runway is the ground the pack flies on; a bridge
plate or a helipad never covers half a runway.

WHAT IT BECOMES: every placement of the set carries ONE
``geom/terrain_deck.TerrainFit`` with ``ground=True`` and the SAME ``z0``
(the rigid L1 fit of the hard skin to the DEM, ``terrain_shaped.fit``), so
the partition skips it whole (``pack_partition``: a ``terrain_fit``
placement is one rigid body), the placement writer seats every row of the
set as ``OBJECT_MSL`` at that ``z0`` (``terrain_shaped.row_seats``) and the
patch under the hard skin takes the skin's top less ``UNDER_M``
(``constraints/terrain_shaped``).  Only the hard member carries the grid
the rows read; the others carry an empty one.  A COMPANION terrain mesh
(``terrain_mesh_witness``) is the author's ground under the set: then
nothing is seated or graded to it (``pipeline/build`` drops the fits) and
the rows keep their authored drape.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import os
import typing as _t

import numpy as np
from shapely.geometry import Polygon
from shapely.ops import unary_union

from ..geom.terrain_deck import UNDER_M, DeckGrid, TerrainFit
from .terrain_shaped import dem_many_of, fit, grid_of_triangles

__all__ = ["RUNWAY_COVER_MIN", "mark", "log_line",
           "notice"]

#: the share of the runway area the hard skin must cover (spec §2, ratified)
RUNWAY_COVER_MIN = 0.5

_EMPTY = DeckGrid(0.0, 0.0, np.full((1, 1), np.nan), np.full((1, 1), np.nan))


def _hard_triangles(g: _t.Any) -> np.ndarray:
    """The plan-bearing ``ATTR_hard`` triangles of an ``ObjGeometry`` as
    ``(n, 3, 3)`` authored points (none: shape ``(0, 3, 3)``)."""
    from .obj8 import HARD, _plan_bearing
    hard = getattr(g, "hardness", None)
    if hard is None or not len(hard):
        return np.zeros((0, 3, 3))
    tri = g.solid[np.asarray(hard) == HARD]
    tri = tri[_plan_bearing(g.vertices, tri)]
    return g.vertices[tri] if len(tri) else np.zeros((0, 3, 3))


def _to_frame(p: np.ndarray, xy: _t.Sequence[float], heading_deg: float) -> np.ndarray:
    """Authored ``(x, z)`` of ``p`` -> frame ``(east, north)`` (the rigid
    frame ``TerrainFit.local`` inverts)."""
    h = math.radians(heading_deg)
    s, c = math.sin(h), math.cos(h)
    x, z = p[..., 0], p[..., 2]
    return np.stack([xy[0] + x * c - z * s, xy[1] - (x * s + z * c)], axis=-1)


def _runway_cover(tris: np.ndarray, xy, heading_deg: float, runway_area) -> float:
    """The share of ``runway_area`` (frame polygon) the triangles cover."""
    if not len(tris) or runway_area is None or runway_area.is_empty:
        return 0.0
    plan = _to_frame(tris, xy, heading_deg)
    skin = unary_union([Polygon(t) for t in plan]).buffer(0)
    return float(skin.intersection(runway_area).area / runway_area.area)


def _runway_area(airport: _t.Any):
    slabs = [Polygon(rw.slab_corners) for rw in getattr(airport, "runways", ()) or ()]
    slabs = [p if p.is_valid else p.buffer(0) for p in slabs]
    return unary_union(slabs) if slabs else None


def _pack_local(o: _t.Any, pack_root: str) -> bool:
    from .obj8 import is_stock_library_resource
    from .pack import live_path_of
    if o.resolved is None or is_stock_library_resource(o.path):
        return False
    if not pack_root:
        return True
    root = os.path.normcase(os.path.abspath(pack_root))
    return os.path.normcase(os.path.abspath(live_path_of(o.resolved))).startswith(root)


def _ground_fits(airport: _t.Any, objects: _t.Sequence[_t.Any], cache: _t.Any,
                dem_many: _t.Callable) -> dict[str, TerrainFit]:
    """The pack-ground fits by placement id (module doc)."""
    from .msl_feet import origin_key
    area = _runway_area(airport)
    if area is None or area.is_empty:
        return {}
    pack = getattr(airport, "pack", None)
    root = getattr(pack, "pack_root", "") or ""
    frames: dict[tuple, list] = {}
    for o in objects:
        if _pack_local(o, root):
            frames.setdefault(origin_key(o.xy, o.heading_deg) + (round(o.agl_m, 3),),
                              []).append(o)
    out: dict[str, TerrainFit] = {}
    for members in frames.values():
        best = None
        for o in members:
            tris = _hard_triangles(cache.geometry(o.resolved))
            cover = _runway_cover(tris, o.xy, o.heading_deg, area)
            if cover >= RUNWAY_COVER_MIN and (best is None or cover > best[1]):
                best = (o, cover, tris)
        if best is None:
            continue
        o, cover, tris = best
        grid = grid_of_triangles(tris)
        got = fit(grid, o.xy, o.heading_deg, dem_many)
        if got is None:
            continue
        z0 = got[0]
        for m in members:
            g = grid if m.id == o.id else _EMPTY
            out[m.id] = TerrainFit(m.id, m.path, tuple(m.xy), float(m.heading_deg), z0,
                                   cover if m.id == o.id else 0.0,
                                   grid.area_m2 if m.id == o.id else 0.0, 0.0, g,
                                   ground=True)
    return out


def mark(airport: _t.Any, objects: _t.Sequence[_t.Any], cache: _t.Any) -> list:
    """``objects`` with every pack-ground placement stamped: its
    ``terrain_fit`` set, and out of the deck verdict and the below-grade /
    basin readings (as ``walled_plate.mark`` does for its class)."""
    fits = _ground_fits(airport, objects, cache, dem_many_of(airport.dem))
    if not fits:
        return list(objects)
    return [o if o.id not in fits else _dc.replace(
        o, terrain_fit=fits[o.id], terrain_feature=False, origin_built=False,
        hard_deck=None, deck_top_z=None,
        deck_kind="", deck_evidence=(), deck_plate=None, below_grade=None,
        below_grade_comps=(), witnesses=(), buried=())
        for o in objects]


def log_line(icao: str, fits: _t.Sequence[TerrainFit], companion: bool) -> str:
    """The build log's one line on the pack's own ground."""
    g = [f for f in fits if getattr(f, "ground", False)]
    if not g:
        return f"[pack-ground] {icao}: none"
    skin = max(g, key=lambda f: f.area_m2)
    head = (f"[pack-ground] {icao}: {len(g)} placement(s) in one frame, hard skin "
            f"{skin.path} covers {skin.follow:.0%} of the runways ({skin.area_m2:,.0f} m2)")
    if companion:
        return head + "; a companion terrain mesh is installed: kept as authored on it"
    return (head + f"; seated rigid at {skin.z0:.2f} m, our ground "
            f"{UNDER_M:.1f} m under it; NO companion terrain mesh found")


def notice(icao: str, fits: _t.Sequence[TerrainFit], pack: str) -> "dict | None":
    """The ``PackGroundNoMesh`` event's fields, or ``None`` when the pack
    supplies no ground of its own."""
    g = [f for f in fits if getattr(f, "ground", False)]
    if not g:
        return None
    skin = max(g, key=lambda f: f.area_m2)
    return {"icao": icao, "pack": pack, "resource": skin.path,
            "ground_m2": round(skin.area_m2, 1), "runway_cover": round(skin.follow, 3)}
