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
the line already follows gains nothing.  Pure geometry over a coordinate
list; the DEM is read through ``z_many`` (frame metres).
"""
from __future__ import annotations

import math
import typing as _t

import numpy as np

from ..model.frame import XY

__all__ = ["follow_ground", "road_ground_densifier"]


def _split_ts(ts: np.ndarray, zs: np.ndarray, length: float, tol_m: float,
              min_piece_m: float) -> list[float]:
    """The parameters (``0 < t < 1``) at which one sampled chord is split
    so every piece follows its ground within ``tol_m``."""
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
        dev = np.where(far, dev, 0.0)
        k = int(np.argmax(dev))
        if dev[k] <= tol_m:
            continue
        out.append(float(ts[i + k]))
        stack.extend(((i, i + k), (i + k, j)))
    return sorted(out)


def follow_ground(points: _t.Sequence[XY], z_many: _t.Callable, tol_m: float,
                  sample_m: float, min_piece_m: float) -> list[XY]:
    """``points`` (an open or closed coordinate list) with a vertex added
    wherever a chord's ground (``z_many(xs, ys)``) departs from the chord
    by more than ``tol_m``; every new vertex lies on the chord it splits.
    Ground the DEM cannot read (NaN) is never a reason to split."""
    pts = list(points)
    if len(pts) < 2 or tol_m <= 0.0 or sample_m <= 0.0:
        return pts
    out: list[XY] = [pts[0]]
    for (ax, ay), (bx, by) in zip(pts, pts[1:], strict=False):
        d = math.hypot(bx - ax, by - ay)
        if d >= 2.0 * min_piece_m and d > sample_m:
            ts = np.linspace(0.0, 1.0, max(3, math.ceil(d / sample_m) + 1))
            zs = np.asarray(z_many(ax + (bx - ax) * ts, ay + (by - ay) * ts), dtype=float)
            if np.isfinite(zs).all():
                for t in _split_ts(ts, zs, d, tol_m, min_piece_m):
                    out.append((ax + (bx - ax) * t, ay + (by - ay) * t))
        out.append((bx, by))
    return out


def road_ground_densifier(airport, law) -> "_t.Callable[[list[XY]], list[XY]] | None":
    """The ring densifier :func:`follow_ground` for this airport's DEM and
    law, or ``None`` when the airport carries no DEM to read."""
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
    return lambda ring: follow_ground(ring, z_many, tol, sample, min_piece)
