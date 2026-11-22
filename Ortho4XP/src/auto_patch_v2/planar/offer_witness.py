"""THE GATEWAY OFFER'S EARLY WITNESS (#2169 follow-up; owner 2026-11-19T00:21Z:
"Can't we detect ahead of time if we need it so we don't have to build the
patch twice?").

An airport X-Plane draws from its Global Airports entry alone cannot carry
a generated taxiway deck or road bridge (RULINGS 2026-11-16y (2)): the
planar refuses each with ``deck_generated.GLOBAL_OFFER`` and the app offers
the Gateway pack.  That refusal lands only once the patch is built, so the
offer came after a patch built against the Global entry, which the next
build threw away.  This module asks the same question BEFORE any patch is
built, from the planar's own witnesses and without classify or solve:

* DECK (spec 2123 A1 (1)/(3)): a road or rail the structure pass bores
  under the airside -- a §34 (5) underpass (a taxied ``aeroway`` bridge,
  ``structure_underpass.aeroway_decks``, over a ``bore_roads`` way, the
  crossing on the airport's pavement), or a mapped tunnel chain
  (``deck_generated._connected``) within its half width of the pavement --
  covered no longer than ``[deck_gen] max_cover_m`` (a longer one is a
  tunnel and offers nothing);
* ROAD BRIDGE (spec 2123 B1 (a)/(b)): a ``highway`` bridge
  (``road_bridge_gen._is_road_bridge``) with ``[road_gen]
  page_cover_frac`` of its carriageway under apt.dat ``110`` pavement,
  crossing a lower road or rail.

What it does NOT read (the planar does, later): the classification's taxi /
runway roles (every apt.dat pavement and runway counts here), the pack's
own decks (a Global entry has none) and the survey's clearance plan.  So
it may offer where the planar would not; it never misses a candidate the
planar reads from the same feeds.

:func:`offer_notes` is the predicate over an airport-shaped record;
:func:`read_airport` builds that record from the apt.dat block and the
OSM feeds already on disk (no download: a tile never built has none, and
the build-time offer stays its path).  Nothing here names an airport.
Build-time impact: none on the patch build; the early pass reads each
tile's road feeds once (seconds) on a thread of its own.
"""
from __future__ import annotations

import importlib
import math
import types
import typing as _t

from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union

from .deck_generated import _connected
from .road_bridge_gen import _is_road_bridge, _layer, _pages
from .structure_approach import carriageway_width_m, is_tunnel
from .structure_underpass import aeroway_decks, bore_roads

__all__ = ["offer_notes", "read_airport", "FEEDS"]

#: the OSM feeds the planar's structure witnesses read
FEEDS = ("airports", "airport_small_roads", "big_roads")


def _airside(airport) -> _t.Any:
    """Every apt.dat pavement and runway strip, one shape."""
    shapes = list(_pages(airport))
    for strip in getattr(airport, "runway_strips", ()) or ():
        if len(strip) >= 3:
            shapes.append(Polygon(strip))
    return unary_union(shapes) if shapes else None


def _kind(tags) -> str:
    return str((tags or {}).get("highway") or (tags or {}).get("railway") or "")


def _decks(airport, law, P) -> list[str]:
    tn = law.tables.structures.tunnel
    cover = float(law.tables.structures.deck_gen.max_cover_m)
    notes: list[str] = []
    roads = bore_roads(airport, law, rail=True)
    lines = [LineString(r.points) for r in roads]
    for d in aeroway_decks(airport, law):
        deck = LineString(d.points)
        for r, ln in zip(roads, lines, strict=False):
            x = deck.intersection(ln)
            if x.is_empty or x.distance(P) > 1.0:
                continue
            under = ln.intersection(P).length
            if under <= cover:
                notes.append(f"deck: {(d.tags or {}).get('aeroway') or 'aeroway'} bridge "
                             f"{d.id} over {_kind(r.tags)} {r.id} "
                             f"({under:.0f} m under the pavement)")
    tunnels = [w for w in getattr(airport, "osm_ways", ()) or ()
               if len(w.points) >= 2 and is_tunnel(w, tn.admitted_values) and _kind(w.tags)]
    for group in _connected(tunnels):
        covered = sum(LineString(w.points).length for w in group)
        if covered > cover or covered < float(tn.underpass_min_span_m):
            continue
        near = [w for w in group if LineString(w.points).distance(P)
                <= carriageway_width_m(w.tags, law) / 2.0 + 1.0]
        if near:
            notes.append(f"deck: {_kind(near[0].tags)} tunnel {near[0].id} under the "
                         f"pavement ({covered:.0f} m covered)")
    return notes


def _road_bridges(airport, law, P) -> list[str]:
    frac = float(law.tables.structures.road_gen.page_cover_frac)
    tn = law.tables.structures.tunnel
    ways = [w for w in getattr(airport, "osm_ways", ()) or () if len(w.points) >= 2]
    others = [w for w in ways if _kind(w.tags)]
    notes: list[str] = []
    seen: set = set()
    for w in ways:
        key = tuple((round(x, 2), round(y, 2)) for x, y in w.points)
        if not _is_road_bridge(w.tags) or key in seen:
            continue                    # one way read from two tiles' extracts is one
        line = LineString(w.points)
        carriage = line.buffer(carriageway_width_m(w.tags, law) / 2.0, cap_style="flat")
        if carriage.area <= 0.0 or carriage.intersection(P).area / carriage.area < frac:
            continue
        lay = max(_layer(w.tags), 1)
        lower = [o for o in others if o.id != w.id
                 and (_layer(o.tags) < lay
                      or str((o.tags or {}).get("tunnel", "no")) in tn.admitted_values)
                 and line.crosses(LineString(o.points))]
        if lower:
            seen.add(key)
            notes.append(f"road bridge: {_kind(w.tags)} {w.id} over "
                         f"{', '.join(str(o.id) for o in lower[:4])}")
    return notes


def offer_notes(airport, law) -> list[str]:
    """One note per deck / road-bridge candidate of ``airport`` (an object
    with ``osm_ways`` and ``pavements`` in the airport's metre frame, and
    optionally ``runway_strips``), ``[]`` with none (module doc)."""
    P = _airside(airport)
    if P is None or P.is_empty:
        return []
    return _decks(airport, law, P) + _road_bridges(airport, law, P)


def _strip(to_xy, rw) -> list:
    """Row 100's paved strip, end to end at its width."""
    (_, la0, lo0, *_r0), (_, la1, lo1, *_r1) = rw.ends
    (x0, y0), (x1, y1) = to_xy(lo0, la0), to_xy(lo1, la1)
    n = math.hypot(x1 - x0, y1 - y0)
    if n <= 0.0:
        return []
    h = float(rw.width_m) / 2.0
    ox, oy = -(y1 - y0) / n * h, (x1 - x0) / n * h
    return [(x0 + ox, y0 + oy), (x1 + ox, y1 + oy), (x1 - ox, y1 - oy), (x0 - ox, y0 - oy)]


def _ring(to_xy, ring) -> tuple:
    return tuple(to_xy(lo, la) for lo, la in ring)


def read_airport(icao: str, xplane_root: str, osm_root: str, law,
                 apt_dat_path: str | None = None, cache: dict | None = None,
                 radius_deg: float = 0.05) -> types.SimpleNamespace | None:
    """The record :func:`offer_notes` reads: ``icao``'s apt.dat block (the
    build's own ``load.read_apt``: its selection, borrow and frame) and the
    :data:`FEEDS` ways within ``radius_deg`` of its reference point, read
    from the tiles that box touches (``osm.load_feed``; ``cache`` shares a
    tile's parse between airports).  ``None`` when no feed is on disk."""
    load = importlib.import_module("auto_patch_v2.airport.load")
    osm = importlib.import_module("auto_patch_v2.airport.osm")
    from ..model.airport import OsmWay
    _sel, _block, apt, _bres, frame = load.read_apt(icao, xplane_root, law, apt_dat_path)
    lat0, lon0 = frame.origin
    to_xy = load._vector_to_xy(frame)
    tiles = sorted({(math.floor(lat0 + a), math.floor(lon0 + b))
                    for a in (-radius_deg, radius_deg) for b in (-radius_deg, radius_deg)})
    ways: list = []
    found = False
    for feed in FEEDS:
        doc = osm.load_feed(osm_root, feed, lat0, lon0, radius_deg, tiles=tiles, cache=cache)
        found = found or bool(doc.sources)
        ways += [OsmWay(load._osm_id(w.id), feed,
                        tuple(to_xy(lo, la) for la, lo in w.points), False, w.tags)
                 for w in doc.ways]
    if not found:
        return None
    pavements = tuple(types.SimpleNamespace(outer=_ring(to_xy, p.rings[0]),
                                            holes=tuple(_ring(to_xy, h) for h in p.rings[1:]))
                      for p in apt.pavements)
    return types.SimpleNamespace(osm_ways=tuple(ways), pavements=pavements,
                                 runway_strips=tuple(_strip(to_xy, rw) for rw in apt.runways))
