"""THE STAND WITNESS — which apron faces contain an aircraft stand (owner
RULINGS 2026-10-15l (3) / 15m (4) "Aprons with stands"; audit row 10).

An apron FACE contains a stand when an apt.dat 1300 startup of one of
``common.stand_kinds`` (gate, tie-down) stands inside it (its ring less its
holes, ``geometry.face_cover`` at no tolerance).  Such a face takes the
stand cap (``tables.apron_stand_cap``, ICAO Annex 14 §3.13.5 / FAA AC
150/5300-13B §5.9.2: 1 %) HARD on its apron rows (``apron.
apron_within_shape``); every other apron face keeps ``common.roles.apron``.
ONE derivation: the sidecar publishes it (``stand_faces``, and the
``o4_grade_law_cap`` way tag the census composes), and v2 verify reads the
published set (``verify.frame.Patch.cap``)."""
from __future__ import annotations

from ..law import Law
from ..model.airport import Airport
from ..model.planar import PlanarMap
from .geometry import face_cover
from .precedence import view

__all__ = ["stand_face_ids"]


def stand_face_ids(planar: PlanarMap, law: Law, airport: Airport) -> frozenset[int]:
    """The apron face ids that contain a stand (module docstring)."""
    kinds = frozenset(law.tables.common.stand_kinds)
    stands = [s.xy for s in getattr(airport, "startups", ()) or ()
              if str(s.kind) in kinds]
    if not stands or law.tables.common.apron_stand_max is None:
        return frozenset()
    from shapely.geometry import Point
    vw = view(planar, law)
    out: set[int] = set()
    for f in vw.faces_of_role(("apron",)):
        poly = face_cover(vw.face_ring_xy(f.id),
                          [[vw.xy[v] for v in h] for h in vw.holes[f.id]], 0.0)
        if poly is None:
            continue
        x0, y0, x1, y1 = poly.bounds
        if any(x0 <= x <= x1 and y0 <= y <= y1 and poly.covers(Point(x, y))
               for x, y in stands):
            out.add(f.id)
    return frozenset(out)
