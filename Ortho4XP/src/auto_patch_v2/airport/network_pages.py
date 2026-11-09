"""THE PAGES THAT CARRY THE TAXI NETWORK ARE THE PAVEMENT (#1957).

§60 (owner RULINGS 2026-10-09a, 2026-10-04e (1)) admits a draped ``.pol``
page that declares its own hard ``SURFACE`` but whose NAME says no material
as a GAP SHEET: never a pavement source, met through the §53 gap stage,
where a piece is groundside unless it runs along an apron (§59).  That law
was measured where the apt.dat pavement (or the name-admitted pages) is the
airport and the SURFACE pages lie over or beside it (OTHH, HECA: the sources
carry 99.6 % / 99.9 % of the 1202 taxi network's length).

THE DEFECT (LIME, Aerosoft, owner 2026-11-07).  The pack authors every
taxiway and apron as ``Material/LIME_Aspalth__0N.pol`` pages (``SURFACE
concrete``, ``LAYER_GROUP runways +3``; "Aspalth" is no material word) and
its apt.dat carries ONE row-110 polygon, the runway's.  The sources carried
6.9 % of the network (482 of 7,006 m); every apron and taxiway became a
groundside gap piece, no taxi role was minted, and the site 45.666711,
9.700247 (mid-apron, ``LIME_Aspalth__04``) read ``groundside_pavement``.

THE RULE.  ``share`` = the length of the non-runway 1202 network on the
pavement sources (every row-110 polygon that paints, the name-admitted pages,
the §42 bodies, the §44 borrow) over its whole length.  Below
``law.structures.load.network_pages_share_max`` the pack's pavement IS its
SURFACE pages: every §60 ``.pol`` sheet becomes a pavement source
(``dsf:netpage<k>``, judged by classify's draped-page gates like any
name-admitted page — boundary, overlay, area floor).  At or above it nothing
changes.  The OBJ8 gap bodies (04o (a)) stay sheets either way.  No network,
no witness: nothing changes.  ONE derivation site: ``load.load_with_report``,
after the §44 borrow's scenery stage (a borrow that stands is pavement the
network may already ride on)."""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union

from ..model.airport import Pavement, TaxiEdge, TaxiNode
from .borrow import counts_as_pavement

__all__ = ["PAGE_PREFIX", "decide"]

#: the id of a §60 page taken as a pavement source (``dsf:`` routes it
#: through classify's draped-page gates, ``evidence._dsf_pavements``)
PAGE_PREFIX = "dsf:netpage"


@_dc.dataclass(frozen=True)
class _Decision:
    """What :func:`decide` found: the network ``share`` on the sources
    (``None`` with no network), the key, and the pages it took."""

    share: float | None
    share_max: float
    pages: int = 0
    pages_m2: float = 0.0

    @property
    def promoted(self) -> bool:
        return self.pages > 0

    def line(self, icao: str) -> str:
        """The build-log line, or ``""`` when nothing was decided."""
        if self.share is None:
            return ""
        verdict = (f"{self.pages} SURFACE page(s) / {self.pages_m2:,.0f} m2 "
                   "taken as pavement sources" if self.promoted
                   else "the §60 pages stay gap sheets")
        return (f"{icao}: the pavement sources carry {self.share:.1%} of the "
                f"taxi network (key {self.share_max:.0%}) — {verdict} (#1957)")


def _poly(p: Pavement) -> Polygon | None:
    if len(p.outer) < 3:
        return None
    g = Polygon(p.outer, [h for h in p.holes if len(h) >= 3])
    if not g.is_valid:
        g = g.buffer(0)
    return None if g.is_empty else g


def _network_share(pavements: _t.Sequence[Pavement],
                  taxi_nodes: _t.Mapping[int, TaxiNode],
                  taxi_edges: _t.Sequence[TaxiEdge]) -> float | None:
    """The share of the non-runway taxi network's length lying on the
    ``pavements`` that paint (:func:`borrow.counts_as_pavement`); ``None``
    when there is no such network."""
    lines = [LineString([taxi_nodes[e.a].xy, taxi_nodes[e.b].xy])
             for e in taxi_edges
             if not e.is_runway and e.a in taxi_nodes and e.b in taxi_nodes
             and taxi_nodes[e.a].xy != taxi_nodes[e.b].xy]
    total = sum(ln.length for ln in lines)
    if total <= 0.0:
        return None
    polys = [g for g in (_poly(p) for p in pavements
                         if counts_as_pavement(p.surface)) if g is not None]
    if not polys:
        return 0.0
    on = unary_union(lines).intersection(unary_union(polys)).length
    return min(1.0, float(on) / total)


def decide(pavements: _t.Sequence[Pavement], pages: _t.Sequence[Pavement],
           taxi_nodes: _t.Mapping[int, TaxiNode],
           taxi_edges: _t.Sequence[TaxiEdge], share_max: float
           ) -> tuple[_Decision, tuple[Pavement, ...]]:
    """The rule (module docstring).  ``pages`` are the §60 ``.pol`` sheets;
    returns the decision and the pages as sources (``()`` when they stay
    sheets), re-numbered ``dsf:netpage<k>`` in order."""
    share = _network_share(pavements, taxi_nodes, taxi_edges)
    if share is None or not pages or share >= share_max:
        return _Decision(share, share_max), ()
    taken = tuple(_dc.replace(p, id=f"{PAGE_PREFIX}{k}")
                  for k, p in enumerate(pages))
    m2 = sum(g.area for g in (_poly(p) for p in taken) if g is not None)
    return _Decision(share, share_max, len(taken), float(m2)), taken
