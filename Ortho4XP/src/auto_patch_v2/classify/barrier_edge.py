"""A LOT'S CONTACT WITH AIRSIDE ACROSS A BARRIER IS NO CONNECTION (owner
RULINGS 2026-10-28p (3), Q242 "a", #1338): "under §27 (RULINGS
2026-09-12c), a lot's contact with airside pavement that runs under a
building or along the pack's own fence does not count as a connection to
airside, so such lots stay groundside."

MEASURED NZWN (-41.32981, 174.81227): the multi-storey car park's lot
``dsf:pol2`` (84,824 m2) shared 347 m of lateral edge with the apron
``pav9``; 168 m of it runs UNDER the terminal footprints and the other
179 m lies along the pack's own fence facades (159 m within 2 m of one).
§27 read that edge as a connection to airside and the car parks shipped
as apron.

The barrier is the union of two plan shapes, both read from what the
airport already carries:

* every BUILDING footprint (``Airport.buildings``, less the open-lot
  facades, which are car parks and not buildings) — pavement that meets
  the lot only under a building is not a way onto the apron;
* every pack LINE facade (``Airport.fences``, the ``.fac`` files whose own
  class is ``line``: fences and walls, read by file and never by name,
  §52) — a contact run lies ALONG one where a fence segment within
  ``[lot] fence_contact_m`` of it runs within ``_ALONG_DEG`` of its
  direction.  The lot's edge and the apron's are drawn either side of the
  fence, never on it (NZWN: 0-7 m off).  A fence that CROSSES the contact
  is no barrier along it: the lot meets the apron on either side.

``airside_edge._lateral_airside_m`` drops a contact's run across it, the
same form as the #1099 storey drop (``classify.storey_edge``).  A lot the
drop alone keeps groundside carries :data:`BARRIER_M_KEY`.
"""
from __future__ import annotations

import math

from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union
from shapely.strtree import STRtree

from ..airport.facade import LOT_SOURCE
from .rules import Rules

__all__ = ["BARRIER_M_KEY", "Barrier", "barrier_band"]

#: evidence: metres of a lot's airside contact §27 read as across a barrier
BARRIER_M_KEY = "airside_edge_barrier_m"

#: a fence runs ALONG a contact within this many degrees of its direction —
#: the complement of §27 (5)'s transverse test
#: (``airside_edge._MOUTH_TRANSVERSE_DEG``, the same face rule)
_ALONG_DEG = 45.0


def _footprint(b) -> "Polygon | None":
    if len(b.outer) < 3:
        return None
    try:
        p = Polygon(b.outer, b.holes)
    except (ValueError, TypeError):
        return None
    if not p.is_valid:
        p = p.buffer(0)
    return None if p.is_empty else p


def _unit(a, b) -> "tuple[float, float] | None":
    dx, dy = b[0] - a[0], b[1] - a[1]
    n = math.hypot(dx, dy)
    return None if n <= 0.0 else (dx / n, dy / n)


def _segments(geom):
    for g in getattr(geom, "geoms", [geom]):
        pts = list(getattr(g, "coords", []))
        for a, b in zip(pts, pts[1:]):
            if a != b:
                yield a, b


class Barrier:
    """The buildings and the pack's fences a §27 contact may run across
    (module docstring)."""

    def __init__(self, buildings, fences, reach_m: float):
        self.buildings = buildings
        self.reach = float(reach_m)
        self.fence = [(LineString((a, b)), _unit(a, b)) for f in fences
                      for a, b in _segments(LineString(f.points))]
        self.tree = STRtree([s for s, _u in self.fence]) if self.fence else None
        self.cos = math.cos(math.radians(_ALONG_DEG))

    def _along(self, a, b):
        """The fence reach a contact segment ``a``-``b`` runs along."""
        u = _unit(a, b)
        seg = LineString((a, b))
        near = [] if self.tree is None or u is None else \
            [self.fence[int(j)] for j in self.tree.query(seg.buffer(self.reach))]
        zones = [s.buffer(self.reach) for s, v in near
                 if v is not None and abs(u[0] * v[0] + u[1] * v[1]) >= self.cos]
        return unary_union(zones) if zones else None

    def split(self, contact):
        """``(rest, dropped)``: the run of ``contact`` that is not across the
        barrier, and the run that is."""
        if self.buildings is not None:
            under = contact.intersection(self.buildings)
            contact = contact.difference(self.buildings)
        else:
            under = None
        along = [z for a, b in _segments(contact) if (z := self._along(a, b)) is not None]
        if along:
            zone = unary_union(along)
            fenced = contact.intersection(zone)
            contact = contact.difference(zone)
        else:
            fenced = None
        dropped = [g for g in (under, fenced) if g is not None and not g.is_empty]
        return contact, (unary_union(dropped) if dropped else None)


def barrier_band(airport, rules: Rules) -> "Barrier | None":
    """THE BARRIER (module docstring), or ``None`` where the airport carries
    neither a building nor a pack fence."""
    if airport is None:
        return None
    parts = [p for b in getattr(airport, "buildings", ()) or ()
             if b.source != LOT_SOURCE and (p := _footprint(b)) is not None]
    fences = [f for f in getattr(airport, "fences", ()) or () if len(f.points) >= 2]
    if not parts and not fences:
        return None
    return Barrier(unary_union(parts) if parts else None, fences,
                   rules.lot.fence_contact_m)
