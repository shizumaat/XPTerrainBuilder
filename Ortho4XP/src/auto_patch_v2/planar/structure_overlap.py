"""TWO STRUCTURES MAY NOT OVERLAP — the pair test of the structure build
(``planar/structures.build_structures``): parallel mouths beyond 31h's
test (a diverging separation profile, a crossing approach) would be
polygonised into crumbs, so the narrower one is refused loudly — after
the ramps that can yield have been asked to (``unframed_ramp.
overlap_yield``: a run end, 2026-10-08d (1); the cap, owner RULINGS
2026-10-14j).

TWO WALL CORRIDORS are never such a pair (owner RULINGS 2026-10-28h (3)):
side-by-side bays that share a wall are all built — each ramp stands
inside its own walls' inner faces, so two of them meet only in the wall
they share, never in a floor.

TWO CUTS ON ONE ROAD ARE ONE RUN-THROUGH (owner RULINGS 2026-11-03b Q340 a
"running all the way through under bridges and out along its roads";
Q367/Q369 2026-11-03, #1717).  Where the corridors of two cuts facing each
other along ONE road overlap — each one's climb runs into the other's cut,
so the road cannot come up to grade between them — neither is refused: the
road stays down at the lower level between them.  This module is the ONE
place that pairs them (:func:`_run_pair`), for every kind of cut: OSM bores
under pack portals (LFPG's A1 under the H17 / H18 / H19 decks, OSM mapping
a separate tunnel under each), hard-deck bridges over one road (the open
stretch of RULINGS 2026-10-29 Q271 b, which ``deck_bridge`` used to pair
on its own) and R6 viaduct runs (KPHX's Terminal 4 road).  Each half of the
pair keeps its floor out to the RUN LINE halfway between the two cuts'
covered ends and never climbs; ``structures`` closes each at its own side
of the line, ``wall_gap_m`` short of it, so two floors at different levels
meet in a vertical step (Q341 a / Q342 a: level B keeps its depth under the
airside beside it and steps with it).  The stretch is open only where no
airside pavement lies over the road between them (§34 (12) (3); measured
kiahdeck: two taxiway bridges 49 m apart with taxiway pavement between).

Nothing here names a pack, a resource or an airport.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

from shapely.geometry import LineString, Point, Polygon

from ..law import Law
from .unframed_ramp import overlap_yield
from .wall_corridor_ramps import KIND as WALL_KIND

__all__ = ["resolve_overlaps", "deck_partner", "run_floor", "run_stop_s", "run_side", "run_group"]

XY = tuple[float, float]
#: two cuts face each other along one road when each one's axis heads at
#: the other's mouth within the tunnel's approach turn cap
_FACING_COS = math.cos(math.radians(30.0))


@_dc.dataclass(frozen=True)
class _Run:
    """One half's place in a run-through: the RUN LINE ``(normal, offset)``
    it stops at, the point on its own side (its mouth) and the partner."""
    partner: str
    normal: XY
    offset: float
    own: XY
    #: the partner's hard-deck bridge (``deck_bridge.DeckBridge``), filled by
    #: ``structures`` from the pass that paired them: two decks over one road
    #: hang their floor between their seats (Q271 b, ``deck_bridge.deck_seats``)
    partner_deck: _t.Any = _dc.field(default=None, compare=False)
    #: the partner's floor on the pass that paired them: the run takes ONE
    #: floor, the lowest of its halves' (owner 2026-11-03, KPHX picture)
    partner_floor: "float | None" = _dc.field(default=None, compare=False)


def _unit(a: XY, b: XY) -> XY | None:
    d = math.hypot(b[0] - a[0], b[1] - a[1])
    return None if d <= 1e-9 else ((b[0] - a[0]) / d, (b[1] - a[1]) / d)


def _floor(t) -> "float | None":
    """A cut's floor at its mouth: its profile's first station, else its datum."""
    prof = tuple(getattr(t, "profile", ()) or ())
    z = prof[0][1] if prof else getattr(t, "mouth_z", None)
    return None if z is None else float(z)


def run_floor(own: float, run: "_Run") -> float:
    """The ONE floor of a run-through: the lowest of its halves' floors (the
    deepest the ladder gives; owner 2026-11-03)."""
    return own if run.partner_floor is None else min(own, run.partner_floor)


def _covered_end(t) -> XY:
    """Where ``t``'s floor ends under its cover: its climb's start."""
    ln = LineString(t.axis)
    p = ln.interpolate(min(max(float(getattr(t, "climb_from_s", 0.0)), 0.0), ln.length))
    return (p.x, p.y)


def _run_pair(ti, tj, paved=None) -> "tuple[_Run, _Run] | None":
    """The two halves' :class:`_Run` records where ``ti`` and ``tj`` are two
    cuts on ONE road facing each other (module doc), else ``None``: each
    one's axis heads at the other's mouth, the other's mouth stands inside
    its corridor's width, and no airside pavement (``paved``) lies over the
    road between their covered ends."""
    if len(ti.axis) < 2 or len(tj.axis) < 2:
        return None
    mi, mj = tuple(ti.axis[0]), tuple(tj.axis[0])
    u = _unit(mi, mj)
    di, dj = _unit(mi, tuple(ti.axis[-1])), _unit(mj, tuple(tj.axis[-1]))
    if u is None or di is None or dj is None:
        return None
    if di[0] * u[0] + di[1] * u[1] < _FACING_COS or -(dj[0] * u[0] + dj[1] * u[1]) < _FACING_COS:
        return None
    half = max(float(ti.half_width_m), float(tj.half_width_m))
    ext_i = LineString([mi, (mi[0] + di[0] * 1e4, mi[1] + di[1] * 1e4)])
    ext_j = LineString([mj, (mj[0] + dj[0] * 1e4, mj[1] + dj[1] * 1e4)])
    if ext_i.distance(Point(mj)) > half or ext_j.distance(Point(mi)) > half:
        return None
    ci, cj = _covered_end(ti), _covered_end(tj)
    if (cj[0] - ci[0]) * u[0] + (cj[1] - ci[1]) * u[1] <= 0.0:
        ci, cj = mi, mj              # the covers meet: the line halfway between the mouths
    between = LineString([ci, cj])
    if _paved_over(between, 0.0, between.length, paved):
        return None
    mid = (0.5 * (ci[0] + cj[0]), 0.5 * (ci[1] + cj[1]))
    off = mid[0] * u[0] + mid[1] * u[1]
    return (_Run(tj.id, u, off, mi, partner_floor=_floor(tj)),
            _Run(ti.id, u, off, mj, partner_floor=_floor(ti)))


def deck_partner(db, axis: LineString, decks: _t.Sequence, paved=None):
    """The hard-deck bridge ``db``'s corridor RUNS THROUGH to (module doc):
    the next deck ``axis`` (from ``db``'s midline outward) runs into beyond
    ``db``'s own ring, the open stretch between them clear of airside
    pavement (``paved``), else ``None``.  Two decks state where both cuts
    stand before either is built, so their pair is read off the rings —
    the same run, the same pavement test as :func:`_run_pair`'s (owner
    RULINGS 2026-10-29 Q271 b; kiahdeck: two taxiway bridges 49 m apart with
    taxiway pavement between them are each their own cut)."""
    s_own = max((axis.project(Point(q)) for q in db.ring), default=0.0)
    best = None
    for o in decks:
        if o is db or o.ring == db.ring:
            continue
        x = axis.intersection(o.polygon)
        if x.is_empty:
            continue
        s0 = min(axis.project(Point(q)) for g in getattr(x, "geoms", [x]) for q in g.coords)
        if s0 >= s_own - 1e-6 and (best is None or s0 < best[0]):
            best = (s0, o)
    if best is None or _paved_over(axis, s_own, best[0], paved):
        return None
    return best[1]


def _paved_over(line: LineString, s0: float, s1: float, paved) -> bool:
    """Whether airside pavement lies over ``line`` strictly between ``s0``
    and ``s1`` (a metre clear of each end): the road does not run open under
    pavement (§34 (12) (3))."""
    if paved is None or paved.is_empty or s1 - s0 <= 2.0:
        return False
    from shapely.ops import substring
    return paved.intersects(substring(line, s0 + 1.0, s1 - 1.0))


def run_stop_s(axis: LineString, run: _Run, gap: float) -> float | None:
    """Where ``axis`` (from the mouth outward) reaches ``gap`` short of the
    run line on its own side, or ``None`` where it never does."""
    (nx, ny), off = run.normal, run.offset
    sg = 1.0 if run.own[0] * nx + run.own[1] * ny <= off else -1.0
    stop = off - sg * gap
    pts = list(axis.coords)
    s = 0.0
    for a, b in zip(pts[:-1], pts[1:], strict=False):
        fa, fb = a[0] * nx + a[1] * ny - stop, b[0] * nx + b[1] * ny - stop
        seg = math.hypot(b[0] - a[0], b[1] - a[1])
        if fa * fb <= 0.0 and abs(fa - fb) > 1e-12:
            return s + seg * fa / (fa - fb)
        s += seg
    return None


def run_side(run: _Run, gap: float, big: float) -> Polygon:
    """The side of the run line holding the half's own mouth, ``gap``
    short of the line, as a ``big`` box (the half is clipped to it)."""
    (nx, ny), off = run.normal, run.offset
    sg = 1.0 if run.own[0] * nx + run.own[1] * ny <= off else -1.0
    stop = off - sg * gap
    px, py, tx, ty = nx * stop, ny * stop, -ny, nx
    c0, c1 = (px + tx * big, py + ty * big), (px - tx * big, py - ty * big)
    return Polygon([c0, c1, (c1[0] - sg * nx * big, c1[1] - sg * ny * big),
                    (c0[0] - sg * nx * big, c0[1] - sg * ny * big)])


def run_group(g, run: _Run, gap: float):
    """``g`` — a corridor group whose floor is a stated PROFILE (an R6
    viaduct run, a sunken road) — kept at its floor out to ``gap`` short of
    its run line and open there: its axis, trench, walls and footprint end
    at its own side of the line, and its profile is level at its mouth's
    floor; ``g`` itself where its axis never reaches the line."""
    c = g.corridor
    profile = tuple(getattr(g, "profile", ()) or ())
    if c is None or not profile or len(g.axis) < 2:
        return g
    from shapely.ops import substring
    ln = LineString(g.axis)
    stop = run_stop_s(ln, run, gap)
    if stop is None or stop <= 0.0:
        return g
    side = run_side(run, gap, 10.0 * (ln.length + 1000.0))
    axis = [(float(x), float(y)) for x, y in substring(ln, 0.0, stop).coords]

    def cut(p):
        q = p.intersection(side)
        parts = [x for x in getattr(q, "geoms", [q]) if x.geom_type == "Polygon" and x.area > 0]
        return max(parts, key=lambda x: x.area) if parts else p
    floor = run_floor(float(profile[0][1]), run)
    c2 = _dc.replace(c, axis=tuple(axis), length_m=stop, walls=cut(c.walls),
                     trench=cut(c.trench), footprint=cut(c.footprint), far_closed=False,
                     floor_z=floor, depth_m=c.mouth_dem_z - floor)
    return _dc.replace(g, axis=axis, corridor=c2, hull_s=stop,
                       profile=((0.0, floor), (stop, floor)))


def resolve_overlaps(tunnels, footprints, keep: list[bool], siblings: _t.Mapping[str, str],
                     run_limits, at_cap: _t.Mapping[str, str],
                     overlap_refused: dict[str, str], law: Law, gap: float, grid: float,
                     may_replan: bool, refused: list[str],
                     runs: "dict[str, _Run] | None" = None, paved=None
                     ) -> tuple[dict, dict, dict]:
    """Every overlapping pair of ``tunnels`` (``keep`` / ``refused`` /
    ``overlap_refused`` / ``runs`` updated in place): ``(new run limits,
    ramps to steepen to the cap, survivors released from the cap)`` for the
    re-plan.  A pair on one road becomes a run-through (:func:`_run_pair`,
    entered in ``runs``; ``paved`` is a callable giving the airside
    pavement union, read once when first needed).  A survivor that
    steepened in vain for a bore refused all the same is released, and that
    refusal carried into the re-plan."""
    new_limits: dict[str, tuple[float, str]] = {}
    new_cap: dict[str, str] = {}
    released: dict[str, str] = {}
    paved_union: list = []
    for i in range(len(tunnels)):
        for j in range(i + 1, len(tunnels)):
            if not (keep[i] and keep[j]):
                continue
            if siblings.get(tunnels[i].id) == tunnels[j].id:
                continue            # two halves of one corridor meet at their mouth line
            if not footprints[i].intersects(footprints[j]):
                continue
            wall_i, wall_j = tunnels[i].source == WALL_KIND, tunnels[j].source == WALL_KIND
            if wall_i and wall_j:
                continue            # 2026-10-28h (3): bays sharing a wall are all built
            inter = footprints[i].intersection(footprints[j])
            # a WALL CORRIDOR may not even TOUCH another structure (Law C):
            # a shared ring vertex carries the other's pin into its rows
            # (measured OTHH: a Parking_004 corridor's vertex on the door
            # ramp Parking-Right_000@1's ring — its 8 % rows over 1.6 m
            # yielded 13 mm); the OTHER structure is senior
            touches = (wall_i or wall_j) and (inter.area > 1e-9 or inter.length > grid)
            if not (inter.area > 1.0 or touches):
                continue
            if runs is not None and may_replan and not (wall_i or wall_j):
                if not paved_union and paved is not None:
                    paved_union.append(paved())
                pair = _run_pair(tunnels[i], tunnels[j], paved_union[0] if paved_union else None)
                if pair is not None and not _ran(runs, tunnels[i].id, tunnels[j].id):
                    # 2026-11-03b Q340 a: one road, one run-through
                    for t, r in zip((tunnels[i], tunnels[j]), pair, strict=True):
                        old = runs.get(t.id)
                        if old is None or _nearer(t, r, old):
                            runs[t.id] = r
                    continue
            yields, steepen = overlap_yield((tunnels[i], tunnels[j]),
                                            (footprints[i], footprints[j]),
                                            run_limits, at_cap, law, gap, may_replan)
            new_limits.update(yields)
            new_cap.update(steepen)
            if wall_i != wall_j:
                drop = i if wall_i else j
            else:
                drop = i if footprints[i].area < footprints[j].area else j
            other = j if drop == i else i
            keep[drop] = False
            line = (f"{tunnels[drop].id}: its corridor overlaps {tunnels[other].id} (not "
                    f"a dual under 31h's separation test)")
            refused.append(line)
            if not (yields or steepen) and at_cap.get(tunnels[other].id) == tunnels[drop].id:
                # 2026-10-14j: steepened in vain for a bore refused anyway
                released[tunnels[other].id] = line
                overlap_refused[tunnels[drop].id] = line
    return new_limits, new_cap, released


def _ran(runs: _t.Mapping[str, _Run], a: str, b: str) -> bool:
    """Whether ``a`` and ``b`` already run through to each other (a re-plan
    pass that still overlaps them must not loop)."""
    ra, rb = runs.get(a), runs.get(b)
    return ra is not None and rb is not None and ra.partner == b and rb.partner == a


def _nearer(t, new: _Run, old: _Run) -> bool:
    """Whether ``new``'s run line stands nearer ``t``'s mouth than ``old``'s."""
    m = t.axis[0]
    return abs(m[0] * new.normal[0] + m[1] * new.normal[1] - new.offset) < \
        abs(m[0] * old.normal[0] + m[1] * old.normal[1] - old.offset)
