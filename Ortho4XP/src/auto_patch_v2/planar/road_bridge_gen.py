"""THE GENERATED ROAD BRIDGE (spec ``docs/specs/2123.md`` Part B; owner
RULINGS 2026-11-16y; issue #2124).

A mapped road bridge over a lower road that the airport's pack draws only
as DRAPED PAVEMENT (a ``.pol`` page or an apt.dat ``110`` laid over the
cutting) cannot be graded: a heightfield has no overpass, and grading the
page into the cutting buries the lower road or the bridge.  The app makes
the bridge an X-Plane ROAD instead -- a chain of network segments whose
middle junctions stand at stacking level 1 (X-Plane draws them as a
bridge) and whose end junctions stand at level 0 on the ground -- and the
page leaves the span:

* WHERE (spec B1; every threshold a ``[road_gen]`` law key): a mapped
  ``highway`` way tagged ``bridge`` (not ``no``) that (a) crosses a LOWER
  mapped road or rail (a lower ``layer``, or a tunnel) where the survey
  shows a grade separation -- its ends on their embankments, at least
  ``witness_share`` of ``[bridge] clearance_minimum_m`` over the lower
  road, the rest cut out of it (``planar/road_bridge_clear``, #2141 item
  5); never an elevated ramp the survey carries at grade over an at-grade
  road; (b) has at least
  ``page_cover_frac`` of its carriageway under the pack's pavement; (c)
  the pack draws no crossing of its own there -- no hard deck, modelled
  crossing, elevated top or road segment of its own over the span ("the
  pack always wins", ``planar/road_bridge_pack``; other installed road
  packs are not read); (d) the airport has a pack DSF to write the chain
  into;
* THE SPAN (B3): the bridge's axis buffered by its carriageway half width
  plus ``span_margin_m``; the pack's pavement there leaves the
  classification's sources (:func:`clip_spans`, upstream of every role
  read) so the lower road's cut stays and the ground under the span
  follows the survey;
* THE ENDS STAND ON THEIR EMBANKMENTS (owner 16y (3): "it's just too low
  because the mesh is still cut down on either end instead of on the
  elevated embankments"): the span's ground is never graded down -- no
  pavement face of the page stands there to pull it -- and the chain's
  level-0 junctions are the bridge's own mapped ends.

The record (:func:`_road_bridges`) is plain data in lon/lat, published to
the object stage on the graded surface's provenance
(``pipeline/generated_publication``).  Nothing here names an airport.

Build-time impact: one pass over the mapped ways and the pavement pages,
milliseconds; an airport with no road bridge over pavement returns at once.
"""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union
from shapely.strtree import STRtree

from .deck_generated import GLOBAL_OFFER, global_only
from .road_bridge_clear import clearance_plan, span_cuts, witnessed
from .structure_approach import carriageway_width_m

__all__ = ["attach_road_bridges", "span_cells"]


def _layer(tags) -> int:
    try:
        return int(float(str((tags or {}).get("layer", "0")).strip() or 0))
    except ValueError:
        return 0


def _is_road_bridge(tags) -> bool:
    b = str((tags or {}).get("bridge", "")).strip()
    return bool(b) and b != "no" and bool((tags or {}).get("highway")) \
        and not (tags or {}).get("aeroway")


def _pages(airport) -> list[Polygon]:
    out = []
    for pv in getattr(airport, "pavements", ()) or ():
        if len(pv.outer) < 3:
            continue
        p = Polygon(pv.outer, [h for h in pv.holes if len(h) >= 3])
        out.append(p if p.is_valid else p.buffer(0.0))
    return out


def _pack_ok(airport) -> bool:
    """B1 (d): a pack DSF to write the chain into; a Global Airports entry
    is read on (its bridges are the offer's candidates, #2169)."""
    pack = getattr(airport, "pack", None)
    return global_only(airport) or bool(pack is not None and getattr(pack, "dsf_paths", ()))


def _cut_region(dem, line: LineString, reach: float, levels: tuple[float, float],
                drop: float, step: float = 2.0):
    """The ground within ``reach`` of the bridge axis where the survey stands
    ``drop`` or more under the deck -- straight between the ends' ``levels``
    on their embankments (``road_bridge_clear.deck_at``) -- (the lower road's
    cutting beside the span, owner 16y (3): the pack's pavement there is
    graded into the cut and pulls the bridge's ends down with it; #2141:
    a page beside a raised end, read whole, stood 4.8 m over the lower road
    2.6 m from it), as one polygon touching the axis, else ``None``."""
    import numpy as np
    from shapely import line_locate_point, points

    from ..airport.dem import dem_z_many
    if dem is None:
        return None
    x0, y0, x1, y1 = line.buffer(reach).bounds
    xs, ys = np.meshgrid(np.arange(x0, x1, step), np.arange(y0, y1, step))
    xs, ys = xs.ravel(), ys.ravel()
    zs = dem_z_many(dem, xs, ys)
    zone = line.buffer(reach)
    from shapely import contains_xy
    w = np.clip(line_locate_point(line, points(xs, ys)) / max(line.length, 1e-9), 0.0, 1.0)
    below = levels[0] + w * (levels[1] - levels[0]) - drop
    m = np.isfinite(zs) & (zs < below) & contains_xy(zone, xs, ys)
    if not m.any():
        return None
    h = step / 2.0 + 0.01
    from shapely.geometry import box as _box
    cells = unary_union([_box(x - h, y - h, x + h, y + h) for x, y in zip(xs[m], ys[m],
                                                                          strict=True)])
    parts = [q for q in getattr(cells, "geoms", [cells]) if q.intersects(line)]
    return unary_union(parts).intersection(zone) if parts else None


def _bridges(airport, law, objects=(), cache=None, mod_cache_root=None
             ) -> tuple[list[dict], list[str]]:
    rg = law.tables.structures.road_gen
    ways = [w for w in getattr(airport, "osm_ways", ()) or () if len(w.points) >= 2]
    # #2169: an airport over two tiles reads a way once per tile's extract
    # (two ids, one line): one bridge per line
    cands = list({tuple((round(x, 2), round(y, 2)) for x, y in w.points): w
                  for w in reversed(ways) if _is_road_bridge(w.tags)}.values())[::-1]
    if not cands or not _pack_ok(airport):
        return [], []
    pages = _pages(airport)
    if not pages:
        return [], []
    P = unary_union(pages)
    others = [w for w in ways if any((w.tags or {}).get(k) for k in ("highway", "railway"))]
    lines = [LineString(w.points) for w in others]
    tree = STRtree(lines)
    tn = law.tables.structures.tunnel
    dem = getattr(airport, "dem", None)
    from .road_bridge_pack import PackRoads, pack_provides
    from .deck_generated import _approach_run_m
    from .structure_underpass import aeroway_decks
    aero = [(LineString(a.points), carriageway_width_m(a.tags, law) / 2.0)
            for a in aeroway_decks(airport, law)]
    run = _approach_run_m(law)
    roads = PackRoads(airport, mod_cache_root)
    _to_xy, to_ll = airport.frame.transformers()
    out: list[dict] = []
    notes: list[str] = []
    for w in cands:
        line = LineString(w.points)
        half = carriageway_width_m(w.tags, law) / 2.0
        carriage = line.buffer(half, cap_style="flat")
        if carriage.area <= 0.0:
            continue
        cover = carriage.intersection(P).area / carriage.area
        lay = max(_layer(w.tags), 1)
        crossed = []
        for j in tree.query(line, predicate="crosses"):
            o = others[int(j)]
            if o.id == w.id:
                continue
            t = o.tags or {}
            if not (_layer(t) < lay or str(t.get("tunnel", "no")) in tn.admitted_values):
                continue
            x = line.intersection(lines[int(j)])
            # a road leaving the bridge's own END is its approach, never a
            # road under it (MEASURED KIAH -1318: service -1482 runs on from
            # its north end and read as a lower road)
            pts = [q for q in getattr(x, "geoms", [x]) if q.geom_type == "Point"
                   and min(q.distance(Point(line.coords[0])),
                           q.distance(Point(line.coords[-1]))) > _JOIN_END_M]
            if pts:
                crossed.append((str(o.id), lines[int(j)], pts[0], t))
        into = None
        if cover < float(rg.page_cover_frac):
            # #2181 item 3 / #2183 item 5: no pack page draws it, but a lower
            # road it crosses runs into a taxiway bridge's cut
            into = _into_deck_cut(crossed, lines, tree, aero, run, law)
            if into is None:
                continue
        # #2141 item 5: the clearance is the survey's ends on their
        # embankments and the lower roads cut by the rest (road_bridge_clear)
        plan = clearance_plan(airport, law, w, line, crossed)
        lower = [c[0] for c in crossed]
        mid = line.interpolate(0.5, normalized=True)
        la, lo = to_ll(mid.x, mid.y)
        where = (f"road bridge {w.id} {w.tags.get('highway')} {line.length:.0f} m "
                 f"at {la:.6f},{lo:.6f}")
        if not witnessed(plan, law):
            notes.append(f"{where}: {100 * cover:.0f} % under pack pavement, "
                         + ("crosses no lower road" if not crossed else
                            f"over {', '.join(lower[:4])} the survey shows "
                            + ("nothing" if plan is None else f"{plan.witnessed:.1f} m")
                            + " of its clearance with its ends on their "
                              f"embankments (under {float(rg.witness_share):g} of it)")
                         + " -- not generated (B1 (a), #2141)")
            continue
        span = line.buffer(half + float(rg.span_margin_m), cap_style="flat")
        provided = pack_provides(span, line, objects, cache, roads, law)
        if provided:
            notes.append(f"{where}: {100 * cover:.0f} % under pack pavement over "
                         f"{', '.join(lower[:4])} -- REFUSED: {provided} (B1 (c), the pack "
                         f"always wins)")
            continue
        if global_only(airport):
            notes.append(f"{where}: {100 * cover:.0f} % under pack pavement over "
                         f"{', '.join(lower[:4])} -- REFUSED: {GLOBAL_OFFER}")
            continue
        low = _cut_region(dem, line, float(rg.cut_reach_m), plan.levels, float(rg.cut_drop_m))
        if low is not None:
            span = unary_union([span, low]).buffer(0.0)
            span = max(getattr(span, "geoms", [span]), key=lambda q: q.area) \
                if span.geom_type != "Polygon" else span
            span = Polygon(span.exterior).simplify(0.5)
        # the cut goes all the way under the span (owner 2026-11-17 18:30Z)
        ground = span_cuts(airport, law, line, plan.levels, crossed, span)
        out.append({"id": str(w.id), "highway": str(w.tags.get("highway")),
                    "_line_xy": plan.chain or line, "_span_xy": span, "half_m": half,
                    "into": into,
                    "cover": round(cover, 3), "over": lower, "ground": ground,
                    "levels": plan.levels, "_axis_xy": line})
        notes.append(f"{where}: " + (f"{100 * cover:.0f} % under pack pavement" if into is None
                                     else f"over {into}")
                     + f" over {', '.join(lower[:4])} -- GENERATED (spec 2123 B; a narrow flat "
                       f"deck, #2183 item 5); {plan.note()}")
    return out, notes


def _road_bridges(airport, law, objects=(), cache=None, mod_cache_root=None
                  ) -> tuple[tuple[dict, ...], list[str]]:
    """``(the generated road bridges as plain records, notes)`` (module
    doc): each ``{"id", "highway", "line", "span_wkt", "junctions",
    "subtype", "net", "cover", "over"}`` in lon/lat, the junctions
    ``[lon, lat, level]``: level 0 at the mapped ends, level 1 at
    ``level1_inset_m`` inside each."""
    rg = law.tables.structures.road_gen
    bs, notes = _bridges(airport, law, objects, cache, mod_cache_root)
    if not bs:
        return (), notes
    _to_xy, to_ll = airport.frame.transformers()

    def ll(x, y):
        la, lo = to_ll(float(x), float(y))
        return [round(float(lo), 9), round(float(la), 9)]
    out = []
    for b in bs:
        line: LineString = b["_line_xy"]
        L = line.length
        inset = min(float(rg.level1_inset_m), L / 3.0)
        js = [ll(*line.coords[0]) + [0]]
        for s in (inset, L - inset):
            p = line.interpolate(s)
            js.append(ll(p.x, p.y) + [1])
        js.append(ll(*line.coords[-1]) + [0])
        span = Polygon([ll(x, y) for x, y in b["_span_xy"].exterior.coords])
        out.append({"id": b["id"], "highway": b["highway"],
                    "line": [ll(x, y) for x, y in line.coords],
                    "span_wkt": span.wkt, "junctions": js, "subtype": int(rg.subtype),
                    "net": str(rg.net_def), "cover": b["cover"], "over": b["over"],
                    "span_xy": [[round(x, 3), round(y, 3)]
                                for x, y in b["_span_xy"].exterior.coords[:-1]],
                    "ground": [dict(g) for g in b["ground"]],
                    # the deck line (``road_bridge_clear.deck_at``): the ends'
                    # levels on their embankments along the mapped axis
                    "levels": [round(float(v), 3) for v in b["levels"]],
                    "half_m": round(float(b["half_m"]), 3),
                    "axis_xy": [[round(x, 3), round(y, 3)] for x, y in b["_axis_xy"].coords]})
    return tuple(out), notes


def attach_road_bridges(airport, law, notes: "list[str] | None" = None, objects=(),
                        cache=None, mod_cache_root: "str | None" = None):
    """``airport`` with its generated road bridges read ONCE
    (:func:`_road_bridges`, on the pavement as loaded; ``objects`` /
    ``cache`` the pack read and ``mod_cache_root`` its DSF dumps, which
    refuse a bridge the pack draws itself, B1 (c)).  A second call is a
    no-op."""
    if getattr(airport, "road_bridges", ()):
        return airport
    bs, bnotes = _road_bridges(airport, law, objects, cache, mod_cache_root)
    if notes is not None:
        notes.extend(bnotes)
    if not bs:
        return airport
    return _dc.replace(airport, road_bridges=tuple(bs),
                       osm_ways=_densified(getattr(airport, "osm_ways", ()) or (), bs))


def _into_deck_cut(crossed, lines, tree, aero, run: float, law) -> "str | None":
    """#2181 item 3 / #2183 item 5: the bridge crosses a lower road that
    runs, within ``run`` (the generated cut's approach run,
    ``deck_generated._approach_run_m``) of the crossing along its mapped
    chain, under a mapped aeroway bridge (``aeroway_decks``) -- the road
    the build cuts down to a taxiway deck's floor: the bridge over it is
    built though no pack page draws it.  Names the crossing, or ``None``.
    MEASURED KPHX ``-301`` / ``-302`` over motorways ``-1002`` / ``-2560``
    64 / 60 m from taxiway bridges ``-96`` / ``-1259``; KIAH ``-1318``
    over ``-59337`` 66 m from ``-373``."""
    from shapely.geometry import Point
    from shapely.ops import substring

    from .deck_generated import _road_chain
    if not aero:
        return None
    for oid, low, pt, tags in crossed:
        # the road grown end to end through OSM's splits, whatever their
        # length (a primary split 34 m short of the bridge runs on under it
        # as a 185 m way: KIAH -59337 / -54869), read within ``run``
        chain = _road_chain(low, lines, tree, 10.0 * run)
        s = chain.project(Point(pt))
        near = substring(chain, max(0.0, s - run), min(chain.length, s + run))
        half = carriageway_width_m(tags, law) / 2.0
        for a, a_half in aero:
            # the lower road's carriageway reaches under the bridge's own
            # (its mapped end may stop short of the aeroway's centreline)
            if near.distance(a) <= half + a_half:
                q = a.interpolate(a.project(near.centroid))
                d = abs(chain.project(q) - s)
                return f"lower road {oid}, {d:.0f} m from a taxiway bridge's cut"
    return None


#: a crossing this close to the bridge's mapped end is its own approach (m)
_JOIN_END_M = 0.5

#: a lower road under a cut ribbon carries a node at least this often (m)
_DENSE_M = 2.0


def _densified(ways, bridges) -> tuple:
    """``ways`` with every LOWER road carrying a node every :data:`_DENSE_M`
    along its cut ribbon's axis (``ground``) and its stretch under the span
    (a node on each side of the span's edge): the map's road vertices are
    the way's nodes, and an edge from a node outside the span to one beyond
    it stands over the cut between them (MEASURED ESSA ``-3`` over ``-80``:
    3 vertices cut under a 55 m span) and escapes the clearance ceiling
    (``constraints/road_bridge_ceiling``).  The nodes lie on the way's own
    line: its shape is unchanged."""
    import math

    from shapely.geometry import Point
    axes: dict[str, list] = {}
    for b in bridges:
        span = Polygon(b["span_xy"]).buffer(_DENSE_M) \
            if len(b.get("span_xy") or ()) >= 3 else None
        for w in b.get("over", ()) or ():
            axes.setdefault(str(w), []).extend(
                LineString(g["axis"]) for g in b.get("ground", ()) or ())
            if span is not None:
                axes[str(w)].append(span)
    if not axes:
        return tuple(ways)
    out = []
    for w in ways:
        cuts = axes.get(str(w.id))
        if not cuts or len(w.points) < 2 or w.closed:
            out.append(w)
            continue
        ln = LineString(w.points)
        extra = []
        for ax in cuts:
            if ax.geom_type == "Polygon":           # the stretch under the span
                x = ln.intersection(ax)
                ends = [(ln.project(Point(g.coords[0])), ln.project(Point(g.coords[-1])))
                        for g in getattr(x, "geoms", [x])
                        if g.geom_type == "LineString" and g.length > 0.0]
            elif ax.distance(ln) <= 1e-3:
                ends = [(ln.project(Point(ax.coords[0])), ln.project(Point(ax.coords[-1])))]
            else:
                continue
            for a, b in ends:
                a, b = min(a, b), max(a, b)
                n = max(1, math.ceil((b - a) / _DENSE_M))
                extra += [a + (b - a) * k / n for k in range(n + 1)]
        if not extra:
            out.append(w)
            continue
        own = [ln.project(Point(p)) for p in w.points]
        if any(b <= a for a, b in zip(own, own[1:], strict=False)):
            out.append(w)               # a way that doubles back: left as mapped
            continue
        keep = sorted(set(own) | {s for s in extra
                                  if all(abs(s - o) > 0.25 for o in own)})
        pts = []
        for s in keep:
            if s in own:
                pts.append(tuple(w.points[own.index(s)]))
            else:
                p = ln.interpolate(s)
                pts.append((float(p.x), float(p.y)))
        out.append(_dc.replace(w, points=tuple(pts)))
    return tuple(out)


def span_cells(classification, airport, law) -> tuple[_t.Any, list[str]]:
    """``classification`` with the PACK PAVEMENT under every generated road
    bridge's span cut out of its cells (B3, upstream of every role read but
    after the sources were read whole: a page's class is the page's, never
    the class of what is left once its bridge is cut out -- MEASURED ESSA
    ``dsf:pol192``, a 14.2 m lot read 11.6 m wide without its 165 m bridge,
    a strip, and graded 6 m into the motorway cut beside the abutment).
    The roads mapped under the span keep their cells."""
    import dataclasses as dc

    from .cell_knife import knife_cells
    bs = getattr(airport, "road_bridges", ()) or ()
    if not bs or classification is None or not classification.cells:
        return classification, []
    knife = unary_union([Polygon(b["span_xy"]) for b in bs])
    pages = {str(pv.id) for pv in getattr(airport, "pavements", ()) or ()}
    polys = []
    for c in classification.cells:
        p = Polygon(c.ring, c.holes) if len(c.ring) >= 3 else Polygon()
        polys.append(p if p.is_valid else p.buffer(0.0))
    cells, n = knife_cells(classification.cells, polys, knife, law, (), cut_pads=False,
                           mark="road_bridge_span",
                           cuts=lambda c: str(c.ref).split("#")[0] in pages)
    return (dc.replace(classification, cells=tuple(cells)),
            [f"generated road bridges: {n} pack pavement cell(s) cut under "
             f"{len(bs)} span(s) (spec 2123 B3)"])
