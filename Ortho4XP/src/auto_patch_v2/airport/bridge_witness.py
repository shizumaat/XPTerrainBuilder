"""THE FREE BRIDGE'S POSITIVE WITNESS (#2065; spec
``bridge-classifier-spec.md`` §1 W1-W6, RULINGS 2026-10-22m/p/d, 13r).

A pack deck (``flag`` / ``signature``) is a FREE-STANDING BRIDGE only when the
map and its own geometry say so — never because nothing refused it.  Pure
geometry on the deck's plate triangles, its ring and the mapped ways, all in
one metric frame (x, y, authored y); the DEM only in W5:

* W1 ROUTE: a chain of mapped ``highway`` / ``railway`` / ``aeroway=taxiway``
  ways (no tunnel), joined end to end by ``deck_carry.route_chains`` (#2035),
  holds at least ``[bridge] deck_min_span_m`` of ``bridge != no`` inside the
  plate and crosses the plate outline twice — or once, ending within
  ``abutment_sample_step_m`` inside.  The crossings ARE the deck's ENDS;
  ``out_a`` / ``out_b`` the route's outward tangents there.
* W2 RIBBON: the chain, buffered ``free_route_half_width_m``, covers at least
  ``free_route_cover_min`` of the plate's plan.
* W3 CONTINUOUS DRIVEN SURFACE: every near-horizontal plate face over a
  station every ``abutment_sample_step_m`` on the route between the ends; a
  LAYER links station to station within ``[tunnel] ramp_max_grade`` x run +
  ``deck_flush_m``; the deck surface is the highest layer present on
  :data:`SURFACE_SHARE` of the stations, both ends included.
* W4 OPEN SKY: no frame solid within ``clearance_minimum_m`` over that layer
  (above its own plane, ``deck_plane_bin_m``) on more than
  :data:`ROOF_SHARE` of the stations — a roof, a canopy, a hall, a floor.
* W5 SPAN: between the ends the plate stands over a crossing way of another
  chain, over water, or over ground ``deck_min_clearance_under_m`` under the
  chord between the end grounds.
* W6 FREE FRAME (:func:`_free_frame`): every other body of the frame inside
  the bridge's decks and route corridors (the plate's width, extended
  ``[building_pad] fill_road_reach_m`` beyond each end) and on no emitted
  object pad.

THE BRIDGE GROUP (:func:`frame_witness`): W-decks of one frame (W1-W5 hold)
whose rings touch within ``[placement] footprint_touch_m``; a ``flag`` deck
with no route of its own (W1 or W2 fails) joins when it touches a W-deck,
carries W3 and W4 along its own long axis (``geom/centreline``: the ribbon's
medial axis, which a curved ramp's rectangle does not follow) and is at most
:data:`STUB_WIDTH_RATIO` x the group's widest W-deck (plan area over length).

Nothing here names a pack, a resource or an airport.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

import numpy as np
from shapely import contains_xy
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import substring, unary_union

from ..geom.centreline import ribbon_centreline
from ..geom.lowest_face import every_z_at
from .deck_carry import route_chains
from .deck_signature import is_bridge_way

__all__ = ["Route", "Witness", "route_of", "deck_witness", "frame_witness",
           "placed_faces", "up_faces", "SURFACE_SHARE", "ROOF_SHARE", "STUB_WIDTH_RATIO"]

XY = tuple[float, float]

#: W3: the deck surface is present on at least this share of the stations
SURFACE_SHARE = 0.8
#: W4: a solid over the surface on more than this share of the stations is a roof
ROOF_SHARE = 0.2
#: the bridge group: a routeless stub is at most this times the widest W-deck
STUB_WIDTH_RATIO = 1.5
#: a hair inside the plate along the route, where an end station reads it
_HAIR = 0.05
#: W6: a body is inside the bridge when this share of its plan vertices is
_INSIDE_SHARE = 0.95
#: the most paths one chain is read along (a chain is a handful of ways)
_MAX_PATHS = 64


@_dc.dataclass(frozen=True)
class Route:
    """W1/W2's reading of one deck: the chain's way ids, the path the ends
    are read along, the two ends (``s`` along the path, the point, the
    outward unit tangent), its ``bridge != no`` metres inside the plate and
    the ribbon's cover of the plate."""

    ways: tuple[int, ...]
    path: LineString
    s_a: float
    s_b: float
    end_a: XY
    end_b: XY
    out_a: XY
    out_b: XY
    bridge_m: float
    cover: float


@_dc.dataclass(frozen=True)
class Witness:
    """One deck's W1-W5 values and the first witness it fails (``""`` when
    W1-W5 hold).  ``layer`` is the deck surface's z per station (``nan``
    where absent); ``span`` names what it spans."""

    route: "Route | None"
    stations: tuple[XY, ...] = ()
    layer: tuple[float, ...] = ()
    surface_share: float = 0.0
    roof_share: float = 0.0
    span: str = ""
    failed: str = ""
    #: the deck's plan width (plate area over its length between the ends)
    width_m: float = 0.0
    #: set by :func:`frame_witness`: the W-deck a routeless stub joined
    joined: str = ""
    #: set by :func:`frame_witness`: W6's failure for the group, ``""`` = free
    frame_failed: str = ""


# ── faces ───────────────────────────────────────────────────────────────

def placed_faces(vertices: np.ndarray, tri: np.ndarray, xy: XY,
                 heading_deg: float) -> np.ndarray:
    """Triangles ``tri`` of an OBJ8's ``vertices`` placed at ``xy`` /
    ``heading_deg``, as ``(n, 3, 3)`` frame x, y, authored y
    (``obj8._to_frame``, vectorised)."""
    if not len(tri):
        return np.zeros((0, 3, 3))
    v = np.asarray(vertices, float)[np.asarray(tri, int)]
    h = math.radians(heading_deg)
    s, c = math.sin(h), math.cos(h)
    x, y, z = v[..., 0], v[..., 1], v[..., 2]
    return np.stack([xy[0] + x * c - z * s, xy[1] - (x * s + z * c), y], axis=-1)


def up_faces(faces: np.ndarray, normal_min: float) -> np.ndarray:
    """The near-horizontal faces of ``faces``: ``|normal z|`` at least
    ``normal_min`` of the normal (``[bridge] deck_plate_normal_y_min``)."""
    if not len(faces):
        return faces
    n = np.cross(faces[:, 1] - faces[:, 0], faces[:, 2] - faces[:, 0])
    norm = np.linalg.norm(n, axis=1)
    ok = norm > 1e-12
    return faces[ok & (np.abs(n[:, 2]) >= normal_min * np.where(ok, norm, 1.0))]


def _near(faces: np.ndarray, region) -> np.ndarray:
    """The faces whose plan box meets ``region``'s box (a cheap cull)."""
    if not len(faces):
        return faces
    x0, y0, x1, y1 = region.bounds
    lo, hi = faces[:, :, :2].min(axis=1), faces[:, :, :2].max(axis=1)
    return faces[(hi[:, 0] >= x0) & (lo[:, 0] <= x1) & (hi[:, 1] >= y0) & (lo[:, 1] <= y1)]


# ── W1 / W2: the route ──────────────────────────────────────────────────

def _route_way(w) -> bool:
    t = w.tags or {}
    if t.get("tunnel", "no") != "no" or len(w.points) < 2:
        return False
    return "highway" in t or "railway" in t or t.get("aeroway") == "taxiway"


def _bridge(t: _t.Mapping[str, str]) -> bool:
    """``bridge != no`` on a route way (``deck_signature.is_bridge_way``,
    and a mapped taxiway bridge)."""
    return is_bridge_way(t) or (t.get("aeroway") == "taxiway"
                                and t.get("bridge", "no") not in ("", "no"))


def _paths(ways: _t.Sequence) -> list[tuple[LineString, tuple[int, ...]]]:
    """Every simple path through one chain, leaf to leaf, as ``(line, way
    indices)`` (a chain of one way is that way)."""
    if len(ways) == 1:
        return [(LineString(ways[0].points), (0,))]
    key = lambda p: (round(float(p[0]), 3), round(float(p[1]), 3))  # noqa: E731
    adj: dict[XY, list[tuple[int, XY]]] = {}
    for k, w in enumerate(ways):
        a, b = key(w.points[0]), key(w.points[-1])
        adj.setdefault(a, []).append((k, b))
        adj.setdefault(b, []).append((k, a))
    leaves = [n for n, e in adj.items() if len(e) == 1] or list(adj)[:1]
    out: list[tuple[LineString, tuple[int, ...]]] = []

    def walk(node: XY, used: list[int], coords: list) -> None:
        if len(out) >= _MAX_PATHS:
            return
        nxt = [(k, b) for k, b in adj[node] if k not in used]
        if not nxt:
            if used and (key(coords[0]) <= key(coords[-1]) or len(leaves) == 1):
                out.append((LineString(coords), tuple(used)))
            return
        for k, b in nxt:
            pts = list(ways[k].points)
            if key(pts[0]) != node:
                pts = pts[::-1]
            walk(b, used + [k], coords + pts[1:] if coords else pts)
    for leaf in leaves:
        walk(leaf, [], [])
    return out or [(LineString(w.points), (k,)) for k, w in enumerate(ways)]


def _ends(path: LineString, ring: Polygon, step: float) -> "tuple[float, float] | str":
    """``(s_a, s_b)``: the path's crossings of the plate outline (W1), or
    why it has no two ends."""
    hit = path.intersection(ring.exterior)
    pts = [Point(c) for g in getattr(hit, "geoms", [hit]) if not g.is_empty
           for c in g.coords]
    ss = sorted(path.project(p) for p in pts)
    tips = [s for s, p in ((0.0, Point(path.coords[0])),
                           (path.length, Point(path.coords[-1])))
            if ring.contains(p) and ring.exterior.distance(p) <= step]
    if len(ss) >= 2 and ss[-1] - ss[0] > 1e-6:
        return ss[0], ss[-1]
    if len(ss) == 1 and tips:
        a, b = sorted((ss[0], tips[0]))
        return a, b
    return f"crosses the plate outline {len(ss)} time(s)"


def _tangent(path: LineString, s: float, sign: float) -> XY:
    a = path.interpolate(max(0.0, min(path.length, s - 0.5)))
    b = path.interpolate(max(0.0, min(path.length, s + 0.5)))
    d = math.hypot(b.x - a.x, b.y - a.y) or 1.0
    return (sign * (b.x - a.x) / d, sign * (b.y - a.y) / d)


def _xy(path: LineString, s: float) -> XY:
    p = path.interpolate(s)
    return (p.x, p.y)


def _read_path(cw: _t.Sequence, path: LineString,
               idx: tuple[int, ...], ring: Polygon, cover: float, law
               ) -> tuple[tuple, "Route | str"]:
    """One path's ``(rank, Route or why W1 fails)``."""
    br = law.tables.structures.bridge
    bm = sum(LineString(cw[k].points).intersection(ring).length for k in idx
             if _bridge(cw[k].tags or {}))
    got = _ends(path, ring, float(br.abutment_sample_step_m))
    ok = not isinstance(got, str) and bm >= float(br.deck_min_span_m)
    rank = (ok, cover, bm)
    if isinstance(got, str):
        return rank, f"W1 route: {got} (bridge {bm:.0f} m, cover {cover:.2f})"
    if not ok:
        return rank, (f"W1 route: bridge stretch {bm:.0f} m < "
                      f"{float(br.deck_min_span_m):.0f} m (cover {cover:.2f})")
    sa, sb = got
    return rank, Route(tuple(int(w.id) for w in cw), path, sa, sb, _xy(path, sa),
                       _xy(path, sb), _tangent(path, sa, -1.0), _tangent(path, sb, 1.0),
                       bm, cover)


def route_of(ring: Polygon, ways: _t.Sequence, law) -> "Route | str":
    """W1 and W2's values for the plate ``ring`` (module doc): the best
    route — passing W1 first, then by ribbon cover, then bridge metres — or
    why no chain is one."""
    br = law.tables.structures.bridge
    reach = ring.buffer(float(br.abutment_sample_step_m))
    near = [w for w in ways if _route_way(w) and LineString(w.points).intersects(reach)]
    if not near:
        return "W1 route: no mapped route over the plate"
    best: "tuple | None" = None
    for chain in route_chains(near, reach):
        cw = [near[k] for k in chain]
        cover = unary_union([LineString(w.points) for w in cw]).buffer(
            float(br.free_route_half_width_m)).intersection(ring).area / max(ring.area, 1e-9)
        for path, idx in _paths(cw):
            got = _read_path(cw, path, idx, ring, cover, law)
            if best is None or got[0] > best[0]:
                best = got
    return best[1] if best is not None else "W1 route: no chain"


# ── W3 / W4: the driven surface and the open sky ───────────────────────

def _stations(path: LineString, s_a: float, s_b: float, step: float) -> tuple[XY, ...]:
    """Stations every ``step`` on ``path`` from ``s_a`` to ``s_b``, each end
    a hair inside."""
    a, b = s_a + _HAIR, s_b - _HAIR
    if b <= a:
        a = b = 0.5 * (s_a + s_b)
    n = max(1, int(round((b - a) / step)))
    return tuple(_xy(path, a + (b - a) * k / n) for k in range(n + 1))


def _distinct(z: np.ndarray, flush: float) -> list[float]:
    """A station's face heights, highest first, one per ``flush`` band."""
    kept: list[float] = []
    for v in sorted({round(float(v), 3) for v in z}, reverse=True):
        if not kept or kept[-1] - v > flush:
            kept.append(v)
    return kept


def _layers(zs: _t.Sequence[np.ndarray], run: _t.Sequence[float], cap: float,
            flush: float) -> list[dict[int, float]]:
    """The faces' z per station linked into LAYERS (W3): a z joins the layer
    it continues within ``cap`` x run + ``flush`` — the one seen most
    recently, then the closest (a layer resuming after a gap has a wider
    reach and must not take the step of one running on)."""
    layers: list[dict[int, float]] = []
    for i, z in enumerate(zs):
        taken: set[int] = set()
        for v in _distinct(z, flush):
            pick, best = None, (math.inf, math.inf)
            for li, lay in enumerate(layers):
                last = max(lay)
                d = abs(v - lay[last])
                if li not in taken and last < i and (i - last, d) < best \
                        and d <= cap * (run[i] - run[last]) + flush:
                    pick, best = li, (i - last, d)
            if pick is None:
                layers.append({i: v})
                pick = len(layers) - 1
            else:
                layers[pick][i] = v
            taken.add(pick)
    return layers


def driven_surface(plate_up: np.ndarray, stations: _t.Sequence[XY], law
                   ) -> tuple[tuple[float, ...], float]:
    """W3: ``(the deck surface's z per station, nan where absent; its share
    of the stations)`` — ``()`` and the best share seen when no layer is
    present on :data:`SURFACE_SHARE` of them with both ends."""
    xs = [p[0] for p in stations]
    ys = [p[1] for p in stations]
    zs = every_z_at(plate_up, xs, ys, edge_m=0.5)
    run = [0.0]
    for a, b in zip(stations, stations[1:], strict=False):
        run.append(run[-1] + math.dist(a, b))
    n = len(stations)
    layers = _layers(zs, run, float(law.tables.structures.tunnel.ramp_max_grade),
                     float(law.tables.structures.bridge.deck_flush_m))
    whole = [lay for lay in layers if len(lay) + 1e-9 >= SURFACE_SHARE * n
             and 0 in lay and n - 1 in lay]
    if not whole:
        return (), max((len(lay) / n for lay in layers), default=0.0)
    best = max(whole, key=lambda lay: float(np.mean(list(lay.values()))))
    return tuple(best.get(i, math.nan) for i in range(n)), len(best) / n


def _filled(layer: _t.Sequence[float]) -> np.ndarray:
    z = np.asarray(layer, float)
    ok = np.isfinite(z)
    idx = np.arange(len(z))
    return np.interp(idx, idx[ok], z[ok]) if ok.any() else z


def open_sky(frame_faces: np.ndarray, stations: _t.Sequence[XY],
             layer: _t.Sequence[float], law) -> float:
    """W4: the share of stations with a frame solid within
    ``clearance_minimum_m`` over the surface (above its own plane,
    ``deck_plane_bin_m``)."""
    br = law.tables.structures.bridge
    lo, hi = float(br.deck_plane_bin_m), float(br.clearance_minimum_m)
    z = _filled(layer)
    zs = every_z_at(frame_faces, [p[0] for p in stations], [p[1] for p in stations])
    hit = sum(1 for k, v in enumerate(zs)
              if v.size and bool(((v > z[k] + lo) & (v <= z[k] + hi)).any()))
    return hit / max(len(stations), 1)


# ── W5: the span ────────────────────────────────────────────────────────

def span_of(route: Route, stations: _t.Sequence[XY], ways: _t.Sequence, law,
            ground: "_t.Callable | None" = None, water=()) -> str:
    """W5: what the plate spans between its ends — ``way <id>``, ``water``,
    ``ground <m>`` — or ``""``.  ``ground(xs, ys)`` is the pre-solve DEM."""
    mid = substring(route.path, route.s_a + _HAIR, route.s_b - _HAIR)
    mine = set(route.ways)
    for w in ways:
        t = w.tags or {}
        if int(w.id) in mine or len(w.points) < 2 or not (
                "highway" in t or "railway" in t or "waterway" in t):
            continue
        if LineString(w.points).crosses(mid):
            return f"way {w.id}"
    for wp in water or ():
        if wp.intersects(mid):
            return "water"
    if ground is None or len(stations) < 3:
        return ""
    g = np.asarray(ground(np.array([p[0] for p in stations]),
                          np.array([p[1] for p in stations])), float)
    if not (np.isfinite(g[0]) and np.isfinite(g[-1])):
        return ""
    under = g[0] + (g[-1] - g[0]) * np.linspace(0.0, 1.0, len(g)) - g
    depth = float(np.nanmax(under[1:-1]))
    bar = float(law.tables.structures.bridge.deck_min_clearance_under_m)
    return f"ground {depth:.1f} m" if depth >= bar else ""


# ── one deck ────────────────────────────────────────────────────────────

def deck_witness(ring: Polygon, plate_up: np.ndarray, frame_faces: np.ndarray,
                 ways: _t.Sequence, law, ground=None, water=()) -> Witness:
    """W1-W5 for one deck plate (module doc): ``plate_up`` its near-horizontal
    faces, ``frame_faces`` every solid face of its frame (both ``(n, 3, 3)``
    frame x, y, authored y)."""
    br = law.tables.structures.bridge
    r = route_of(ring, ways, law)
    if isinstance(r, str):
        return Witness(None, failed=r)
    width = ring.area / max(r.s_b - r.s_a, 1e-6)
    if r.cover + 1e-9 < float(br.free_route_cover_min):
        return Witness(r, width_m=width, failed=f"W2 ribbon: cover {r.cover:.2f} < "
                       f"{float(br.free_route_cover_min):.2f}")
    st = _stations(r.path, r.s_a, r.s_b, float(br.abutment_sample_step_m))
    box = LineString(st).buffer(1.0) if len(st) > 1 else Point(st[0]).buffer(1.0)
    layer, share = driven_surface(_near(plate_up, box), st, law)
    if not layer:
        return Witness(r, st, surface_share=share, width_m=width,
                       failed=f"W3 surface: no layer on {SURFACE_SHARE:.0%} of "
                       f"{len(st)} stations with both ends (best {share:.2f})")
    roof = open_sky(_near(frame_faces, box), st, layer, law)
    if roof > ROOF_SHARE:
        return Witness(r, st, layer, share, roof, width_m=width,
                       failed=f"W4 open sky: a solid within "
                       f"{float(br.clearance_minimum_m):.1f} m over {roof:.0%} of the stations")
    sp = span_of(r, st, ways, law, ground, water)
    if not sp:
        return Witness(r, st, layer, share, roof, width_m=width,
                       failed="W5 span: no crossing way, water or ground "
                       f"{float(br.deck_min_clearance_under_m):.1f} m under the end chord")
    return Witness(r, st, layer, share, roof, sp, width_m=width)


# ── the frame: groups and W6 ───────────────────────────────────────────

def _stub_joins(ring: Polygon, plate_up: np.ndarray, frame_faces: np.ndarray,
                widest: float, law) -> str:
    """Why a routeless stub does not join a touching W-deck's group, or
    ``""`` when it does: its width (plan area over its own long axis, the
    ribbon's centreline — a curved ramp's rectangle does not follow it) at
    most :data:`STUB_WIDTH_RATIO` x the widest W-deck's, and W3 and W4
    along that axis."""
    line = ribbon_centreline(ring)
    if line is None or line.length <= 0.0:
        return "no axis"
    width = ring.area / line.length
    if width > STUB_WIDTH_RATIO * widest + 1e-6:
        return f"width {width:.0f} m > {STUB_WIDTH_RATIO} x {widest:.0f} m"
    st = _stations(line, 0.0, line.length,
                   float(law.tables.structures.bridge.abutment_sample_step_m))
    layer, share = driven_surface(plate_up, st, law)
    if not layer:
        return f"W3 surface on its own axis (best {share:.2f})"
    roof = open_sky(frame_faces, st, layer, law)
    return f"W4 open sky on its own axis ({roof:.0%})" if roof > ROOF_SHARE else ""


def _extended(path: LineString, a: float, b: float) -> LineString:
    """``path`` from ``a`` to ``b``, carried straight on along its end
    tangent where ``a`` / ``b`` lie past its ends (a chain that stops at the
    plate)."""
    pts = list(substring(path, max(0.0, a), min(path.length, b)).coords)
    if a < 0.0:
        t = _tangent(path, 0.0, -1.0)
        pts.insert(0, (pts[0][0] - a * t[0], pts[0][1] - a * t[1]))
    if b > path.length:
        t = _tangent(path, path.length, 1.0)
        over = b - path.length
        pts.append((pts[-1][0] + over * t[0], pts[-1][1] + over * t[1]))
    return LineString(pts)


def _corridor(w: Witness, law) -> Polygon:
    """A W-deck's route corridor: the plate's width about its route,
    ``[building_pad] fill_road_reach_m`` past each end."""
    reach = float(law.tables.structures.building_pad.fill_road_reach_m)
    r = w.route
    return _extended(r.path, r.s_a - reach, r.s_b + reach).buffer(max(0.5 * w.width_m, 0.5))


def _free_frame(bodies: _t.Mapping[str, np.ndarray], region, law, pads=()) -> str:
    """W6: the first other body of the frame not inside ``region`` (the
    bridge's decks and route corridors, grown ``[placement]
    footprint_touch_m``) or standing on an emitted object pad, named; ``""``
    when the frame is free.  ``bodies``: id -> its plan vertices ``(n, 2)``."""
    grown = region.buffer(float(law.tables.structures.placement.footprint_touch_m))
    for oid, pts in sorted(bodies.items()):
        if not len(pts):
            continue
        share = float(contains_xy(grown, pts[:, 0], pts[:, 1]).mean())
        if share + 1e-9 < _INSIDE_SHARE:
            return f"W6 free frame: {oid} stands {1.0 - share:.0%} outside the bridge"
        if any(contains_xy(pad, pts[:, 0], pts[:, 1]).any() for pad in pads or ()):
            return f"W6 free frame: {oid} stands on an object pad"
    return ""


def _join_stubs(decks, out: dict, frame_faces: np.ndarray, law) -> dict:
    """Every ``flag`` stub with no route of its own (W1 or W2 fails) touching
    a W-deck that :func:`_stub_joins` admits, marked ``joined``."""
    touch = float(law.tables.structures.placement.footprint_touch_m)
    wd = [o for o, w in out.items() if not w.failed]
    widest = max(out[o].width_m for o in wd)
    for oid, (ring, up, kind) in decks.items():
        w = out[oid]
        if kind != "flag" or not w.failed.startswith(("W1", "W2")):
            continue
        host = next((o for o in wd if ring.distance(decks[o][0]) <= touch), None)
        if host is None:
            continue
        why = _stub_joins(ring, _near(up, ring.buffer(1.0)),
                          _near(frame_faces, ring.buffer(1.0)), widest, law)
        out[oid] = _dc.replace(w, joined="" if why else host,
                               failed=f"{w.failed}; stub of {host} refused: {why}"
                               if why else w.failed)
    return out


def frame_witness(decks: _t.Mapping[str, tuple[Polygon, np.ndarray, str]],
                  frame_faces: np.ndarray, bodies: _t.Mapping[str, np.ndarray],
                  ways: _t.Sequence, law, ground=None, water=(), pads=()
                  ) -> dict[str, Witness]:
    """Every deck of ONE frame read (module doc): ``decks`` id -> ``(ring,
    near-horizontal plate faces, deck_kind)``; ``bodies`` id -> the plan
    vertices of every member of the frame.  The W-decks and the stubs that
    joined them carry W6's verdict for the frame in ``frame_failed``."""
    out = {oid: deck_witness(ring, up, frame_faces, ways, law, ground, water)
           for oid, (ring, up, _k) in decks.items()}
    wd = [oid for oid, w in out.items() if not w.failed]
    if not wd:
        return out
    out = _join_stubs(decks, out, frame_faces, law)
    group = [o for o, w in out.items() if not w.failed or w.joined]
    region = unary_union([decks[o][0] for o in group] + [_corridor(out[o], law) for o in wd])
    why = _free_frame({b: p for b, p in bodies.items() if b not in group}, region, law, pads)
    return {o: (_dc.replace(w, frame_failed=why) if o in group else w)
            for o, w in out.items()}
