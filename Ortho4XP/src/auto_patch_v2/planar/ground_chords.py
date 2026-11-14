"""A GRADED ROAD'S RING FOLLOWS ITS GROUND (issue #2070).

§37 (6) prices a groundside road at its RING VERTICES: each takes the ramp
target ``max(clamp(s), z_contact - grade * s)``, and ``clamp`` follows the
ground wherever the ground is cap-lawful.  The drawn surface between two
vertices is the straight chord, and the chord cap (``[chords]
pavement_max_chord_m``, 60 m) lets a road chord span ground the law never
read.  MEASURED ENTC (69.680905, 18.907925): ``small_roads:-255`` runs 48 m
from a car park (DEM 5.76) to the apron edge (7.76) in ONE chord, across a
1.3 m bank to the apron-level ground (7.97) — the drawn road stood 1.14 m
under that ground for 30 m, a cut the ramp law never asked for, read in
the sim as a road across the grass pulling the apron edge down.

THE RULE: a road-family ring chord whose ground departs from its straight
line by more than the cockpit's ``visual_m`` gains a vertex where the
ground departs most, recursively (a Douglas-Peucker split of the ground
profile), never closer than ``road_ground_min_chord_m`` to either end — so
the law's own per-vertex targets reach the surface.  A chord whose ground
the line already follows gains nothing.

NEVER ON A DESIGNED RAMP: where the road leaves an airside CONTACT (a ring
vertex on a ``law.tables.contact_roles`` face, the ramp law's MOUTH) over
ground it cannot follow inside its cap (``road_descent._forced``: coming
down from the mouth at the cap it still stands over the ground), the ramp
law builds the road on its DESIGN-grade ramp from the mouth's level to its
first meet with the ground (§37 (6a) (iii)).  That stretch's level is the
ramp's, not the ground's, and a vertex on it is a vertex the ramp's own walk
reads (``road_descent._hop`` holds the ramp's height over the floor from
the mouth's first hop on) — measured: a split 4 m out on a 12 m fill drop
took the shelf ramp of ``test_v2roadramp`` from 5 % to 6.7 %.  So no
split lands on a ring sample between a forced mouth and the design ramp's
first meet, walked along the ring both ways from the mouth (the ring's
length is the kerb's, never shorter than the route's).  Pure geometry over
a coordinate list; the DEM is read through ``z_many`` (frame metres).
"""
from __future__ import annotations

import math
import typing as _t

import numpy as np

from ..model.frame import XY

__all__ = ["road_ground_densifier"]

#: a ring vertex is a MOUTH when it stands this close to a contact face
#: (the identity spacing is 0.5 m)
MouthOf = _t.Callable[[XY], bool]


class Ramp(_t.NamedTuple):
    """What the ramp law builds from a mouth: the DESIGN grade it is built
    at, the CAP it may not be followed past, and the height over the ground
    from which a vertex stands on it (``road_descent.STAND_M``)."""
    design: float
    cap: float
    stand: float


def _split_ts(ts: np.ndarray, zs: np.ndarray, length: float, tol_m: float,
              min_piece_m: float, free: np.ndarray | None = None) -> list[float]:
    """The parameters (``0 < t < 1``) at which one sampled chord is split
    so every piece follows its ground within ``tol_m``; never at a sample
    ``free`` marks False."""
    out: list[float] = []
    stack = [(0, len(ts) - 1)]
    while stack:
        i, j = stack.pop()
        if j - i < 2:
            continue
        seg = ts[i:j + 1]
        line = zs[i] + (zs[j] - zs[i]) * (seg - ts[i]) / (ts[j] - ts[i])
        dev = np.abs(zs[i:j + 1] - line)
        far = ((seg - ts[i]) * length >= min_piece_m) & \
              ((ts[j] - seg) * length >= min_piece_m)
        if free is not None:
            far &= free[i:j + 1]
        dev = np.where(far, dev, 0.0)
        k = int(np.argmax(dev))
        if dev[k] <= tol_m:
            continue
        out.append(float(ts[i + k]))
        stack.extend(((i, i + k), (i + k, j)))
    return sorted(out)


def _walk(zs: list[np.ndarray], ds: list[np.ndarray], start: int, step: int,
          closed: bool, ramp: Ramp) -> list[tuple[int, int]]:
    """The ring samples ``(chord, sample)`` on the ramp the mouth at vertex
    ``start`` builds walking ``step`` (+1 forward, -1 back): from the
    mouth's ground at the design grade to its first meet with the ground —
    empty where the road follows its ground from the mouth inside its cap
    (the cap's cone meets the ground before it stands ``stand`` over it)."""
    n = len(zs)
    z_m = float(zs[start][0] if start < n else zs[n - 1][-1])
    on: list[tuple[int, int]] = []
    forced, cap_cone, s = False, True, 0.0
    c = start if step > 0 else start - 1
    for _ in range(n):
        if not 0 <= c < n:
            if not closed:
                break
            c %= n
        ks = range(1, len(zs[c])) if step > 0 else range(len(zs[c]) - 2, -1, -1)
        for k in ks:
            s += float(ds[c][k - 1] if step > 0 else ds[c][k])
            g = float(zs[c][k])
            if not math.isfinite(g) or z_m - ramp.design * s <= g:
                return on if forced else []           # the ramp's first meet
            if cap_cone:
                forced = forced or z_m - ramp.cap * s >= g + ramp.stand
                cap_cone = z_m - ramp.cap * s > g
            on.append((c, k))
        c += step
    return on if forced else []


def follow_ground(points: _t.Sequence[XY], z_many: _t.Callable, tol_m: float,
                  sample_m: float, min_piece_m: float,
                  mouth: MouthOf | None = None, ramp: Ramp | None = None) -> list[XY]:
    """``points`` (an open or closed coordinate list) with a vertex added
    wherever a chord's ground (``z_many(xs, ys)``) departs from the chord
    by more than ``tol_m``; every new vertex lies on the chord it splits.
    Ground the DEM cannot read (NaN) is never a reason to split; nor is a
    designed ramp's stretch (module docstring), where ``mouth`` names the
    ring vertices on a contact and ``ramp`` the ramp law's grades."""
    pts = list(points)
    if len(pts) < 2 or tol_m <= 0.0 or sample_m <= 0.0:
        return pts
    chords = list(zip(pts, pts[1:], strict=False))
    tss: list[np.ndarray] = []
    zss: list[np.ndarray] = []
    lens: list[float] = []
    for (ax, ay), (bx, by) in chords:
        d = math.hypot(bx - ax, by - ay)
        ts = np.linspace(0.0, 1.0, max(3, math.ceil(d / sample_m) + 1)) \
            if d >= 2.0 * min_piece_m and d > sample_m else np.array([0.0, 1.0])
        tss.append(ts)
        lens.append(d)
        zss.append(np.asarray(z_many(ax + (bx - ax) * ts, ay + (by - ay) * ts), dtype=float))
    free = [np.ones(len(ts), dtype=bool) for ts in tss]
    if mouth is not None and ramp is not None:
        closed = pts[0] == pts[-1]
        ds = [np.diff(ts) * d for ts, d in zip(tss, lens, strict=True)]
        for i, p in enumerate(pts[:-1] if closed else pts):
            if not mouth(p):
                continue
            for step in (1, -1):
                for c, k in _walk(zss, ds, i, step, closed, ramp):
                    free[c][k] = False
    out: list[XY] = [pts[0]]
    for ((ax, ay), (bx, by)), ts, zs, d, fr in zip(chords, tss, zss, lens, free, strict=True):
        if len(ts) > 2 and np.isfinite(zs).all():
            for t in _split_ts(ts, zs, d, tol_m, min_piece_m, fr):
                out.append((ax + (bx - ax) * t, ay + (by - ay) * t))
        out.append((bx, by))
    return out


def road_ground_densifier(airport, law, contacts: _t.Sequence = ()
                          ) -> "_t.Callable[[list[XY]], list[XY]] | None":
    """The ring densifier :func:`follow_ground` for this airport's DEM and
    law, or ``None`` when the airport carries no DEM to read.  ``contacts``
    are the plan polygons of the airside contact faces (the ramp law's
    ``contact_roles``): a ring vertex on one is a mouth."""
    dem = getattr(airport, "dem", None)
    if dem is None:
        return None
    z_many = getattr(dem, "z_many", None)
    if z_many is None:
        def z_many(xs, ys):      # a DEM that answers one point at a time
            return np.array([dem.z(float(x), float(y)) for x, y in zip(xs, ys, strict=True)])
    ch = law.tables.emit.chords
    tol = float(law.tables.emit.cockpit.visual_m)
    sample = float(ch.road_ground_sample_m)
    min_piece = float(ch.road_ground_min_chord_m)
    mouth = ramp = None
    if contacts:
        from shapely.geometry import Point
        from shapely.strtree import STRtree

        from ..airport.road_descent import STAND_M
        from ..law.tables import snap_margin_m
        tree = STRtree(list(contacts))
        near = float(snap_margin_m(law))
        ramp = Ramp(float(law.tables.emit.road_contact.ramp_grade),
                    float(law.tables.common.road_max_grade), STAND_M)

        def mouth(p: XY) -> bool:
            return len(tree.query(Point(p), predicate="dwithin", distance=near)) > 0
    return lambda ring: follow_ground(ring, z_many, tol, sample, min_piece, mouth, ramp)
