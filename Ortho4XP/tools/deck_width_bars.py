"""THE GENERATED DECK'S WIDTH, READ OFF A SOLVED REPLAY (owner RULINGS
2026-11-21c, lane ltsawidth; ``tools/deck_probe.py --widths``).

Per generated deck of ``PlanarMap.decks``: the apt.dat taxi route crossing
its ring furthest (row 1202), the size letters of the routes crossing it,
the law's taxiway safety area for the letter (``[deck_gen]
tsa_by_letter_m``), and the ring's extent across that route -- its width
and how far it stands each side of the centreline (``left_m`` /
``right_m``: a deck centred on its taxiway reads them equal, a riding
service road (19s (8) (c)) or the parallel gap (20f) moves one side
only).  ``route: None`` where no taxi route crosses the ring (a deck
standing off its taxiway).  Reads nothing but the pickle.
"""
from __future__ import annotations

import math
import typing as _t


def width_rows(pm, airport, law) -> list[dict]:
    """One row per generated deck (module doc)."""
    from shapely.geometry import LineString, Polygon

    from auto_patch_v2.planar.deck_generated import is_generated
    tsa = dict(law.tables.structures.deck_gen.tsa_by_letter_m)
    to_ll = airport.frame.transformers()[1]
    nodes = getattr(airport, "taxi_nodes", {}) or {}
    rows: list[dict] = []
    for db in getattr(pm, "decks", ()) or ():
        if not is_generated(db):
            continue
        ring = Polygon(db.ring)
        lat, lon = to_ll(ring.centroid.x, ring.centroid.y)
        row: dict[str, _t.Any] = {"deck": db.object_id, "ll": (round(lat, 6), round(lon, 6)),
                                  "riders": list(getattr(db, "riders", ()) or ()), "route": None}
        cross = []
        for e in getattr(airport, "taxi_edges", ()) or ():
            if getattr(e, "is_runway", False) or e.a not in nodes or e.b not in nodes:
                continue
            ln = LineString([nodes[e.a].xy, nodes[e.b].xy])
            if ln.length > 1e-6 and ln.intersection(ring).length > 1.0:
                cross.append((ln.intersection(ring).length, e, ln))
        rows.append(row)
        if not cross:
            continue
        _l, e, ln = max(cross, key=lambda c: c[0])
        (x0, y0), (x1, y1) = ln.coords
        n = math.hypot(x1 - x0, y1 - y0)
        nx, ny = -(y1 - y0) / n, (x1 - x0) / n
        side = [(x - x0) * nx + (y - y0) * ny for x, y in db.ring]
        letters = sorted({str(c[1].width_class).upper() for c in cross if c[1].width_class})
        row.update(route=str(getattr(e, "name", "") or "?"), letters=letters,
                   tsa_m=tsa.get(letters[-1]) if letters else None,
                   width_m=round(max(side) - min(side), 1), left_m=round(-min(side), 1),
                   right_m=round(max(side), 1))
    return rows
