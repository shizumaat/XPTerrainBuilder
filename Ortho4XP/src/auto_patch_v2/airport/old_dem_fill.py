"""THE DEM OLDER THAN THE AIRPORT IS FILL (owner RULINGS 2026-11-06a (2),
refined by 2026-11-06b (4) and (5); #1915; spec
``docs/specs/old-dem-fill-spec.md``).

The owner: "when the DEM is older than the airport (it sits well below
CIFP-stood runway ends or the field elevation), the graded surface is built
up to the runway as FILL (an embankment), never pulled down to the DEM";
"the service roads are on terraces wrapping around the runway end safety
area relatively flat, with steep embankments between each terrace"; and
"where the DEM predates the airport, no runway or airside level stands
above field elevation plus the DEM-class tolerance".

ONE derivation, at load, right after the runway-end pins stand
(``end_pins.verify``), and ONE consumer: the airport's DEM sampler is
wrapped (:class:`FillDem`) so every reader of the ground — the end area,
the terrain edge, the zones' datum, the road profiles, the pack's object
reads — reads the airport's ground as built.  An airport with no fill
station is returned unchanged (byte-identical).

THE WITNESS (spec §1).  A FILL STATION is a station of a runway's
centreline, every ``emit.design.edge_grid_m``, where the line through its
two stood pins stands more than ``runway_ends.grade_disagree_m[class]``
over the DEM — further than the DEM's own class can be wrong.  A FILL RUN
is the stretch round a fill station where the pin line stands over the DEM
at all, so the fill begins and ends on the DEM.

THE CREST.  The runway's band (``zone2_half_width_m`` from the centreline)
over each fill run, and over the end area beyond an end the run reaches
(``runway_safety_area_length_m``).  Its level is the pin line at the
point's station (held at the end's level beyond it).

THE TERRACES (2026-11-06b (4)).  A mapped at-grade road whose centreline
runs where the crest's embankment (the crest level less
``zones.adjacent_ground.old_dem_fill_slope`` x the distance) stands over
the DEM is a TERRACE there: the RULE that picks its level is that the road
keeps the undisturbed DEM's level where it leaves the fill, held along its
run — linear between its two exits, flat from its one exit, and at another
terrace's level where it ends on that road (a junction).  A run with no
exit and no junction is under the fill (the owner's Q1 (a)): no terrace.

THE END AREA STOPS ABOVE THE FIRST TERRACE (the "steep embankments
between the RESA and the top terrace").  A terrace station ahead of a fill
end (within the band's half-width plus its own of the extended centreline)
sets that end's area back to where the embankment from the end's level
reaches the terrace at the fill grade, plus the road's half-width and the
groundside stand-off.  Beside the band nothing is set back — the strip's
width is airside law (airside is king): a terrace closer than its
embankment allows rides the band's embankment there (the fill surface is
the highest of the cones).

THE FILL SURFACE ``F = max(DEM, C)`` inside the FOOTPRINT, where ``C`` is
the highest of the crest's cone and every terrace's cone (its level, less
the fill grade x the distance past its half-width), and the footprint is
the ground ``C`` stands more than ``[cockpit] visual_m`` over the DEM,
connected to the crest.  Outside it the DEM is the ground.

THE CEILING (2026-11-06b (5)).  With a fill station, the DEM inside the
airport's airside envelope (every runway's band and end areas, every
pavement) is cut to the field elevation plus the DEM-class tolerance, and
falls back to the DEM outside it at the fill grade: the trends that read
the ground yield to it (the real airport was cut through the old hill).

FHSH (St Helena) is where the defect was found: the Copernicus 2010-2014
DEM shows the Dry Gut valley ~100 m under the 02 (01) end.  No airport is
named here (RULINGS 2026-10-05e)."""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

import numpy as np
import shapely
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import substring, unary_union

from ..law import Law
from ..law.inset_class import dem_source_class
from ..law.reference_code import runway_status
from ..law.tables import runway_ends, runway_safety_area_length_m, snap_margin_m, zone2_half_width_m
from ..model.airport import Airport, Runway
from .dem import dem_z_many
from .road_ways import ribbon_half_width_m, road_ways

__all__ = ["FillDem", "attach", "fill_model_of"]


@_dc.dataclass(frozen=True)
class _PinLine:
    """A runway's stood pin line: ``z(s)`` through its two pins, ``s``
    metres from end 0 along the axis ``a`` + ``s`` x ``u``."""

    a: tuple[float, float]
    u: tuple[float, float]
    length: float
    s0: float
    z0: float
    s1: float
    z1: float

    def z(self, s):
        """The pin line's level at station(s) ``s``."""
        if abs(self.s1 - self.s0) < 1e-9:
            return np.full(np.shape(s), self.z0) if np.ndim(s) else self.z0
        return self.z0 + (self.z1 - self.z0) * (np.asarray(s) - self.s0) / (self.s1 - self.s0)

    def station(self, xs, ys) -> np.ndarray:
        """Each point's station, clamped to the runway (an end area holds
        its end's level)."""
        s = (np.asarray(xs) - self.a[0]) * self.u[0] + (np.asarray(ys) - self.a[1]) * self.u[1]
        return np.clip(s, 0.0, self.length)

    def at(self, s: float) -> tuple[float, float]:
        """The axis point at station ``s`` (unclamped)."""
        return (self.a[0] + self.u[0] * s, self.a[1] + self.u[1] * s)


@_dc.dataclass(frozen=True)
class _Terrace:
    """One road's run across the fill (``line``, that stretch of the road),
    held at its terrace level: ``level[i]`` at arc ``at[i]`` metres along
    it; ``exits`` says what each end meets (``ground`` / ``junction`` /
    ``end``)."""

    way_id: object
    line: LineString
    half_m: float
    at: tuple[float, ...]
    level: tuple[float, ...]
    exits: tuple[str, str]


@_dc.dataclass(frozen=True)
class _FillModel:
    """The airport's fill (module docstring)."""

    grade: float
    #: ``(crest polygon, its pin line)`` per runway fill run
    crest: tuple[tuple[Polygon, _PinLine], ...]
    terraces: tuple[_Terrace, ...]
    footprint: _t.Any
    #: 2026-11-06b (5): the airside ceiling and the envelope it holds in
    cap_m: float | None = None
    cap_envelope: _t.Any = None
    #: ``{runway id: (end area past end 0, past end 1)}`` where a fill end
    #: was set back above a terrace
    end_area_m: dict = _dc.field(default_factory=dict)

    def __post_init__(self) -> None:
        # the carriageways the crest's cone is shadowed by (derived, held)
        object.__setattr__(self, "_ways", tuple(t.line.buffer(t.half_m, cap_style="flat")
                                                for t in self.terraces))

    def cone(self, xs: np.ndarray, ys: np.ndarray) -> np.ndarray:
        """``C`` at every point (``-inf`` where nothing reaches): the
        highest of every terrace's cone and the crest's.  The crest's cone
        falls at the fill slope, never past a terrace (a point whose way to
        the crest crosses a terrace road is the terrace's ground), and
        steepens to land on a terrace standing closer than the slope allows:
        between the two it is the straight face from the crest's edge to
        the road's kerb (airside keeps its width, the road its level)."""
        xs, ys = np.asarray(xs, dtype=float), np.asarray(ys, dtype=float)
        out = np.full(xs.shape, -np.inf)
        if xs.size == 0:
            return out
        pts = shapely.points(xs, ys)
        g = self.grade
        reads = []
        for t in self.terraces:
            d = np.maximum(shapely.distance(t.line, pts) - t.half_m, 0.0)
            lev = np.interp(shapely.line_locate_point(t.line, pts), t.at, t.level)
            np.maximum(out, lev - g * d, out=out)
            reads.append((d, lev))
        for poly, pl in self.crest:
            d_b = shapely.distance(poly, pts)
            z_c = pl.z(pl.station(xs, ys))
            c = z_c - g * d_b
            if reads:
                to_crest = shapely.shortest_line(pts, poly)
                for way, (d_r, lev) in zip(self._ways, reads, strict=True):
                    far = (d_b > 0.0) & shapely.intersects(to_crest, way) & (d_r > 0.0)
                    c = np.where(far, -np.inf, c)
                    with np.errstate(invalid="ignore", divide="ignore"):
                        face = z_c - (z_c - lev) * d_b / np.maximum(d_b + d_r, 1e-9)
                    c = np.minimum(c, np.where(lev < z_c, face, np.inf))
            np.maximum(out, c, out=out)
        return out

    def apply(self, xs, ys, z) -> np.ndarray:
        """The ground as built at every point, from the DEM's ``z``."""
        xs, ys = np.asarray(xs, dtype=float), np.asarray(ys, dtype=float)
        out = np.array(z, dtype=float, copy=True)
        if out.ndim == 0 or out.size == 0:
            return out
        fp = self.footprint
        if fp is not None and not fp.is_empty:
            x0, y0, x1, y1 = fp.bounds
            near = (xs >= x0) & (xs <= x1) & (ys >= y0) & (ys <= y1)
            if near.any():
                ix = np.flatnonzero(near)
                inside = shapely.contains_xy(fp, xs[ix], ys[ix])
                ix = ix[inside]
                if ix.size:
                    c = self.cone(xs[ix], ys[ix])
                    ok = np.isfinite(out[ix])
                    out[ix[ok]] = np.maximum(out[ix[ok]], c[ok])
        if self.cap_m is not None and self.cap_envelope is not None:
            env = self.cap_envelope
            over = np.isfinite(out) & (out > self.cap_m)
            if over.any():
                ix = np.flatnonzero(over)
                d = shapely.distance(env, shapely.points(xs[ix], ys[ix]))
                out[ix] = np.minimum(out[ix], self.cap_m + self.grade * d)
        return out


class FillDem:
    """The airport's DEM sampler with the fill applied (module docstring):
    ``z`` / ``z_many`` read the ground as built; everything else is the
    wrapped sampler's."""

    def __init__(self, inner, model: _FillModel) -> None:
        self.inner = inner
        self.model = model

    def z_many(self, xs, ys) -> np.ndarray:
        """The ground as built at every point."""
        xs, ys = np.asarray(xs, dtype=float), np.asarray(ys, dtype=float)
        return self.model.apply(xs, ys, dem_z_many(self.inner, xs, ys))

    def z(self, x: float, y: float) -> float:
        """The ground as built at one point."""
        return float(self.z_many(np.array([float(x)]), np.array([float(y)]))[0])

    def __getattr__(self, name: str):
        if name in ("inner", "model") or name.startswith("__"):
            raise AttributeError(name)
        return getattr(self.inner, name)


def fill_model_of(airport) -> _FillModel | None:
    """The airport's fill, or ``None`` when its DEM is the ground."""
    dem = getattr(airport, "dem", None)
    return dem.model if isinstance(dem, FillDem) else None


# ── the derivation ──────────────────────────────────────────────────────

def _pin_line(rw: Runway) -> _PinLine | None:
    a, b = rw.ends[0].xy, rw.ends[1].xy
    L = math.hypot(b[0] - a[0], b[1] - a[1])
    e0, e1 = rw.ends
    if L <= 0.0 or e0.threshold_elev_m is None or e1.threshold_elev_m is None:
        return None
    u = ((b[0] - a[0]) / L, (b[1] - a[1]) / L)
    return _PinLine(a, u, L, float(e0.pin_along()), float(e0.threshold_elev_m),
                   L - float(e1.pin_along()), float(e1.threshold_elev_m))


def _fill_runs(pl: _PinLine, dem, step: float, tol: float, hw: float
               ) -> list[tuple[int, float, float, float]]:
    """``(side, s_a, s_b, deepest)`` per fill run of each half of the band
    (``side`` -1 / +1 of the axis): the stretches where the pin line stands
    over the DEM on the centreline or that half's edge, holding a
    centreline station deeper than ``tol`` (the witness is the pavement's;
    a half whose own ground stands over the runway is never filled)."""
    n = max(1, int(math.ceil(pl.length / step)))
    ss = np.linspace(0.0, pl.length, n + 1)
    px, py = -pl.u[1], pl.u[0]

    def deficit(t: float) -> np.ndarray:
        return pl.z(ss) - dem_z_many(dem, pl.a[0] + pl.u[0] * ss + px * t,
                                     pl.a[1] + pl.u[1] * ss + py * t)

    axis = deficit(0.0)
    runs = []
    for side in (-1, 1):
        over = np.nanmax(np.vstack([axis, deficit(side * hw)]), axis=0) > 0.0
        i = 0
        while i <= n:
            if not over[i]:
                i += 1
                continue
            j = i
            while j + 1 <= n and over[j + 1]:
                j += 1
            seg = axis[i:j + 1]
            deepest = float(np.nanmax(seg)) if np.isfinite(seg).any() else 0.0
            if deepest > tol:
                runs.append((side, float(ss[i]), float(ss[j]), deepest))
            i = j + 1
    return runs


def _crest(pl: _PinLine, runs, hw: float, ends: tuple[float, float]) -> list[Polygon]:
    """Each run's half of the band, run out by ``ends[k]`` past an end it
    reaches."""
    out = []
    px, py = -pl.u[1], pl.u[0]
    for side, sa, sb, _deep in runs:
        lo = -ends[0] if sa <= 0.0 else sa
        hi = pl.length + ends[1] if sb >= pl.length else sb
        a, b = pl.at(lo), pl.at(hi)
        o = (px * side * hw, py * side * hw)
        out.append(Polygon([a, b, (b[0] + o[0], b[1] + o[1]), (a[0] + o[0], a[1] + o[1])]))
    return out


def _model(grade, crest, terraces=(), footprint=None) -> _FillModel:
    return _FillModel(grade, tuple(crest), tuple(terraces), footprint)


def _stations(line: LineString, step: float) -> np.ndarray:
    n = max(1, int(math.ceil(line.length / step)))
    return np.linspace(0.0, line.length, n + 1)


def _terraces(roads, crest, dem, grade, step, eps, weld) -> list[_Terrace]:
    """THE TERRACES (module docstring) under the crest's cone.

    Each road's profile is read every ``step``; over every DIP of it that
    the crest's cone stands over the DEM in (the fill), the road holds its
    LOWER RIM: the lower of the highest ground along the road behind and ahead of
    the station — where it meets undisturbed ground on its lower side, held
    flat while it wraps the fill.  A road that ends on another road's
    terrace takes that terrace's level as its rim there (a junction)."""
    cone = _model(grade, crest)
    prof = {}
    for k, (_w, line, _half) in enumerate(roads):
        ss = _stations(line, step)
        pts = [line.interpolate(s) for s in ss]
        xs = np.array([p.x for p in pts])
        ys = np.array([p.y for p in pts])
        dz = dem_z_many(dem, xs, ys)
        if not np.isfinite(dz).all():
            continue
        inside = cone.cone(xs, ys) - dz > eps
        if inside.any():
            prof[k] = (ss, dz, inside)
    lines = [line for _w, line, _h in roads]

    def partner(k: int, side: int):
        """The road road ``k``'s ``side`` end lies on, and the point."""
        _w, line, half = roads[k]
        p = Point(line.coords[0] if side == 0 else line.coords[-1])
        for m, other in enumerate(lines):
            if m != k and other.distance(p) <= half + weld:
                return m, p
        return None

    levels: dict[int, np.ndarray] = {}

    def level_on(m: int, p: Point) -> float | None:
        """Road ``m``'s terrace level at ``p``; ``None`` where it is on its
        ground there (or not yet resolved)."""
        if m not in levels:
            return None
        ss, dz, _inside = prof[m]
        lev = levels[m]
        s = lines[m].project(p)
        i = int(np.argmin(np.abs(ss - s)))
        return float(lev[i]) if lev[i] - dz[i] > eps else None

    waiting = {k: [partner(k, 0), partner(k, 1)] for k in prof}
    for _pass in range(len(prof) + 1):
        moved = False
        for k, (_ss, dz, _inside) in prof.items():
            if k in levels:
                continue
            jn = waiting[k]
            if _pass == 0 and any(j is not None and j[0] in prof for j in jn):
                continue                # a road ending on another waits one pass for it
            rim0 = level_on(*jn[0]) if jn[0] is not None and jn[0][0] in prof else None
            rim1 = level_on(*jn[1]) if jn[1] is not None and jn[1][0] in prof else None
            left = np.maximum.accumulate(np.where(np.isfinite(dz), dz, -np.inf))
            right = np.maximum.accumulate(dz[::-1])[::-1]
            if rim0 is not None:
                left = np.maximum(left, rim0)
            if rim1 is not None:
                right = np.maximum(right, rim1)
            levels[k] = np.maximum(np.minimum(left, right), dz)
            moved = True
        if not moved and _pass > 0:
            break
    out = []
    for k, lev in levels.items():
        ss, dz, inside = prof[k]
        w, line, half = roads[k]
        filled = lev - dz > eps
        i = 0
        while i < len(ss):
            if not filled[i]:
                i += 1
                continue
            j = i
            while j + 1 < len(ss) and filled[j + 1]:
                j += 1
            if not inside[i:j + 1].any():
                i = j + 1
                continue                # a dip of the road's own, off the fill
            a, b = max(0, i - 1), min(len(ss) - 1, j + 1)   # the run meets its ground
            at, lv = ss[a:b + 1], np.maximum(lev[a:b + 1], dz[a:b + 1])
            kinds = tuple("ground" if e != f else ("junction" if waiting[k][n] else "end")
                          for n, (e, f) in enumerate(((a, i), (b, j))))
            run = substring(line, float(at[0]), float(at[-1]))
            out.append(_Terrace(getattr(w, "id", k), run, float(half),
                               tuple(float(s - at[0]) for s in at), tuple(map(float, lv)), kinds))
            i = j + 1
    return out


def _set_back(pl: _PinLine, runs, terraces, rsa: float, hw: float, grade: float,
              standoff: float, eps: float) -> tuple[float, float]:
    """Each fill end's area: ``rsa``, set back above every terrace station
    ahead of it (module docstring)."""
    out = []
    for k, reaches in ((0, any(sa <= 0.0 for _side, sa, _sb, _d in runs)),
                       (1, any(sb >= pl.length for _side, _sa, sb, _d in runs))):
        keep = rsa
        if reaches:
            end = pl.at(0.0 if k == 0 else pl.length)
            ux, uy = (-pl.u[0], -pl.u[1]) if k == 0 else pl.u
            z_end = float(pl.z(0.0 if k == 0 else pl.length))
            for t in terraces:
                for s, lev in zip(t.at, t.level, strict=True):
                    p = t.line.interpolate(s)
                    ahead = (p.x - end[0]) * ux + (p.y - end[1]) * uy
                    side = -(p.x - end[0]) * uy + (p.y - end[1]) * ux
                    if ahead <= 0.0 or abs(side) > hw + t.half_m or z_end - lev <= eps:
                        continue
                    keep = min(keep, ahead - t.half_m - standoff - (z_end - lev) / grade)
        out.append(max(0.0, keep))
    return out[0], out[1]


def _footprint(model: _FillModel, dem, step: float):
    """The ground the fill stands over the DEM on, connected to the crest,
    read on a ``step`` grid and grown one step (its toe on the DEM)."""
    crest = unary_union([p for p, _pl in model.crest])
    zmax = max(float(np.max(pl.z(np.array([0.0, pl.length])))) for _p, pl in model.crest)
    region = unary_union([crest] + [t.line.buffer(t.half_m) for t in model.terraces])
    reach = 0.0
    for _round in range(2):     # the reach the cone can fall from the crest to the ground
        x0, y0, x1, y1 = region.buffer(reach).bounds
        gx = np.arange(x0, x1 + step, step)
        gy = np.arange(y0, y1 + step, step)
        X, Y = np.meshgrid(gx, gy)
        dz = dem_z_many(dem, X.ravel(), Y.ravel())
        zmin = float(np.nanmin(dz)) if np.isfinite(dz).any() else zmax
        reach = max(0.0, (zmax - zmin) / model.grade) + step
    x0, y0, x1, y1 = region.buffer(reach).bounds
    gx = np.arange(x0, x1 + step, step)
    gy = np.arange(y0, y1 + step, step)
    X, Y = np.meshgrid(gx, gy)
    xs, ys = X.ravel(), Y.ravel()
    dz = dem_z_many(dem, xs, ys)
    over = np.isfinite(dz) & (model.cone(xs, ys) - dz > 0.0)
    h = 0.5 * step
    cells = [box(x - h, y - h, x + h, y + h) for x, y in zip(xs[over], ys[over], strict=True)]
    if not cells:
        return Polygon()
    u = shapely.union_all(cells, grid_size=h)
    parts = [g for g in shapely.get_parts(u) if g.intersects(crest)]
    if not parts:
        return Polygon()
    # one grid step out, so the toe ring stands where the fill has met the
    # DEM (``F`` is the DEM there); the grid's stairs rounded off
    return unary_union(parts).buffer(step).simplify(h)


def _envelope(airport: Airport, law: Law, lines) -> _t.Any:
    """The airside envelope the ceiling holds in: every runway's band and
    end areas, every pavement."""
    polys = []
    for rw, pl in lines:
        st = runway_status(rw)
        hw = float(zone2_half_width_m(law, "runway", rw.code_number, rw.code_letter, st) or 0.0)
        rsa = float(runway_safety_area_length_m(law, rw.code_number, rw.code_letter, st))
        polys.append(LineString([pl.at(-rsa), pl.at(pl.length + rsa)]).buffer(hw, cap_style="flat"))
    for p in getattr(airport, "pavements", ()) or ():
        try:
            g = Polygon(p.outer, p.holes)
        except Exception:                                   # pragma: no cover
            continue
        if g.is_valid and not g.is_empty:
            polys.append(g)
    return unary_union(polys) if polys else None


def attach(airport: Airport, law: Law, klass: str | None = ""
           ) -> tuple[Airport, list[dict], list[str]]:
    """THE RULE (module docstring) on ``airport``: the airport with its DEM
    wrapped in its fill, one record per fill run and per terrace, and the
    loud lines; ``(airport, [], [])`` when no runway stands over a fill
    station."""
    dem = getattr(airport, "dem", None)
    if dem is None or isinstance(dem, FillDem) or not airport.runways:
        return airport, [], []
    if klass == "":
        try:
            klass, _pixel, _whence = dem_source_class(dem, law)
        except Exception:                                   # pragma: no cover
            klass = None
    if klass is None:
        return airport, [], []          # a sampler of no stated class is no witness
    tol = float(runway_ends(law).grade_disagree_m.of(klass))
    d_ = law.tables.emit.design
    step = float(d_.edge_grid_m)
    eps = float(law.tables.emit.cockpit.visual_m)
    grade = float(law.tables.zones.adjacent_ground.old_dem_fill_slope)
    standoff = float(law.tables.zones.adjacent_ground.groundside_cutback_m) + snap_margin_m(law)
    weld = float(law.tables.emit.identity.weld_spacing_m)
    roads = [(w, line, ribbon_half_width_m(getattr(w, "tags", None), law))
             for w, line in road_ways(getattr(airport, "osm_ways", ()))]
    lines, per = [], []
    for rw in airport.runways:
        pl = _pin_line(rw)
        if pl is None:
            continue
        lines.append((rw, pl))
        st = runway_status(rw)
        # the band is measured off the runway CELL's edge, which a pack may
        # draw off the apt.dat centreline: the crest covers it with a
        # runway half-width to spare (under-covered, the zone's ring hung
        # over the embankment — measured FHSH: 2-10 m tears along 400 m)
        hw = float(zone2_half_width_m(law, "runway", rw.code_number, rw.code_letter, st)
                   or 0.0) + 0.5 * float(rw.width_m)
        runs = _fill_runs(pl, dem, step, tol, hw)
        if not runs:
            continue
        rsa = float(runway_safety_area_length_m(law, rw.code_number, rw.code_letter, st))
        per.append((rw, pl, runs, hw, rsa))
    if not per:
        return airport, [], []
    # pass 1: the terraces under the band run out its full end areas
    crest = [(g, pl) for rw, pl, runs, hw, rsa in per for g in _crest(pl, runs, hw, (rsa, rsa))]
    terr = _terraces(roads, crest, dem, grade, step, eps, weld)
    ends = {rw.id: _set_back(pl, runs, terr, rsa, hw, grade, standoff, eps)
            for rw, pl, runs, hw, rsa in per}
    # pass 2: the terraces under the band as set back above them
    crest = [(g, pl) for rw, pl, runs, hw, _rsa in per
             for g in _crest(pl, runs, hw, ends[rw.id])]
    terr = _terraces(roads, crest, dem, grade, step, eps, weld)
    model = _model(grade, crest, terr)
    model = _dc.replace(model, footprint=_footprint(model, dem, step),
                        end_area_m=dict(ends),
                        cap_m=float(airport.elevation_m) + tol,
                        cap_envelope=_envelope(airport, law, lines))
    records, out_lines = _report(airport, per, model, dem, tol, klass)
    return _dc.replace(airport, dem=FillDem(dem, model)), records, out_lines


def _report(airport, per, model: _FillModel, dem, tol, klass) -> tuple[list[dict], list[str]]:
    records, out = [], []
    for rw, _pl, runs, _hw, rsa in per:
        ends = model.end_area_m.get(rw.id, (rsa, rsa))
        for side, sa, sb, deep in runs:
            records.append({"kind": "run", "runway": rw.id, "side": side, "s_a": round(sa, 1),
                            "s_b": round(sb, 1), "deepest_m": round(deep, 2),
                            "end_area_m": [round(e, 1) for e in ends]})
            out.append(f"OLD-DEM FILL (#1915, RULINGS 2026-11-06a (2)) {airport.icao} "
                       f"{rw.id} {'left' if side < 0 else 'right'}: the pin line stands up to "
                       f"{deep:.1f} m over the {klass} DEM "
                       f"(tolerance {tol:g} m) over s {sa:.0f}-{sb:.0f} m; the ground there is "
                       f"fill at 1:{1.0 / model.grade:.2g}; end areas "
                       f"{ends[0]:.0f} / {ends[1]:.0f} m (RSA {rsa:.0f} m)")
    for t in model.terraces:
        records.append({"kind": "terrace", "way": t.way_id, "run_m": round(t.at[-1] - t.at[0], 1),
                        "level_m": [round(min(t.level), 2), round(max(t.level), 2)],
                        "exits": list(t.exits)})
        out.append(f"  terrace road {t.way_id}: {t.at[-1] - t.at[0]:.0f} m held at "
                   f"{t.level[0]:.1f} -> {t.level[-1]:.1f} m (ends: {t.exits[0]} / {t.exits[1]})")
    fp = model.footprint
    if fp is not None and not fp.is_empty:
        records.append({"kind": "footprint", "area_m2": round(fp.area, 0)})
        out.append(f"  fill footprint {fp.area:,.0f} m2; airside ceiling {model.cap_m:.1f} m "
                   f"(field + {tol:g} m, RULINGS 2026-11-06b (5))")
    return records, out
