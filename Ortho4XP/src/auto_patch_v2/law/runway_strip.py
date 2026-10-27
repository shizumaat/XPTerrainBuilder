"""§40 (5) (1) THE RUNWAY'S GRADED STRIP AS A BAND about its CENTRELINE —
ONE derivation (Fable 2026-09-15; owner RULINGS 2026-09-15az), read by
classification (``classify/roles.py``: the region a pavement cell must lie
inside to be the runway's) and by DEM prep's flat-site decision
(``airport/flat_site_prep.py``: the strip the plateau keeps graded, owner
RULINGS 2026-10-27v (2), #1208).  Moved here from ``classify/roles`` so a
reader below ``classify`` in the layer order can take the same band.

The axis is the apt.dat ends (the same two points ``constraints/strips``
and ``law/approach_corridor`` read, never the emitted rings), and the half
width is ``tables.zone2_half_width_m("runway", code)`` — ICAO Annex 14's
graded strip by code number, the FAA RSA table under an FAA ruleset.

THE END CAP (§40 (5) as ruled 2026-09-15bl, r2): the graded strip does not
stop at the threshold — the axis is extended at both ends by
``tables.runway_safety_area_length_m`` (owner RULINGS 2026-10-15c (2))
before the flat cap.  ``end_cap=False`` restores the flat cap at the
apt.dat ends.

``rw`` is duck-typed: ``ends[k].xy`` (frame metres) and ``ends[k].approach``,
``instrument``, ``code_number``, ``code_letter`` — a
``model.airport.Runway`` or anything carrying those names.
"""
from __future__ import annotations

import math

from . import Law
from .reference_code import runway_status
from .tables import runway_safety_area_length_m, zone2_half_width_m

__all__ = ["strip_band"]


def strip_band(rw, law: Law, *, end_cap: bool = True):
    """The runway's graded strip as a shapely polygon in the frame, or
    ``None`` where the law states no strip for the class (module doc)."""
    from shapely.geometry import LineString

    status = runway_status(rw)
    hw = zone2_half_width_m(law, "runway", rw.code_number, rw.code_letter, status)
    if not hw or hw <= 0.0:
        return None
    a, b = rw.ends[0].xy, rw.ends[1].xy
    if a == b:
        return None
    if end_cap:
        ext = runway_safety_area_length_m(law, rw.code_number, rw.code_letter, status)
        if ext > 0.0:
            length = math.hypot(b[0] - a[0], b[1] - a[1])
            ux, uy = (b[0] - a[0]) / length, (b[1] - a[1]) / length
            a = (a[0] - ux * ext, a[1] - uy * ext)
            b = (b[0] + ux * ext, b[1] + uy * ext)
    return LineString([a, b]).buffer(hw, cap_style="flat")
