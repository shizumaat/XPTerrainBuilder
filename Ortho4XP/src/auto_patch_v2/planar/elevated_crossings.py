"""THE CROSSING GROUPS ON THE AIRPORT, read ONCE beside the pack stage (owner
RULINGS 2026-11-20g / 20k / 20s; ``airport/crossing_seat`` is the read).

:func:`attach_crossings` puts the crossing groups on ``Airport.
elevated_crossings``: the trench planner (``planar/soffit_road``), the
floor rows (``constraints/soffit_floor``), the low-member ties
(``constraints/foot_rows``) and the published seat (``crossing_seat.
publication``) read them.  The ways are not touched: the trench is cut by
the structure pass, never a ceiling on the road's own vertices.  Nothing
names an airport.
"""
from __future__ import annotations

import dataclasses as _dc

from ..airport.crossing_seat import crossing_records

__all__ = ["attach_crossings"]


def attach_crossings(airport, law, cache, notes: "list[str] | None" = None):
    """``airport`` with its crossing groups; a second call is a no-op."""
    if getattr(airport, "elevated_crossings", ()):
        return airport
    recs, rnotes = crossing_records(airport, law, cache)
    if notes is not None:
        notes.extend(rnotes)
    return _dc.replace(airport, elevated_crossings=tuple(recs)) if recs else airport
