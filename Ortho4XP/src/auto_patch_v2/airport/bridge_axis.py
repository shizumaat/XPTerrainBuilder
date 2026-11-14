"""THE UNMAPPED BRIDGE (#2090; RULINGS 2026-11-14f (1)): a pack deck that
carries no mapped route is read along its OWN AXIS when the geometry and the
map say it is a bridge — W1's alternative in ``bridge_witness.deck_witness``.

KDEN's Bridge_South_East spans the motorway (way -12158, at 50 degrees) on
an embankment the map does not draw: no mapped road runs along its plate,
so W1 failed (the motorway under it carries no bridge stretch) and the deck
took the graded face under its ring — the motorway — for its datum, its
ends 6.7 and 7.4 m under their ground.

THE WITNESS (:func:`axis_witness`), every part of it positive:

* AXIS: the plate ring's minimum rotated rectangle; its ends are the short
  sides' midpoints, the path its long axis (``deck_carry._edges``).
* W3 / W4 along the axis exactly as along a route (``driven_surface``,
  ``open_sky``).
* SPAN, both of: a mapped ``highway`` / ``railway`` way crosses the axis
  between the ends, AND the DEM at BOTH ends stands at least ``[bridge]
  clearance_minimum_m`` over the DEM where that way crosses — the ground at
  each end line stands a lawful clearance over the face under the deck.

Read wherever W1 fails.  A deck the witness does not hold keeps W1's
failure (a routeless ``flag`` stub still joins its host,
``bridge_witness._join_stubs``).  Nothing here
names a pack, a resource or an airport.
"""
from __future__ import annotations

import math
import typing as _t

import numpy as np
from shapely.geometry import LineString, Point, Polygon

__all__ = ["axis_route", "axis_span", "axis_witness"]

XY = tuple[float, float]


def axis_route(ring: Polygon, law) -> _t.Any:
    """The deck's own axis as a W1 ``Route`` with no way (module doc), or
    None for a ring with no long axis."""
    from .bridge_witness import Route
    from .deck_carry import _edges
    got = _edges(ring)
    if got is None:
        return None
    ea, eb, _s1, _s2, long_m, short_m = got
    if long_m <= short_m or long_m <= 0.0:
        return None
    a = ((ea[0][0] + ea[1][0]) / 2.0, (ea[0][1] + ea[1][1]) / 2.0)
    b = ((eb[0][0] + eb[1][0]) / 2.0, (eb[0][1] + eb[1][1]) / 2.0)
    d = math.dist(a, b)
    if d <= 0.0:
        return None
    u = ((b[0] - a[0]) / d, (b[1] - a[1]) / d)
    step = float(law.tables.structures.bridge.abutment_sample_step_m)
    path = LineString([(a[0] - u[0] * step, a[1] - u[1] * step),
                       (b[0] + u[0] * step, b[1] + u[1] * step)])
    return Route((), path, step, step + d, a, b, (-u[0], -u[1]), u, d, 1.0)


def axis_span(route, stations: _t.Sequence[XY], ways: _t.Sequence, law,
              ground: "_t.Callable | None") -> str:
    """The SPAN of an unmapped deck (module doc): ``way <id> <depth> m under
    both ends`` or ``""``."""
    if ground is None or len(stations) < 2:
        return ""
    mid = LineString([stations[0], stations[-1]])
    bar = float(law.tables.structures.bridge.clearance_minimum_m)
    ends = np.asarray(ground(np.array([stations[0][0], stations[-1][0]]),
                             np.array([stations[0][1], stations[-1][1]])), float)
    if not np.all(np.isfinite(ends)):
        return ""
    best = None
    for w in ways:
        t = w.tags or {}
        if len(w.points) < 2 or not ("highway" in t or "railway" in t):
            continue
        line = LineString(w.points)
        if not line.crosses(mid):
            continue
        hit = line.intersection(mid)
        pts = [hit] if isinstance(hit, Point) else list(getattr(hit, "geoms", []))
        for p in pts:
            if not isinstance(p, Point):
                continue
            g = float(np.asarray(ground(np.array([p.x]), np.array([p.y])), float)[0])
            if not math.isfinite(g):
                continue
            depth = float(ends.min()) - g
            if depth + 1e-9 >= bar and (best is None or depth > best[0]):
                best = (depth, w.id)
    return "" if best is None else f"way {best[1]} {best[0]:.1f} m under both ends"


def axis_witness(ring: Polygon, plate_up: np.ndarray, frame_faces: np.ndarray,
                 ways: _t.Sequence, law, ground=None) -> _t.Any:
    """The W1-W5 ``Witness`` of a deck read along its own axis, or the
    reason it is not one (``str``) (module doc)."""
    from . import bridge_witness as _bw
    if ground is None:
        return "no ground to read its span"
    r = axis_route(ring, law)
    if r is None:
        return "no long axis"
    br = law.tables.structures.bridge
    st = _bw._stations(r.path, r.s_a, r.s_b, float(br.abutment_sample_step_m))
    sp = axis_span(r, st, ways, law, ground)
    if not sp:
        return (f"no mapped way {float(br.clearance_minimum_m):.1f} m under both "
                f"axis ends")
    width = ring.area / max(r.s_b - r.s_a, 1e-6)
    box = LineString(st).buffer(1.0)
    layer, share = _bw.driven_surface(_bw._near(plate_up, box), st, law)
    if not layer:
        return f"W3 surface along the axis (best {share:.2f})"
    roof = _bw.open_sky(_bw._near(frame_faces, box), st, layer, law)
    if roof > _bw.ROOF_SHARE:
        return f"W4 open sky along the axis ({roof:.0%})"
    return _bw.Witness(r, st, layer, share, roof, f"axis {sp}", width_m=width)
