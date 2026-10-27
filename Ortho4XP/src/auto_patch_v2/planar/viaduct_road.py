"""R6 — A ROAD UNDER STACKED VIADUCTS INSIDE THE AIRPORT SITS A MOUTH DEPTH
BELOW THE APRON (owner RULINGS 2026-10-28k, Q228 a; spec
``docs/specs/lfpg-cuts-tunnels-rules-spec.md`` R6).

THE WITNESS is OSM alone: a mapped road (``layer <= 0``, neither a bridge
nor a tunnel) running at least ``[tunnel] viaduct_min_run_m`` under bridge
ways (``highway`` / ``railway`` with ``bridge``) of ``layer >=
[tunnel] viaduct_min_layer``, inside the aerodrome boundary (apt.dat row
130).  The run is read along the road's ROUTE, never per way: a forecourt
road is mapped in many short ways meeting at junctions, and the route walks
through them keeping its heading (the tunnel's approach law, spec §34 (2): the least turn at
every node, none over ``approach_turn_max_deg``).  Two parallel carriageways within
``dual_carriageway_max_separation_m`` are ONE trench spanning both
(2026-08-31h, as a dual bore is one ramp).  A survey cannot see this level — the DTM reads the
viaduct decks — so the survey is not a witness for or against it.

THE LEVEL: the road along the covered run is lowered to ``apron −
[tunnel] mouth_depth_m``, ``apron`` the median DEM at the nearest edge of
every airside apron cell within ``[tunnel] viaduct_apron_reach_m`` of the
run; beyond each end of the run it climbs back along its own mapped chain at
the tunnel's design grade (R4: ``ramp_grade``, never above
``ramp_max_grade``) to meet the ground.

THE MODEL is Law B's (RULINGS 2026-09-08b/c, ``door_ramps.sunken_groups``):
an OPEN trench whose floor is the stated profile per station, pinned by the
generator, its rim at the ground, the mesh making the walls — the only form
a heightfield can emit for "an open road level under the viaduct objects"
(spec §7).  The run is two HALVES meeting capless at its midpoint (the
sibling pair of Law C's level corridors): each half is flat at the floor to
its end of the run and climbs from there.  A run whose climb cannot top out
on its mapped chain within ``max_ramp_length_m`` is refused by name."""
from __future__ import annotations

import math
import statistics
import typing as _t

from shapely.geometry import LineString, Point
from shapely.ops import substring, unary_union

from ..airport.dem import dem_z_at
from ..law import Law
from ..law.tables import apron_roles, role_side
from ..model.frame import XY
from .door_ramps import RampCorridor
from .object_corridor import Group
from .structure_approach import carriageway_width_m, is_bridge, is_tunnel, unit

__all__ = ["viaduct_road_groups", "ID_PREFIX"]

ID_PREFIX = "viaduct-road"
#: the station step the covered run is read at (the §45 lateral step)
_STEP_M = 5.0
#: Law B's group kind: the profile is pinned per station by the generator
_KIND = "sunken_road"


def _layer(tags: _t.Mapping[str, str]) -> int:
    try:
        return int(float(str(tags.get("layer", "0")).strip()))
    except ValueError:
        return 0


def _boundary(airport):
    from ..classify.evidence import polygon_from
    bs = [polygon_from(b.outer, b.holes) for b in getattr(airport, "boundaries", ()) or ()]
    bs = [b for b in bs if b is not None and not b.is_empty]
    return unary_union(bs) if bs else None


def covered_runs(line: LineString, cover, inside, min_run: float) -> list[tuple[float, float]]:
    """The ``(s0, s1)`` runs along ``line`` whose stations stand under
    ``cover`` and inside ``inside``, a one-station gap bridged, at least
    ``min_run`` long."""
    n = max(2, int(line.length // _STEP_M) + 1)
    ss = [line.length * k / (n - 1) for k in range(n)]
    runs: list[tuple[float, float]] = []
    start = last = None
    for s in ss:
        p = line.interpolate(s)
        q = Point(p.x, p.y)
        if cover.contains(q) and inside.contains(q):
            if start is not None and s - last > 2.0 * _STEP_M + 1e-9:
                runs.append((start, last))
                start = None
            start = s if start is None else start
            last = s
    if start is not None:
        runs.append((start, last))
    return [(a, b) for a, b in runs if b - a >= min_run - 1e-9]


def _apron_level(airport, law: Law, run: LineString, cells, polys, reach: float
                 ) -> float | None:
    """The apron's level beside the run: the median DEM at the nearest edge
    point of every airside apron cell within ``reach``."""
    roles = apron_roles(law)
    zone = run.buffer(reach)
    zs: list[float] = []
    for c, p in zip(cells, polys):
        if c.role not in roles or role_side(law, c.role) != "airside" or not p.intersects(zone):
            continue
        ring = p.exterior
        q = ring.interpolate(ring.project(run.interpolate(run.project(p.centroid))))
        z = dem_z_at(airport, (q.x, q.y))
        if not math.isnan(z):
            zs.append(z)
    return statistics.median(zs) if zs else None


def _graph(roads) -> dict[tuple[int, int], set[XY]]:
    """Every mapped node of ``roads`` → its neighbouring nodes (a junction
    at a way's INTERIOR node joins it: the forecourt's ways meet there)."""
    nb: dict[tuple[int, int], set[XY]] = {}
    for w in roads:
        pts = [(float(x), float(y)) for x, y in w.points]
        for p, q in zip(pts[:-1], pts[1:]):
            if p != q:
                nb.setdefault(_key(p), set()).add(q)
                nb.setdefault(_key(q), set()).add(p)
    return nb


def _key(p: XY) -> tuple[int, int]:
    return (round(p[0] * 20.0), round(p[1] * 20.0))      # 5 cm: one OSM node


def _walk(start: XY, heading: XY, nb, reach: float, cos_max: float) -> list[XY]:
    """The mapped route from node ``start`` along ``heading``: at every node
    the continuation with the least turn, none over the tunnel's
    ``approach_turn_max_deg`` (the approach walk's heading law, spec §34
    (2)); it ends where no mapped road continues — never a straight
    extension (#1028 Q32)."""
    path, cur, h, length = [start], start, heading, 0.0
    seen = {_key(start)}
    while length < reach:
        best, best_c = None, cos_max
        for q in nb.get(_key(cur), ()):
            if _key(q) in seen:
                continue
            u = unit(cur, q)
            c = u[0] * h[0] + u[1] * h[1]
            if c >= best_c:
                best, best_c = q, c
        if best is None:
            break
        length += math.dist(cur, best)
        h, cur = unit(cur, best), best
        seen.add(_key(cur))
        path.append(cur)
    return path


def _route(w, nb, law: Law) -> LineString:
    """The route through way ``w``: walked both ways from its end nodes."""
    tn = law.tables.structures.tunnel
    reach = 4.0 * tn.max_ramp_length_m
    cos_max = math.cos(math.radians(tn.approach_turn_max_deg))
    pts = [(float(x), float(y)) for x, y in w.points]
    fwd = _walk(pts[-1], unit(pts[-2], pts[-1]), nb, reach, cos_max)
    back = _walk(pts[0], unit(pts[1], pts[0]), nb, reach, cos_max)
    line = list(reversed(back[1:])) + pts + fwd[1:]
    out = [line[0]]
    for p in line[1:]:
        if p != out[-1]:
            out.append(p)
    return LineString(out)


def _outward(route: LineString, s_end: float, forward: bool) -> LineString | None:
    """The route beyond station ``s_end``, walked away from the run."""
    if forward:
        if s_end >= route.length - 1e-6:
            return None
        return substring(route, s_end, route.length)
    if s_end <= 1e-6:
        return None
    return LineString(list(substring(route, 0.0, s_end).coords)[::-1])


def _climb(airport, law: Law, out: LineString | None, floor: float
           ) -> tuple[float | None, float]:
    """Where the climb from ``floor`` at the start of ``out`` meets the DEM
    at the design grade: ``(s_top, top_z)``, or ``(None, nan)`` within
    ``max_ramp_length_m`` / the mapped road's end."""
    if out is None:
        return None, math.nan
    tn = law.tables.structures.tunnel
    grade = min(tn.ramp_grade, tn.ramp_max_grade)
    s = 0.0
    lim = min(out.length, tn.max_ramp_length_m)
    while s + _STEP_M <= lim + 1e-9:
        s += _STEP_M
        p = out.interpolate(s)
        d = dem_z_at(airport, (p.x, p.y))
        if math.isnan(d):
            return None, math.nan
        z = floor + grade * s
        if z >= d:
            return s, z
    return None, math.nan


#: the most a trench's axis may turn within one trench width: a tighter
#: curl folds its ring onto itself (the corridor geometry refuses it)
_MAX_TURN_DEG = 45.0


def _straight_m(line: LineString, width: float) -> float:
    """How far along ``line`` its heading turns less than
    :data:`_MAX_TURN_DEG` within every ``width`` of run."""
    pts = list(line.coords)
    heads, ss, s = [], [], 0.0
    for p, q in zip(pts[:-1], pts[1:]):
        d = math.dist(p, q)
        if d > 1e-9:
            heads.append(math.atan2(q[1] - p[1], q[0] - p[0]))
            ss.append(s)
        s += d
    for i in range(len(heads)):
        for j in range(i + 1, len(heads)):
            if ss[j] - ss[i] > width:
                break
            t = abs((math.degrees(heads[j] - heads[i]) + 180.0) % 360.0 - 180.0)
            if t > _MAX_TURN_DEG:
                return ss[j]
    return line.length


def _side(route: LineString, mid: float, end: float, floor: float, half_w: float,
          airport, law: Law) -> tuple[LineString, float, float] | None:
    """One half's ``(axis from the midpoint, where the level ends, the top
    z)``: the climb beyond the run's ``end`` along the mapped route (R4's
    design grade); where no mapped road carries it (or the road curls
    tighter than the trench is wide), the climb INSIDE the run, ending on the
    ground there (the level shortens); ``None`` where neither fits within
    ``ramp_max_grade``."""
    tn = law.tables.structures.tunnel
    grade = min(tn.ramp_grade, tn.ramp_max_grade)
    fwd = end > mid
    run = substring(route, mid, end) if fwd else \
        LineString(list(substring(route, end, mid).coords)[::-1])
    out = _outward(route, end, fwd)
    top, top_z = _climb(airport, law, out, floor)
    if top is not None:
        axis = LineString(list(run.coords) + list(substring(out, 0.0, top).coords)[1:])
        if _straight_m(axis, 2.0 * half_w) >= axis.length - 1e-6:
            return axis, run.length, top_z
    # inside the run: the design grade, steeper only where that cannot top
    # out in the half-run (2026-10-08c (1)), never above the cap
    ok = min(run.length, _straight_m(run, 2.0 * half_w))
    if ok < run.length - 1e-6:
        run = substring(run, 0.0, ok)
    p = run.coords[-1]
    ground = dem_z_at(airport, (p[0], p[1]))
    avail = run.length - _STEP_M
    if math.isnan(ground) or avail <= 0.0:
        return None
    rise = max(0.0, ground - floor)
    g = max(grade, rise / avail)
    if g > tn.ramp_max_grade + 1e-9:
        return None
    return run, run.length - rise / g, ground


def _half(axis_ln: LineString, flat_m: float, top_z: float, floor: float, rid: str,
          sib: str, half_w: float, law: Law, ground: float, notes: tuple) -> Group:
    """One half: s = 0 at the run's midpoint, level at ``floor`` to
    ``flat_m``, climbing to ``top_z`` at the axis end."""
    tn = law.tables.structures.tunnel
    rim = tn.wall_gap_m + tn.wall_band_width_m
    axis = [(float(x), float(y)) for x, y in axis_ln.coords]
    length = axis_ln.length
    profile = ((0.0, floor), (flat_m, floor), (length, top_z))
    u0 = unit(axis[0], axis[1])
    trench = axis_ln.buffer(half_w, cap_style="flat")
    foot = axis_ln.buffer(half_w + rim, cap_style="flat")
    mid_xy: XY = axis[0]
    c = RampCorridor(rid, f"{ID_PREFIX} (OSM, R6)", (), tuple(axis), length, 2.0 * half_w,
                     rim, rim, "cut", ground, floor, foot, trench, foot, mid_xy, ground, 0.0,
                     ground - floor, notes, mouth_closed=False)

    def half_fn(s: float, _h=half_w) -> tuple[float, float]:
        return (_h, _h)

    def rim_fn(s: float, _r=rim) -> tuple[float, float]:
        return (_r, _r)
    return Group([], mid_xy, (-u0[0], -u0[1]), 2.0 * half_w, axis, c, rid, length, True, False,
                 False, half_fn, rim_fn, None, None, min(tn.ramp_grade, tn.ramp_max_grade),
                 kind=_KIND, spacing_m=_STEP_M, profile=profile, mouth_strip=False, sibling=sib)


def viaduct_road_groups(airport, law: Law, cells, polys
                        ) -> tuple[list[Group], list[str], list[str]]:
    """``(groups, notes, refused)`` — the R6 build groups (module doc)."""
    tn = law.tables.structures.tunnel
    ways = list(getattr(airport, "osm_ways", ()) or ())
    vias = [w for w in ways if len(w.points) >= 2 and is_bridge(w)
            and _layer(w.tags or {}) >= tn.viaduct_min_layer]
    inside = _boundary(airport) if vias else None
    if not vias or inside is None:
        return [], [], []
    deck = unary_union([LineString(w.points).buffer(carriageway_width_m(w.tags, law) / 2.0)
                        for w in vias])
    roads, seen = [], set()
    for w in ways:          # one road per geometry: the feeds carry duplicates
        if len(w.points) < 2 or not (w.tags or {}).get("highway") or is_bridge(w) \
                or is_tunnel(w, tn.admitted_values) or _layer(w.tags or {}) > 0:
            continue
        key = tuple((round(x, 2), round(y, 2)) for x, y in w.points)
        if key in seen or key[::-1] in seen:
            continue
        seen.add(key)
        roads.append(w)
    runs = _runs(roads, deck, inside, law)
    groups: list[Group] = []
    notes: list[str] = []
    refused: list[str] = []
    for k, (route, s0, s1, half_w, ids) in enumerate(runs):
        rid = f"{ID_PREFIX}:{k}"
        run = substring(route, s0, s1)
        apron = _apron_level(airport, law, run, cells, polys, tn.viaduct_apron_reach_m)
        if apron is None:
            refused.append(f"{rid} ({ids}): no airside apron within "
                           f"{tn.viaduct_apron_reach_m:.0f} m of the {s1 - s0:.0f} m run")
            continue
        floor = apron - tn.mouth_depth_m
        ground = [dem_z_at(airport, (p.x, p.y)) for p in
                  (run.interpolate(f * run.length) for f in (0.0, 0.25, 0.5, 0.75, 1.0))]
        ground = [z for z in ground if not math.isnan(z)]
        if not ground or min(ground) - floor <= law.tables.structures.placement.split_tol_m:
            refused.append(f"{rid} ({ids}): the ground already stands at the floor "
                           f"{floor:.2f} (apron {apron:.2f} − {tn.mouth_depth_m})")
            continue
        mid = 0.5 * (s0 + s1)
        up = _side(route, mid, s1, floor, half_w, airport, law)
        dn = _side(route, mid, s0, floor, half_w, airport, law)
        if up is None or dn is None:
            refused.append(f"{rid} ({ids}): the {100.0 * tn.ramp_grade:.0f} % climb from "
                           f"{floor:.2f} fits neither on the mapped road beyond the run's "
                           f"{'far' if up is None else 'near'} end (within "
                           f"{tn.max_ramp_length_m:.0f} m) nor inside the run")
            continue
        g_mid = statistics.median(ground)
        note = (f"R6 (RULINGS 2026-10-28k Q228 a): road {ids} runs {s1 - s0:.0f} m under "
                f"layer>={tn.viaduct_min_layer} viaducts inside the aerodrome boundary — "
                f"floor {floor:.2f} = apron {apron:.2f} − {tn.mouth_depth_m}, trench "
                f"{2.0 * half_w:.1f} m wide, level {up[1] + dn[1]:.0f} m, ramps "
                f"{up[0].length - up[1]:.0f} m / {dn[0].length - dn[1]:.0f} m (R4: the design "
                f"grade {100.0 * tn.ramp_grade:.1f} %, steeper up to the cap only inside the "
                f"run)",)
        a, b = f"{rid}/a", f"{rid}/b"
        groups.append(_half(up[0], up[1], up[2], floor, a, b, half_w, law, g_mid, note))
        groups.append(_half(dn[0], dn[1], dn[2], floor, b, a, half_w, law, g_mid, note))
        notes.append(note[0])
    return groups, notes, refused


def _runs(roads, deck, inside, law: Law) -> list[tuple]:
    """``(route, s0, s1, half width, ids)`` per covered run: every road's
    route walked once, its runs under ``deck`` inside ``inside``; a run
    within ``dual_carriageway_max_separation_m`` of a longer one beside it
    widens that one (a dual is one trench) instead of standing alone."""
    tn = law.tables.structures.tunnel
    used: set[int] = set()
    found: list[tuple] = []
    nb = _graph(roads)
    for w in sorted(roads, key=lambda r: -LineString(r.points).length):
        if id(w) in used or not LineString(w.points).intersects(deck):
            continue
        route = _route(w, nb, law)
        on = [r for r in roads if LineString(r.points).within(route.buffer(0.05))]
        used.update(id(r) for r in on)
        half_w = max([carriageway_width_m(r.tags, law) for r in on]
                     or [carriageway_width_m(w.tags, law)]) / 2.0
        ids = "+".join(str(r.id) for r in on[:4]) + ("+…" if len(on) > 4 else "")
        for s0, s1 in covered_runs(route, deck.buffer(half_w), inside, tn.viaduct_min_run_m):
            found.append([route, s0, s1, half_w, ids, substring(route, s0, s1)])
    found.sort(key=lambda f: -(f[2] - f[1]))
    kept: list[list] = []
    sep = tn.dual_carriageway_max_separation_m
    for f in found:
        host = next((h for h in kept if f[5].within(h[5].buffer(sep))), None)
        if host is None:
            kept.append(f)
            continue
        lateral = max(host[5].distance(Point(p)) for p in f[5].coords)
        host[3] = max(host[3], lateral + f[3])
        host[4] += f" (dual {f[4]})"
    return [tuple(f[:5]) for f in kept]
