"""THE ROAD OVERPASS: A PACK HARD DECK OVER A MAPPED ROAD THE AIRPORT'S
PAVEMENT DOES NOT CROSS (owner RULINGS 2026-10-30f (1) / (5); #1692; the
hard-deck bridge's sibling, ``planar/deck_bridge``).

"Every bridge and tunnel object is identified and analysed before the
solve.  That covers taxiway decks, road overpasses and portals" and "a road
bridge object sits on its road".  A pack may carry a road over a mapped
road on a HARD DECK (``ATTR_hard_deck``, ``deck_kind == "flag"``, or a deck
plate the signature read) that no airside pavement drives across — KBNA's
crossing bridge over the road east of the terminal: a deck 7.5 m over its
authored zero, its abutment walls running 5.5 m under it, the road it
carries off the airport's map.  Nothing read it before the solve, and the
object stage seated the frame on the median ground of its footprint — the
embankments either side — 4.8 m over the road beneath it.

THE WITNESS is the geometry, never a name: a deck piece (``deck_bridge.
_frames``) that

* no airport pavement runs across (else it is a hard-deck BRIDGE,
  ``deck_bridges``) and stands beside no building in its frame (22n);
* a mapped ROAD runs under — a ``highway`` way that is no bridge itself,
  its centreline crossing the piece; and
* the pack authored the deck at least ``[bridge] clearance_minimum_m`` over
  its zero: the zero is the road the deck spans.

THE SEAT: the deck's zero sits on the road beneath — the SOLVED surface at
the road's centreline under the deck, its stations every ``[bridge]
abutment_sample_step_m`` (``pipeline/rebake_inputs`` publishes them as the
deck member's plate, ``airport/airside_deck_seat`` reads the zero off it and
the frame moves as one).  The road it carries meets the deck at the pack's
own authored height over that road.

Nothing here names a pack, a resource or an airport.
"""
from __future__ import annotations

import dataclasses as _dc

from shapely.geometry import LineString, Point
from shapely.ops import unary_union

__all__ = ["Overpass", "road_overpasses"]

XY = tuple[float, float]


@_dc.dataclass(frozen=True)
class Overpass:
    """One road overpass deck piece (module doc)."""

    #: the deck placement's id (the plate's member) and resource
    object_id: str
    resource: str
    #: the deck piece's outline (frame xy)
    ring: tuple[XY, ...]
    #: the road beneath: stations on its centreline under the deck
    stations: tuple[XY, ...]
    #: the mapped ways beneath
    ways: tuple[int, ...]
    #: the authored deck top over the zero (y)
    top_y: float


def _road_under(piece, ways, step: float) -> tuple[tuple[XY, ...], tuple[int, ...]]:
    """``(stations, way ids)`` of every road centreline crossing ``piece``."""
    from .structure_approach import is_bridge
    st: list[XY] = []
    ids: list[int] = []
    for w in ways:
        t = w.tags or {}
        if "highway" not in t or is_bridge(w) or len(w.points) < 2:
            continue
        ln = LineString(w.points)
        if not ln.intersects(piece):
            continue
        x = ln.intersection(piece)
        for g in getattr(x, "geoms", [x]):
            if g.geom_type != "LineString" or g.length < step:
                continue
            k = max(1, int(g.length // step))
            st.extend((p.x, p.y) for p in (g.interpolate(i / k, normalized=True)
                                           for i in range(k + 1)))
            ids.append(int(w.id))
    return tuple(st), tuple(ids)


def road_overpasses(objects, cache, classification, airport, law, decks=()
                    ) -> tuple[tuple[Overpass, ...], list[str]]:
    """``(every road overpass deck piece, one note per piece read)``
    (module doc).  ``decks`` are the hard-deck bridges already read."""
    from .deck_bridge import CellRoles, _beside_a_building, _frames, _slab
    if not objects or cache is None or classification is None:
        return (), []
    br = law.tables.structures.bridge
    step = float(br.abutment_sample_step_m)
    tol = float(law.tables.structures.tunnel.object.cover_placement_tol_m)
    taken = {str(d.object_id) for d in decks or ()}
    roles = CellRoles(classification, airport)
    ways = [w for w in airport.osm_ways or () if len(w.points) >= 2]
    out: list[Overpass] = []
    notes: list[str] = []
    for dks, frame in _frames(objects, tol):
        d = dks[0]
        if str(d.id) in taken:
            continue
        slab = _slab(cache, dks)
        top = max((y for _x, _y, y in slab), default=None)
        if top is None or top < float(br.clearance_minimum_m):
            continue
        u = unary_union([q.hard_deck for q in dks])
        name = f"{d.id} {str(d.path).rsplit('/', 1)[-1]}"
        for piece in sorted(getattr(u, "geoms", [u]), key=lambda p: -p.area):
            if piece.geom_type != "Polygon" or piece.area < 1.0:
                continue
            st, ids = _road_under(piece, ways, step)
            if not st:
                continue
            if _beside_a_building(frame, piece, roles):
                notes.append(f"{name}: a building stands beside it in its frame (22n)")
                continue
            out.append(Overpass(str(d.id), str(d.path), tuple(piece.exterior.coords[:-1]),
                                st, ids, float(top)))
            c = Point(st[len(st) // 2])
            notes.append(f"{name}: a road overpass over way(s) {list(ids)}, deck y "
                         f"{top:+.2f} over its zero; the zero sits on the road beneath "
                         f"({len(st)} stations at {c.x:.0f},{c.y:.0f}; RULINGS 2026-10-30f (5))")
    return tuple(out), notes
