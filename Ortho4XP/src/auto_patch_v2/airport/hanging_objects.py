"""HANGING PACK OBJECTS SET THE CUT (owner RULINGS 2026-10-26p Q164–Q168;
2026-10-20am/an/ao/ar/at/au; #1298 EGLL/EGGW, #1138 KATL; findings
``docs/findings/1298-1138-lpackcut.md``).

A HANGING object is a pack object whose solids hang ``shell_floor_min_m`` or
more below its zero with NO plate of ``plate_min_area_m2`` at its walls'
bottom: it states no floor, so its DEPTH IS ITS WALLS' BOTTOM (Q167; 20am
"the bottom of the object is at the road"; 20ar the object wins over the
lidar).  Two kinds, by one witness — a flush ``ATTR_hard_deck``:

* a **COVER** carries a flush hard deck (``object_cut._cover_plate``): the
  pack's deck carries the airside (Q165) and the trench is cut under it.  It
  is read as a §33 (6) B shell with ITSELF as the cover
  (:func:`read_hanging_covers`); a co-placed FLOOR object overlapping it —
  EGLL's ``Na.obj`` beside ``N.obj`` — is read WITH it as one tunnel (Q166),
  and the floor is then that object's authored plate.
* a **PORTAL** carries none (``portal_objects``): a bare face at a bore's
  end (EGGW ``eggw_tex14``: one quad to −8.33 m) — the mouth's depth is its
  walls' bottom under its top (Q168, 20at).
* an **EDGE-WALL BRIDGE** carries none either, but its top IS a deck — plates
  of a plate's worth flush with its zero on walls hanging under them
  (:func:`edge_wall_reading`; KATL ``tunel_A/B/C``: deck slabs at 0 / −2.1 on
  a headwall to −23.2 and piers to −25.9).  It models the bridge's EDGES and
  no deck over the span (owner RULINGS 2026-10-27l, 20ao): the trench stops
  at its walls' backs, the span behind them stays graded at the deck level
  its top gives, and the depth is its walls' bottom (20am, 20ar).

Every number is a law-table value; nothing here names a pack or an airport.
"""
from __future__ import annotations

import math
import types
import typing as _t

import numpy as np

from . import obj8 as _obj8
from .object_cut import (
    ObjectCut,
    _base,
    _cover_plate,
    _face_normals_y,
    _plan_area,
    _plan_segments,
    placement_order,
    shell_cut,
    shell_reading,
)

__all__ = ["edge_wall_reading", "flush_hanging", "hanging_bottom", "read_hanging_covers"]


def hanging_bottom(v: np.ndarray, tris: np.ndarray, law) -> "float | None":
    """The walls' BOTTOM ``y`` of an object that hangs below its zero and
    states no floor there, else ``None``: its non-horizontal faces reach
    ``shell_floor_min_m`` under its zero, and no plate of a plate's worth
    stands within ``plate_bin_m`` of that bottom."""
    ob = law.tables.structures.tunnel.object
    if tris is None or not len(tris):
        return None
    ny = _face_normals_y(v, tris)
    walls = ny < ob.plate_normal_y_min
    if not walls.any():
        return None
    ymin = np.minimum(np.minimum(v[tris[:, 0], 1], v[tris[:, 1], 1]), v[tris[:, 2], 1])
    bottom = float(ymin[walls].min())
    if bottom > -ob.shell_floor_min_m:
        return None
    ymax = np.maximum(np.maximum(v[tris[:, 0], 1], v[tris[:, 1], 1]), v[tris[:, 2], 1])
    plates = (~walls) & (ymax <= bottom + ob.plate_bin_m)
    if plates.any() and float(_plan_area(v, tris)[plates].sum()) >= ob.plate_min_area_m2:
        return None
    return bottom


def flush_hanging(g: _obj8.ObjGeometry, law) -> "tuple[float, float] | None":
    """``(top, bottom)`` of a resource with NO hard deck whose solids top
    out flush with its zero (``cover_flush_m``) and hang to a bottom that
    states no floor (:func:`hanging_bottom`), else ``None`` — what a bare
    portal face and an edge-wall bridge share."""
    ob = law.tables.structures.tunnel.object
    if len(g.hard_deck) or not len(g.solid):
        return None
    v = g.vertices
    top = float(v[np.unique(g.solid), 1].max())
    if abs(top) > ob.cover_flush_m:
        return None
    bottom = hanging_bottom(v, g.solid, law)
    return None if bottom is None else (top, bottom)


def edge_wall_reading(o: _obj8.PlacedObject, g: _obj8.ObjGeometry, law
                      ) -> "tuple[float, tuple, tuple] | None":
    """``(depth, placed plan hull, deep wall segments)`` of an EDGE-WALL
    BRIDGE (module doc; owner RULINGS 2026-10-27l), else ``None``.  The
    deck: plates of ``plate_min_area_m2`` within ``cover_flush_m`` of its
    top.  The walls: its faces that are no plate and reach
    ``shell_floor_min_m`` under its zero, each as its plan segment in the
    airport frame — the trench stops at their back
    (``planar/structure_mouth.edge_wall_mouth``)."""
    from shapely.geometry import MultiPoint
    ob = law.tables.structures.tunnel.object
    hung = flush_hanging(g, law)
    if hung is None:
        return None
    top, bottom = hung
    v, t = g.vertices, g.solid
    plate = _face_normals_y(v, t) >= ob.plate_normal_y_min
    ys = v[t, 1]
    deck = plate & (ys.max(axis=1) >= top - ob.cover_flush_m)
    if not deck.any() or float(_plan_area(v, t)[deck].sum()) < ob.plate_min_area_m2:
        return None
    deep = (~plate) & (ys.min(axis=1) <= -ob.shell_floor_min_m)
    a, b, d, e, xo, yo = _obj8.placement_affine(o.xy, o.heading_deg)
    walls = tuple(tuple((a * x + b * z + xo, d * x + e * z + yo) for x, z in seg.coords)
                  for seg in _plan_segments(v, t[deep]))
    if not walls:
        return None
    hull = MultiPoint([(a * x + b * z + xo, d * x + e * z + yo)
                       for x, _y, z in v[np.unique(t)]]).convex_hull
    if hull.geom_type != "Polygon":
        return None
    return (top - bottom, tuple((float(x), float(y)) for x, y in hull.exterior.coords),
            walls)


def _co_placed(o, p, tol: float) -> bool:
    return (p is not o and p.path != o.path
            and math.hypot(p.xy[0] - o.xy[0], p.xy[1] - o.xy[1]) <= tol
            and abs(((p.heading_deg - o.heading_deg + 180.0) % 360.0) - 180.0) <= 1.0)


def _has_floor(cache, p, law) -> bool:
    """A FLOOR part: a plate of a plate's worth ``shell_floor_min_m`` under
    its zero (EGLL ``Na.obj``: its floor and ramps, no walls)."""
    ob = law.tables.structures.tunnel.object
    if p.resolved is None or cache.y_range(p.resolved)[0] > -ob.shell_floor_min_m:
        return False
    g = cache.geometry(p.resolved)
    if g is None or not len(g.solid):
        return False
    v, t = g.vertices, g.solid
    deep = (_face_normals_y(v, t) >= ob.plate_normal_y_min) & (
        np.maximum(np.maximum(v[t[:, 0], 1], v[t[:, 1], 1]), v[t[:, 2], 1])
        <= -ob.shell_floor_min_m)
    return bool(deep.any()) and float(_plan_area(v, t)[deep].sum()) >= ob.plate_min_area_m2


def _union(members, cache):
    """The co-placed members' geometry as ONE authored-frame object (they
    share the placement), with their genuine components re-indexed."""
    verts, comps, off = [], [], 0
    for p in members:
        g = cache.geometry(p.resolved)
        verts.append(g.vertices)
        for c in cache.genuine(p.resolved):
            comps.append(types.SimpleNamespace(tris=c.tris + off))
        off += len(g.vertices)
    return types.SimpleNamespace(vertices=np.concatenate(verts)), comps


def read_hanging_covers(placed: _t.Sequence[_obj8.PlacedObject], cache: _obj8.ResourceCache,
                        law, taken: _t.AbstractSet[str], msl: _t.Mapping[str, float],
                        k_by_res: dict) -> tuple[list[ObjectCut], list[str]]:
    """Every HANGING COVER (module doc) as an ``ObjectCut``, and one refusal
    line per cover the shell reading refuses.  ``taken`` are the placement
    ids a shell already took; ``k_by_res`` the per-resource label counter
    ``object_cut.read_shells`` keeps."""
    ob = law.tables.structures.tunnel.object
    out: list[ObjectCut] = []
    refused: list[str] = []
    used: set[str] = set(taken)
    for o in placement_order(placed):
        if o.id in used or o.resolved is None or _obj8.is_stock_library_resource(o.path):
            continue
        if cache.y_range(o.resolved)[0] > -ob.shell_floor_min_m:
            continue
        g = cache.geometry(o.resolved)
        if g is None:
            continue
        cover, area = _cover_plate(g, law)
        if cover is None:
            continue
        genuine = cache.genuine(o.resolved)
        tris = np.concatenate([c.tris for c in genuine]) if genuine else None
        bottom = hanging_bottom(g.vertices, tris, law)
        if bottom is None:
            continue
        box = getattr(o, "plan_bbox", None)
        floors = [p for p in placed
                  if p.id not in used and _co_placed(o, p, ob.cover_placement_tol_m)
                  and _has_floor(cache, p, law)
                  and (box is None or getattr(p, "plan_bbox", None) is None
                       or box.intersects(p.plan_bbox))]
        if floors:
            geom, comps = _union([o, *floors], cache)
            n_cover = sum(len(c.tris) for c in genuine)
            floor_faces = np.arange(sum(len(c.tris) for c in comps)) >= n_cover
            r = shell_reading(geom, comps, law, walls_to_floor=True, interior_from=floor_faces)
            shell_o = floors[0]
            note = (f"a SPLIT shell (RULINGS 2026-10-26p Q166): cover {_base(o.path)} "
                    f"(walls to {bottom:+.2f}) + floor "
                    + ", ".join(_base(p.path) for p in floors))
        else:
            r = shell_reading(g, genuine, law, floor_y=bottom, walls_to_floor=True)
            shell_o = o
            note = (f"a HANGING cover (RULINGS 2026-10-26p Q167): no floor, the depth is "
                    f"its walls' bottom {bottom:+.2f}")
        if isinstance(r, str):
            refused.append(f"{o.id} {_base(o.path)}: a hanging cover, but {r}")
            continue
        k = k_by_res.get(shell_o.path, 0)
        rec = shell_cut(shell_o, r, o, cover, area, k, cache, law, msl, (note,))
        if isinstance(rec, str):
            refused.append(rec)
            continue
        k_by_res[shell_o.path] = k + 1
        out.append(rec)
        used.update({o.id, *(p.id for p in floors)})
    return out, refused
