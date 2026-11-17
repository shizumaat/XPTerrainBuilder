"""WHERE ONE ROAD PASSES OVER ANOTHER (#2128 round 4; owner RULINGS
2026-11-17d; spec ``sim-review/2128-R2b.md`` B2): the ONE derivation of
``PlanarMap.road_crossings`` (``model/grade_separation``), read by the road
ramp (``airport/road_ramp``).

THE ROADS are centrelines: every mapped highway way passing over a road
face, and the map's own road centreline breaklines (apt.dat routes and
network ways) by ref -- the names the road profile's ways carry.  Two of
them CROSS where their lines meet at a point at least one lane width from
either line's ends (a T-junction, end on mid, never crosses).  A crossing
is GRADE-SEPARATED where a witness says one passes over the other:

* TAGS: their mapped levels differ (``layer``; else ``bridge`` +1,
  ``tunnel`` -1; ``airport/deck_signature``'s predicates).  A centreline
  with no tags of its own (an apt.dat route, ``airport/ground_route_ways``)
  takes the level of a mapped bridge or tunnel way running ALONG it within
  the 1206 dedup distance (``classify/rules.toml`` ``[osm_roads] dedup_m``)
  at the crossing: the way its corridor duplicates.
* SURVEY, on a credible inset only (``law/inset_class.lidar_credible``):
  each road read on its own line beside the other (from one lane width
  past the other's carriageway edge for 20 m, both sides, median) stands
  ``[bridge] clearance_minimum_m`` or more from the other.

EACH SIDE is the road faces near the crossing that are that road's: a
mapped way's ribbon (and a mapped bridge's deck) by its ref,
``<feed>:<way>`` (``model/deck_ends.way_of_ref``; two feeds reuse way ids);
any other road face (an apt.dat route corridor, a pack road page) where it
runs ALONG the centreline (three quarters of the face within its
carriageway half width plus a lane of the line) and not along the other's
too, so a face the other road merely crosses, or a page standing at the
crossing along both, is not its.  Every other crossing is at grade and
joined as before.  Nothing here names an airport, a pack or a resource.
"""
from __future__ import annotations

import math
import statistics
import typing as _t

from shapely.geometry import LineString, Point, Polygon
from shapely.ops import linemerge
from shapely.strtree import STRtree

from ..airport.deck_signature import is_bridge_way, is_tunnel_way
from ..airport.road_ways import mapped_width_m
from ..law import Law
from ..law.tables import family
from ..model.deck_ends import way_of_ref
from ..model.grade_separation import RoadCrossing, road_key
from ..model.planar import PlanarMap

__all__ = ["road_crossings"]

#: the survey reads this far along a road past the other's edge (m)
_READ_M = 20.0
#: ... every this many metres
_STEP_M = 2.0
#: a mapped way runs ALONG a centreline where their directions agree this well
_ALONG_COS = 0.8
#: a face runs along a centreline where this share of it lies within the
#: carriageway half width plus a lane of the line
_ALONG_SHARE = 0.75


def _level(tags: _t.Mapping[str, str], law: Law) -> int:
    """The way's mapped level: its ``layer``, else +1 for a bridge, -1 for
    a bore, 0."""
    try:
        return int(str(tags.get("layer", "")).strip())
    except ValueError:
        pass
    if is_bridge_way(tags):
        return 1
    tn = law.tables.structures.tunnel
    return -1 if is_tunnel_way(tags, tn.admitted_values) else 0


def _faces(pm: PlanarMap, law: Law) -> list[tuple[int, Polygon]]:
    """``(face id, polygon)`` of every road face."""
    roads = frozenset(family(law, "road_cross_section").roles)
    out = []
    for fid, f in pm.faces.items():
        if f.role not in roads:
            continue
        ring = [pm.vertices[v].xy for v in pm.ring_vertices(f.ring)]
        if len(ring) < 3:
            continue
        holes = [[pm.vertices[v].xy for v in pm.ring_vertices(h)] for h in f.holes]
        p = Polygon(ring, [h for h in holes if len(h) >= 3])
        p = p if p.is_valid else p.buffer(0.0)
        if not p.is_empty:
            out.append((fid, p))
    return out


def _lines(pm: PlanarMap, airport, ftree: STRtree) -> list[tuple[str, LineString, dict, str]]:
    """``(road name, centreline, tags, feed-qualified name)``: the mapped
    highway ways over a road face (named ``osm:<way>`` as the road profile
    names them, qualified ``<feed>:<way>`` as their ribbons are: two feeds
    reuse way ids), and the map's road centreline breaklines merged by ref
    (no tags)."""
    out = []
    for w in getattr(airport, "osm_ways", ()) or ():
        if len(w.points) < 2 or not (w.tags or {}).get("highway"):
            continue
        ln = LineString(w.points)
        if len(ftree.query(ln, predicate="intersects")):
            out.append((f"osm:{w.id}", ln, dict(w.tags), f"{w.kind}:{w.id}"))
    parts: dict[str, list] = {}
    for b in pm.breaklines.values():
        if b.kind == "road_centerline":
            pts = [pm.vertices[v].xy for v in b.vertices(pm)]
            if len(pts) >= 2:
                parts.setdefault(road_key(b.ref), []).append(LineString(pts))
    for k, ls in sorted(parts.items()):
        m = linemerge(ls) if len(ls) > 1 else ls[0]
        out.extend((k, g, {}, k) for g in getattr(m, "geoms", [m]) if g.length > 0)
    return out


def _direction(line: LineString, p: Point) -> tuple[float, float]:
    s = line.project(p)
    a = line.interpolate(max(0.0, s - 2.0))
    b = line.interpolate(min(line.length, s + 2.0))
    n = math.hypot(b.x - a.x, b.y - a.y) or 1.0
    return (b.x - a.x) / n, (b.y - a.y) / n


def _interior(line: LineString, p: Point, m: float) -> bool:
    s = line.project(p)
    return m <= s <= line.length - m


def _twin_level(line: LineString, p: Point, mapped, dedup: float, law: Law) -> int:
    """The level of a mapped bridge / bore way running ALONG ``line``
    within ``dedup`` of ``p`` (0 for none): an untagged centreline's."""
    d = _direction(line, p)
    for w, wl in mapped:
        if wl.distance(p) > dedup:
            continue
        e = _direction(wl, p)
        if abs(d[0] * e[0] + d[1] * e[1]) >= _ALONG_COS:
            return _level(w.tags or {}, law)
    return 0


def _beside(line: LineString, p: Point, gap: float, airport) -> float:
    """The median survey along ``line`` from ``gap`` to ``gap + _READ_M``
    either side of ``p`` (nan where nothing is read)."""
    from ..airport.dem import dem_z_at
    s0 = line.project(p)
    zs = []
    for sign in (-1.0, 1.0):
        d = gap
        while d <= gap + _READ_M:
            s = s0 + sign * d
            if 0.0 <= s <= line.length:
                q = line.interpolate(s)
                z = dem_z_at(airport, (q.x, q.y))
                if not math.isnan(z):
                    zs.append(z)
            d += _STEP_M
    return statistics.median(zs) if zs else math.nan


def _half_width(tags, law: Law) -> float:
    tn = law.tables.structures.tunnel
    return 0.5 * mapped_width_m(tags or {"highway": "service"}, tn.lane_width_m,
                                tn.default_lanes)


def _ref_key(ref: str) -> "tuple[str, int] | None":
    """``(feed, way)`` a mapped ribbon's (or a mapped bridge's deck) ref
    names, else ``None``."""
    base = str(ref).split("#", 1)[0]
    w = way_of_ref(base) if ":" in base else None
    return None if w is None else (base.rsplit(":", 1)[0], int(w))


def _is_named(named: "tuple[str, int]", qual: str) -> bool:
    feed, way = qual.rsplit(":", 1) if ":" in qual else (qual, "")
    return str(named[1]) == way and named[0] in (feed, "bridge_deck")


def _side(pm: PlanarMap, faces, ftree: STRtree, qual: str, line: LineString, p: Point,
          half: float, reach: float) -> tuple[set[int], set[int]]:
    """``(the faces within reach of p the road's ref names, the unnamed
    road faces running along its line there)`` (module doc, EACH SIDE)."""
    band = line.buffer(half)
    named_f: set[int] = set()
    along: set[int] = set()
    for i in ftree.query(p.buffer(reach), predicate="intersects"):
        fid, poly = faces[int(i)]
        named = _ref_key(pm.faces[fid].ref)
        if named is not None:
            if _is_named(named, qual):
                named_f.add(fid)
        elif (poly.area > 0.0 and poly.intersects(line)
              and poly.intersection(band).area >= _ALONG_SHARE * poly.area):
            along.add(fid)
    return named_f, along


def _vertices(pm: PlanarMap, fids: _t.Iterable[int]) -> frozenset[int]:
    out: set[int] = set()
    for fid in fids:
        f = pm.faces[fid]
        for cyc in (f.ring, *f.holes):
            out.update(pm.ring_vertices(cyc))
    return frozenset(out)


def _witness(a, b, p: Point, mapped, dedup: float, lane: float, clear: float,
             survey: bool, airport, law: Law) -> str:
    """What says one of ``a`` / ``b`` (``(key, line, tags)``) passes over
    the other at ``p`` ("" for nothing: at grade)."""
    za = _level(a[2], law) if a[2] else _twin_level(a[1], p, mapped, dedup, law)
    zb = _level(b[2], law) if b[2] else _twin_level(b[1], p, mapped, dedup, law)
    if za != zb:
        return f"mapped levels {za} / {zb}"
    if not survey:
        return ""
    sa = _beside(a[1], p, _half_width(b[2], law) + lane, airport)
    sb = _beside(b[1], p, _half_width(a[2], law) + lane, airport)
    return f"surveyed levels {sa:.2f} / {sb:.2f}" if abs(sa - sb) >= clear else ""


def road_crossings(pm: PlanarMap, airport, law: Law
                   ) -> tuple[tuple[RoadCrossing, ...], list[str]]:
    """``(the separated crossings, notes)`` (module doc)."""
    faces = _faces(pm, law)
    if len(faces) < 1:
        return (), []
    ftree = STRtree([p for _f, p in faces])
    lines = _lines(pm, airport, ftree)
    if len(lines) < 2:
        return (), []
    from ..classify.rules import load_rules
    from ..law import inset_class
    dedup = float(load_rules().osm_roads.dedup_m)
    lane = float(law.tables.emit.road_profile.lane_width_m)
    clear = float(law.tables.structures.bridge.clearance_minimum_m)
    survey = airport is not None and getattr(airport, "dem", None) is not None \
        and inset_class.lidar_credible(airport, law)
    mapped = [(w, LineString(w.points)) for w in getattr(airport, "osm_ways", ()) or ()
              if len(w.points) >= 2 and (w.tags or {}).get("highway")
              and _level(w.tags or {}, law) != 0]
    ltree = STRtree([ln[1] for ln in lines])
    found: dict[tuple[str, str], RoadCrossing] = {}
    for i, a in enumerate(lines):
        for j in ltree.query(a[1], predicate="intersects"):
            b = lines[int(j)]
            if int(j) <= i or a[3] == b[3] or (a[3], b[3]) in found:
                continue
            x = a[1].intersection(b[1])
            for p in [g for g in getattr(x, "geoms", [x]) if g.geom_type == "Point"]:
                if not (_interior(a[1], p, lane) and _interior(b[1], p, lane)):
                    continue
                why = _witness(a, b, p, mapped, dedup, lane, clear, survey, airport, law)
                if not why:
                    continue
                ha, hb = _half_width(a[2], law), _half_width(b[2], law)
                reach = ha + hb + 2.0 * lane
                na, la = _side(pm, faces, ftree, a[3], a[1], p, ha + lane, reach)
                nb, lb = _side(pm, faces, ftree, b[3], b[1], p, hb + lane, reach)
                # an unnamed face along BOTH lines is neither road's (a pack
                # page at the crossing): it stays joined as today
                sa, sb = _vertices(pm, na | (la - lb)), _vertices(pm, nb | (lb - la))
                if sa and sb:
                    found[(a[3], b[3])] = RoadCrossing(
                        a[0], b[0], (round(p.x, 3), round(p.y, 3)), why, sa, sb)
                    break
    out = tuple(found.values())
    notes = [f"{c.a} x {c.b} at ({c.xy[0]:.1f}, {c.xy[1]:.1f}): one passes over the other "
             f"({c.witness}); {len(c.a_vertices)} / {len(c.b_vertices)} side vertices, "
             f"{len(c.vertices)} shared un-joined, no level crosses (#2128 R4, RULINGS "
             f"2026-11-17d)" for c in out]
    return out, notes
