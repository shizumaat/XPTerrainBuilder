"""THE GROUND UNDER A MAPPED BRIDGE IS THE GROUND BESIDE IT (issue #1935).

A DEM that carries a road bridge's DECK (a DSM, or lidar whose ground
classes kept the deck) reads the deck's height over the road and the lot
under it: at EFHK the departures drive's bridge stands over the terminal's
land-side kerb road, and the kerb and the lot under the deck read metres
above the ground either side — above the terminal's own pad.

THE WITNESS.  Every 5 m along a highway way ``deck_signature.is_bridge_way``
accepts, the DECK in the DEM is the highest DEM inside the carriageway
(half the way's mapped width, ``road_ways.mapped_width_m`` at the
``[tunnel]`` lane law — ``planar/structure_approach.carriageway_width_m``'s
reading), and the ground BESIDE it is the DEM at the PROBE on each side

    probe = half-width + the stand-off (``groundside_cutback_m`` +
            ``snap_margin_m``) + ``[bridge] ground_probe_dem_cells`` DEM
            postings (the DEM's own ``posting_m``; none: no posting).

A station whose deck stands ``[bridge] clearance_minimum_m`` (4.2) over the
lower side and ``[cockpit] visual_m`` (0.5) over the higher is a deck in
the DEM.  Such stations are grouped into RUNS (``geom/station_runs``, the
covered-ground rule of #1996: one dropped station is bridged, never a
longer gap; a run of fewer than two stations reads nothing).

THE VALUE.  Each run's ribbon is ``probe`` wide each side of the way; a
point inside reads the lower of its DEM and the ground beside the deck,
interpolated across (right side to left) and along the run.  LOWER ONLY:
where the DEM already stands at the ground (bare earth) nothing moves.
Every road inside a ribbon reads it, the road a bridge leaves from
included (DEVIATION from the round-3 spec, awaiting its author's ruling:
the spec kept a bridge's APPROACH — a way whose end meets the bridge's end
— raw; at EFHK the terminal kerb road ends where the one-lane ramp bridge
-842 leaves it, under the departures drive's deck, and kept raw it stays
on the deck the DEM carries, 0.8 m over the terminal pad).

TWO SITES, ONE MODEL: ``planar/build`` substitutes ``Vertex.dem_z`` of the
vertices no airside face carries (airside vertices keep their DEM and are
counted; tile-seam vertices keep theirs), and ``airport/road_profile.
core_profiles`` chains :func:`bridge_sampler` after the wall-smear sampler
inside the patch's band (out of band the core's own profile stands), so
the road profiles and every ``preferred_z`` reader read the same ground.
Readers that ask ``airport.dem`` directly (the structure stage, the deck
seats, the emitter's outside mesh) keep the real DEM."""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

import numpy as np
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union
from shapely.strtree import STRtree

from ..geom.station_runs import section_runs
from ..law import Law
from ..law.tables import snap_margin_m
from .deck_signature import is_bridge_way
from .dem import dem_z_many
from .road_ways import mapped_width_m

__all__ = ["BridgeGround", "BridgeRun", "bridge_ground", "bridge_runs", "bridge_sampler"]

#: the spacing of the witness stations along a bridge way (metres)
_STATION_M = 5.0
#: the across-carriageway sampling step of the deck reading (metres)
_STEP_M = 1.0


@_dc.dataclass(frozen=True)
class _Station:
    s: float
    foot: tuple[float, float]
    normal: tuple[float, float]
    zl: float
    zr: float


@_dc.dataclass(frozen=True)
class BridgeRun:
    """One run of deck-in-DEM stations along a bridge way and its ribbon."""

    way_id: int
    line: LineString
    probe: float
    stations: tuple[_Station, ...]
    poly: Polygon

    def ground(self, p: Point) -> float:
        """The ground beside the deck at ``p``: across, then along."""
        st = self.stations
        s = self.line.project(p)
        k = int(np.clip(np.searchsorted([c.s for c in st], s), 1, len(st) - 1))
        a, b = st[k - 1], st[k]
        w = 0.0 if b.s <= a.s else min(1.0, max(0.0, (s - a.s) / (b.s - a.s)))
        q = self.line.interpolate(s)
        nx = a.normal[0] + w * (b.normal[0] - a.normal[0])
        ny = a.normal[1] + w * (b.normal[1] - a.normal[1])
        off = (p.x - q.x) * nx + (p.y - q.y) * ny
        t = min(1.0, max(0.0, (off + self.probe) / (2.0 * self.probe)))
        zl = a.zl + w * (b.zl - a.zl)
        zr = a.zr + w * (b.zr - a.zr)
        return zr + t * (zl - zr)


class BridgeRuns(tuple):
    """The witnessed runs (a tuple of :class:`BridgeRun`), with their
    spatial index cached once built."""

    _index: _t.Any = None


@_dc.dataclass
class BridgeGround:
    """What the bridge ground did at the planar site (the build's line)."""

    runs: int = 0
    ways: list[int] = _dc.field(default_factory=list)
    area_m2: float = 0.0
    vertices_lowered: int = 0
    max_lower_m: float = 0.0
    max_xy: tuple[float, float] | None = None
    airside_inside: int = 0
    seam_kept: int = 0

    def line(self) -> str:
        at = f" at ({self.max_xy[0]:.0f}, {self.max_xy[1]:.0f})" if self.max_xy else ""
        return (f"bridge ground (#1935): {self.runs} run(s) over {len(self.ways)} way(s) "
                f"{self.ways}, footprint {self.area_m2:,.0f} m2, "
                f"{self.vertices_lowered} vertex(es) lowered, max {self.max_lower_m:.2f} m{at}; "
                f"airside vertices inside (not lowered): {self.airside_inside}; "
                f"tile-seam vertices kept: {self.seam_kept}")


def _half(tags, law: Law) -> float:
    tn = law.tables.structures.tunnel
    return 0.5 * mapped_width_m(tags, tn.lane_width_m, tn.default_lanes)


def _probe_m(dem, law: Law, half: float) -> float:
    post = getattr(dem, "posting_m", None)
    cell = (post() if callable(post) else None) or 0.0
    cut = float(law.tables.zones.adjacent_ground.groundside_cutback_m) + snap_margin_m(law)
    return half + cut + float(law.tables.structures.bridge.ground_probe_dem_cells) * float(cell)


def _stations(dem, law: Law, ln: LineString, half: float, probe: float) -> list[_Station]:
    """The way's deck-in-DEM stations (module doc)."""
    rise = float(law.tables.structures.bridge.clearance_minimum_m)
    eps = float(law.tables.emit.cockpit.visual_m)
    offs = np.arange(-half, half + 1e-9, _STEP_M)
    out = []
    for s in np.append(np.arange(0.0, ln.length, _STATION_M), ln.length):
        a = ln.interpolate(max(0.0, s - 1.0))
        b = ln.interpolate(min(ln.length, s + 1.0))
        tx, ty = b.x - a.x, b.y - a.y
        n = math.hypot(tx, ty) or 1.0
        nx, ny = -ty / n, tx / n
        q = ln.interpolate(s)
        across = dem_z_many(dem, q.x + nx * offs, q.y + ny * offs)
        if not np.isfinite(across).any():
            continue
        deck = float(np.nanmax(across))
        zl, zr = (float(z) for z in dem_z_many(
            dem, np.array([q.x + nx * probe, q.x - nx * probe]),
            np.array([q.y + ny * probe, q.y - ny * probe])))
        if not (math.isfinite(zl) and math.isfinite(zr)):
            continue
        if deck - min(zl, zr) >= rise and deck - max(zl, zr) >= eps:
            out.append(_Station(float(s), (q.x, q.y), (nx, ny), zl, zr))
    return out


def _ribbon(st: _t.Sequence[_Station], probe: float) -> Polygon | None:
    left = [(c.foot[0] + c.normal[0] * probe, c.foot[1] + c.normal[1] * probe) for c in st]
    right = [(c.foot[0] - c.normal[0] * probe, c.foot[1] - c.normal[1] * probe) for c in st]
    poly = Polygon(left + right[::-1]).buffer(0)
    return None if poly.is_empty else poly


def bridge_runs(airport, law: Law) -> BridgeRuns:
    """Every run of deck-in-DEM stations along the airport's mapped highway
    bridges (module doc)."""
    dem = getattr(airport, "dem", None)
    runs: list[BridgeRun] = []
    for w in getattr(airport, "osm_ways", ()) if dem is not None else ():
        t = w.tags or {}
        if not t.get("highway") or not is_bridge_way(t) or len(w.points) < 2:
            continue
        ln = LineString(w.points)
        if ln.length <= 0.0:
            continue
        half = _half(t, law)
        probe = _probe_m(dem, law, half)
        for run in section_runs(_stations(dem, law, ln, half, probe), _STATION_M):
            poly = _ribbon(run, probe)
            if poly is not None:
                runs.append(BridgeRun(int(w.id), ln, probe, tuple(run), poly))
    return BridgeRuns(runs)


def _index(runs) -> tuple[STRtree, tuple[float, float, float, float]]:
    """``(tree, bounds)`` of ``runs``, built once per run set."""
    got = getattr(runs, "_index", None)
    if got is None:
        polys = [r.poly for r in runs]
        got = (STRtree(polys), unary_union(polys).bounds)
        if isinstance(runs, BridgeRuns):
            runs._index = got
    return got


def _ground_under(runs, xs: np.ndarray, ys: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """``(inside mask, ground beside)`` per point: the lowest reading of
    every ribbon covering it."""
    n = len(xs)
    inside = np.zeros(n, bool)
    g = np.full(n, np.inf)
    if not runs or n == 0:
        return inside, g
    tree, (x0, y0, x1, y1) = _index(runs)
    for i in np.flatnonzero((xs >= x0) & (xs <= x1) & (ys >= y0) & (ys <= y1)):
        p = Point(float(xs[i]), float(ys[i]))
        hit = [int(k) for k in tree.query(p) if runs[int(k)].poly.covers(p)]
        if not hit:
            continue
        inside[i] = True
        g[i] = min(runs[k].ground(p) for k in hit)
    return inside, g


def bridge_sampler(sample: _t.Callable[[np.ndarray, np.ndarray], np.ndarray],
                   runs: _t.Sequence[BridgeRun],
                   in_band: _t.Callable[[np.ndarray], np.ndarray] | None = None):
    """``sample`` read under the bridges: inside a run's ribbon (and inside
    the patch's band, ``in_band``: ``(xy (n, 2)) -> mask``, where given) the
    lower of the sample and the ground beside the deck (module doc);
    ``sample`` itself where no run is witnessed."""
    if not runs:
        return sample

    def _sample(xs, ys):
        xs = np.atleast_1d(np.asarray(xs, float))
        ys = np.atleast_1d(np.asarray(ys, float))
        z = np.array(sample(xs, ys), dtype=float)
        inside, g = _ground_under(runs, xs, ys)
        if in_band is not None and inside.any():
            band = np.asarray(in_band(np.column_stack([xs, ys])), bool)
            _sample.edge_kept += int((inside & ~band).sum())
            inside &= band
        low = inside & np.isfinite(z) & (g < z)
        _sample.lowered += int(low.sum())
        z[low] = g[low]
        return z

    #: stations lowered / kept raw outside the patch's band (the report)
    _sample.lowered = 0
    _sample.edge_kept = 0
    return _sample


def bridge_ground(runs: _t.Sequence[BridgeRun], xs: np.ndarray, ys: np.ndarray,
                  zs: np.ndarray, airside: _t.AbstractSet[int],
                  seam: _t.AbstractSet[int] = frozenset()
                  ) -> tuple[np.ndarray, BridgeGround]:
    """THE PLANAR SITE: ``zs`` with every vertex inside a run's ribbon that
    no airside face carries (``airside``: those keep their DEM, counted) and
    that is not on a tile seam (``seam``, counted) lowered to the ground
    beside the deck; and the report."""
    rep = BridgeGround(runs=len(runs), ways=sorted({r.way_id for r in runs}))
    if not runs:
        return zs, rep
    rep.area_m2 = float(unary_union([r.poly for r in runs]).area)
    inside, g = _ground_under(runs, np.asarray(xs, float), np.asarray(ys, float))
    out = np.array(zs, dtype=float, copy=True)
    for v in (int(i) for i in np.flatnonzero(inside)):
        if v in airside:
            rep.airside_inside += 1
            continue
        if v in seam:
            rep.seam_kept += 1
            continue
        here = float(out[v])
        if not math.isfinite(here) or g[v] >= here:
            continue
        out[v] = g[v]
        rep.vertices_lowered += 1
        if here - g[v] > rep.max_lower_m:
            rep.max_lower_m, rep.max_xy = here - float(g[v]), (float(xs[v]), float(ys[v]))
    return out, rep
