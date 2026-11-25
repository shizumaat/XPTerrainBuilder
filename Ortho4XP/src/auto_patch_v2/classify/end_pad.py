"""PAVEMENT PAST A RUNWAY END, WITHIN ITS END AREA, IS A TURN PAD GRADED
WITH THE RUNWAY (owner 2026-11-25, #2286 TNCS, #2281 / #2282 EKVG: "a
widened runway-end pavement is a turn pad and must be graded with the
runway (flat across, runway grade along)").

``classify/blast_pad`` (#1332) read every pavement face past an end with no
declared overrun as a blast pad that follows the DEM (GCLA 36's chevrons
"follow the terrain down to the road").  At TNCS both turn-around pads
read so, and their pavement followed the slope beside the runway.

A TURN PAD is where aircraft turn around: an end NO TAXIWAY REACHES (the
owner's words, #2282) — no taxi centreline within one runway width of the
end's edge (:func:`taxi_reaches_end`).  At such an end the part of the face
within the end's END AREA (``model/end_area``: the RSA length, stopped at
the top of a drop) is the runway's — a runway-shoulder cell, graded with
the runway — and only what lies past the end area's crest follows the DEM
as a blast pad.  An end a taxiway reaches keeps #1332's blast pad
(MEASURED: KPHX's and KBNA's FAA blast pads, 8,400 / 3,800 m2 each, stay).
TNCS 12's end area holds 55 m on level ground, 30's 30 m to its drop.

Nothing here names an airport; build-time impact: one end-area read per
airport (cached by the caller) and a box clip per blast-pad face.
"""
from __future__ import annotations

import math

from shapely.geometry import LineString, Polygon

from .evidence import polygon_parts

__all__ = ["end_pad_split", "taxi_reaches_end"]


def end_pad_split(face: Polygon, rw, end_name: str, length_m: float,
                  floor_m2: float) -> tuple[list[Polygon], list[Polygon]]:
    """``(turn pad parts, blast pad parts)`` of ``face``, a blast pad past
    ``rw``'s end ``end_name`` whose end area runs ``length_m`` from the end
    (module doc); parts under ``floor_m2`` are dropped."""
    a, b = rw.ends[0].xy, rw.ends[1].xy
    L = math.hypot(b[0] - a[0], b[1] - a[1])
    if L <= 0.0 or length_m <= 0.0:
        return [], [p for p in polygon_parts(face) if p.area >= floor_m2]
    ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
    (ox, oy), (dx, dy) = (a, (-ux, -uy)) if rw.ends[0].name == end_name else (b, (ux, uy))
    x0, y0, x1, y1 = face.bounds
    w = math.hypot(x1 - x0, y1 - y0) + math.hypot(ox - x0, oy - y0)
    px, py = -dy, dx
    box = Polygon([(ox + px * w, oy + py * w), (ox - px * w, oy - py * w),
                   (ox - px * w + dx * length_m, oy - py * w + dy * length_m),
                   (ox + px * w + dx * length_m, oy + py * w + dy * length_m)])
    pad = [p for p in polygon_parts(face.intersection(box)) if p.area >= floor_m2]
    rest = [p for p in polygon_parts(face.difference(box)) if p.area >= floor_m2]
    return pad, rest


def taxi_reaches_end(rw, end_name: str, taxi_lines) -> bool:
    """True when a taxi centreline of ``taxi_lines`` stands within one
    runway width of ``rw``'s end ``end_name`` — the edge across the slab
    there (module doc)."""
    a, b = rw.ends[0].xy, rw.ends[1].xy
    L = math.hypot(b[0] - a[0], b[1] - a[1])
    if L <= 0.0:
        return True
    ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
    ox, oy = a if rw.ends[0].name == end_name else b
    h = 0.5 * float(rw.width_m)
    edge = LineString([(ox - uy * h, oy + ux * h), (ox + uy * h, oy - ux * h)])
    return any(ln.distance(edge) <= float(rw.width_m) for ln in taxi_lines)
