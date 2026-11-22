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
network may already ride on).

THE PAGE THAT CARRIES A TAXIWAY NO SOURCE HOLDS (owner RULINGS 2026-10-30e,
#2215).  At or above the key the sources carry the airport, but a single
§60 page may still be the only pavement under a taxiway: KRDU's
``Ground_Textures/Ground/L2.pol`` (no material word, ``SURFACE`` asphalt)
is the pack's taxiway A beside runway 05R/23L, 566 m of the 1202 network
with no row-110 polygon and no name-admitted page under it, so the §53 gap
stage minted it as ONE 18,326 m2 groundside piece (``gap:2``) graded at the
road cap, "cut flat" across the taxiway (owner 2026-11-21T06:28Z).  30e:
where the centreline runs over ground no pavement source holds, "it then
looks for the pack page that covers it (a misread page, as at KIND)".  So
each §60 page carrying at least ``[load] network_page_unheld_min_m`` of the
non-runway network over ground no source and no runway slab holds is a
pavement source too (``dsf:netpage<k>``); every other page stays a sheet."""
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
    (``None`` with no network), the key, and the pages it took (``ids``:
    their sheet ids; ``unheld_m``: the centreline only they hold, ``None``
    when the share took every page)."""

    share: float | None
    share_max: float
    pages: int = 0
    pages_m2: float = 0.0
    ids: tuple[str, ...] = ()
    unheld_m: float | None = None

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
        if self.promoted and self.unheld_m is not None:
            verdict += (f": they alone hold {self.unheld_m:,.0f} m of taxi "
                        "centreline (RULINGS 2026-10-30e)")
        return (f"{icao}: the pavement sources carry {self.share:.1%} of the "
                f"taxi network (key {self.share_max:.0%}) — {verdict} (#1957)")


def _poly(p: Pavement) -> Polygon | None:
    if len(p.outer) < 3:
        return None
    g = Polygon(p.outer, [h for h in p.holes if len(h) >= 3])
    if not g.is_valid:
        g = g.buffer(0)
    return None if g.is_empty else g


def _taxi_lines(taxi_nodes: _t.Mapping[int, TaxiNode],
                taxi_edges: _t.Sequence[TaxiEdge]) -> list[LineString]:
    """The non-runway 1202 network, one segment per edge."""
    return [LineString([taxi_nodes[e.a].xy, taxi_nodes[e.b].xy])
            for e in taxi_edges
            if not e.is_runway and e.a in taxi_nodes and e.b in taxi_nodes
            and taxi_nodes[e.a].xy != taxi_nodes[e.b].xy]


def _painting(pavements: _t.Sequence[Pavement]) -> list[Polygon]:
    return [g for g in (_poly(p) for p in pavements
                        if counts_as_pavement(p.surface)) if g is not None]


def _network_share(pavements: _t.Sequence[Pavement],
                  taxi_nodes: _t.Mapping[int, TaxiNode],
                  taxi_edges: _t.Sequence[TaxiEdge]) -> float | None:
    """The share of the non-runway taxi network's length lying on the
    ``pavements`` that paint (:func:`borrow.counts_as_pavement`); ``None``
    when there is no such network."""
    lines = _taxi_lines(taxi_nodes, taxi_edges)
    total = sum(ln.length for ln in lines)
    if total <= 0.0:
        return None
    polys = _painting(pavements)
    if not polys:
        return 0.0
    on = unary_union(lines).intersection(unary_union(polys)).length
    return min(1.0, float(on) / total)


def _unheld_pages(pavements: _t.Sequence[Pavement], pages: _t.Sequence[Pavement],
                  taxi_nodes: _t.Mapping[int, TaxiNode],
                  taxi_edges: _t.Sequence[TaxiEdge], slabs: _t.Sequence[Polygon],
                  min_m: float) -> list[tuple[int, float]]:
    """``(page index, metres)`` for each of ``pages`` carrying at least
    ``min_m`` of the non-runway network over ground no painting source and
    no runway slab (``slabs``) holds (module doc, 30e)."""
    lines = _taxi_lines(taxi_nodes, taxi_edges)
    if min_m <= 0.0 or not lines:
        return []
    net = unary_union(lines)
    held = [*_painting(pavements), *slabs]
    free = net.difference(unary_union(held)) if held else net
    out = []
    for k, p in enumerate(pages):
        g = _poly(p)
        if g is None or not counts_as_pavement(p.surface):
            continue
        m = float(free.intersection(g).length)
        if m >= min_m:
            out.append((k, m))
    return out


def decide(pavements: _t.Sequence[Pavement], pages: _t.Sequence[Pavement],
           taxi_nodes: _t.Mapping[int, TaxiNode],
           taxi_edges: _t.Sequence[TaxiEdge], share_max: float,
           slabs: _t.Sequence[Polygon] = (), unheld_min_m: float = 0.0
           ) -> tuple[_Decision, tuple[Pavement, ...]]:
    """The rule (module docstring).  ``pages`` are the §60 ``.pol`` sheets;
    returns the decision and the pages taken as sources (``()`` when every
    page stays a sheet), re-numbered ``dsf:netpage<k>`` in order: every
    page below the share, else each page that alone holds ``unheld_min_m``
    of the network (``slabs``: the runway slabs, which hold their own
    ground)."""
    share = _network_share(pavements, taxi_nodes, taxi_edges)
    if share is None or not pages:
        return _Decision(share, share_max), ()
    if share < share_max:
        picked, unheld = list(range(len(pages))), None
    else:
        hits = _unheld_pages(pavements, pages, taxi_nodes, taxi_edges, slabs,
                             unheld_min_m)
        if not hits:
            return _Decision(share, share_max), ()
        picked, unheld = [k for k, _m in hits], sum(m for _k, m in hits)
    taken = tuple(_dc.replace(pages[k], id=f"{PAGE_PREFIX}{j}")
                  for j, k in enumerate(picked))
    m2 = sum(g.area for g in (_poly(p) for p in taken) if g is not None)
    return _Decision(share, share_max, len(taken), float(m2),
                     tuple(pages[k].id for k in picked), unheld), taken
