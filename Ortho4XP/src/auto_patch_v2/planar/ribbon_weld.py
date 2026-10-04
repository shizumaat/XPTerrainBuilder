"""THE RIBBON'S WELD AT THE RIM'S OWN NODES (RULINGS 2026-09-30aa rules 2
and 9; issue #100) — split out of ``planar/pad_cut.py`` for its line budget
(lane roadmint100b).  ``pad_cut.airside_clip`` imports it at call time."""
from __future__ import annotations

import shapely
from shapely.geometry import LineString, MultiLineString, Point, Polygon
from shapely.ops import unary_union

__all__ = ["_weld_to_rim"]


def _weld_to_rim(g, rim, band: float, counts: dict, keep_out=None):
    """RULINGS 2026-09-30aa rules 2 and 9 — A RIBBON'S CONTACT IS A WELD AT
    THE RIM'S OWN NODES.  ``g`` is the ribbon already clipped by the
    airside.  Its part within ``band`` of the airside (the hot-pixel band,
    where noding would round a ribbon coordinate onto an airside edge and
    SPLIT it) is rebuilt: every coordinate standing ON the rim is replaced,
    per contact run, by the rim NODES lying on that run in order (the
    weld: the ribbon shares the airside's vertices and no other), every
    coordinate between the rim and the band's edge is dropped, and the
    band edge is kept.  A contact run with no node on it has nothing to
    weld to: the ribbon stands off by the band there, counted
    (``unwelded_contacts``) — never an airside node minted, never a
    stand-off anywhere a node exists."""
    from .pad_cut import _polys   # lazy: pad_cut imports this module at call time
    if g is None or g.is_empty or rim.boundary is None:
        return g
    # the airside union carries the IDENTITY GRID's precision model, and a
    # buffer of it would round the band edge onto that grid (a 0.75 m band
    # read 0.5 m on one side, 1.0 m on the other): the band is cut FLOATING
    air0 = shapely.set_precision(rim.airside, 0.0)
    zone = air0.buffer(band, join_style="mitre", mitre_limit=2.0)
    g = shapely.set_precision(g, 0.0)
    # A RIBBON WITHIN THE BAND OF THE RIM TOUCHES IT: it is grown to the rim
    # there (never more than the band), so its contact is a run of rim
    # nodes — a ribbon standing a hair off an apron edge would otherwise
    # sit in the hot-pixel band, where its crossings with the zone lines
    # round onto the rim and re-route it (measured HECA
    # ``small_roads:-4059#5``, 0.75 m off ``dsf:objpav1``)
    grow = g.buffer(band, join_style="mitre", mitre_limit=2.0).intersection(zone)
    if keep_out is not None and not keep_out.is_empty:
        grow = grow.difference(keep_out)
    g = unary_union([g, grow]).difference(air0)
    core = g.difference(zone)
    strip = g.intersection(zone)
    eps = 1e-6
    tabs: list[Polygon] = []
    for w in _polys(strip):
        ring = [(float(x), float(y)) for x, y in w.exterior.coords[:-1]]
        dist = [rim.rim_distance(c, band) for c in ring]
        on = [d is not None and d <= eps for d in dist]
        if all(on) or not any(on):
            if any(on):
                counts["unwelded_contacts"] = int(counts.get("unwelded_contacts", 0)) + 1
            continue
        k0 = on.index(False)
        ring, dist, on = ring[k0:] + ring[:k0], dist[k0:] + dist[:k0], on[k0:] + on[:k0]
        new: list[tuple[float, float]] = []
        run: list[tuple[float, float]] = []

        def _flush() -> None:
            if not run:
                return
            ns = rim.nodes_along(run, rim.node_tol) if len(run) > 1 else \
                ([run[0]] if rim.has(run[0]) else [])
            if not ns:
                counts["unwelded_contacts"] = int(counts.get("unwelded_contacts", 0)) + 1
            new.extend(ns)
            run.clear()

        for c, d, o in zip(ring, dist, on):
            if o:
                run.append(c)
                continue
            _flush()
            if d is None or d >= band - eps:
                new.append(c)          # the band edge (a side vertex inside it drops)
        _flush()
        dedup = [c for i, c in enumerate(new) if i == 0 or c != new[i - 1]]
        if len(dedup) >= 2 and dedup[0] == dedup[-1]:
            dedup.pop()
        if len(dedup) < 3:
            continue
        t = Polygon(dedup)
        if not t.is_valid or t.area <= 0.0 or \
                t.intersection(rim.airside).area > 1e-6 * max(t.area, 1.0):
            counts["weld_refused"] = int(counts.get("weld_refused", 0)) + 1
            continue
        tabs.append(t)
        counts["weld_tabs"] = int(counts.get("weld_tabs", 0)) + 1
    return unary_union([core, *tabs]) if tabs else core
