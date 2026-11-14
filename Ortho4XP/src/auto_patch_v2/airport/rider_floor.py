"""A FOOTED RIDER ON NO HOST SURFACE STANDS ON ITS OWN GROUND — ONLY WHEN
CERTAIN (owner RULINGS 2026-11-13r, issue #2053).

Owner 16:59Z: *"A is correct in this situation, but i fear it could cause
issues with other packages... we need to be certain, if there's any
doubt, objects stay with their group where the author placed them."*

The case: SBRJ ``policeman4`` is the CONTENTS (F.9, :mod:`contents`) of
the floorless booth ``Guarita_Mil.obj``, whose walls are authored to
``y = -0.69``; 22b "the walls seat the unit" lifts the unit's zero 0.69 m
over the ground and the policeman floats with it.  He stands on NOTHING
of the booth: it has no floor, his feet are on the ground inside it.

:func:`free_rider_witness` answers, for one rider MEMBER's leaf bodies and
the walled SINGLETON that would host them, "is it CERTAIN the rider stands
on no surface of its host?"  True only when EVERY clause holds:

1. the rider is FOOTED (its parts carry ground feet) and every one of its
   feet lies inside the host's own walled outline (never the widened one);
2. the host and every member with a body over the rider's footprint read
   in ONE height frame with the rider (same AGL, no authored ``zero_y``,
   a known origin) and their files parse — a missing or ambiguous witness
   is doubt;
3. NO near-horizontal face (``|n_y| >= UP_FACE_NY_MIN``, EITHER winding:
   a ``no_cull`` floor may face down) of the host's file, or of any other
   member's file with a body over the rider, covers any of the rider's
   plan footprint at a height at or under the rider's lowest foot plus
   ``[basin] contact_band_m``.  The triangles themselves are read — never
   ``base_profile.floor_fraction``, which reads the contact band only and
   calls a terminal with a RAISED floor floorless (the named false
   positive the ruling refuses).

4. the host's group seat LIFTS the rider: the median of the host's own
   ground feet stands more than ``[placement] split_tol_m`` (the
   materiality the sim read is judged at) UNDER the rider's lowest foot —
   walls authored down past the ground the rider stands on.  A rider whose
   feet stand level with the walls' feet (a multi-file building's piece,
   a statue inside a fence) gains nothing by leaving and stays.

Anything else is doubt and the rider stays with its group.  Name-free.
"""
from __future__ import annotations

import functools
import math
import typing as _t

import numpy as np
import shapely
from shapely.geometry import Point

__all__ = ["free_rider_witness", "UP_FACE_NY_MIN", "COVER_EPS_M2"]

#: A face whose normal's |y| reaches this is a SURFACE something could
#: stand on (about 78 degrees from vertical): far below any plate
#: threshold, so a sloped or ramped floor counts as a floor (doubt).
UP_FACE_NY_MIN = 0.2
#: A face covers the rider when it overlaps his footprint by more than
#: this in plan (one square centimetre).
COVER_EPS_M2 = 1.0e-4


@functools.lru_cache(maxsize=256)
def _surfaces(path: str) -> "tuple[np.ndarray, np.ndarray] | None":
    """``(plan triangles (m, 3, 2) as authored (x, z), their lowest y)``
    of every near-horizontal SOLID face of the file at ``path``; None
    where it does not parse."""
    from .obj8 import parse_obj8
    from .slab_faces import tri_normals_y
    try:
        g = parse_obj8(path)
    except (OSError, ValueError, IndexError):
        return None
    tris = np.asarray(g.solid, dtype=np.int64).reshape(-1, 3)
    if not tris.shape[0]:
        return np.zeros((0, 3, 2)), np.zeros(0)
    ny, _a = tri_normals_y(g.vertices, tris)
    v = g.vertices[tris[np.abs(ny) >= UP_FACE_NY_MIN]]       # (m, 3, 3)
    return v[:, :, [0, 2]], v[:, :, 1].min(axis=1)


def _placed(member: _t.Any, xz: np.ndarray, ml: float, mo: float
            ) -> np.ndarray:
    """Authored plan ``(x, z)`` to the contents frame's metres ``(lon *
    mo, lat * ml)`` at ``member``'s origin and heading (the rotation of
    ``obj8._to_frame``)."""
    h = math.radians(float(member.heading_deg))
    s, c = math.sin(h), math.cos(h)
    x, z = xz[..., 0], xz[..., 1]
    o = member.origin
    return np.stack([float(o[1]) * mo + (x * c - z * s),
                     float(o[0]) * ml - (x * s + z * c)], -1)


def _covered(member: _t.Any, foot: _t.Any, top_y: float,
             ml: float, mo: float) -> "bool | None":
    """Does a surface of ``member``'s file at or under ``top_y`` cover more
    than ``COVER_EPS_M2`` of ``foot``?  None where the file is unread."""
    got = _surfaces(str(getattr(member, "authored_path", "") or ""))
    if got is None:
        return None
    xz, low = got
    near = low <= top_y
    if not near.any():
        return False
    polys = shapely.polygons(_placed(member, xz[near], ml, mo))
    hit = shapely.intersects(polys, foot)
    if not hit.any():
        return False
    area = shapely.area(shapely.intersection(polys[hit], foot))
    return bool((area > COVER_EPS_M2).any())


def free_rider_witness(plan: _t.Any, shims: _t.Sequence[_t.Any],
                       poly: _t.Callable[[int], _t.Any],
                       ml: float, mo: float, band_m: float,
                       lift_m: float = 0.0
                       ) -> _t.Callable[[_t.Sequence[int], int], bool]:
    """The 13r witness over ``shims`` (``footprint_unit._PShim``):
    ``free(rider bodies, host singleton) -> certain``.  ``poly(i)`` is a
    body's plan polygon in the frame's metres (``contents._poly``);
    ``lift_m`` clause 4's materiality."""
    parts = {p.pid: p for u in plan.units for m in u.members for p in m.parts}
    geoms: list = []
    ok: list[int] = []
    trees: list = []

    def index() -> "_t.Any":
        """The plan's body polygons and their tree, read on first use."""
        if not trees:
            geoms[:] = [poly(i) for i in range(len(shims))]
            ok[:] = [j for j, g in enumerate(geoms) if g is not None]
            trees.append(shapely.STRtree([geoms[j] for j in ok]) if ok else None)
        return trees[0]

    def frame(key) -> "tuple[_t.Any, float] | None":
        u = plan.units[key[0]]
        m = u.members[key[1]]
        if getattr(m, "origin", None) is None or getattr(m, "zero_y", 0.0):
            return None
        return m, float(getattr(u, "agl_m", 0.0) or 0.0)

    def others(rider: _t.Sequence[int], foot: _t.Any) -> set:
        """The members (other than the rider's) with a body over ``foot``."""
        mine = shims[rider[0]].key[:2]
        out = set()
        for k in index().query(foot):
            j = ok[int(k)]
            if j not in rider and shims[j].key[:2] != mine \
                    and geoms[j].intersection(foot).area > COVER_EPS_M2:
                out.add(shims[j].key[:2])
        return out

    def free(rider: _t.Sequence[int], host: int) -> bool:
        if index() is None or not rider:
            return False
        feet = [f for i in rider for q in shims[i].pids if q in parts
                and not parts[q].line for f in parts[q].feet]
        own, me, walls = frame(shims[host].key), frame(shims[rider[0]].key), geoms[host]
        gs = [geoms[i] for i in rider]
        if (not feet or own is None or me is None or walls is None
                or any(g is None for g in gs) or own[1] != me[1]):
            return False
        low = min(float(f[2]) for f in feet)
        base = sorted(float(f[2]) for q in shims[host].pids if q in parts
                      for f in parts[q].feet)
        if not base or base[len(base) // 2] >= low - lift_m:
            return False                    # clause 4: nothing lifts him
        if not all(walls.covers(Point(f[1] * mo, f[0] * ml)) for f in feet):
            return False
        foot = shapely.union_all(gs)
        top = low + band_m
        for key in sorted({shims[host].key[:2]} | others(rider, foot)):
            fr = frame(key)
            if fr is None or fr[1] != me[1]:
                return False
            hit = _covered(fr[0], foot, top, ml, mo)
            if hit is None or hit:
                return False
        return True
    return free
