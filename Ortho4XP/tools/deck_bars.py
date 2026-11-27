"""LIBRARY of ``tools/deck_probe.py --weld / --underside / --envelope``
(#2239 / #2241; owner sim read 2026-11-26T15:02Z: "the weld must span the
deck's full width including shoulders", "the ground under the bridge is
too deep", "the road envelope under/through the bridge must stay clear"):
THREE OF A PACK DECK'S BARS, off a ``--solved-out`` pickle, read on the
solved surface as the mesh takes it (``pipeline/generated_publication.
_surface_at``: each map face triangulated on its own ring).

* THE WELD: every metre along each END EDGE (``geom/deck_end_edge``: the
  ring's side the end line lies on, corner to corner), :data:`WELD_OUT_M`
  outside the ring, the solved surface less the deck's top there: the
  object's ONE zero (the mean over both end lines' anchor stations of the
  solved level less the slab's top abeam, as the object stage seats it,
  ``check_grade_lib/families/deck_end_flush``) plus the slab's top along
  the edge (a straight fit over ``DeckBridge.station_tops`` against the
  seats' run, else the end's authored top).  Bar ``|d| <= tol``.
* THE UNDERSIDE: every :data:`GRID_M` inside the ring (``INSET_M`` in) on
  a trench floor face (``tunnel_ramp``), the solved surface less the
  deck's bottom (the end levels' mean less ``depth_m``).  Bar: median
  within ``tol``, max ``<= tol``.
* SQUARE ENDS: every map vertex inside the deck's MOUTH ZONE between its
  band lines (``geom/deck_plan``: beyond each mouth between the prolonged
  end edges, out to the trench's farthest reach, less the safe bands), its
  solved level less the surface on the nearest mapped road's centreline
  abeam -- the floor flat across, no rim or DEM-pinned outline vertex
  across the open mouth.  Bar: none over ``tol``.
* THE ROAD ENVELOPE: every :data:`ROAD_STEP_M` over each mapped road's
  carriageway (``structure_approach.carriageway_width_m``) crossing the
  ring (``ROAD_REACH_M`` past it), the solved surface less the surface on
  the road's centreline abeam.  Bar: none over ``tol``.

Promoted from lane lcyyz7's scratch ``bars.py`` on its second use (tool
discipline, RULINGS 7e90032).  Pure: reads the pickle; writes nothing.
"""
from __future__ import annotations

import math
import typing as _t

__all__ = ["GRID_M", "ROAD_REACH_M", "ROAD_STEP_M", "WELD_OUT_M", "deck_bars", "envelope",
           "square_ends", "underside", "weld"]

#: the weld is read this far outside the end edge (m)
WELD_OUT_M = 0.3
#: the underside grid (m) and its inset from the ring (m)
GRID_M = 3.0
INSET_M = 2.0
#: the road envelope's sample step and its reach past the ring (m)
ROAD_STEP_M = 0.5
ROAD_REACH_M = 5.0


class _Near:
    """The faces of a map near ``region`` (a bounding-box cull), with the
    map's own vertex and ring readers -- the surface reader's view."""

    def __init__(self, pm, region):
        self.vertices = pm.vertices
        self._pm = pm
        x0, y0, x1, y1 = region.bounds
        self.faces = {}
        for k, f in pm.faces.items():
            xs = [pm.vertices[v].xy for v in pm.ring_vertices(f.ring)]
            if xs and not (max(q[0] for q in xs) < x0 or min(q[0] for q in xs) > x1
                           or max(q[1] for q in xs) < y0 or min(q[1] for q in xs) > y1):
                self.faces[k] = f

    def ring_vertices(self, r):
        return self._pm.ring_vertices(r)

    def role_at(self, p) -> "str | None":
        from shapely.geometry import Point, Polygon
        for f in self.faces.values():
            poly = Polygon([self.vertices[v].xy for v in self.ring_vertices(f.ring)])
            if poly.is_valid and poly.contains(Point(p)):
                return f.role
        return None


def _levels(pm, z, db) -> dict:
    """``{"a": level, "b": level}``: each end line's mean at its anchor's
    stations, else its seat level (``deck_cut_cover._end_level``)."""
    from deck_cut_cover import _end_level
    out = {}
    for e in ("a", "b"):
        an = [x for x in getattr(pm, "deck_anchors", ()) or ()
              if x.object_id == db.object_id and str(x.end).lower() == e]
        vs = an[0].stations if an else ()
        out[e] = (sum(float(z[v]) for v in vs) / len(vs)) if vs else _end_level(pm, z, db, e)
    return out


def _top_fit(edge, seats, tops, top: float) -> _t.Callable[[float], float]:
    """The slab's top along ``edge`` at run ``s``: a straight fit over the
    stations' ``tops`` (``top`` with fewer than two)."""
    from shapely.geometry import Point
    if len(tops) != len(seats) or len(seats) < 2:
        return lambda _s: top
    ss = [edge.project(Point(q)) for q in seats]
    ts = [float(t) for t in tops]
    n = len(ss)
    ms, mt = sum(ss) / n, sum(ts) / n
    var = sum((s - ms) ** 2 for s in ss)
    k = 0.0 if var <= 1e-12 else sum((s - ms) * (t - mt) for s, t in zip(ss, ts, strict=True)) / var
    return lambda s: mt + k * (s - ms)


def _edges(db) -> list:
    """``[(end, edge LineString, seat line, top(s)), ...]`` per end line."""
    from auto_patch_v2.geom.deck_end_edge import end_edge
    from shapely.geometry import LineString, Point
    sts = getattr(db, "station_tops", ()) or ()
    out = []
    for k, (e, st, top) in enumerate((("a", db.seats_a, db.top_a), ("b", db.seats_b, db.top_b))):
        pts = end_edge(db.ring, st) if len(st) else []
        if len(pts) < 2:
            continue
        edge = LineString(pts)
        out.append((e, edge, LineString(st) if len(st) > 1 else Point(st[0]),
                    _top_fit(edge, st, sts[k] if len(sts) == 2 else (), float(top))))
    return out


def _zero(pm, z, db, edges) -> "float | None":
    """The object's one zero: the mean over its anchors' stations of the
    solved level less the slab's top abeam (module doc)."""
    from shapely.geometry import Point
    acc = []
    for e, edge, _line, top in edges:
        for x in getattr(pm, "deck_anchors", ()) or ():
            if x.object_id == db.object_id and str(x.end).lower() == e:
                acc += [float(z[v]) - top(edge.project(Point(pm.vertices[v].xy)))
                        for v in x.stations]
    return sum(acc) / len(acc) if acc else None


def weld(pm, z, db, za, to_ll, tol: float) -> dict:
    """The weld read (module doc)."""
    from shapely.geometry import Point, Polygon
    ring = Polygon(db.ring)
    edges = _edges(db)
    zero = _zero(pm, z, db, edges)
    out = []
    for e, edge, line, top in edges if zero is not None else ():
        for i in range(int(edge.length)):
            s = min(max(i + 0.5, 0.25), edge.length - 0.25)
            p, q = edge.interpolate(s), edge.interpolate(min(edge.length, s + 0.1))
            tx, ty = q.x - p.x, q.y - p.y
            n = math.hypot(tx, ty) or 1.0
            nx, ny = ty / n, -tx / n
            if ring.contains(Point(p.x + nx * WELD_OUT_M, p.y + ny * WELD_OUT_M)):
                nx, ny = -nx, -ny
            o = (p.x + nx * WELD_OUT_M, p.y + ny * WELD_OUT_M)
            zz = za(o)
            if zz is None:
                continue
            where = "pave" if line.distance(Point(p.x, p.y)) < 1.0 else "shoulder"
            out.append((round(zz - zero - top(s), 3), e, where, to_ll(*o), round(s, 1)))
    over = [w for w in out if abs(w[0]) > tol]
    return {"zero": None if zero is None else round(zero, 3), "n": len(out), "over": len(over),
            "worst": max(out, key=lambda w: abs(w[0])) if out else None,
            "shoulder_n": sum(w[2] == "shoulder" for w in out),
            "shoulder_over": sum(w[2] == "shoulder" for w in over), "samples": out}


def underside(near, db, za, lv) -> dict:
    """The underside read (module doc)."""
    from shapely.geometry import Point, Polygon
    want = 0.5 * (lv["a"] + lv["b"]) - float(db.depth_m)
    inner = Polygon(db.ring).buffer(-INSET_M)
    fl = []
    if not inner.is_empty:
        x0, y0, x1, y1 = inner.bounds
        y = y0
        while y <= y1:
            x = x0
            while x <= x1:
                if inner.contains(Point(x, y)) and near.role_at((x, y)) == "tunnel_ramp":
                    zz = za((x, y))
                    if zz is not None:
                        fl.append(zz - want)
                x += GRID_M
            y += GRID_M
    fl.sort()
    return {"want": round(want, 3), "n": len(fl),
            "median": round(fl[len(fl) // 2], 3) if fl else None,
            "min": round(fl[0], 3) if fl else None, "max": round(fl[-1], 3) if fl else None}


def square_ends(near, z, airport, law, db, za, to_ll, tol: float) -> dict:
    """The square-ends read (module doc)."""
    from auto_patch_v2.geom.deck_end_edge import end_edge
    from auto_patch_v2.geom.deck_plan import plan, safe_band
    from shapely.geometry import LineString, Point, Polygon
    from shapely.ops import unary_union
    ea, eb = (end_edge(db.ring, st) if len(st) else [] for st in (db.seats_a, db.seats_b))
    dp = plan(db.ring, ea, eb, safe_band(law))
    ring = Polygon(db.ring)
    floors = [Polygon([near.vertices[v].xy for v in near.ring_vertices(f.ring)])
              for f in near.faces.values() if f.role == "tunnel_ramp"]
    floors = [p if p.is_valid else p.buffer(0.0) for p in floors if len(p.exterior.coords) > 3]
    roads = [LineString(w.points) for w in getattr(airport, "osm_ways", ()) or ()
             if len(w.points) >= 2 and "highway" in w.tags
             and LineString(w.points).intersects(ring)]
    if dp is None or not floors or not roads:
        return {"n": 0, "over": 0, "worst": None}
    outer = unary_union(floors)
    zone = dp.mouth_zone(outer).intersection(dp.floor())
    out = []
    if not zone.is_empty:
        x0, y0, x1, y1 = zone.bounds
        for v, vx in near.vertices.items():
            x, y = vx.xy
            if not (x0 <= x <= x1 and y0 <= y <= y1) or not zone.contains(Point(x, y)):
                continue
            p = Point(x, y)
            cl = min(roads, key=lambda r: r.distance(p))
            c = cl.interpolate(cl.project(p))
            zc = za((c.x, c.y))
            if zc is not None:
                out.append((round(float(z[v]) - zc, 3), to_ll(x, y), int(v)))
    return {"n": len(out), "over": sum(abs(e[0]) > tol for e in out),
            "worst": max(out, key=lambda e: abs(e[0])) if out else None,
            "zone_m2": round(zone.area, 1)}


def envelope(airport, law, db, za, to_ll, tol: float) -> dict:
    """The road envelope read (module doc), per road and in all."""
    from auto_patch_v2.planar.structure_approach import carriageway_width_m
    from shapely.geometry import LineString, Point, Polygon
    ring = Polygon(db.ring)
    reach = ring.buffer(ROAD_REACH_M)
    env, roads = [], {}
    for w in getattr(airport, "osm_ways", ()) or ():
        if len(w.points) < 2 or "highway" not in w.tags:
            continue
        cl = LineString(w.points)
        if not cl.intersects(ring):
            continue
        half = carriageway_width_m(w.tags, law) / 2.0
        reg = cl.buffer(half, cap_style="flat").intersection(reach)
        if reg.is_empty:
            continue
        bx0, by0, bx1, by1 = reg.bounds
        mine = []
        y = by0
        while y <= by1:
            x = bx0
            while x <= bx1:
                if reg.contains(Point(x, y)):
                    c = cl.interpolate(cl.project(Point(x, y)))
                    zz, zc = za((x, y)), za((c.x, c.y))
                    if zz is not None and zc is not None:
                        mine.append((round(zz - zc, 3), w.id, to_ll(x, y)))
                x += ROAD_STEP_M
            y += ROAD_STEP_M
        roads[str(w.id)] = {"n": len(mine), "over": sum(e[0] > tol for e in mine)}
        env += mine
    return {"n": len(env), "over": sum(e[0] > tol for e in env),
            "worst": max(env) if env else None, "roads": roads,
            "samples": sorted(env, reverse=True)[:200]}


def deck_bars(pm, z, airport, law, decks, tol: float,
              which=("weld", "underside", "envelope", "ends")) -> list[dict]:
    """Per deck of ``decks``: its levels and each read in ``which``."""
    from auto_patch_v2.pipeline.generated_publication import _surface_at
    from shapely.geometry import Polygon
    to_ll = airport.frame.transformers()[1]
    out = []
    for db in decks:
        if len(getattr(db, "ring", ()) or ()) < 3:
            continue
        near = _Near(pm, Polygon(db.ring).buffer(25.0))
        za = _surface_at(near, z, airport)
        lv = _levels(pm, z, db)
        q = {"object": db.object_id, "levels": {k: round(v, 3) for k, v in lv.items()
                                                 if v is not None}}
        if None in lv.values():
            q["note"] = "an end line has no solved level"
            out.append(q)
            continue
        if "weld" in which:
            q["weld"] = weld(pm, z, db, za, to_ll, tol)
        if "underside" in which:
            q["underside"] = underside(near, db, za, lv)
        if "envelope" in which:
            q["envelope"] = envelope(airport, law, db, za, to_ll, tol)
        if "ends" in which:
            q["ends"] = square_ends(near, z, airport, law, db, za, to_ll, tol)
        out.append(q)
    return out
