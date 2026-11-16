"""AN ENTRANCE FACE'S FRONT WALL (#2062 spec R3b C; owner RULINGS
2026-11-06c (5), "the bottom of the ramp meets the bottom of the mouth
object that faces the ramp", applied to the face's wings; owner
2026-11-15T04:08Z Q1: expose the whole headwall the object models).

``trench_objects._wall_opening`` reads the OPENING between a face's jambs.
The FRONT is the face's front wall either side of it, as far as it stands
full height: its two ends across the bore (``Portal.front_xy``).  Read on
the object's own solids, per ACROSS STATION (``STEP_M`` apart):

* the faces that count are near-vertical (``|n_y|`` under
  ``split_level._VERTICAL_NY``), cross the bore (``|plan normal . into| >= 0.5``)
  and stand within the face reach along it;
* a station is FULL where their cross-sections there cover the face's
  whole height (its bottom to its top, gaps under ``cover_flush_m``): a
  lintel, a parapet band or a coping alone is no front;
* the chain starts at the opening's jambs and runs outward while the
  stations are full -- over another opening of the same object it runs on
  past its far jamb (a pier between two bores is front; the back plug
  behind an opening never is) -- stopping at a gap of more than one grid
  step, at a plan TURN of more than ``TURN_DEG`` off the wall at the jamb,
  or where it would leave the object's own footprint.

Only a WALLED face is read (its height ``shell_floor_min_m`` or more).
MEASURED KLAX ``Underpass_1``: openings 14.3 / 14.5 m (jamb to pier),
front 1136.8 .. 1198.9 (the headwall wings, 62.2 m).
Nothing here names a pack, a resource or an airport."""
from __future__ import annotations

import typing as _t

import numpy as np

from . import obj8 as _obj8
from .portal_objects import across_bore, opening_span
from .split_level import _VERTICAL_NY

__all__ = ["front_of", "jamb_to_jamb"]

#: the across-bore station spacing of the front read
STEP_M = 0.5
#: a plan turn of the wall beyond this ends the front
TURN_DEG = 30.0


def _zspan(acr: np.ndarray, z: np.ndarray, s: float) -> tuple[np.ndarray, np.ndarray]:
    """Each triangle's cross-section height range at across offset ``s``
    (``inf`` / ``-inf`` where it does not reach ``s``)."""
    a0, a1 = acr, np.roll(acr, -1, axis=1)
    z0, z1 = z, np.roll(z, -1, axis=1)
    on = (np.minimum(a0, a1) <= s) & (np.maximum(a0, a1) >= s)
    flat = a1 == a0
    den = np.where(flat, 1.0, a1 - a0)
    zz = np.where(flat, np.minimum(z0, z1), z0 + (z1 - z0) * (s - a0) / den)
    zz2 = np.where(flat, np.maximum(z0, z1), zz)
    lo = np.where(on, np.minimum(zz, zz2), np.inf).min(axis=1)
    hi = np.where(on, np.maximum(zz, zz2), -np.inf).max(axis=1)
    return lo, hi


def _full(acr, z, s: float, bottom: float, top: float, flush: float) -> bool:
    """Do the faces cover ``bottom .. top`` at ``s`` (gaps under ``flush``)?"""
    lo, hi = _zspan(acr, z, s)
    m = np.isfinite(lo)
    if not m.any():
        return False
    reach = None
    for a, b in sorted(zip(lo[m].tolist(), hi[m].tolist(), strict=True)):
        if reach is None:
            if a > bottom + flush:
                return False
            reach = b
        elif a <= reach + flush:
            reach = max(reach, b)
        else:
            break
    return reach is not None and reach >= top - flush


def _cross_faces(o: _obj8.PlacedObject, g: _obj8.ObjGeometry, xy, into, r: float):
    """``(across, z, plan angle, mean along)`` of ``o``'s near-vertical faces
    crossing the bore (``|plan normal . into| >= 0.5``) within ``r`` of the
    end ``xy`` along it -- per face, its corners' across offsets and heights,
    its plan direction folded to one sense, its mean station along the
    bore -- or ``None``."""
    v, t = g.vertices, g.solid
    a, b, d, e, xo, yo = _obj8.placement_affine(o.xy, o.heading_deg)
    px, py = a * v[:, 0] + b * v[:, 2] + xo, d * v[:, 0] + e * v[:, 2] + yo
    P = np.stack([px[t], py[t], v[t, 1]], axis=-1)
    n = np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0])
    nl = np.linalg.norm(n, axis=1)
    ok = nl > 1e-9
    n, P = n[ok] / nl[ok, None], P[ok]
    hn = np.hypot(n[:, 0], n[:, 1])
    wall = np.abs(n[:, 2]) < _VERTICAL_NY
    dot = (n[:, 0] * into[0] + n[:, 1] * into[1]) / np.maximum(hn, 1e-9)
    along = (P[:, :, 0] - xy[0]) * into[0] + (P[:, :, 1] - xy[1]) * into[1]
    sel = wall & (np.abs(dot) >= 0.5) & (np.abs(along).min(axis=1) <= r)
    if not sel.any():
        return None
    nx, ny = -into[1], into[0]
    acr = (P[sel, :, 0] - xy[0]) * nx + (P[sel, :, 1] - xy[1]) * ny
    ang = np.degrees(np.arctan2(n[sel, 1], n[sel, 0]))
    ang = np.where(dot[sel] < 0.0, ang + 180.0, ang) % 360.0
    return acr, P[sel, :, 2], ang, along.mean(axis=1)[sel]


def jamb_to_jamb(o: _obj8.PlacedObject, g: _obj8.ObjGeometry, xy, into, r: float, law,
                 bottom: float, outline=None) -> tuple[float, tuple, float]:
    """``(width, (jamb, jamb), top)``: the face read JAMB TO JAMB from the
    bore line (owner RULINGS 2026-11-16a: an opening narrower than one road
    lane is a misread) -- ``top`` the face's top where the bore crosses it
    (the highest of its crossing faces there), the span the :func:`front_of`
    chain from the bore line out while the face stands ``bottom`` .. that
    top.  ``(0.0, (), top)`` where it stands no wall's height there."""
    if into is None or g.solid is None or not len(g.solid):
        return 0.0, (), bottom
    got = _cross_faces(o, g, xy, into, r)
    if got is None:
        return 0.0, (), bottom
    acr, z = got[0], got[1]
    _lo, hi = _zspan(acr, z, 0.0)
    hi = hi[np.isfinite(hi)]
    top = float(hi.max()) if len(hi) else bottom
    p = (float(xy[0]), float(xy[1]))
    w, ends = front_of(o, g, xy, into, r, law, (p, p), bottom, top, (), outline)
    return w, ends, top


def front_of(o: _obj8.PlacedObject, g: _obj8.ObjGeometry, xy, into, r: float, law,
             edges: tuple, bottom: float, top: float, others: _t.Sequence[tuple] = (),
             outline=None) -> tuple[float, tuple]:
    """``(width, (end, end))`` of the FRONT of the entrance face at the
    bore end ``xy`` (module docstring) -- ``edges`` its opening's jambs,
    ``others`` the openings of the object's other ends, ``outline`` its
    plan -- or ``(0.0, ())``."""
    if into is None or not edges or g.solid is None or not len(g.solid):
        return 0.0, ()
    ob = law.tables.structures.tunnel.object
    flush = float(ob.cover_flush_m)
    if top - bottom < float(ob.shell_floor_min_m):
        return 0.0, ()
    grid = float(law.tables.emit.identity.min_distinct_spacing_m)
    got = _cross_faces(o, g, xy, into, r)
    if got is None:
        return 0.0, ()
    acr, z, ang, amid = got
    nx, ny = -into[1], into[0]
    spans = [sorted(across_bore(q, xy, into)) for q in (edges, *others) if q]
    e_l, e_r = sorted(across_bore(edges, xy, into))
    inside = None
    if outline is not None:
        from shapely.prepared import prep
        inside = prep(outline.buffer(grid))

    def chain(s0: float, sign: float) -> float:
        from shapely.geometry import Point
        last, miss, s, ref = s0, 0.0, s0, None
        while abs(s - s0) < 1000.0:
            s += sign * STEP_M
            jump = [hi if sign > 0 else lo for lo, hi in spans if lo < s < hi]
            if jump:
                # another opening of the object: the front runs on past it
                s = max(jump) if sign > 0 else min(jump)
                last, miss = s, 0.0
                continue
            lo_s, _hi = _zspan(acr, z, s)
            at = np.isfinite(lo_s)
            if ref is not None:
                at &= np.abs((ang - ref + 180.0) % 360.0 - 180.0) <= TURN_DEG
            ok_s = bool(at.any()) and _full(acr[at], z[at], s, bottom, top, flush)
            if ok_s and inside is not None:
                # on the wall itself (its faces' mean station along the bore)
                q = float(np.median(amid[at]))
                ok_s = inside.contains(Point(xy[0] + s * nx + q * into[0],
                                             xy[1] + s * ny + q * into[1]))
            if ok_s:
                if ref is None:
                    ref = float(np.median(ang[at]))
                last, miss = s, 0.0
            else:
                miss += STEP_M
                if miss > grid:
                    break
        return last
    return opening_span(chain(e_l, -1.0), chain(e_r, +1.0), xy, into)
