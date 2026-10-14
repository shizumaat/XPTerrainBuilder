"""THE PROPORTIONS OF A PAVED SHAPE: how wide it is at its widest place and
how long it runs — what says ROAD or LOT (owner RULINGS 2026-10-14d (2);
lane drape229).

* :func:`inscribed_width_m` — the face's WIDTH, the diameter of its maximum
  inscribed circle (RULINGS 2026-09-14g item 4: never ``2 A / P``).  Moved
  down from ``planar/overlay`` so ``classify`` can read it; ``overlay``
  re-exports it under its old name.
* :func:`typical_width_m` — how wide the shape is WHERE MOST OF IT IS:
  four times the median distance from its interior to its boundary (a
  strip of width ``w`` reads ``w`` less its ends; a square of side ``s`` reads
  ``0.59 s``).  The widest place is the wrong reading for a proportion: a
  road's junction holds a disc twice its carriageway (HECA ``T3_road``:
  inscribed 30.6 m, typical 9 m).
* :func:`road_proportioned` — LONG AND NARROW: at most ``max_width_m``
  typical width (the free-road width, ``classify/rules.toml [service]
  free_max_width_m``) and its RUN — area over typical width, the length of
  a strip that wide — at least ``min_aspect`` widths (``[apron]
  arm_min_aspect``, the "follows a path" elongation).  A curved road reads
  as a road: the run follows the shape, never a box (a minimum rotated
  rectangle reads HECA's 600 m ``T3_road`` sheet 163 m wide)."""
from __future__ import annotations

import shapely
from shapely.geometry import Polygon

import numpy as np

__all__ = ["inscribed_width_m", "typical_width_m", "road_proportioned"]

#: how many interior samples :func:`typical_width_m` reads at most
_SAMPLES = 4000


def inscribed_width_m(poly: Polygon, tol: float = 0.01) -> float:
    """THE WIDTH OF A FACE: twice the radius of its MAXIMUM INSCRIBED
    CIRCLE — the diameter of the largest disc the shape holds, i.e. how
    wide it is at its WIDEST place.

    Deliberately NOT ``2 A / P``, which is a mean-width proxy: a shape
    with one fat end and a long tail reads narrow under the proxy while
    holding a wide disc, and on the owner's 1.0.331 HECA patch the proxy
    called 153 zone faces narrower than 3 m where the inscribed circle
    calls 42 (RULINGS 2026-09-14g item 4 — "use the INSCRIBED circle")."""
    if poly is None or poly.is_empty or poly.area <= 0.0:
        return 0.0
    try:
        return 2.0 * float(shapely.maximum_inscribed_circle(poly, tol).length)
    except Exception:                                      # pragma: no cover
        return 0.0


def typical_width_m(poly: Polygon) -> float:
    """Four times the MEDIAN interior distance to the boundary (module
    doc), read on a regular grid of at most :data:`_SAMPLES` points; 0.0
    for a degenerate shape."""
    if poly is None or poly.is_empty or poly.area <= 0.0:
        return 0.0
    x0, y0, x1, y1 = poly.bounds
    step = max(0.25, float(np.sqrt((x1 - x0) * (y1 - y0) / _SAMPLES)))
    xs, ys = np.meshgrid(np.arange(x0 + 0.5 * step, x1, step),
                         np.arange(y0 + 0.5 * step, y1, step))
    xs, ys = xs.ravel(), ys.ravel()
    inside = shapely.contains_xy(poly, xs, ys)
    if not inside.any():
        return inscribed_width_m(poly)
    d = shapely.distance(shapely.points(xs[inside], ys[inside]), poly.boundary)
    return 4.0 * float(np.median(d))


def road_proportioned(poly: Polygon, max_width_m: float, min_aspect: float) -> bool:
    """Whether ``poly`` has ROAD proportions (module doc); a degenerate
    shape, or ``max_width_m`` 0, is not a road."""
    w = typical_width_m(poly)
    if w <= 0.0 or max_width_m <= 0.0 or w > max_width_m:
        return False
    return float(poly.area) / w >= float(min_aspect) * w
