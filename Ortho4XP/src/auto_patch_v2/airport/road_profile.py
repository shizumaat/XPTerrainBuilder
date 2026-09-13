"""THE CORE ROAD PROFILE ADAPTER (RULINGS 2026-09-04t-4 "the core smooths
first"; 2026-08-31 "leverage the core"; M3c).

Ortho4XP's own road machinery (``O4_Vector_Map.include_roads``) levels a
road in two steps: the LONGITUDINAL CLAMP — per OSM way, on the
centreline, ``refine_way`` at ≤ ``station_m`` stations, then
``cap_lipschitz_profile`` (the mid-envelope ``(floor + ceil) / 2`` of the
terrain at the grade cap: the terrain itself wherever it is cap-lawful,
the minimum lift/cut elsewhere) — and the LATERAL LEVELLING — a ribbon
vertex reads the nearest clamped station within ``2 × lane_width``
(``Levelled_Roads.answer``), so both kerbs carry the centreline value.
That pass runs AFTER the patch is inserted and NEVER inside it: the
ribbon is cut back ``lane_width + 2`` m from the airport area
(``apt_area``), and the core never reads apt.dat 1206 routes or DSF road
pages at all.  Inside the patch the road surface is v2's alone.

This adapter gives every v2 road-family vertex THE VALUE THE CORE WOULD
GIVE IT: the same clamp (the core's own ``cap_lipschitz_profile`` — the
one ``O4_*`` import v2 makes for roads, allowed in this adapter only),
on v2's DEM (the production tile raster the mesh drapes on, the core's
``tile.dem``), over

* every OSM ``highway=*`` way the core levels (whole way, as the core
  clamps it; asserted ``bridge`` / ``tunnel`` spans excluded as the core
  excludes them) — kind ``osm``;
* every ``road_centerline`` breakline of the planar map (a 1206 route,
  or an OSM road's on-pavement part) as its own way — kind ``route`` —
  so a road the core never sees still gets the core's ALGORITHM;
* the OWN AXIS of a road face (service_road / service_junction /
  groundside_pavement) no way runs through — a DSF road page with no
  OSM way and no 1206 route (CYXY's shape 153, ``dsf:pol120``) — the
  ring's mid-line swept along its long axis, clamped the same way —
  kind ``axis``.  A parking lot has no axis in law (04m) and no axis
  here.

A vertex is answered by PROJECTION onto a way, the profile interpolated
at the projection (the continuous form of the core's nearest-station
rule, exact at a station): the ways running THROUGH a road face answer
every vertex of that face whatever the lateral distance (the face IS
the road; both kerbs read the centreline — the core's lateral
levelling), the face's axis where none does; any other way within the
core's answer radius (``2 × lane_width``) answers a vertex as the core
would (a lot beside a road, a sliver).  Nearest wins; an OSM way within
the radius wins over a route (the core's authority where it has one).
A vertex with no source keeps the DEM and is COUNTED.

The answers become ``PlanarMap.preferred_z`` — the objective's fit
target replacing the raw DEM for road-family vertices.  The cap rows
(8 % longitudinal, 2 % cross-section, lot 5 %, lateral contiguity) stay:
v2 moves a vertex off this profile ONLY where a row binds, which is the
ruling's "v2 adds smoothing only where a road is still over its cap
afterwards".  Read-only; no environment; every constant from the law
tables (``emit.road_profile``) or the caller.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import sys
import typing as _t
from pathlib import Path

import numpy as np
from shapely.geometry import LineString, Point, Polygon
from shapely.strtree import STRtree

from ..law import Law
from ..model.frame import rotated_rectangle
from ..law.tables import family, role_cap, senior_role
from ..model.airport import Airport
from ..model.frame import XY
from ..model.planar import PlanarMap

__all__ = ["Way", "Answer", "RoadProfiles", "stations", "clamp_profile",
           "clamp_way", "face_axis", "road_family_roles", "axis_roles",
           "road_family_vertices", "core_profiles", "preferred_road_z",
           "ENGINE_DIR"]

#: The engine tree (``src/auto_patch_v2/airport``): the core lives in
#: ``<engine>/src``.
ENGINE_DIR = Path(__file__).resolve().parents[3]

OSM, ROUTE, AXIS = "osm", "route", "axis"


def _core_vector_utils():
    """``O4_Vector_Utils`` — the core's clamp.  The ONLY core import v2
    makes for roads, and it is made here."""
    d = str(ENGINE_DIR / "src")
    if d not in sys.path:
        sys.path.append(d)
    import O4_Vector_Utils as VECT  # noqa: WPS433 (core adapter)
    return VECT


@_dc.dataclass(frozen=True)
class Way:
    """One clamped centreline: stations ``xy`` (n, 2), arclength ``s``,
    terrain ``dem`` and the clamped profile ``z`` at each station."""

    kind: str
    ref: str
    xy: np.ndarray
    s: np.ndarray
    dem: np.ndarray
    z: np.ndarray

    @property
    def line(self) -> LineString:
        return LineString(self.xy)

    def at(self, s: float) -> float:
        """The clamped profile at arclength ``s`` (linear between stations)."""
        return float(np.interp(s, self.s, self.z))


def _signed_offset(line: LineString, s: float, pt: XY) -> float:
    """The SIGNED distance from ``line`` at station ``s`` to ``pt``: the
    cross product of the line's local direction with the offset, so the
    two KERBS of one section read opposite signs and ``|t_a - t_b|`` is
    the road's width across it (§37 (7)).  An unsigned distance would read
    ~0 across the section and price a cross-section pair as if it were
    one point."""
    e = 0.5
    a = line.interpolate(max(0.0, s - e))
    b = line.interpolate(min(line.length, s + e))
    ux, uy = b.x - a.x, b.y - a.y
    n = math.hypot(ux, uy)
    if n <= 0.0:
        return 0.0
    f = line.interpolate(s)
    return ((pt[0] - f.x) * (-uy / n)) + ((pt[1] - f.y) * (ux / n))


@_dc.dataclass(frozen=True)
class Answer:
    """One vertex's answer: the value, which way gave it (``None`` = the
    DEM fallback) and the lateral distance to that way."""

    z: float
    kind: str | None
    ref: str | None
    lateral_m: float
    #: THE ROUTE FRAME OF THE ANSWER (§37 (7)): the winning way, the
    #: station (arclength ALONG its polyline, the route distance the road
    #: pair law is priced over) and the SIGNED lateral offset across it.
    #: ``None`` / 0.0 on the DEM fallback.  Additive: every earlier reader
    #: of ``Answer`` sees the same first four fields.
    way: "Way | None" = None
    s: float = 0.0
    t: float = 0.0


def face_axis(ring: _t.Sequence[XY], step_m: float) -> list[XY] | None:
    """A road face's OWN centreline: the mid-points of the ring's
    cross-chords swept every ``step_m`` along the long axis of its
    minimum-area rectangle (the axis ``roads.py`` splits cross-section
    pairs on), each chord's piece the one nearest the previous mid-point
    (a curved page keeps ONE line).  ``None`` for a degenerate ring."""
    try:
        poly = Polygon(ring)
        if not poly.is_valid:
            poly = poly.buffer(0)
    except (ValueError, TypeError):
        return None
    if poly.is_empty or poly.area <= 0:
        return None
    if poly.length < 1e-3 or poly.area < 1e-6:
        return None
    rect = rotated_rectangle(poly)
    if rect.geom_type != "Polygon":
        return None
    c = list(rect.exterior.coords)[:4]
    e0 = math.hypot(c[1][0] - c[0][0], c[1][1] - c[0][1])
    e1 = math.hypot(c[2][0] - c[1][0], c[2][1] - c[1][1])
    if max(e0, e1) < 1e-6:
        return None
    if e0 >= e1:
        ux, uy, L, W = (c[1][0] - c[0][0]) / e0, (c[1][1] - c[0][1]) / e0, e0, e1
    else:
        ux, uy, L, W = (c[2][0] - c[1][0]) / e1, (c[2][1] - c[1][1]) / e1, e1, e0
    cx, cy = rect.centroid.x, rect.centroid.y
    nx, ny = -uy, ux
    half = W + 1.0
    n = max(2, int(math.ceil(L / step_m)) + 1)
    prev: XY | None = None
    out: list[XY] = []
    for k in range(n):
        t = -L / 2 + (k + 0.5) * L / n if n > 1 else 0.0
        px, py = cx + ux * t, cy + uy * t
        chord = LineString([(px - nx * half, py - ny * half), (px + nx * half, py + ny * half)])
        cut = chord.intersection(poly)
        pieces = [g for g in getattr(cut, "geoms", [cut]) if g.geom_type == "LineString"
                  and g.length > 0]
        if not pieces:
            continue
        ref = Point(prev) if prev is not None else Point(px, py)
        best = min(pieces, key=lambda g: g.centroid.distance(ref))
        m = best.interpolate(0.5, normalized=True)
        prev = (float(m.x), float(m.y))
        out.append(prev)
    return out if len(out) >= 2 else None


def stations(points: _t.Sequence[XY], station_m: float) -> np.ndarray:
    """The core's ``refine_way`` in the metric frame: every input vertex
    kept, ``int(L // station_m)`` evenly spaced points inserted per
    segment (so consecutive stations are ≤ ``station_m`` apart, and often
    much closer — the sidecar's own caveat)."""
    pts = [(float(x), float(y)) for x, y in points]
    out: list[XY] = []
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        out.append((x0, y0))
        L = math.hypot(x1 - x0, y1 - y0)
        ins = int(L // station_m) if station_m > 0 else 0
        for j in range(1, ins + 1):
            t = j / (ins + 1)
            out.append((x0 + t * (x1 - x0), y0 + t * (y1 - y0)))
    out.append(pts[-1])
    return np.asarray(out, dtype=float)


def _arclength(xy: np.ndarray) -> np.ndarray:
    d = np.diff(xy, axis=0)
    return np.concatenate(([0.0], np.cumsum(np.hypot(d[:, 0], d[:, 1]))))


def clamp_profile(s: np.ndarray, dem: np.ndarray, cap: float) -> np.ndarray:
    """The core's clamp, verbatim (``O4_Vector_Utils.cap_lipschitz_profile``
    without pins): the cap-Lipschitz mid-envelope of ``dem`` over
    arclength ``s``.  Identity wherever the terrain is cap-lawful."""
    VECT = _core_vector_utils()
    return np.asarray(VECT.cap_lipschitz_profile(s, dem, cap), dtype=float)


Inside = _t.Callable[[np.ndarray], np.ndarray]
"""``(xy (n, 2)) -> bool mask``: which stations the DEM may be sampled at."""


def clamp_way(kind: str, ref: str, points: _t.Sequence[XY],
              sample: _t.Callable[[np.ndarray, np.ndarray], np.ndarray],
              cap: float, station_m: float,
              inside: Inside | None = None) -> list[Way]:
    """Station ``points``, sample the terrain, clamp — one :class:`Way`
    per maximal run of stations ``inside`` the sampleable DEM (a
    tile-wide OSM way leaving the warm tiles is clamped in parts: a cold
    neighbour tile is never composed for a road)."""
    if len(points) < 2:
        return []
    xy = stations(points, station_m)
    # collapse coincident consecutive stations (a zero-length segment)
    keep = np.ones(len(xy), bool)
    keep[1:] = np.hypot(*(np.diff(xy, axis=0).T)) > 1e-9
    xy = xy[keep]
    if len(xy) < 2:
        return []
    ok = np.ones(len(xy), bool) if inside is None else np.asarray(inside(xy), bool)
    out: list[Way] = []
    i = 0
    n = len(xy)
    while i < n:
        if not ok[i]:
            i += 1
            continue
        j = i
        while j < n and ok[j]:
            j += 1
        part = xy[i:j]
        i = j
        if len(part) < 2:
            continue
        s = _arclength(part)
        dem = np.asarray(sample(part[:, 0], part[:, 1]), dtype=float)
        if not np.all(np.isfinite(dem)):
            continue
        out.append(Way(kind, ref, part, s, dem, clamp_profile(s, dem, cap)))
    return out


@_dc.dataclass
class RoadProfiles:
    """The clamped ways (``osm`` / ``route``), the face axes (``axis``,
    keyed by face id) and the answering index."""

    cap: float
    station_m: float
    lane_width_m: float
    radius_m: float
    ways: tuple[Way, ...]
    axes: dict[int, Way] = _dc.field(default_factory=dict)
    #: face id -> the ways that ANSWER that face's vertices, with the
    #: face's own answer radius (:func:`core_profiles`' second return,
    #: carried on the object so a second reader of the SAME profiles does
    #: not rebuild them — ``airport/road_ramp.py``, §37 (6))
    per_face: dict[int, list[tuple[Way, float]]] = _dc.field(default_factory=dict)
    _tree: STRtree | None = _dc.field(default=None, repr=False)
    _lines: list[LineString] = _dc.field(default_factory=list, repr=False)

    def __post_init__(self) -> None:
        self._lines = [w.line for w in self.ways]
        self._tree = STRtree(self._lines) if self._lines else None

    @property
    def all_ways(self) -> tuple[Way, ...]:
        return self.ways + tuple(self.axes.values())

    def ways_through(self, poly: Polygon) -> list[int]:
        """Indices of the ways whose line runs through ``poly``."""
        if self._tree is None:
            return []
        return [int(i) for i in self._tree.query(poly, predicate="intersects")
                if self._lines[int(i)].intersection(poly).length > 1e-6]

    def ways_near(self, pt: Point) -> list[int]:
        """Indices of the ways within the core's answer radius."""
        if self._tree is None:
            return []
        return [int(i) for i in self._tree.query(pt, predicate="dwithin",
                                                  distance=self.radius_m)]

    def project(self, way: Way, line: LineString, pt: Point) -> tuple[float, float]:
        """``(profile value at the projection, lateral distance)``."""
        return way.at(line.project(pt)), float(line.distance(pt))

    def answer(self, pt: XY, dem: float,
               through: _t.Iterable[tuple[Way, float]] = ()) -> Answer:
        """One vertex: the nearest of the ways ``through`` its faces (each
        within ITS face's radius) and the ways within the core's radius;
        an OSM way within the core's radius outranks the rest; else the
        DEM."""
        p = Point(pt)
        best: tuple[int, float, Way] | None = None
        cands: list[tuple[Way, LineString, float]] = [(w, w.line, r) for w, r in through]
        cands += [(self.ways[i], self._lines[i], self.radius_m) for i in self.ways_near(p)]
        bline: LineString | None = None
        for w, line, r in cands:
            z, lat = self.project(w, line, p)
            if lat > r:
                continue
            rank = 0 if (w.kind == OSM and lat <= self.radius_m) else 1
            if best is None or (rank, lat) < (best[0], best[1]):
                best = (rank, lat, w)
                bz = z
                bline = line
        if best is None:
            return Answer(float(dem), None, None, math.inf)
        s = float(bline.project(p)) if bline is not None else 0.0
        return Answer(bz, best[2].kind, best[2].ref, best[1], best[2], s,
                      _signed_offset(bline, s, pt) if bline is not None else 0.0)

    def summary(self) -> dict[str, _t.Any]:
        """Population + intervention counts (the core's own summary)."""
        n_st = n_moved = 0
        lift = cut = 0.0
        by_kind = {OSM: 0, ROUTE: 0, AXIS: 0}
        for w in self.all_ways:
            by_kind[w.kind] = by_kind.get(w.kind, 0) + 1
            delta = w.z - w.dem
            n_st += len(delta)
            n_moved += int((np.abs(delta) > 0.01).sum())
            if len(delta):
                lift = max(lift, float(delta.max()))
                cut = max(cut, float((-delta).max()))
        return {"ways": len(self.all_ways), "ways_by_kind": by_kind,
                "stations": n_st, "clamped_stations": n_moved,
                "max_lift_m": round(lift, 4), "max_cut_m": round(cut, 4),
                "cap": self.cap, "station_m": self.station_m,
                "lane_width_m": self.lane_width_m, "answer_radius_m": self.radius_m}


def road_family_roles(law: Law) -> tuple[str, ...]:
    """The roles whose vertices prefer the core profile: the road
    cross-section family (service_road, service_junction) and the
    groundside classes ``roads.road_within_shape`` prices with them."""
    return tuple(family(law, "road_cross_section").roles) + \
        ("groundside_pavement", "parking_lot")


def axis_roles(law: Law) -> tuple[str, ...]:
    """The road-family roles a face axis is derived for — every one but
    the parking lot (no axis in law, RULINGS 2026-09-04m)."""
    return tuple(r for r in road_family_roles(law) if r != "parking_lot")


def road_family_vertices(pm: PlanarMap, law: Law) -> dict[int, str]:
    """Vertex id -> its senior role, for every vertex a road-family face
    OWNS (``senior_role`` over ``roles_at``: a kerb shared with the ground
    beside it is the road's; a vertex shared with an apron or taxiway is
    the airside surface's and keeps the DEM preference)."""
    roads = set(road_family_roles(law))
    out: dict[int, str] = {}
    for vid, v in pm.vertices.items():
        roles = pm.roles_at(vid)
        if not roles or not (set(roles) & roads):
            continue
        sr = senior_role(law, roles)
        if sr in roads:
            out[vid] = sr
    return out


def _sample_fn(airport: Airport) -> _t.Callable[[np.ndarray, np.ndarray], np.ndarray]:
    dem = airport.dem
    many = getattr(dem, "z_many", None)
    if callable(many):
        return lambda xs, ys: np.asarray(many(xs, ys), dtype=float)
    return lambda xs, ys: np.array([dem.z(float(x), float(y)) for x, y in zip(xs, ys)])


def _inside_fn(airport: Airport) -> Inside:
    """Where the DEM may be sampled: the WARM tiles of a production
    sampler (``warm_tiles`` / ``tile_of_many`` — the planar build has
    already composed every tile a map vertex touches; a road never
    composes a cold one), else the sampler's ``bounds``."""
    dem = airport.dem
    warm = getattr(dem, "warm_tiles", None)
    tiles = getattr(dem, "tile_of_many", None)
    if callable(warm) and callable(tiles):
        keys = warm()

        def inside(xy: np.ndarray) -> np.ndarray:
            return np.array([k in keys for k in tiles(xy[:, 0], xy[:, 1])], bool)
        return inside
    x0, y0, x1, y1 = dem.bounds()

    def inside_box(xy: np.ndarray) -> np.ndarray:
        return (xy[:, 0] >= x0) & (xy[:, 0] <= x1) & (xy[:, 1] >= y0) & (xy[:, 1] <= y1)
    return inside_box


def _osm_levelled(w) -> bool:
    """The core's population: a ``highway`` way whose ``bridge`` /
    ``tunnel`` is not ASSERTED (``bridge=no`` is an ordinary road)."""
    if not w.tags.get("highway") or len(w.points) < 2:
        return False
    for k in ("bridge", "tunnel"):
        v = w.tags.get(k)
        if v and v != "no":
            return False
    return True


def _face_polygon(pm: PlanarMap, fid: int) -> Polygon | None:
    ring = [pm.vertices[v].xy for v in pm.ring_vertices(pm.faces[fid].ring)]
    if len(ring) < 3:
        return None
    try:
        poly = Polygon(ring)
        return poly if poly.is_valid else poly.buffer(0)
    except (ValueError, TypeError):                      # pragma: no cover
        return None


def core_profiles(airport: Airport, pm: PlanarMap, law: Law,
                  cap: float | None = None, lane_width_m: float | None = None
                  ) -> tuple[RoadProfiles, dict[int, list[Way]]]:
    """Clamp the core's OSM population, the map's road centrelines and
    the axis of every axis-role face no way runs through, on the
    airport's DEM.  Returns the profiles and ``face id -> [(way, answer
    radius)]``: the ways that answer that face's vertices (through-ways,
    else its axis) within the face's own radius.
    ``cap`` / ``lane_width_m`` default to the law's (= the core's cfg
    defaults); a hosted build passes the tile's own."""
    rp = law.tables.emit.road_profile
    cap_ = float(cap) if cap is not None else role_cap(law, "service_road").longitudinal
    lw = float(lane_width_m) if lane_width_m is not None else rp.lane_width_m
    sample = _sample_fn(airport)
    inside = _inside_fn(airport)
    ways: list[Way] = []
    for w in airport.osm_ways:
        if _osm_levelled(w):
            ways.extend(clamp_way(OSM, f"osm:{w.id}", w.points, sample, cap_,
                                  rp.station_m, inside))
    for b in pm.breaklines.values():
        if b.kind != "road_centerline":
            continue
        pts = [pm.vertices[v].xy for v in b.vertices(pm)]
        ways.extend(clamp_way(ROUTE, f"{b.ref}#{b.id}", pts, sample, cap_,
                              rp.station_m, inside))
    prof = RoadProfiles(cap_, rp.station_m, lw, rp.answer_radius_lane_widths * lw,
                        tuple(ways))
    axis_set = set(axis_roles(law))
    per_face: dict[int, list[tuple[Way, float]]] = {}
    for fid, f in pm.faces.items():
        if f.role not in axis_set:
            continue
        poly = _face_polygon(pm, fid)
        if poly is None or poly.is_empty or poly.length <= 0:
            continue
        # THE FACE'S OWN ANSWER RADIUS: the core reads a ribbon vertex
        # within ``answer_radius_lane_widths`` lane widths of the
        # centreline, a lane width being the ribbon's half-width; a face
        # reads its ways within the same multiple of ITS half-width
        # (width = area / half-perimeter, ``classify/sources.py``'s
        # measure), never less than the core's radius.  A vertex of an
        # L-shaped page beyond that is not on this road: DEM, counted.
        width = poly.area / (poly.length / 2.0)
        radius = max(prof.radius_m, rp.answer_radius_lane_widths * width / 2.0)
        through = [prof.ways[i] for i in prof.ways_through(poly)]
        if through:
            per_face[fid] = [(w, radius) for w in through]
            continue
        axis = face_axis(list(poly.exterior.coords)[:-1], rp.station_m / 2.0)
        if axis is None:
            continue
        aw = clamp_way(AXIS, f"face:{fid}", axis, sample, cap_, rp.station_m, inside)
        if aw:
            prof.axes[fid] = aw[0]
            per_face[fid] = [(aw[0], radius)]
    prof.per_face = per_face
    return prof, per_face


def preferred_road_z(airport: Airport, pm: PlanarMap, law: Law,
                     cap: float | None = None, lane_width_m: float | None = None
                     ) -> tuple[dict[int, float], dict[str, _t.Any], RoadProfiles]:
    """``(preferred, report, profiles)``: the fit target of every road-
    family vertex (DEM-fallback vertices are NOT in ``preferred`` — they
    keep ``dem_z`` — and are counted per role in the report)."""
    profiles, per_face = core_profiles(airport, pm, law, cap, lane_width_m)
    owned = road_family_vertices(pm, law)
    preferred: dict[int, float] = {}
    by_role: dict[str, dict[str, int]] = {}
    moved = 0
    max_shift = 0.0
    tol = law.tables.emit.materiality.elevation_m
    for v in sorted(owned):
        vx = pm.vertices[v]
        through: list[tuple[Way, float]] = []
        for fid in vx.incident_faces:
            through.extend(per_face.get(fid, ()))
        a = profiles.answer(vx.xy, vx.dem_z or 0.0, through)
        rec = by_role.setdefault(owned[v], {"vertices": 0, OSM: 0, ROUTE: 0, AXIS: 0, "dem": 0})
        rec["vertices"] += 1
        if a.kind is None:
            rec["dem"] += 1
            continue
        rec[a.kind] += 1
        preferred[v] = a.z
        d = abs(a.z - (vx.dem_z or 0.0))
        if d > tol:
            moved += 1
        max_shift = max(max_shift, d)
    report = {"profiles": profiles.summary(), "by_role": by_role,
              "vertices": len(owned), "preferred": len(preferred),
              "dem_fallback": len(owned) - len(preferred),
              "preferred_off_dem": moved, "max_preferred_shift_m": round(max_shift, 4)}
    return preferred, report, profiles
