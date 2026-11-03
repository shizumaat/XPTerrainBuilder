"""Rotating whole shapes in the patch editor (issue #1746).

Option-drag (Alt on Windows and Linux) near a shape's node turns the shape
about its centre; this is the geometry both apps share (the Mac app's
``SceneryKit/PatchRotate.swift`` is the twin, and both run the
``rotate_ways`` cases of ``tests/fixtures/patch_edit_ops.json``):

* :func:`centre` — the pivot: the area-weighted centroid of the closed
  ways, or the mean of the distinct nodes when they enclose no area;
* :func:`rotate_point` — one ``(lat, lon)`` turned about a pivot by an
  angle in degrees, counter-clockwise seen from above (north up), in the
  pivot's local east/north plane (longitude scaled by ``cos(lat)``);
* :func:`rotate_ways` (in ``patch_edit``) applies it to every node of the
  ways.  Elevations are kept; nothing merges.
"""
from __future__ import annotations

import math
import typing as _t

__all__ = ["centre", "rotate_point"]


def _k(lat: float) -> float:
    return max(math.cos(math.radians(lat)), 1.0e-6)


def centre(nodes: _t.Mapping[int, _t.Sequence], rings: _t.Iterable[_t.Sequence[int]]
           ) -> tuple[float, float] | None:
    """The pivot ``(lat, lon)`` of the ways whose refs are ``rings`` (a
    closed way repeats its first ref last); None with no known node."""
    rings = [[r for r in refs if r in nodes] for refs in rings]
    distinct = list(dict.fromkeys(r for refs in rings for r in refs))
    if not distinct:
        return None
    lat0 = sum(nodes[r][1] for r in distinct) / len(distinct)
    lon0 = sum(nodes[r][2] for r in distinct) / len(distinct)
    k = _k(lat0)
    area = cx = cy = 0.0
    for refs in rings:
        if len(refs) < 4 or refs[0] != refs[-1]:
            continue
        pts = [((nodes[r][2] - lon0) * k, nodes[r][1] - lat0) for r in refs]
        a = sx = sy = 0.0
        for (x1, y1), (x2, y2) in zip(pts, pts[1:], strict=False):
            cross = x1 * y2 - x2 * y1
            a += cross
            sx += (x1 + x2) * cross
            sy += (y1 + y2) * cross
        if abs(a) > 0.0:
            # a ring's centroid is (sx, sy) / (3 a); weight it by |a| / 2
            w = abs(a) / 2.0
            area += w
            cx += w * sx / (3.0 * a)
            cy += w * sy / (3.0 * a)
    if area <= 1.0e-18:
        return lat0, lon0
    return lat0 + cy / area, lon0 + cx / (area * k)


def rotate_point(lat: float, lon: float, pivot: tuple[float, float],
                 angle_deg: float) -> tuple[float, float]:
    """``(lat, lon)`` turned about ``pivot`` by ``angle_deg``
    (counter-clockwise, north up)."""
    plat, plon = pivot
    k = _k(plat)
    x, y = (lon - plon) * k, lat - plat
    c, s = math.cos(math.radians(angle_deg)), math.sin(math.radians(angle_deg))
    return plat + x * s + y * c, plon + (x * c - y * s) / k
