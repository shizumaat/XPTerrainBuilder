"""THE PACK ALREADY DRAWS THE ROAD BRIDGE (spec ``docs/specs/2123.md`` B1
(c); "the pack always wins", owner 2026-11-17: "We should only be adding
our bridges when the pack does not provide an object").

``planar/road_bridge_gen`` generates an X-Plane road over a mapped road
bridge the pack draws only as draped pavement.  Before it does, the pack
is read over the bridge's span (its carriageway buffered by
``[road_gen] span_margin_m``) and along its mapped axis; any one of these
refuses the bridge, naming what the pack draws there:

(a) a pack HARD DECK over the span, or the pack's MODELLED CROSSING -- a
    structure under its ground and a top over the axis
    (``planar/deck_pack_cover.pack_refusal``, the reading that refuses a
    generated taxiway deck);
(b) an ELEVATED TOP: a placement's solid up-facing faces standing at
    least ``[road_gen] pack_top_min_m`` over its ground -- the pack's
    bridge or overpass object, a roof -- over at least ``[deck_gen]
    pack_cover_share`` of the bridge's axis (``pack_decks_near`` kind
    ``"over"``);
(c) the pack's own ROAD: segments of its DSF road network (any level: a
    level of 1 or more is the pack's bridge, level 0 a road it drapes
    over the span) within ``[road_gen] pack_road_near_m`` of the axis and
    within ``pack_road_angle_deg`` of its bearing, over at least
    ``pack_cover_share`` of the axis.  A crossing road (the lower road
    under the span) is never parallel and never counts.

Draped faces and ``.pol`` pages are NOT a crossing: draped pavement over
the span is the case the generated bridge exists for (B1 (b)).  Other
installed road packs (an overlay's network) are not read here: the build
reads only the airport's own pack.

Nothing here names an airport.  Build-time impact: the pack placements
whose plan box reaches a span (their geometry already cached by the pack
read) and one pass over the pack DSF dump's segment rows, once per build
with a road-bridge candidate.
"""
from __future__ import annotations

import math
import os
import re
import typing as _t

from shapely.geometry import LineString
from shapely.ops import unary_union

from .deck_pack_cover import pack_decks_near, pack_refusal

__all__ = ["PackRoads", "pack_provides"]

_TILE = re.compile(r"([+-]\d{2})([+-]\d{3})\.dsf", re.IGNORECASE)


class PackRoads:
    """The pack's own road segments in frame xy, read ONCE from the cached
    dump of each pack DSF when first asked (``mod_cache_root`` ``None`` or
    no dump: none)."""

    def __init__(self, airport, mod_cache_root: "str | None"):
        self._airport = airport
        self._root = mod_cache_root
        self._segs: "list | None" = None

    def _dumps(self) -> list[str]:
        from ..airport.object_pack import pristine_dump
        pack = getattr(self._airport, "pack", None)
        out = []
        for dsf in getattr(pack, "dsf_paths", ()) or ():
            m = _TILE.search(os.path.basename(str(dsf)))
            if not m or not self._root:
                continue
            root = os.path.dirname(os.path.dirname(os.path.dirname(str(dsf))))
            try:
                d = pristine_dump(self._root, root, int(m.group(1)), int(m.group(2)))
            except OSError:
                d = None
            if d:
                out.append(d)
        return out

    def segments(self) -> list[tuple[str, int, int, LineString]]:
        """``(net, subtype, level, line)`` of every pack segment; ``level``
        the higher of its two end junctions'."""
        if self._segs is not None:
            return self._segs
        from ..airport.dsf_segments import read_segments
        to_xy, _ll = self._airport.frame.transformers()
        self._segs = []
        for d in self._dumps():
            segs, _excl = read_segments(d, (-180.0, -90.0, 180.0, 90.0))
            for net, sub, pts in segs:
                if len(pts) < 2:
                    continue
                lv = int(max(pts[0][2] or 0.0, pts[-1][2] or 0.0))
                self._segs.append((os.path.basename(net), int(sub), lv,
                                   LineString([to_xy(lo, la) for lo, la, _z in pts])))
        return self._segs


def _bearing(a, b) -> float:
    return math.degrees(math.atan2(b[1] - a[1], b[0] - a[0])) % 180.0


def _road_share(line: LineString, roads: PackRoads, law) -> tuple[float, str]:
    """The share of ``line`` a parallel pack segment runs along, and the
    segment's description (module doc (c))."""
    rg = law.tables.structures.road_gen
    near, ang = float(rg.pack_road_near_m), float(rg.pack_road_angle_deg)
    zone = line.buffer(near)
    pieces, names = [], {}
    for net, sub, lv, seg in roads.segments():
        if not seg.intersects(zone):
            continue
        cs = list(seg.coords)
        for a, b in zip(cs[:-1], cs[1:], strict=True):
            piece = LineString([a, b])
            if piece.length <= 0.0 or not piece.intersects(zone):
                continue
            at = line.project(piece.interpolate(0.5, normalized=True))
            p0 = line.interpolate(max(0.0, at - 1.0))
            p1 = line.interpolate(min(line.length, at + 1.0))
            d = abs(_bearing(a, b) - _bearing((p0.x, p0.y), (p1.x, p1.y)))
            if min(d, 180.0 - d) > ang:
                continue
            pieces.append(piece.buffer(near))
            names[(net, sub, lv)] = names.get((net, sub, lv), 0) + 1
    if not pieces:
        return 0.0, ""
    share = line.intersection(unary_union(pieces)).length / max(line.length, 1e-9)
    net, sub, lv = max(names, key=names.get)
    return share, f"{net} type {sub} level {lv}"


def pack_provides(span, line: LineString, objects: _t.Sequence, cache, roads: PackRoads,
                  law) -> str:
    """What the pack draws over the road bridge ``line`` (its ``span``,
    frame) -- the refusal of a generated bridge (module doc) -- or ``""``."""
    g = law.tables.structures.deck_gen
    share = float(g.pack_cover_share)
    packs = pack_decks_near(objects, cache, law, span,
                            over_m=float(law.tables.structures.road_gen.pack_top_min_m))
    why = pack_refusal(span, [line], packs, law) if packs else ""
    if why:
        return why
    axis = line.intersection(span)
    for p in packs:
        if p.kind != "over" or axis.length <= 0.0:
            continue
        try:
            cov = axis.intersection(p.plan).length / axis.length
        except Exception:                      # an invalid pack outline  # noqa: BLE001
            continue
        if cov >= share:
            return (f"the pack's {p.object_id} ({p.resource}) draws a top over "
                    f"{100 * cov:.0f} % of the bridge")
    rs, what = _road_share(line, roads, law)
    if rs >= share:
        return f"the pack's road network draws it ({what}, along {100 * rs:.0f} % of the bridge)"
    return ""
