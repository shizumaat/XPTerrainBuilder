"""THE RAMP FOOT RUNS OUT AT ROAD GRADE (issue #669; owner RULINGS
2026-10-14c (5), amending 2026-10-03e in the direction of travel).

The owner, at a terminal's departures ramp: "If we grade terrain up to meet
an object ramp bottom, we should continue road grade until we get back to
raw dem so we don't have a sharp cliff even if there is no road evidence."
RULED: where the ground is graded to an object ramp's foot, it continues
beyond the foot along the ramp's direction of travel at road grade (design
5 %, cap 10 %) until it meets raw DEM, whether or not a mapped road
continues there; 10-03e's 1:3 bank stays for the ramp's sides.

MEASURED (KCLT, sw27): the departures ramp (``techos_1_charlotte.obj``)
comes down northward to its zero at 35.2223739, -80.9423249; the pack
pavement under it (``gap:0``) stood at 222.2 m to the patch edge 8 m on,
and the raw DEM beyond stood at 218.1 m — a 4 m cliff.

THE RUN-OUT, minted in the LAST STAGE beside the pad-road exits
(``classify/pad_road_exit``), where the level of the ground at the foot is
a solved constant: for each foot (``airport/ramp_feet``) the patch must
hold the ground under the ramp's last ``FOOT_SPAN_M`` (else nothing graded
the ground to it); a strip of the ramp's width leaves the lip along the
direction of travel over the ground no cell holds.  It starts where the
patch ends, at the level the map solved there (``z0``), and runs for the
foot's OFFSET at the design grade, ``|z0 - DEM| / ramp_grade`` (the ramp
closes the offset; the terrain's own slope beyond is the terrain's —
``pad_road_exit``'s round 5), or until a standing face stops it (then the
road's own cap steepens it).  The strip is a
ROAD (``service_road``, the road law's caps) and a PAD ROAD (a follower of
the last stage, junior to every pavement it meets); its profile rows are
``constraints/ramp_runout``'s.  A foot whose ground already stands within
``[cockpit] visual_m`` of the DEM where the patch ends asks nothing.

THE STRIP ENDS ON THE GROUND (#1093; owner direction RULINGS 2026-10-20aw,
a trial, for the bar 20ay "no visible edge"): every side and the end of the
strip that stands on open ground is finished by a 1:3 bank
``runout:<k>#collar`` (the collar class every bank reader knows) whose width
at each station is the DAYLIGHT distance — where a 1:3 slope off the strip's
edge meets the raw ground, never wider than ``[building_pad]
platform_collar_max_m`` (:func:`_daylight`).  Its vertices take design rows
off the strip's profile toward the DEM (``constraints/ramp_runout``), so its
toe lies on the ground (MEASURED, lane l1093b's fixed 15 m bank: the toe had
no row and stood -2.00 / +2.37 m off the DEM).

A 10-03e LANDING's foot (counted ``landing`` here) runs out in the PLANAR
stage instead (``planar/landing_runout``, issue #711): the lot it crosses is
cut back from the strip there and the strip is held against the landing's
block datum in stage 2, so the lot meets it rather than the strip meeting a
lot already solved.  (RULINGS 2026-10-14i's "road carries the run-out" was
tried here and withdrawn: the lot ``dsf:pol10`` welded to HECA's landing
level, +5.7 m, and the mapped road ``-3963`` ended 6 m over the raw DEM.)
"""
from __future__ import annotations

import dataclasses as _dc
import math as _math
import typing as _t

import numpy as np
import shapely
from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union

from ..airport.ramp_feet import FOOT_SPAN_M
from ..law import Law
from .rules import Rules

__all__ = ["mint_ramp_runouts", "runout_of", "RUNOUT_PREFIX", "MAX_RUN_M", "BANK_EVIDENCE"]

#: the run-out cell's ref: ``runout:<k>``
RUNOUT_PREFIX = "runout"

#: the run's bound (``pad_road_exit.MAX_REACH_M``'s order: a ramp the DEM
#: never meets inside it is not a ramp foot's)
MAX_RUN_M = 400.0

#: the stations of the strip's sides (``mint_ramp_runouts``): a vertex on
#: each side every this many metres along the run
STATION_M = 10.0

#: the evidence key of a run-out's bank cell (``runout:<k>#collar``)
BANK_EVIDENCE = "ramp_runout_bank"

#: the daylight search's step along the bank's outward direction (metres)
DAYLIGHT_STEP_M = 0.5

_KEYS = ("runout_x0", "runout_y0", "runout_dx", "runout_dy", "runout_z0",
         "runout_dem0")


def runout_of(cell) -> "tuple | None":
    """``(x0, y0, dx, dy, z0, dem0)`` of a run-out cell, else None."""
    ev = getattr(cell, "evidence", None) or {}
    if not ev.get("ramp_runout"):
        return None
    return tuple(float(ev[k]) for k in _KEYS)


def _stations(s0: float, s1: float, step: float) -> list[float]:
    """``s0``, every ``step`` after it and ``s1`` (``step`` 0: the ends)."""
    n = int(_math.ceil((s1 - s0) / step - 1.0e-9)) if step > 0.0 and s1 > s0 else 1
    return [s0 + (s1 - s0) * k / max(1, n) for k in range(max(1, n) + 1)]


def _level_at(seg: LineString, xy: np.ndarray, z: np.ndarray,
              reach: float) -> "float | None":
    """The median solved level of the base map's vertices within ``reach``
    of ``seg`` (the line where the strip leaves the patch)."""
    d = shapely.distance(seg, shapely.points(xy))
    near = d <= reach
    if not near.any():
        k = int(np.argmin(d))
        return float(z[k]) if d[k] <= 3.0 * reach else None
    return float(np.median(z[near]))


def _daylight(z_in: float, px: float, py: float, ux: float, uy: float, dem,
              k: float, dmax: float, band: float) -> float:
    """THE BANK'S TOE DISTANCE off the strip's edge point ``(px, py)`` along
    the outward unit ``(ux, uy)``: 0 where the edge already stands within
    ``band`` of its ground, else the first ``d`` where a slope of ``k``
    (1:3) off the edge's level ``z_in`` meets the raw ground —
    ``|z_in - DEM(p + u d)| <= k d`` — never more than ``dmax``."""
    if abs(z_in - float(dem.z(px, py))) <= band:
        return 0.0
    d = 0.0
    while d < dmax:
        d = min(dmax, d + DAYLIGHT_STEP_M)
        if abs(z_in - float(dem.z(px + ux * d, py + uy * d))) <= k * d:
            return d
    return dmax


def _bank_ring(x0: float, y0: float, dx: float, dy: float, w: float, run: float,
               z_at: _t.Callable[[float], float], dem, k: float, dmax: float,
               band: float) -> "Polygon | None":
    """The DAYLIGHT polygon of a strip (:func:`_daylight` at every side
    station, along the end, and diagonally at the two end corners): the
    region a 1:3 bank off the strip's sides and end covers before it meets
    the ground.  ``z_at(S)`` is the strip's profile ``S`` metres along."""
    nx, ny = -dy, dx
    h = 0.5 * w
    ss = _stations(0.0, run, STATION_M)

    def toe(S: float, t: float, ux: float, uy: float) -> tuple[float, float]:
        px, py = x0 + dx * S + nx * t, y0 + dy * S + ny * t
        d = _daylight(z_at(S), px, py, ux, uy, dem, k, dmax, band)
        return px + ux * d, py + uy * d
    r2 = 0.5 ** 0.5
    left = [toe(S, -h, -nx, -ny) for S in ss]
    right = [toe(S, h, nx, ny) for S in reversed(ss)]
    m = max(1, int(_math.ceil(w / STATION_M)))
    end = [toe(run, -h + w * i / m, dx, dy) for i in range(m + 1)]
    cl = toe(run, -h, r2 * (dx - nx), r2 * (dy - ny))
    cr = toe(run, h, r2 * (dx + nx), r2 * (dy + ny))
    q = Polygon([*left, cl, *end, cr, *right])
    q = q if q.is_valid else q.buffer(0)
    return None if q.is_empty else q


def _side_ring(held, box: Polygon, z_of: _t.Callable[[float, float], float], dem, k: float,
               dmax: float, band: float) -> "Polygon | None":
    """THE DAYLIGHT POLYGON OFF THE FOOT'S HELD GROUND (#1093 round 3;
    RULINGS 2026-10-14c (5): "the 1:3 bank of 10-03e stays for the ramp's
    sides"): along every exterior edge of ``held`` (the union of the faces
    the patch holds under the foot, and the pad roads beside them) inside
    ``box``, the region a 1:3 bank off that edge covers before it meets the
    ground (:func:`_daylight` every ``STATION_M`` and at each vertex, the
    edge's level ``z_of(x, y)``), with a fan at each convex corner — its
    holes' edges too (open ground the held faces ring).  What
    another face already holds is the caller's to subtract: an edge with a
    face across it is no open edge, and its bank is clipped away there."""
    from shapely.geometry.polygon import orient
    quads: list[Polygon] = []
    rings = [r for part in getattr(held, "geoms", [held])
             if not part.is_empty and part.geom_type == "Polygon"
             for o in [orient(part, 1.0)] for r in [o.exterior, *o.interiors]]
    for lr in rings:
        # a HOLE of the held ground is open ground ringed by it (a slot
        # between the pad and the pavement under the foot): it banks too;
        # oriented, the ground outside the faces is right of every ring
        ring = list(lr.coords)[:-1]
        n = len(ring)
        toes: list[tuple] = []
        for i in range(n):
            (ax, ay), (bx, by) = ring[i], ring[(i + 1) % n]
            L = _math.hypot(bx - ax, by - ay)
            if L <= 0.0 or not box.intersects(LineString([(ax, ay), (bx, by)])):
                toes.append(None)
                continue
            ux, uy = (by - ay) / L, -(bx - ax) / L       # outward: right of a CCW ring
            pts = []
            for S in _stations(0.0, L, STATION_M):
                px, py = ax + (bx - ax) * S / L, ay + (by - ay) * S / L
                d = _daylight(z_of(px, py), px, py, ux, uy, dem, k, dmax, band)
                pts.append(((px, py), (px + ux * d, py + uy * d)))
            for (p0, t0), (p1, t1) in zip(pts, pts[1:], strict=False):
                if t0 != p0 or t1 != p1:
                    quads.append(Polygon([p0, p1, t1, t0]))
            toes.append((pts[0][1], pts[-1][1]))
        for i in range(n):
            a, b = toes[i - 1], toes[i]
            if a is not None and b is not None and a[1] != b[0]:
                quads.append(Polygon([ring[i], a[1], b[0]]))
    q = unary_union([x if x.is_valid else x.buffer(0) for x in quads if x.area > 0.0])
    q = q.intersection(box)
    return None if q.is_empty else q


def _held_banks(pm_base, xy: np.ndarray, zz: np.ndarray, cells: list, back: Polygon,
                box: Polygon, occupied, air: _t.AbstractSet[str], dem, k: float,
                dmax: float, band: float, snap: float, touch: float,
                road_roles: _t.AbstractSet[str]) -> list[Polygon]:
    """The bank parts off a foot's HELD GROUND (:func:`_side_ring`): the
    base map's non-airside faces under the foot's last metres (``back``),
    and the pad-road cells touching them inside ``box``, never across a
    road's far end (:func:`_road_ends`); each edge's level
    is the nearest base-map vertex's (a pad road beside its pad stands at
    the pad's rim).  An airside face is never banked (airside is king); a
    part narrower than ``touch`` (the touch grid, wider than the last
    stage's stand-off) is minted only in a slot of the held ground."""
    from scipy.spatial import cKDTree

    from .evidence import polygon_parts
    faces = getattr(pm_base, "faces", None) or {}
    refs: set[str] = set()
    held = []
    for f in faces.values():
        if f.role in air:
            continue
        q = Polygon([pm_base.vertices[v].xy for v in pm_base.ring_vertices(f.ring)])
        q = q if q.is_valid else q.buffer(0)
        if not q.is_empty and q.intersection(back).area > touch * touch:
            refs.add(str(f.ref))
            held.append(q)
    if not held:
        return []
    # the held ground in the base map's faces (snapped to the identity
    # lattice: the slots the emitted patch leaves) AND in the cells' own
    # geometry (what ``occupied`` is made of)
    held.extend(q for c in cells if str(c.ref) in refs
                for q in [Polygon(c.ring, c.holes)] if q.is_valid and not q.is_empty)
    core = unary_union(held)
    roads, ends = [], []
    for c in cells:
        ev = getattr(c, "evidence", None) or {}
        if ev.get("ramp_runout") or ev.get(BANK_EVIDENCE):
            continue
        q = Polygon(c.ring, c.holes)
        if not q.is_valid or not q.intersects(box.buffer(dmax)):
            continue
        if ev.get("pad_road") and q.intersects(box) and q.distance(core) <= touch:
            held.append(q)
        if c.role in road_roles:
            roads.append(q)
    for q in roads:
        ends.extend(_road_ends(q, core, dmax, touch))
    tree = cKDTree(xy)

    def z_of(x: float, y: float) -> float:
        return float(zz[tree.query((x, y))[1]])
    ground = unary_union(held).buffer(0)
    ring = _side_ring(ground, box, z_of, dem, k, dmax, band)
    if ring is None:
        return []
    # a road's far END is where the core's ribbon carries the road on
    # (``emit/road_join``, §37 (9)): no bank across it (MEASURED, KCLT: a
    # bank past ``small_roads:-8201``'s end took the coverage join, 5.18 m
    # off the ribbon)
    ring = ring.difference(unary_union(ends)) if ends else ring
    # a part narrower than the touch grid fills a SLOT between the held
    # ground and the run-out's own cells, or is not minted: against any
    # other face it re-nodes that face instead (MEASURED, KCLT west foot: a
    # 1 m wedge between the pad road and a standing road gave the road two
    # pad-level vertices, 22 within-shape rows to 4.5 m)
    mine = unary_union([ground, *(Polygon(c.ring, c.holes) for c in cells
                                  if (getattr(c, "evidence", None) or {}).get("ramp_runout")
                                  or (getattr(c, "evidence", None) or {}).get(BANK_EVIDENCE))])
    others = occupied.difference(mine.buffer(snap))
    return [b for b in polygon_parts(shapely.set_precision(ring.difference(occupied), snap))
            if b.area >= touch * touch and (not b.buffer(-0.5 * touch).is_empty
                                            or b.distance(others) >= 0.5 * touch)]


def _road_ends(q: Polygon, core, reach: float, touch: float) -> list[Polygon]:
    """The CORRIDORS past a road cell's far ends: each short side of its
    minimum rotated rectangle that lies off the held ``core`` (farther than
    ``touch``), extruded outward along the road's long axis by ``reach``."""
    with np.errstate(divide="ignore", invalid="ignore"):     # an axis-aligned cell
        c = list(q.minimum_rotated_rectangle.exterior.coords)[:4]
    if len(c) < 4:
        return []
    sides = [(c[i], c[(i + 1) % 4]) for i in range(4)]
    L = [_math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in sides]
    from shapely.geometry import Point
    i = 0 if L[0] <= L[1] else 1
    out = []
    for a, b in (sides[i], sides[i + 2]):
        mid = Point((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        if mid.distance(core) <= touch:
            continue
        ox, oy = mid.x - q.centroid.x, mid.y - q.centroid.y
        n = _math.hypot(ox, oy) or 1.0
        ux, uy = ox / n * reach, oy / n * reach
        out.append(Polygon([a, b, (b[0] + ux, b[1] + uy), (a[0] + ux, a[1] + uy)]))
    return out


def _run_box(lip, direction, s1: float, h: float, m: float) -> Polygon:
    """The run-out's box: ``m`` behind the lip to ``m`` past the strip's end
    ``s1``, the strip's half width ``h`` and ``m`` to each side (the bank's
    widest reach)."""
    (lx, ly), (dx, dy) = lip, direction
    nx, ny = -dy, dx
    return Polygon([(lx + dx * s + nx * t, ly + dy * s + ny * t) for s, t in
                    ((-m, -h - m), (s1 + m, -h - m), (s1 + m, h + m), (-m, h + m))])


def _landing_faces(pm):
    """The 10-03e landings and their collars on the solved map: planar pad
    regions (``planar/landing``), never classification cells."""
    from ..model.platform import LANDING_SEP
    faces = getattr(pm, "faces", None) or {}
    return unary_union([
        q for f in faces.values() if LANDING_SEP in str(f.ref)
        for q in [Polygon([pm.vertices[v].xy for v in pm.ring_vertices(f.ring)])]
        if q.is_valid and not q.is_empty])


def mint_ramp_runouts(cl, airport, law: Law, rules: Rules, pm_base, z_base
                      ) -> tuple[_t.Any, dict]:
    """``cl`` with a run-out strip minted off every object ramp's graded
    foot (module docstring); ``(cl, report)``."""
    from ..airport.ramp_feet import ramp_feet
    from ..geom.ramp_profile import axis_ground, lead_section, strip_level
    from ..law.tables import role_side
    from ..model.planar import COLLAR_SUFFIX, is_lead_face
    from .evidence import polygon_parts
    from .roles import Cell
    rep: dict[str, _t.Any] = {"feet": 0, "ungraded": 0, "landing": 0, "at_grade": 0, "blocked": 0,
                              "runouts": 0, "run_m": 0.0, "banks": 0, "bank_m2": 0.0,
                              "side_banks": 0, "side_bank_m2": 0.0,
                              "list": []}
    dem = getattr(airport, "dem", None)
    frame = getattr(airport, "frame", None)
    if dem is None or frame is None or pm_base is None or z_base is None:
        return cl, rep
    feet = ramp_feet(airport, law, frame.entry())
    rep["feet"] = len(feet)
    if not feet:
        return cl, rep
    g = float(law.tables.emit.road_contact.ramp_grade)
    band = float(law.tables.emit.cockpit.visual_m)
    snap = float(rules.cells.snap_grid_m)
    touch = float(law.tables.structures.placement.sunken_ramp_grid_m) or 2.0
    k_bank = float(law.tables.emit.design.bank_slope)
    bank_max = float(law.tables.structures.building_pad.platform_collar_max_m)
    ids = sorted(pm_base.vertices)
    xy = np.array([pm_base.vertices[v].xy for v in ids], dtype=float)
    zz = np.array([float(z_base[v]) for v in ids], dtype=float)
    landings = _landing_faces(pm_base)
    # the mapped roads a strip may ride (``geom/ramp_profile.strip_level``)
    pads_b = frozenset(getattr(pm_base, "pad_roads", None) or ())
    runs_b = frozenset(getattr(pm_base, "ramp_runouts", None) or ())
    lead_v = sorted({v for f in (getattr(pm_base, "faces", None) or {}).values()
                     if is_lead_face(f, pads_b, runs_b) for v in pm_base.ring_vertices(f.ring)})
    lead_xy = np.array([pm_base.vertices[v].xy for v in lead_v], dtype=float).reshape(-1, 2)
    lead_z = np.array([float(z_base[v]) for v in lead_v], dtype=float)
    occupied = unary_union([Polygon(c.ring, c.holes) for c in cl.cells] + [landings])
    cells = list(cl.cells)
    to_ll = frame.transformers()[1]
    from ..law.tables import airside_stage_roles, road_family_roles
    air = frozenset(airside_stage_roles(law))
    roads = frozenset(road_family_roles(law))
    for f in feet:
        (lx, ly), (dx, dy), w = f.lip, f.direction, f.width_m
        nx, ny = -dy, dx

        def rect(s0: float, s1: float, step: float = 0.0) -> Polygon:
            h = 0.5 * w
            ss = _stations(s0, s1, step)
            return Polygon([(lx + dx * s + nx * t, ly + dy * s + ny * t)
                            for s, t in [*((s, -h) for s in ss),
                                         *((s, h) for s in reversed(ss))]])
        # the patch holds the ground under the ramp's last metres: else
        # nothing graded the ground to the foot and nothing runs out
        back = rect(-FOOT_SPAN_M, 0.0)
        if back.intersection(occupied).area < 0.5 * back.area:
            rep["ungraded"] += 1
            continue
        if back.intersects(landings):
            rep["landing"] += 1           # 10-03e: not yet (module NOT YET)
            continue
        free = [q for q in polygon_parts(rect(0.0, MAX_RUN_M).difference(occupied))
                if q.distance(occupied) <= touch]
        if not free:
            rep["blocked"] += 1
            continue

        def s_of(q):
            c = np.asarray(q.exterior.coords)
            return float(((c[:, 0] - lx) * dx + (c[:, 1] - ly) * dy).min())
        first = min(free, key=s_of)
        s0 = max(0.0, s_of(first))
        x0, y0 = lx + dx * s0, ly + dy * s0
        h = 0.5 * w
        seg = LineString([(x0 - nx * h, y0 - ny * h), (x0 + nx * h, y0 + ny * h)])
        z0 = _level_at(seg, xy, zz, touch)
        if z0 is None:
            rep["ungraded"] += 1
            continue
        dem0 = float(dem.z(x0, y0))
        if abs(z0 - dem0) <= band:
            rep["at_grade"] += 1
            continue
        # THE RUN IS THE FOOT'S OFFSET (``pad_road_exit``'s round 5): the
        # ramp closes the ground's offset at the foot, the terrain's own
        # slope beyond is the terrain's
        run = min(MAX_RUN_M, abs(z0 - dem0) / g)
        # both SIDES carry a vertex every ``STATION_M`` at the same stations:
        # the profile and its cross-fall are only what the ring's vertices
        # can hold (MEASURED, KCLT #1093: a 61 m strip with one mid vertex on
        # one side only, 13.4 % across the chord to the other side)
        strip = rect(s0 - snap, s0 + run, STATION_M).difference(occupied)
        strip = shapely.set_precision(strip, snap)
        parts = [q for q in polygon_parts(strip)
                 if q.area >= touch * touch and q.distance(seg) <= touch]
        if not parts:
            rep["blocked"] += 1
            continue
        lat, lon = to_ll(x0, y0)
        own: list[tuple[int, Polygon]] = []
        for q in parts:
            k = rep["runouts"]
            own.append((k, q))
            ev = {"pad_road": 1.0, "ramp_runout": 1.0, "runout_x0": x0, "runout_y0": y0,
                  "runout_dx": dx, "runout_dy": dy, "runout_z0": z0, "runout_dem0": dem0,
                  "runout_run_m": run, "runout_width_m": w}
            cells.append(Cell(len(cells), "service_road", f"{RUNOUT_PREFIX}:{k}",
                              tuple(q.exterior.coords)[:-1],
                              tuple(tuple(r.coords)[:-1] for r in q.interiors),
                              None, None, role_side(law, "service_road"),
                              "service_road", ev))
            occupied = unary_union([occupied, q])
            rep["runouts"] += 1
        # THE STRIP ENDS ON THE GROUND (#1093, 20aw / 20ay): its 1:3 bank
        # to the daylight line, over the open ground beside and beyond it,
        # after every part stands (a part's bank never takes its sibling's)
        if k_bank > 0.0 and bank_max >= snap:
            # the strip's level: its lead's where a mapped road carries the
            # run-out beside it, else the profile (the rows' own reading)
            S_ = (lead_xy[:, 0] - x0) * dx + (lead_xy[:, 1] - y0) * dy
            T_ = -(lead_xy[:, 0] - x0) * dy + (lead_xy[:, 1] - y0) * dx
            on = (np.abs(T_) <= h + touch) & (S_ >= -touch) & (S_ <= run + touch)
            lead = lead_section(zip(S_[on], lead_z[on], strict=True))

            def z_at(S: float, x0=x0, y0=y0, dx=dx, dy=dy, z0=z0, dem0=dem0, lead=lead) -> float:
                return strip_level(S, z0, dem0, axis_ground(dem, x0, y0, dx, dy), g, lead)
            ring = _bank_ring(x0, y0, dx, dy, w, run, z_at, dem, k_bank, bank_max, band)
            body = rect(s0 - snap, s0 + run, STATION_M)
            got = [] if ring is None else polygon_parts(shapely.set_precision(
                ring.difference(body).difference(occupied), snap))
            for b in got:
                if b.area < touch * touch:
                    continue
                k, _q = min(own, key=lambda kq: kq[1].distance(b))
                if _q.distance(b) > snap:
                    continue
                cells.append(Cell(len(cells), "building", f"{RUNOUT_PREFIX}:{k}{COLLAR_SUFFIX}",
                                  tuple(b.exterior.coords)[:-1],
                                  tuple(tuple(r.coords)[:-1] for r in b.interiors),
                                  None, None, role_side(law, "building"), "building",
                                  {BANK_EVIDENCE: 1.0}))
                occupied = unary_union([occupied, b])
                rep["banks"] += 1
                rep["bank_m2"] = round(rep["bank_m2"] + b.area, 1)
            # THE FOOT'S HELD GROUND ENDS ON THE GROUND TOO (#1093 round 3;
            # 14c (5) "the 1:3 bank stays for the ramp's sides"; bar 11-03e):
            # the faces the patch holds under the deck's last metres and the
            # pad roads beside them bank down to the daylight line inside the
            # run-out's box, as the strip's own bank does
            got = _held_banks(pm_base, xy, zz, cells, back,
                              _run_box(f.lip, f.direction, s0 + run, h, bank_max),
                              occupied, air, dem, k_bank, bank_max, band, snap, touch,
                              roads)
            for b in got:
                k, _q = min(own, key=lambda kq: kq[1].distance(b))
                cells.append(Cell(len(cells), "building", f"{RUNOUT_PREFIX}:{k}{COLLAR_SUFFIX}",
                                  tuple(b.exterior.coords)[:-1],
                                  tuple(tuple(r.coords)[:-1] for r in b.interiors),
                                  None, None, role_side(law, "building"), "building",
                                  {BANK_EVIDENCE: 1.0}))
                occupied = unary_union([occupied, b])
                rep["side_banks"] += 1
                rep["side_bank_m2"] = round(rep["side_bank_m2"] + b.area, 1)
        rep["run_m"] = round(rep["run_m"] + run, 1)
        rep["list"].append(f"{f.member} foot {lat:.7f},{lon:.7f} z0 {z0:.2f} dem "
                           f"{dem0:.2f} run {run:.0f} m x {w:.0f} m")
    if not rep["runouts"]:
        return cl, rep
    return _dc.replace(cl, cells=tuple(cells)), rep
