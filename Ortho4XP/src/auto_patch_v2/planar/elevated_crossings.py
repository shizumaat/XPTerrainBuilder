"""THE SHORT CROSSINGS ON THE AIRPORT, read ONCE beside the pack stage (owner
RULINGS 2026-11-20g / 20k; ``airport/crossing_seat`` is the read).

:func:`attach_crossings` puts the crossing records on ``Airport.
elevated_crossings`` (the road ceiling ``constraints/elevated_clearance``
and the published seat read them) and DENSIFIES every crossed way under
its crossing's region (``road_bridge_gen._densified``, the generated road
bridge's own reading: a node each side of the region's edge), so the road
faces carry vertices the ceiling binds -- an edge from a node outside the
region to one beyond it would stand over the soffit and escape it.
Nothing names an airport.
"""
from __future__ import annotations

import dataclasses as _dc

from ..airport.crossing_seat import crossing_records
from .road_bridge_gen import _densified

__all__ = ["attach_crossings"]


def attach_crossings(airport, law, cache, notes: "list[str] | None" = None):
    """``airport`` with its short crossings and the crossed ways densified;
    a second call is a no-op."""
    if getattr(airport, "elevated_crossings", ()):
        return airport
    recs, rnotes = crossing_records(airport, law, cache)
    if notes is not None:
        notes.extend(rnotes)
    if not recs:
        return airport
    spans = [{"span_xy": r["region"], "over": [r["way"]]} for r in recs]
    return _dc.replace(airport, elevated_crossings=tuple(recs),
                       osm_ways=_densified(getattr(airport, "osm_ways", ()) or (), spans))
