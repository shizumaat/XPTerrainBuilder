"""THE ROAD THAT RUNS ALONG A TAXI BAND (owner RULINGS 2026-11-18b, #2152;
resolves 2026-09-29r against 2026-10-19a / 17k for this case).

The owner, KEGE 2026-11-18T01:55Z: "The road stays at the taxiway level until
about here ... then begins its descent.  The first part of the road and
taxiway area are on a filled area with a big embankment".  As a general
rule: a road that RUNS ALONG inside a taxi zone band grades WITH the band --
at the taxiway's level, on the airport's platform -- and begins its descent
where it leaves the band's run, at its built grade (``road_ramp.terrace_profile``'s
bare exit).  A road CROSSING a band keeps 10-19a / 17k: at or below it.

ALONG versus CROSSING, from geometry alone:

* IN THE BAND -- the stretch of a route whose ribbon shares the band's
  KERB (``PlanarMap.band_kerb_vertices``) with a taxi zone band, on a road
  the band was not cut back from (a road THROUGH zone 2 is cut out of it and
  follows its own ground, 2026-10-20c (39), ``planar/road_yield``): each kerb
  station give or take one lane width, and every station between two kerb
  stations of the route that lie on one band face (the road's edge runs ON
  that face between them, however sparse the ring's vertices).
* ALONG -- the road's OFFSET from the band's pavement (the distance to the
  nearest taxi-family foot, ``road_ramp._FeetIndex``) holds within
  :data:`ALONG_DEG` of parallel: over :data:`WINDOW_LANES` lane widths
  either side of the station, read along each kerb line of the road, it
  changes by less than ``tan(ALONG_DEG)`` per metre on both kerb lines.  The offset rate, not
  the angle to the nearest edge: at a pavement's rounded corner the nearest
  edge turns with the road, so a road leaving the corner diagonally reads
  parallel to the chord beside it while its offset grows (MEASURED KEGE
  ``small_roads:-311`` at taxiway ``dsf:pol93``'s east end: offset 3 m held
  for 80 m, then 5.6 -> 18 m over 30 m -- 0.36 m/m -- where the owner
  places the descent).

WHERE THE ROAD LEAVES ITS RUN the band beside it comes down to it
(:func:`ramp_banks`): the descending road is the platform's edge there, so a
band vertex within one lane width of the road off its run yields its zone
floor and stands between the road and the road plus the 1:3 bank
(``[design] bank_slope``) -- never a wall (owner 2026-11-17f: the band
follows its own ground down to a road where no wall witness lines it).

A route END inside the band is on the run up to it: the road meets its
pavement there (:func:`_ends_in_band`).

A RUNWAY band is out: a road beside a runway stays at or below its band
(owner 2026-10-19a, sim read 2026-10-28T14:26Z point 6); its terrace keeps
``road_ramp.road_terrace``'s ``runway`` rule."""
from __future__ import annotations

import bisect
import math
import typing as _t

from ..law import Law
from ..model.planar import PlanarMap
from ..model.road_yield import is_band_zone_ref

__all__ = ["band_runs", "ramp_banks", "ALONG_DEG", "WINDOW_LANES"]

#: a road runs ALONG its band while its offset from the band's pavement
#: changes by under tan(15 deg) per metre -- a geometric reading of
#: "parallel", not a law figure (cf. ``road_ramp._OPPOSITE_COS``)
ALONG_DEG = 15.0
#: the offset rate is read over this many lane widths either side of a
#: station: a ring vertex sits up to a metre or so off its kerb line, so a
#: rate over one lane would read that jitter as a turn
WINDOW_LANES = 2.0


def _is_taxi_band(face) -> bool:
    """A taxi zone band's face."""
    return (face.role == "graded_strip" and is_band_zone_ref(face.ref)
            and str(face.ref).split(":")[1] == "taxi")


def _taxi_band_faces(pm: PlanarMap, v: int) -> frozenset[int]:
    """The taxi zone-band faces at ``v``."""
    return frozenset(f for f in pm.vertices[v].incident_faces
                     if f in pm.faces and _is_taxi_band(pm.faces[f]))


def _in_band(pm: PlanarMap, kerb: _t.AbstractSet[int],
             frame: _t.Mapping[int, tuple[int, float, float]], lane: float
             ) -> dict[int, list[tuple[float, float]]]:
    """``{route: [(s0, s1), ...]}`` -- the stations of each route inside a
    taxi band (module docstring, IN THE BAND)."""
    by_route: dict[int, list[tuple[float, frozenset[int]]]] = {}
    for v in kerb:
        if v not in frame:
            continue
        faces = _taxi_band_faces(pm, v)
        if faces:
            r, s_, _t_ = frame[v]
            by_route.setdefault(int(r), []).append((float(s_), faces))
    # a road THROUGH zone 2 is cut out of it and follows its own ground
    # (owner RULINGS 2026-10-20c (39), ``planar/road_yield``): no band run
    cut = {int(frame[v][0]) for y in (getattr(pm, "road_yield", ()) or ())
           for v in y.kerb if v in frame}
    out: dict[int, list[tuple[float, float]]] = {}
    for r, ks in by_route.items():
        if r in cut:
            continue
        ks.sort(key=lambda k: k[0])
        spans = [(s_ - lane, s_ + lane) for s_, _f in ks]
        # the road's edge runs ON one band face between two of its kerb
        # stations: everything between them is in the band
        last: dict[int, float] = {}
        for s_, faces in ks:
            for f in faces:
                if f in last:
                    spans.append((last[f], s_))
                last[f] = s_
        out[r] = spans
    return out


def _rate(side: _t.Sequence[tuple[float, float]], s_: float, w: float) -> float:
    """``|d(s+w) - d(s-w)| / span`` on one side's ``(station, offset)``
    sequence, read linearly and clamped to the side's own extent."""
    ss = [p[0] for p in side]

    def at(x: float) -> float:
        i = bisect.bisect_left(ss, x)
        if i <= 0:
            return side[0][1]
        if i >= len(side):
            return side[-1][1]
        (s0, d0), (s1, d1) = side[i - 1], side[i]
        return d0 if s1 <= s0 else d0 + (d1 - d0) * (x - s0) / (s1 - s0)

    lo, hi = max(ss[0], s_ - w), min(ss[-1], s_ + w)
    if hi - lo < 1e-6:
        return 0.0
    return abs(at(hi) - at(lo)) / (hi - lo)


def band_runs(pm: PlanarMap, law: Law, vs: _t.Iterable[int], kerb: _t.AbstractSet[int],
              frame: _t.Mapping[int, tuple[int, float, float]], feet
              ) -> dict[int, str]:
    """``{road vertex: taxi pavement ref}`` for every road vertex of ``vs``
    that stands on a stretch running ALONG inside a taxi zone band (module
    docstring), with the ref of the band's pavement (its nearest
    taxi-family foot in ``feet``, the terrace's ``_FeetIndex``)."""
    if feet is None:
        return {}
    taxi = frozenset(law.tables.precedence.taxi_family.members)
    lane = float(law.tables.emit.road_profile.lane_width_m)
    spans = _in_band(pm, kerb, frame, lane)
    if not spans:
        return {}
    near: dict[int, tuple[float, str]] = {}
    for v in vs:
        fr = frame.get(v)
        if fr is None or int(fr[0]) not in spans:
            continue
        cands = [(d, ref) for ref, (d, *_x) in feet(pm.vertices[v].xy).items()
                 if feet.role_of.get(ref) in taxi]
        if cands:
            near[v] = min(cands)
    # each KERB LINE's offset sequence, read over the whole route (a window
    # at the band's end reads the road leaving it); a vertex near the
    # centre line (under half a lane off it) is on neither kerb line
    sides: dict[tuple[int, bool], list[tuple[float, float]]] = {}
    for v, (d, _ref) in near.items():
        r, s_, t_ = frame[v]
        if abs(t_) >= 0.5 * lane:
            sides.setdefault((int(r), t_ > 0.0), []).append((float(s_), float(d)))
    for side in sides.values():
        side.sort()
    tan_a = math.tan(math.radians(ALONG_DEG))
    w = WINDOW_LANES * lane
    out: dict[int, str] = {}
    for v, (_d, ref) in near.items():
        r, s_, _t_ = frame[v]
        if not any(a <= s_ <= b for a, b in spans[int(r)]):
            continue
        # ALONG on BOTH kerb lines: a road leaving the band moves off it
        # on both
        rates = [_rate(sides[(int(r), k)], float(s_), w) for k in (False, True)
                 if (int(r), k) in sides]
        if rates and max(rates) < tan_a:
            out[v] = ref
    _ends_in_band(out, near, spans, frame, vs, lane)
    return out


def _ends_in_band(out: dict[int, str], near: _t.Mapping[int, tuple[float, str]],
                  spans: _t.Mapping[int, list[tuple[float, float]]],
                  frame: _t.Mapping[int, tuple[int, float, float]],
                  vs: _t.Iterable[int], lane: float) -> None:
    """A ROUTE THAT ENDS IN THE BAND AT ITS PAVEMENT -- its end vertex
    within one lane width of the pavement, a touch (27a (11)) -- meets the
    pavement there: from that end to its run the road is on the run (in
    place).  It turns into the pavement, so its offset falls fast -- a
    mouth, not a road leaving the band (MEASURED KEGE ``small_roads:-311``:
    read as a bare exit, its last 3 m fell 3.8 m under the taxiway it
    meets).  An end in the band that has moved away from it is a road
    leaving the band and stays off the run."""
    by_route: dict[int, list[tuple[float, int]]] = {}
    for v in vs:
        fr = frame.get(v)
        if fr is not None and int(fr[0]) in spans:
            by_route.setdefault(int(fr[0]), []).append((float(fr[1]), v))
    for r, items in by_route.items():
        items.sort()
        for seq in (items, items[::-1]):
            if seq[0][1] not in near or near[seq[0][1]][0] > lane:
                continue                    # no end at the pavement
            walked: list[int] = []
            for s_, v in seq:
                if v in out:
                    out.update((u, near[u][1]) for u in walked)
                    break
                if v not in near or not any(a <= s_ <= b for a, b in spans[r]):
                    break
                walked.append(v)


def ramp_banks(pm: PlanarMap, law: Law, run: _t.Mapping[int, str],
               station: _t.Mapping[int, tuple[int, float]]
               ) -> dict[int, tuple[int, float]]:
    """``{band vertex: (road vertex, plan distance)}`` -- every taxi-band
    GROUND vertex (no face but taxi zone bands) within one lane width of a
    road vertex (``station``, the terrace's) of a route with a band run
    (``run``, :func:`band_runs`), whose nearest road vertex is OFF the run:
    the band beside the road where it has left the band's level comes down
    to it (module docstring; published as ``road_terrace``'s ``bank``, rows
    ``constraints/zones``)."""
    if not run:
        return {}
    routes = {station[v][0] for v in run if v in station}
    road = sorted(v for v, (r, _s) in station.items() if r in routes and v in pm.vertices)
    if not road:
        return {}
    from shapely import STRtree
    from shapely.geometry import Point
    lane = float(law.tables.emit.road_profile.lane_width_m)
    pts = [Point(pm.vertices[v].xy) for v in road]
    tree = STRtree(pts)
    on_road = frozenset(road)
    out: dict[int, tuple[int, float]] = {}
    seen: set[int] = set()
    for f in pm.faces.values():
        if not _is_taxi_band(f):
            continue
        for cyc in (f.ring, *f.holes):
            for v in pm.ring_vertices(cyc):
                if v in seen or v in on_road:
                    continue
                seen.add(v)
                if len(_taxi_band_faces(pm, v)) != len(pm.vertices[v].incident_faces):
                    continue                    # a pavement's or a road's vertex
                p = Point(pm.vertices[v].xy)
                hits = [int(k) for k in tree.query(p, predicate="dwithin", distance=lane)]
                if not hits:
                    continue
                d, k = min((p.distance(pts[k]), k) for k in hits)
                if road[k] not in run:
                    out[v] = (road[k], float(d))
    return out
