"""#1638 — A DUAL ROADWAY THROUGH THE AIRPORT IS ONE TRENCH AT ONE DEPTH
(owner 2026-10-29, read of LFPG 1.0.444: "where a dual roadway crosses
through most of the airport, there's a single, continuous cut that spans
both roadways and everything in between"; the same pattern at KPHX).

THE WITNESS is the map's geometry alone, never a name or an airport:

* two CARRIAGEWAYS — the routes of ``[tunnel] dual_trench_highways`` ways,
  each walked through its many short ways by heading
  (``viaduct_road.walk_route``, the approach walk's least-turn law) — run
  parallel (headings within 30°, 31h's dual test) and apart by more than one
  road mapped twice and at most ``dual_trench_max_separation_m``;
* the pair runs BELOW THE AIRPORT'S SURFACE: from the first to the last
  station inside the aerodrome boundary where either carriageway is mapped
  under something — any ``tunnel`` value but ``no`` (a ``building_passage``
  is a passage under the cover too), ``covered=yes``, or ``layer < 0`` —
  for at least ``dual_trench_min_run_m``.  Between those stations the road
  may rise onto viaducts or pass at grade briefly: the trench under it is
  the one level the owner reads ("uninterrupted and same-depth").

THE TRENCH spans both carriageways and everything between them: its axis
is the midline of the pair, its half width at a station half the
centre-to-centre distance plus half the wider carriageway, the widest within
25 m (a junction's jitter never pinches it).  ONE FLOOR along the whole run:
the COVER beside it (the upper quartile of the ground 25–60 m beyond its
edges, §2's crest read along the trench; RULINGS 2026-10-28k 226 a) less
``mouth_depth_m`` — 231 b, a road under the airport's surface goes to the
mouth depth — or, on a CREDIBLE survey, the surveyed road where the survey
sees it open (``layer < 0`` with no tunnel, covered or bridge tag)
and lower (230 a: a surveyed cut is kept, never filled).  Beyond each end it
climbs back along the pair's midline at the design grade (R4), or inside the
run where the pair does not carry the climb (``viaduct_road.level_side``).

THE MODEL is R6's: two sibling Law-B (``sunken_road``) halves meeting
capless at the run's midpoint (``viaduct_road.level_half``), the profile
pinned per station by the generator.  A run inside a runway strip keep-out
is refused by name (the trench is not cut under a runway; a hard deck there
is R3's, #1138).

THE ONE DERIVATION SITE (RULINGS 2026-08-30l): :func:`dual_trench_groups`
states the trench and its FOOTPRINT; ``build_structures`` hands every mouth
standing inside the footprint to the trench (:func:`absorb_mouths`: the
trench carries the road there — no second ramp, no second depth) and every
R6 level inside it (:func:`yield_groups`), before anything is built.  Every
pass downstream reads the trench as it reads an R6 level."""
from __future__ import annotations

import dataclasses as _dc
import math
import statistics
import typing as _t

from shapely.geometry import LineString, Point
from shapely.ops import substring, unary_union
from shapely.strtree import STRtree

from ..airport.dem import dem_z_at
from ..law import Law, inset_class
from ..model.frame import XY
from .object_corridor import Group
from .structure_approach import carriageway_width_m, is_bridge, unit
from .viaduct_road import (aerodrome_boundary, layer_of, level_half, level_side, road_graph,
                           walk_route)

__all__ = ["DualTrenches", "ID_PREFIX", "absorb_mouths", "dual_trench_groups",
           "yield_groups"]

ID_PREFIX = "dual-trench"
_STEP_M = 5.0
#: the two carriageways run parallel: headings within 30° (31h's dual test)
_PARALLEL_COS = math.cos(math.radians(30.0))
#: nearer than this the "pair" is one road mapped twice (the feeds carry duplicates)
_SAME_ROAD_M = 3.0
#: the half width at a station is the widest within this of it
_WIDTH_WINDOW_M = 25.0
#: a station of one carriageway is ON a way within this of it
_ON_WAY_M = 0.5
#: the cover is read every this along the run, at these offsets beyond its edges (§2's 25–60 m)
_COVER_STEP_M = 25.0
_COVER_OFFSETS_M = (25.0, 30.0, 35.0, 40.0, 45.0, 50.0, 55.0, 60.0)


@_dc.dataclass(frozen=True)
class DualTrenches:
    """The build groups, their union FOOTPRINT (``None`` with none), the
    report lines and the refusals."""

    groups: tuple[Group, ...] = ()
    footprint: _t.Any = None
    notes: tuple[str, ...] = ()
    refused: tuple[str, ...] = ()


def _below_grade(w) -> bool:
    """Whether way ``w`` is mapped under something: a ``tunnel`` (any value
    but ``no``), ``covered=yes`` or a negative ``layer``."""
    t = w.tags or {}
    return str(t.get("tunnel", "no")).strip().lower() not in ("no", "") \
        or str(t.get("covered", "no")).strip().lower() == "yes" or layer_of(t) < 0


def _open_below(w) -> bool:
    """Below grade and OPEN to the sky (the survey sees its road): a
    negative layer with no tunnel, covered or bridge tag."""
    t = w.tags or {}
    return layer_of(t) < 0 and str(t.get("tunnel", "no")).strip().lower() in ("no", "") \
        and str(t.get("covered", "no")).strip().lower() != "yes" and not is_bridge(w)


def _carriageways(airport, law: Law, inside) -> list[tuple[LineString, list]]:
    """Every through road's ROUTE that reaches the boundary, with its ways:
    walked from its longest unwalked way both ways by heading."""
    tn = law.tables.structures.tunnel
    classes = set(tn.dual_trench_highways)
    roads, seen = [], set()
    for w in getattr(airport, "osm_ways", ()) or ():
        if len(w.points) < 2 or (w.tags or {}).get("highway") not in classes:
            continue
        key = tuple((round(x, 2), round(y, 2)) for x, y in w.points)
        if key in seen or key[::-1] in seen:
            continue
        seen.add(key)
        roads.append(w)
    lines = {id(w): LineString(w.points) for w in roads}
    nb = road_graph(roads)
    x0, y0, x1, y1 = inside.bounds
    reach = 4.0 * math.hypot(x1 - x0, y1 - y0)
    cos_max = math.cos(math.radians(tn.approach_turn_max_deg))
    used: set[int] = set()
    out: list[tuple[LineString, list]] = []
    for w in sorted(roads, key=lambda r: -lines[id(r)].length):
        if id(w) in used:
            continue
        pts = [(float(x), float(y)) for x, y in w.points]
        fwd = walk_route(pts[-1], unit(pts[-2], pts[-1]), nb, reach, cos_max)
        back = walk_route(pts[0], unit(pts[1], pts[0]), nb, reach, cos_max)
        seq = list(reversed(back[1:])) + pts + fwd[1:]
        path = [seq[0]] + [p for prev, p in zip(seq, seq[1:]) if p != prev]
        if len(path) < 2:
            continue
        route = LineString(path)
        zone = route.buffer(0.05)
        on = [r for r in roads if lines[id(r)].within(zone)] or [w]
        used.update(id(r) for r in on)
        used.add(id(w))
        if route.intersects(inside) and not any(          # one road mapped twice is one
                route.intersection(r.buffer(_SAME_ROAD_M)).length >= 0.8 * route.length
                for r, _on in out):
            out.append((route, on))
    return out


class _Ways:
    """One carriageway's ways, indexed: :meth:`at` is the way a station
    stands on (within :data:`_ON_WAY_M`), else ``None``."""

    def __init__(self, ways):
        self.ways = list(ways)
        self.tree = STRtree([LineString(w.points) for w in self.ways])
        self.below = any(_below_grade(w) for w in self.ways)

    def at(self, p: Point):
        hit = self.tree.query_nearest(p, max_distance=_ON_WAY_M)
        return self.ways[int(hit[0])] if len(hit) else None


def _heading(line: LineString, s: float) -> XY:
    a = line.interpolate(max(0.0, s - _STEP_M / 2.0))
    b = line.interpolate(min(line.length, s + _STEP_M / 2.0))
    return unit((a.x, a.y), (b.x, b.y))


def _span(a: LineString, a_ways: _Ways, b: LineString, b_ways: _Ways, law: Law, inside
          ) -> list[dict]:
    """Per station of carriageway ``a``, where ``b`` runs parallel within
    the separation: the midpoint, the half width spanning both, whether
    either is below grade, whether open below grade (the survey's road
    points), inside the boundary — the longest contiguous stretch."""
    tn = law.tables.structures.tunnel
    sep = tn.dual_trench_max_separation_m
    rows: list[dict | None] = []
    near = inside.buffer(tn.max_ramp_length_m)   # the run and the climbs beyond it
    n = int(a.length // _STEP_M) + 1
    for k in range(n):
        s = k * _STEP_M
        p = a.interpolate(s)
        if not near.contains(p):
            rows.append(None)
            continue
        t = b.project(p)
        q = b.interpolate(t)
        d = p.distance(q)
        ha, hb = _heading(a, s), _heading(b, t)
        if not (_SAME_ROAD_M < d <= sep) or abs(ha[0] * hb[0] + ha[1] * hb[1]) < _PARALLEL_COS:
            rows.append(None)
            continue
        wa, wb = a_ways.at(p), b_ways.at(q)
        cw = max(carriageway_width_m(w.tags, law) for w in (wa, wb) if w is not None) \
            if (wa or wb) else carriageway_width_m({}, law)
        mid = ((p.x + q.x) / 2.0, (p.y + q.y) / 2.0)
        rows.append(dict(mid=mid, half=d / 2.0 + cw / 2.0,
                         below=any(w is not None and _below_grade(w) for w in (wa, wb)),
                         open=[(x.x, x.y) for x, w in ((p, wa), (q, wb))
                               if w is not None and _open_below(w)],
                         inside=inside.contains(Point(mid))))
    best: list[dict] = []
    cur: list[dict] = []
    gap = 0
    for r in rows + [None] * 3:
        if r is None:
            gap += 1
            if gap > 2 and cur:
                best, cur = (cur if len(cur) > len(best) else best), []
            continue
        gap = 0
        cur.append(r)
    return best


def _half_at(ss: list[float], hs: list[float]) -> _t.Callable[[float], float]:
    """The half width by station along the midline: the widest within
    :data:`_WIDTH_WINDOW_M`, linear between stations."""
    wide = [max(h for s2, h in zip(ss, hs, strict=True) if abs(s2 - s) <= _WIDTH_WINDOW_M)
            for s in ss]

    def f(s: float) -> float:
        if s <= ss[0]:
            return wide[0]
        for (s0, h0), (s1, h1) in zip(zip(ss, wide), zip(ss[1:], wide[1:])):
            if s <= s1:
                return h0 + (h1 - h0) * (s - s0) / max(s1 - s0, 1e-9)
        return wide[-1]
    return f


def _candidates(airport, law: Law, inside) -> list[tuple]:
    """``(midline, stations s, rows, ids)`` per dual pair whose below-grade
    run inside the boundary is long enough, longest first."""
    tn = law.tables.structures.tunnel
    cw = [(a, _Ways(on)) for a, on in _carriageways(airport, law, inside)]
    out = []
    for i in range(len(cw)):
        for j in range(i + 1, len(cw)):
            (a, aw), (b, bw) = cw[i], cw[j]
            if not (aw.below or bw.below) or \
                    a.distance(b) > tn.dual_trench_max_separation_m:
                continue
            near = a.intersection(inside).intersection(b.buffer(tn.dual_trench_max_separation_m))
            if near.length < tn.dual_trench_min_run_m or \
                    a.intersection(b.buffer(_SAME_ROAD_M)).length >= 0.5 * near.length:
                continue
            rows = _span(a, aw, b, bw, law, inside)
            if len(rows) < 2:
                continue
            mid = LineString([r["mid"] for r in rows]).simplify(0.5)
            ss = [mid.project(Point(r["mid"])) for r in rows]
            run = [s for s, r in zip(ss, rows, strict=True) if r["below"] and r["inside"]]
            if not run or run[-1] - run[0] < tn.dual_trench_min_run_m:
                continue
            ids = "+".join(str(w.id) for w in (aw.ways[:2] + bw.ways[:2])) + "+…"
            out.append((mid, ss, rows, run[0], run[-1], ids))
    out.sort(key=lambda c: -(c[4] - c[3]))
    return out


def _cover(airport, run: LineString, half_at, s0: float) -> float | None:
    """THE COVER the trench is cut under: the upper quartile of the ground
    25–60 m beyond its edges, both sides, along the run — §2's crest (RULINGS
    2026-10-28k 226 a, R1's surrounding ground) read along a trench instead
    of round a portal.  Never the ground at the edge itself: where the survey
    already shows the road sunk, its lip is the cut's slope."""
    zs: list[float] = []
    n = max(2, int(run.length // _COVER_STEP_M) + 1)
    for k in range(n):
        s = run.length * k / (n - 1)
        p = run.interpolate(s)
        ux, uy = _heading(run, s)
        h = half_at(s0 + s)
        for side in (-1.0, 1.0):
            for off in _COVER_OFFSETS_M:
                z = dem_z_at(airport, (p.x - side * uy * (h + off), p.y + side * ux * (h + off)))
                if not math.isnan(z):
                    zs.append(z)
    if not zs:
        return None
    zs.sort()
    return zs[int(0.75 * (len(zs) - 1))]


def _floor(airport, law: Law, run: LineString, rows, ss, s0, s1, half_at
           ) -> tuple[float | None, str]:
    """The ONE floor (module doc) and how it was read."""
    tn = law.tables.structures.tunnel
    cover = _cover(airport, run, half_at, s0)
    if cover is None:
        return None, f"no ground beside the {run.length:.0f} m run"
    floor = cover - tn.mouth_depth_m
    how = f"cover {cover:.2f} − {tn.mouth_depth_m}"
    if inset_class.lidar_credible(airport, law):
        zs = [dem_z_at(airport, xy) for s, r in zip(ss, rows, strict=True) if s0 <= s <= s1
              for xy in r["open"]]
        zs = [z for z in zs if not math.isnan(z)]
        if zs and statistics.median(zs) < floor:
            floor = statistics.median(zs)
            how = (f"the surveyed open road {floor:.2f} (median of {len(zs)} stations; under "
                   f"cover {cover:.2f} − {tn.mouth_depth_m}: a surveyed cut is kept, 230 a)")
    return floor, how


def dual_trench_groups(airport, law: Law, strip=None) -> DualTrenches:
    """The #1638 trenches (module doc); ``strip`` the runway strip keep-out
    (``structure_mouth.runway_strip``)."""
    tn = law.tables.structures.tunnel
    inside = aerodrome_boundary(airport)
    if inside is None:
        return DualTrenches()
    rim = tn.wall_gap_m + tn.wall_band_width_m
    groups: list[Group] = []
    feet: list = []
    notes: list[str] = []
    refused: list[str] = []
    seen: list = []                      # every run read, built or refused
    for mid, ss, rows, s0, s1, ids in _candidates(airport, law, inside):
        run = substring(mid, s0, s1)
        if any(run.intersection(f).length >= 0.5 * run.length for f in seen):
            continue                          # the same pair walked from another route
        seen.append(run.buffer(tn.dual_trench_max_separation_m))
        rid = f"{ID_PREFIX}:{len(notes) + len(refused)}"
        half_at = _half_at(ss, [r["half"] for r in rows])
        h_max = max(half_at(s) for s in ss if s0 <= s <= s1)
        foot = run.buffer(h_max + rim, cap_style="flat")
        if strip is not None and foot.intersection(strip).area > 1e-6:
            refused.append(f"{rid} ({ids}): the dual roadway's {s1 - s0:.0f} m run stands in the "
                           f"runway strip keep-out — no trench under a runway (#1138 / R3)")
            continue
        floor, how = _floor(airport, law, run, rows, ss, s0, s1, half_at)
        if floor is None:
            refused.append(f"{rid} ({ids}): {how}")
            continue
        ground = [dem_z_at(airport, (p.x, p.y)) for p in
                  (run.interpolate(f * run.length) for f in (0.0, 0.25, 0.5, 0.75, 1.0))]
        ground = [z for z in ground if not math.isnan(z)]
        if not ground or max(ground) - floor <= law.tables.structures.placement.split_tol_m:
            refused.append(f"{rid} ({ids}): the ground already stands at the floor {floor:.2f}")
            continue
        m = 0.5 * (s0 + s1)
        up = level_side(mid, m, s1, floor, h_max, airport, law)
        dn = level_side(mid, m, s0, floor, h_max, airport, law)
        if up is None or dn is None:
            refused.append(f"{rid} ({ids}): the {100.0 * tn.ramp_grade:.0f} % climb from "
                           f"{floor:.2f} fits neither beyond the run's "
                           f"{'far' if up is None else 'near'} end nor inside it")
            continue
        widths = [2.0 * half_at(s) for s in ss if s0 <= s <= s1]
        note = (f"#1638 dual roadway {ids}: ONE trench {s1 - s0:.0f} m inside the aerodrome "
                f"boundary, spanning both carriageways {min(widths):.0f}-{max(widths):.0f} m "
                f"wide, floor {floor:.2f} ({how}), ramps {up[0].length - up[1]:.0f} m / "
                f"{dn[0].length - dn[1]:.0f} m")
        g_mid = statistics.median(ground)
        a, b = f"{rid}/a", f"{rid}/b"
        res = f"{ID_PREFIX} (OSM, #1638)"
        groups.append(level_half(up[0], up[1], up[2], floor, a, b, h_max, law, g_mid, (note,),
                                 half_at=lambda s, _m=m, _f=half_at: _f(_m + s), resource=res))
        groups.append(level_half(dn[0], dn[1], dn[2], floor, b, a, h_max, law, g_mid, (note,),
                                 half_at=lambda s, _m=m, _f=half_at: _f(_m - s), resource=res))
        feet.append(unary_union([groups[-2].corridor.footprint, groups[-1].corridor.footprint]))
        notes.append(note)
    return DualTrenches(tuple(groups), unary_union(feet) if feet else None, tuple(notes),
                        tuple(refused))


def absorb_mouths(mouths, footprint) -> tuple[list, list[str]]:
    """``(kept, notes)``: a bore MOUTH standing inside a dual trench is the
    trench's — the trench carries its road at its one floor, so no ramp and
    no second depth is built there (the bore's other mouth keeps its own)."""
    if footprint is None:
        return list(mouths), []
    kept, notes = [], []
    for m in mouths:
        if footprint.contains(Point(m.xy)):
            notes.append(f"mouth of {'+'.join(str(i) for i in m.ways)}: inside the dual "
                         f"roadway's trench, which carries it (#1638)")
        else:
            kept.append(m)
    return kept, notes


def yield_groups(groups, footprint) -> tuple[list, list[str]]:
    """``(kept, refusals)``: a level group (R6) whose axis runs mostly inside
    a dual trench is the trench's."""
    if footprint is None:
        return list(groups), []
    kept, out = [], []
    for g in groups:
        ax = LineString(g.axis)
        if ax.length > 0 and ax.intersection(footprint).length >= 0.5 * ax.length:
            out.append(f"{g.tid}: inside the dual roadway's trench, which carries it (#1638)")
        else:
            kept.append(g)
    return kept, out
