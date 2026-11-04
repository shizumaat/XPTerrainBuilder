"""PAVEMENT PAST A RUNWAY END IS A BLAST PAD THAT FOLLOWS THE DEM (owner
2026-11-04, "Yes to recommendations", #1332).

A pack often paints the chevron area beyond a runway end as its own
pavement polygon while the apt.dat declares no overrun (GCLA 36: an 84 m x
61 m page past the end, ``overrun_m`` 0, which the lot branch read as a
``parking_lot`` and graded flat at the lot law, with the roads below cut
through the fill).  The owner: the chevron pavement "follows the terrain
down to the road".  So such a face is no value surface: it is NOT a cell of
the classification.  The ground there is the end area's (graded by the end
profile within its length, ``model/end_area``) and raw DEM beyond it; the
pack's own pavement still draws over the mesh.

The witness, read from the layout alone (no airport named):

* the face lies past a runway END with no declared overrun — at least
  ``CONTAINED`` of its area inside the rectangle from that end out to the
  runway safety area length, as wide as the runway's band
  (``zone2_half_width_m``, the end area's own side lines);
* it TOUCHES the end edge (within the contact tolerance ``on_tol``);
* no taxi or service centreline touches it (an end-around taxiway, a
  turn pad or a holding bay is a taxi surface, never a blast pad).
"""
from __future__ import annotations

import math
import typing as _t

from shapely.geometry import LineString, Polygon

from ..law import Law
from ..law.reference_code import runway_status
from ..law.tables import runway_safety_area_length_m, zone2_half_width_m

__all__ = ["blast_pad_end"]

#: the share of the face's area that must lie in an end's safety-area box
CONTAINED = 0.9


def blast_pad_end(face: Polygon, runways: _t.Iterable[_t.Any], law: Law,
                  on_tol: float) -> tuple[str, str] | None:
    """``(runway id, end name)`` when ``face`` is a blast pad past that end
    (module docstring; the caller has already found no taxi contact), else
    ``None``."""
    if face.is_empty or face.area <= 0.0:
        return None
    for rw in runways:
        a, b = rw.ends[0].xy, rw.ends[1].xy
        L = math.hypot(b[0] - a[0], b[1] - a[1])
        if L <= 0.0:
            continue
        ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
        st = runway_status(rw)
        rsa = runway_safety_area_length_m(law, rw.code_number, rw.code_letter, st)
        hw = float(zone2_half_width_m(law, "runway", rw.code_number, rw.code_letter, st) or 0.0)
        hw = max(hw, 0.5 * float(rw.width_m))
        for end, (ox, oy), (dx, dy) in ((rw.ends[0], a, (-ux, -uy)), (rw.ends[1], b, (ux, uy))):
            if float(getattr(end, "overrun_m", 0.0) or 0.0) > 0.0 or rsa <= 0.0:
                continue
            px, py = -dy, dx
            box = Polygon([(ox + px * hw, oy + py * hw), (ox - px * hw, oy - py * hw),
                           (ox - px * hw + dx * rsa, oy - py * hw + dy * rsa),
                           (ox + px * hw + dx * rsa, oy + py * hw + dy * rsa)])
            if face.intersection(box).area < CONTAINED * face.area:
                continue
            half = 0.5 * float(rw.width_m)
            edge = LineString([(ox + px * half, oy + py * half), (ox - px * half, oy - py * half)])
            if face.distance(edge) <= on_tol:
                return rw.id, end.name
    return None
