"""THE DRAWN GATE'S ROAD LAYER (#2072 step 5): is every mapped road the
drawn mesh carries near a judged site smooth enough to drive?

``tools/harness/drawn_gate.py --site NAME=LAT,LON[,R] --road-step M``: every
mapped vehicle road (the OSM road feeds, ``highway`` in the classifier's
``[osm_roads] ribbon_highways``; a mapped ``bridge`` is drawn by its object,
never the mesh, and is skipped) is clipped to each site's radius and
sampled on the DRAWN mesh every :data:`STEP_M`; a site FAILs when any two
consecutive samples differ by more than ``M`` (default
:data:`ROAD_STEP_M`, the owner's ground bar 2026-10-15).  A stretch UNDER a
mapped bridge way (within its half width + :data:`UNDER_BRIDGE_M`) is not
read: the mesh there is the bridge's ground, never the road under it.  The trench steps
of #1902 (a ramp top 2.3-2.7 m over the floor, a road ending on a 1 m lip)
are exactly the class the patch->drawn layer cannot see: the patch and the
mesh agree, and the road still jumps.

A step pair STRADDLING a claimed tunnel mouth of the road's OWN tunnel way
(``mouths``: :func:`claimed_mouths` of the sidecar) is that mouth's FACE --
the drawn cut face from the ramp floor up to the cover over the bore --
reported as ``mouth_faces``, never judged (#1689 A7: KBNA P1's "4.9 m road
step" was the tunnel way's own sample 1.17 m behind its mouth line).

The layer reads the road feeds the build read (``OSM_data``), never a
capture, so it measures an owner install (``--tile``) and a harness build
(``--tag``) alike.  Nothing here names an airport.
"""
from __future__ import annotations

import math

__all__ = ["ROAD_STEP_M", "STEP_M", "UNDER_BRIDGE_M", "MOUTH_FACE_M", "road_lines",
           "road_profile_step", "road_layer", "claimed_mouths"]

#: the default FAIL bar between consecutive samples (owner ground bar)
ROAD_STEP_M = 0.5
#: the margin past a mapped bridge's half width a road under it is not read
UNDER_BRIDGE_M = 2.0
#: the sampling interval along a road (m)
STEP_M = 1.0
#: a step pair within this of a claimed mouth's line (along the road) is
#: its face: the drawn cut face runs 1.8-2.3 m from floor to cover (KBNA P1)
MOUTH_FACE_M = 2.5
#: ... and within this across the road of the mouth point (half the widest
#: ramp opening read, 40 m at KBNA P1)
MOUTH_ACROSS_M = 25.0
_M_PER_DEG = 111320.0


def claimed_mouths(sidecar):
    """``[(tunnel way ids, lat, lon)]``: every sidecar tunnel mouth
    (``tunnel_mouth_depths``) a pack portal claims (``portal_cuts``); the
    way ids read off the tunnel id (``tunnel:<w>[+<w>...]@<k>``)."""
    claimed = {r["id"] for r in (sidecar or {}).get("portal_cuts", []) or ()}
    out = []
    for r in (sidecar or {}).get("tunnel_mouth_depths", []) or ():
        if r["id"] not in claimed:
            continue
        ids = r["id"].split(":", 1)[-1].split("@", 1)[0]
        try:
            ways = frozenset(int(w) for w in ids.split("+") if w)
        except ValueError:
            continue
        out.append((ways, float(r["mouth_ll"][0]), float(r["mouth_ll"][1])))
    return out


def _way_number(wid) -> "int | None":
    """The OSM way number of a road feed's way id -- an int, or the feed's
    tile-qualified string (``+36-087:-1986``); the mouth's tunnel id names
    the bare number (#1689 R3: the qualified id never matched, so KBNA P1's
    mouth face was judged as a 4.0 m road step)."""
    if isinstance(wid, int):
        return wid
    try:
        return int(str(wid).rsplit(":", 1)[-1])
    except ValueError:
        return None


def _straddles(mouths, lat0):
    """``(way id, a, b) -> bool``: the pair ``a`` -> ``b`` (lat, lon) of road
    ``way id`` stands on the face of a claimed mouth of that way."""
    kx = _M_PER_DEG * math.cos(math.radians(lat0))

    def test(wid, a, b):
        w = _way_number(wid)
        for ways, la, lo in mouths:
            if w not in ways:
                continue
            ax, ay = (a[1] - lo) * kx, (a[0] - la) * _M_PER_DEG
            dx, dy = (b[1] - a[1]) * kx, (b[0] - a[0]) * _M_PER_DEG
            L = math.hypot(dx, dy)
            if L <= 0.0:
                continue
            s = -(ax * dx + ay * dy) / L           # the mouth's station along a -> b
            across = abs(ax * dy - ay * dx) / L
            if -MOUTH_FACE_M <= s <= L + MOUTH_FACE_M and across <= MOUTH_ACROSS_M:
                return True
        return False
    return test


def road_lines(osm_root, lat, lon, radius_m, bridges_out=None):
    """``[(way id, highway, [(lat, lon), ...])]``: the mapped vehicle roads
    with a vertex within ``radius_m`` (plus a margin) of ``(lat, lon)``;
    ``bridges_out`` (a list) receives ``(half width m, [(lat, lon), ...])``
    of every mapped highway / railway bridge there."""
    from auto_patch_v2.airport.deck_signature import is_bridge_way
    from auto_patch_v2.airport.osm import ROAD_FEEDS, load_feed
    from auto_patch_v2.airport.road_ways import mapped_width_m
    from auto_patch_v2.classify.rules import load_rules
    kinds = set(load_rules().osm_roads.ribbon_highways)
    rad = (radius_m + 200.0) / _M_PER_DEG / max(0.2, math.cos(math.radians(lat)))
    out, seen = [], set()
    for feed in ROAD_FEEDS:
        for w in load_feed(osm_root, feed, lat, lon, rad).ways:
            tags = dict(w.tags or {})
            if w.id in seen:
                continue
            seen.add(w.id)
            if is_bridge_way(tags):
                if bridges_out is not None:
                    bridges_out.append((0.5 * mapped_width_m(tags, 3.5, 2),
                                        [tuple(p) for p in w.points]))
                continue
            if tags.get("highway") in kinds:
                out.append((w.id, tags.get("highway"), [tuple(p) for p in w.points]))
    return out


def _under_bridge(bridges, lat0, lon0):
    """``(lat, lon) -> bool``: the point stands under a mapped bridge
    (within its half width + :data:`UNDER_BRIDGE_M`)."""
    if not bridges:
        return lambda _la, _lo: False
    from shapely.geometry import LineString, Point
    from shapely.ops import unary_union
    kx = _M_PER_DEG * math.cos(math.radians(lat0))
    cover = unary_union([LineString([((lo - lon0) * kx, (la - lat0) * _M_PER_DEG)
                                     for la, lo in pts]).buffer(half + UNDER_BRIDGE_M)
                         for half, pts in bridges if len(pts) >= 2])
    return lambda la, lo: cover.contains(Point((lo - lon0) * kx, (la - lat0) * _M_PER_DEG))


def _clip_runs(pts, lat0, lon0, radius_m, step):
    """The road's sample runs inside the site circle: lists of
    ``(lat, lon)`` every ``step`` metres, one list per inside stretch."""
    kx = _M_PER_DEG * math.cos(math.radians(lat0))
    xy = [((lo - lon0) * kx, (la - lat0) * _M_PER_DEG) for la, lo in pts]
    runs, cur = [], []
    for (x0, y0), (x1, y1) in zip(xy, xy[1:], strict=False):
        n = max(1, int(math.ceil(math.hypot(x1 - x0, y1 - y0) / step)))
        for k in range(n):
            t = k / n
            x, y = x0 + t * (x1 - x0), y0 + t * (y1 - y0)
            if math.hypot(x, y) <= radius_m:
                cur.append((lat0 + y / _M_PER_DEG, lon0 + x / kx))
            elif cur:
                runs.append(cur)
                cur = []
    if xy and math.hypot(*xy[-1]) <= radius_m:
        x, y = xy[-1]
        cur.append((lat0 + y / _M_PER_DEG, lon0 + x / kx))
    if cur:
        runs.append(cur)
    return runs


def road_profile_step(samples, sample, face=None, faces=None):
    """``(max |dz| between consecutive drawn samples, (lat, lon) of its
    first sample, drawn z there, drawn z next)``; a sample off the mesh
    (nan) breaks the run.  A pair ``face(a, b)`` calls a mouth's face is
    not judged: it goes to ``faces`` (a list) as ``(|dz|, (lat, lon))``."""
    worst = (0.0, None, None, None)
    prev = None
    for la, lo in samples:
        z = sample(lo, la)
        if math.isnan(z):
            prev = None
            continue
        if prev is not None and face is not None and face(prev[:2], (la, lo)):
            if faces is not None:
                faces.append((round(abs(z - prev[2]), 2), (round(prev[0], 6), round(prev[1], 6))))
            prev = (la, lo, z)
            continue
        if prev is not None and abs(z - prev[2]) > worst[0]:
            worst = (abs(z - prev[2]), (round(prev[0], 6), round(prev[1], 6)),
                     round(prev[2], 2), round(z, 2))
        prev = (la, lo, z)
    return worst


def road_layer(sites, sample, osm_root, bar=ROAD_STEP_M, step=STEP_M, mouths=()):
    """The layer over ``sites`` (``(name, lat, lon, r)``); ``sample(lon,
    lat)`` is the drawn mesh height (nan off it); ``mouths``
    (:func:`claimed_mouths`) the faces never judged."""
    rows, failed = [], 0
    for name, lat, lon, r in sites:
        worst, n, bridges, faces = None, 0, [], []
        roads = road_lines(osm_root, lat, lon, r, bridges)
        under = _under_bridge(bridges, lat, lon)
        straddles = _straddles(mouths, lat) if mouths else None

        def drawn(lo, la, _u=under):
            return float("nan") if _u(la, lo) else sample(lo, la)
        for wid, hw, pts in roads:
            for run in _clip_runs(pts, lat, lon, r, step):
                if len(run) < 2:
                    continue
                n += 1
                face = None if straddles is None else (
                    lambda a, b, _w=wid, _s=straddles: _s(_w, a, b))
                got: list = []
                d, at, za, zb = road_profile_step(run, drawn, face, got)
                faces.extend(dict(way=wid, step_m=g[0], lat=g[1][0], lon=g[1][1])
                             for g in got if g[0] > bar)
                if at is not None and (worst is None or d > worst["max_step_m"]):
                    worst = {"max_step_m": round(d, 2), "way": wid, "highway": hw,
                             "lat": at[0], "lon": at[1], "drawn": [za, zb]}
        bad = worst is not None and worst["max_step_m"] > bar
        failed += bad
        rows.append(dict({"site": name, "roads": n, "verdict": "FAIL" if bad else "PASS"
                          if n else "NOT MEASURED"}, **(worst or {}),
                         **({"mouth_faces": faces} if faces else {})))
    measured = any(r["verdict"] != "NOT MEASURED" for r in rows)
    return {"bar_m": bar, "step_m": step, "sites": rows, "failed": failed,
            "verdict": "FAIL" if failed else "PASS" if measured else "NOT MEASURED"}
