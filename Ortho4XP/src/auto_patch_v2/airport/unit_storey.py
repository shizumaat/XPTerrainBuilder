"""THE UPPER STOREY OF A PACK UNIT (#1101 / #1099; owner answer 47,
2026-10-20: "yes to both" — the mirror of the lower level, RULINGS
2026-10-19ai, #809; spec ``docs/specs/low-level-pad-spec.md`` §5).

A terminal cut into a hill stands with its airside floor on the apron and
its landside one storey up.  The OBJECT says so: the unit's parts at the
apron are authored at its floor ``t``, its landside parts — the forecourt
parapet, the kerb columns, the landside hall — a storey higher.  MEASURED
LPHR (38.521557, −28.716632): the terminal unit's grounded parts stand at
y 0; a 68 m x 1 m parapet (``lphr_tps_06``) runs at y +6.0 exactly along
the forecourt's 68 m contact with the apron, and the landside hall and its
columns stand at +6.0 too.

THE FLOOR.  ``t`` is the base most of the unit's GROUNDED parts (a part
with its own ground feet, ``Part.feet``) within ``pad_frontage_m`` of
airside pavement stand at — the floor the apron meets.  A part the plan
judged elevated (a canopy, a roof, the parapet itself) never sets it.

THE UPPER STOREY.  The unit's parts authored at least ``[building_pad]
low_level_min_step_m`` (one storey) above ``t``.  Their plan footprints
are the storey's witness on the map: ``classify/airside_edge`` reads a
lot's contact with the apron ALONG them as a contact across the storey —
no apron contact (§27 amended).

THE UPPER PAD (RULINGS 2026-11-13aa (1), #2068; spec
``docs/specs/2068-upper-pad-spec.md`` §1, witness T1-T4 of amendment A1
(3)): a pad no born-airside pavement comes near, only a road §27 flipped
round it, whose every part of the unit stands a storey over its floor, its
plinth covering half of it, while another pad of the unit stands at the
floor and fronts airside pavement, over ground that stands that storey
over the airside the floor meets (:func:`upper_pads`) — the pad under a unit's upper storey (a tower
on a hill behind its terminal).  Doubt refuses (13r).

It lives in ``airport`` because ``classify`` reads it before any pad
exists and ``planar`` reads the same floor rule inside a pad."""
from __future__ import annotations

import dataclasses as _dc
import math
import statistics as _st
import typing as _t

import numpy as np
import shapely
from shapely.geometry import Polygon
from shapely.ops import unary_union

from .dem import dem_z_or_nan

__all__ = ["FAR", "HELD", "PLINTH_COVER", "SINGLE", "UNCONFIRMED", "Level", "Storey",
           "UnitLevels", "carried_by", "dem_samples", "frontage_held", "part_footprint",
           "unit_floor",
           "unit_levels", "upper_pads", "upper_storeys"]


@_dc.dataclass(frozen=True)
class Storey:
    """One unit's upper storey: the unit's index in ``airport.partition``,
    its airside floor ``floor_y`` (authored), its upper parts and the union
    of their plan footprints (the engine's xy frame)."""

    unit: int
    floor_y: float
    parts: tuple
    footprint: _t.Any


@_dc.dataclass(frozen=True)
class _UpperPad:
    """One pad under a unit's upper storey (:func:`upper_pads`): the pad's
    ref and plan, the unit, its floor ``floor_y`` and the storey's base
    ``y`` (authored), the walled-plane cover of the pad, the ground step
    ``delta`` (pad DEM median less the floor's airside), the pad's DEM
    ``relief`` and whether a pack wall/fence of the unit retains it
    (recorded only, spec §1 (5))."""

    ref: str
    polygon: _t.Any
    unit: int
    floor_y: float
    y: float
    cover: float
    walled: int
    delta: float
    relief: float
    fence: bool
    #: T4's airside ground: the DEM median over the airside the floor meets
    air_z: float = float("nan")

    @property
    def rise(self) -> float:
        return self.y - self.floor_y


def dem_samples(dem, g, step: float = 2.0) -> list:
    """The DEM over ``g`` on a ``step`` grid (at most ~400 samples): the
    grid's points (row by row, each axis stepped by repeated addition)
    that ``g`` contains, their finite heights.  The points are tested and
    sampled at once (#2206: ``shapely.contains_xy``, the point-in-area
    predicate ``contains`` reads; the DEM's own ``z_many``, its ``z`` bit
    for bit); a DEM whose array read raises is asked point by point."""
    if dem is None or g is None or g.is_empty:
        return []
    x0, y0, x1, y1 = g.bounds
    h = max(step, math.sqrt(max(g.area, 1.0) / 400.0))
    xs, ys = _steps(x0 + 0.5 * h, x1, h), _steps(y0 + 0.5 * h, y1, h)
    if not xs or not ys:
        return []
    px, py = np.tile(np.array(xs), len(ys)), np.repeat(np.array(ys), len(xs))
    inside = np.asarray(shapely.contains_xy(g, px, py), dtype=bool)
    px, py = px[inside], py[inside]
    if not len(px):
        return []
    many = getattr(dem, "z_many", None)
    try:
        zs = np.asarray(many(px, py), dtype=float).ravel().tolist()
    except Exception:  # noqa: BLE001 -- no array read: point by point
        zs = [dem_z_or_nan(dem, x, y) for x, y in zip(px.tolist(), py.tolist(), strict=True)]
    return [z for z in zs if z == z]


def _steps(a: float, b: float, h: float) -> list:
    """``a, a + h, a + h + h, ...`` while below ``b`` (repeated addition)."""
    out = []
    while a < b:
        out.append(a)
        a += h
    return out


def part_footprint(p, to_xy) -> "Polygon | None":
    """The plan footprint of one pack part (the union of its rings), or
    ``None`` where it carries no ring of three vertices."""
    gs = []
    for rg in getattr(p, "rings", ()) or ():
        if len(rg) < 3:
            continue
        g = Polygon([to_xy(lon, lat) for lat, lon in rg])
        g = g if g.is_valid else g.buffer(0.0)
        if not g.is_empty:
            gs.append(g)
    return unary_union(gs) if gs else None


def unit_floor(parts, near, to_xy) -> "float | None":
    """THE AIRSIDE FLOOR of a unit (module docstring): the base most of its
    GROUNDED ``parts`` whose footprint meets ``near`` stand at (the lowest
    of a tie), or ``None`` where no grounded part meets it."""
    return _plan_floor([(p, g) for p in parts if getattr(p, "feet", ())
                        and (g := part_footprint(p, to_xy)) is not None], near)


def _plan_floor(pg, near) -> "float | None":
    """:func:`unit_floor` off the unit's solid parts with their footprints
    ``pg`` (``_unit_plans``: the same parts, in order, their footprints
    already read)."""
    ys = [p.base_y for p, g in pg if getattr(p, "feet", ()) and _meets(near, g)]
    return float(min(_st.multimode(round(y) for y in ys))) if ys else None


def _near(air, near_m: float):
    """``air`` widened by ``near_m``, PREPARED (#2206): every part of every
    unit is asked whether it meets it, and :func:`_meets` reads it with the
    prepared predicate -- the same answer, the airside indexed once."""
    near = air.buffer(near_m)
    shapely.prepare(near)
    return near


def _meets(near, g) -> bool:
    """``g.intersects(near)``, asked of ``near`` (symmetric; a prepared
    ``near``, :func:`_near`, answers through its index)."""
    return bool(near.intersects(g))


def _solid(u) -> list:
    return [p for m in u.members for p in m.parts
            if not getattr(p, "line", False) and not getattr(p, "scatter", False)]


def _floors(part, near, to_xy) -> _t.Iterator[tuple]:
    """``(index, unit, solid parts, floor)`` per unit of ``part`` with an
    airside floor (:func:`unit_floor` against ``near``), as
    :func:`upper_storeys` reads it (:func:`unit_levels` reads the same
    floor off its unit plans, :func:`_plan_floor`)."""
    for ui, u in enumerate(part.units):
        parts = _solid(u)
        t = unit_floor(parts, near, to_xy)
        if t is not None:
            yield ui, u, parts, t


def upper_storeys(airport, law, air) -> list[Storey]:
    """Every pack unit of ``airport`` that stands at airside pavement
    ``air`` (one geometry, the engine's frame) and carries parts a storey
    above its airside floor (module docstring)."""
    part = getattr(airport, "partition", None)
    frame = getattr(airport, "frame", None)
    if part is None or frame is None or air is None or air.is_empty:
        return []
    step = float(getattr(law.tables.structures.building_pad,
                         "low_level_min_step_m", 0.0) or 0.0)
    if step <= 0.0:
        return []
    near = _near(air, _near_m(law))
    to_xy = frame.entry()
    out: list[Storey] = []
    for ui, _u, parts, t in _floors(part, near, to_xy):
        up = [p for p in parts if p.base_y >= t + step]
        polys = [g for p in up if (g := part_footprint(p, to_xy)) is not None]
        if polys:
            out.append(Storey(ui, t, tuple(up), unary_union(polys)))
    return out



@_dc.dataclass(frozen=True)
class _UnitRead:
    """One unit as :func:`upper_pads` reads it: its solid parts with their
    footprints, its floor ``t`` and the union of its footprints' boxes."""

    ui: int
    unit: _t.Any
    parts: tuple
    t: float
    bounds: tuple


def _unit_reads(part, near, to_xy) -> list:
    out = []
    for ui, u in enumerate(part.units):
        parts = _solid(u)
        t = unit_floor(parts, near, to_xy)
        if t is None:
            continue
        pg = tuple((p, g) for p in parts if (g := part_footprint(p, to_xy)) is not None
                   and g.area > 0.0)
        if pg:
            bx = [g.bounds for _p, g in pg]
            out.append(_UnitRead(ui, u, pg, float(t),
                                 (min(b[0] for b in bx), min(b[1] for b in bx),
                                  max(b[2] for b in bx), max(b[3] for b in bx))))
    return out


#: the share of an upper pad its plinth plane covers (spec 2068 A1 (3) T2)
PLINTH_COVER = 0.5


def _on(ur: _UnitRead, P) -> list:
    """The unit's solid parts with half their plan or more on ``P``."""
    return [(p, g) for p, g in ur.parts if g.intersects(P)
            and g.intersection(P).area >= 0.5 * g.area]


def _floor_pad(ref, ur: _UnitRead, pads, air, near_m: float) -> bool:
    """T3: another pad of the unit whose lowest solid base stands within
    ``split_level.BAND_M`` of the unit's floor and fronts airside pavement
    ``air`` (the block the upper pad's level is tied to)."""
    from .split_level import BAND_M
    for r, Q in pads:
        if r == ref or Q is None or Q.is_empty or Q.distance(air) > near_m:
            continue
        on = _on(ur, Q)
        if on and abs(min(p.base_y for p, _g in on) - ur.t) <= BAND_M:
            return True
    return False


def _upper_pad(ref, P, ur: _UnitRead, near, air, dem, law, to_xy,
               born, pads) -> "_UpperPad | None":
    """:func:`upper_pads` for one pad ``P`` and one unit, or ``None``."""
    from .split_level import BAND_M
    t = ur.t
    step = float(law.tables.structures.building_pad.low_level_min_step_m)
    wall = float(law.tables.structures.placement.chain_min_height_m)
    on = _on(ur, P)
    if not on or any(p.base_y < t + step for p, _g in on):
        return None                                       # every part a storey up
    y_p = min(p.base_y for p, _g in on)
    plane = [(p, g) for p, g in on if p.base_y <= y_p + BAND_M]
    cover = unary_union([g for _p, g in plane]).intersection(P).area / P.area
    walled = sum(1 for p, _g in plane if float(getattr(p, "height_m", 0.0) or 0.0) >= wall)
    if cover < PLINTH_COVER or walled < 1:
        return None                                       # T2, T4 (walled on the plane)
    if not _floor_pad(ref, ur, pads, air, _near_m(law)):
        return None                                       # T3
    rise = y_p - t
    floor = [g for p, g in ur.parts if getattr(p, "feet", ()) and round(p.base_y) == t
             and _meets(near, g)]
    zp = dem_samples(dem, P)
    za = dem_samples(dem, air.intersection(unary_union(floor).buffer(_near_m(law))))
    if not zp or not za:
        return None                                       # T4: no ground
    delta, relief = _st.median(zp) - _st.median(za), max(zp) - min(zp)
    if not (0.5 * rise <= delta <= 1.5 * rise) or relief >= rise:
        return None                                       # T4
    reach = P.buffer(_near_m(law))
    fence = any(getattr(p, "line", False) and p.base_y <= y_p - 0.5 * rise
                and p.base_y + float(getattr(p, "height_m", 0.0) or 0.0) >= y_p - BAND_M
                and (g := part_footprint(p, to_xy)) is not None and g.intersects(reach)
                for m in ur.unit.members for p in m.parts)
    return _UpperPad(str(ref), P, ur.ui, t, float(y_p), round(cover, 3), walled,
                    round(delta, 2), round(relief, 2), fence, round(_st.median(za), 2))


def _near_m(law) -> float:
    """``[design] pad_frontage_m``."""
    from ..law.tables import design as design_law
    return float(design_law(law).pad_frontage_m)


def upper_pads(airport, law, air, pads, *, born=None, flipped=None) -> list[_UpperPad]:
    """THE UPPER PADS (module docstring; spec 2068 §1 (1)-(5)) among
    ``pads`` (``(ref, polygon)``, the engine's frame), read against the
    airside pavement ``air``: a pad is under unit ``u``'s upper storey when
    ``u`` has a floor ``t``; every solid part of ``u`` with half its plan
    on the pad stands at least ``low_level_min_step_m`` over ``t``; the
    parts within ``split_level.BAND_M`` of the lowest of those bases
    ``y_p`` cover :data:`PLINTH_COVER` of the pad and one is walled; and the
    ground confirms both sides — the pad's DEM median stands half to one
    and a half rises over the median of the airside within
    ``pad_frontage_m`` of the floor's parts, and the pad's own relief is
    under the rise.  No DEM refuses.

    T1 (spec 2068 A1 (3)): ``born`` is the airside pavement BORN airside
    (``air`` less the road faces §27 flipped, ``flipped``): no born pavement
    within ``pad_frontage_m`` of the pad, and the airside there is a
    flipped road -- the road §27 pulled down round the pad is the case this
    reader exists for (``classify/storey_edge.arm_storeys``).  MEASURED
    (U8 census, 76 captures + LPPI): KBWI ``building18/23/33`` and LOWS
    ``building8`` pass T2-T4 with no flipped road within 400 m of them;
    LPPI ``building2`` touches ``dsf:pol96``.  T3 (another pad of the unit
    at its floor fronts airside) reads ``air`` whole: the LPPI terminal's
    only frontage is that same flipped road (born airside 8.5 m off).
    Without ``born`` / ``flipped`` T1 reads ``air`` and requires nothing
    flipped."""
    part = getattr(airport, "partition", None)
    frame = getattr(airport, "frame", None)
    dem = getattr(airport, "dem", None)
    if part is None or frame is None or dem is None or air is None or air.is_empty:
        return []
    born = air if born is None else born
    near_m = _near_m(law)
    near = _near(air, near_m)
    to_xy = frame.entry()
    units = None
    out: list[_UpperPad] = []
    for ref, P in pads:
        if P is None or P.is_empty or P.area <= 0.0 or P.distance(born) <= near_m \
                or (flipped is not None and P.distance(flipped) > near_m):
            continue                                      # T1
        units = _unit_reads(part, near, to_xy) if units is None else units
        x0, y0, x1, y1 = P.bounds
        for ur in units:
            b = ur.bounds
            if b[0] > x1 or b[2] < x0 or b[1] > y1 or b[3] < y0:
                continue
            got = _upper_pad(ref, P, ur, near, air, dem, law, to_xy, born, pads)
            if got is not None:
                out.append(got)
                break
    return out


# ---------------------------------------------------------------------------
# THE UNIT'S TWO FLOORS (RULINGS 2026-11-25g, 25h; spec
# ``docs/specs/terminal-frontage-split-level-20261125.md`` §1.2-§1.5, step 1:
# a RECORD -- nothing reads it into the solve yet)
# ---------------------------------------------------------------------------

#: the verdicts of a :class:`UnitLevels` (spec §1.5)
HELD, SINGLE, UNCONFIRMED, FAR = "held", "single", "unconfirmed", "far"
#: the rungs of the witness ladder (spec §1.3) step 1 reads
_L1, _L2, _L6 = "storey_parts", "split_level", "ground"


@_dc.dataclass(frozen=True)
class Level:
    """One groundside floor plane of a unit (authored ``y``, the unit's own
    frame): the plan its parts cover, how many parts, and the median
    distance of those parts from the airside pavement (0 for a rung that
    reads no parts)."""

    y: float
    area_m2: float
    parts: int
    dist_m: float


@_dc.dataclass(frozen=True)
class UnitLevels:
    """THE RECORD (spec §1.2): a terminal-sized unit's airside floor
    ``air_y`` and groundside floor ``land_y`` (``None``: one level), every
    groundside plane the pack authors (``levels``, nearest the airside
    first -- owner 25h Q1: the groundside may drop more than one level),
    the rung that read them, the landside ``face`` (frame metres), the
    ground medians ``(g_air, g_land)``, the verdict and the clues
    (``airport/frontage_face.face_clues``)."""

    unit: int
    plan: _t.Any
    air_y: float
    land_y: "float | None"
    levels: tuple
    witness: "str | None"
    face: _t.Any
    ground: tuple
    verdict: str
    clues: _t.Mapping
    #: RUNG L0 (owner RULINGS 2026-11-25m (5); underside spec §1, U7): the
    #: groundside level the unit's underside contacts stand at along its
    #: landside face (:func:`_contact_level`), ``None`` where they state
    #: none; a twin of ``land_y`` -- nothing reads it yet
    l0: "float | None" = None

    @property
    def rise(self) -> float:
        return 0.0 if self.land_y is None else float(self.land_y) - float(self.air_y)


#: the units' plans, held by the partition they were read from and dropped
#: with it (``model/map_memo.per_map``; #2206)
_PLANS: dict = {}


def _plans_of(part, frame, to_xy):
    """:func:`_unit_plans` once per partition and frame (#2206: the main pass,
    stage 1 and the late map read the same plans, each in full); the frame
    is checked by identity, the plans are read-only."""
    from ..model.map_memo import per_map
    held = per_map(_PLANS, part)
    got = held.get("plans")
    if got is None or got[0] is not frame:
        got = held["plans"] = (frame, _unit_plans(part, to_xy))
    return got[1]


def _unit_plans(part, to_xy):
    from .frontage_face import UnitPlans
    solid, lines, boxes = [], [], []
    for u in part.units:
        pg = tuple((p, g) for p in _solid(u) if (g := part_footprint(p, to_xy)) is not None)
        ln = tuple((p, g) for m in u.members for p in m.parts if getattr(p, "line", False)
                   and (g := part_footprint(p, to_xy)) is not None)
        bx = [g.bounds for _p, g in pg + ln]
        solid.append(pg)
        lines.append(ln)
        boxes.append((min(b[0] for b in bx), min(b[1] for b in bx),
                      max(b[2] for b in bx), max(b[3] for b in bx)) if bx else None)
    return UnitPlans(tuple(solid), tuple(lines), tuple(boxes))


def _planes(pg, air, band: float) -> list[Level]:
    """The parts ``pg`` clustered into planes ``band`` deep (chained on
    ``base_y``): each plane's modal base to the decimetre (as
    ``classify/storey_edge.storey_height`` reads a rise), its plan area,
    its part count and its parts' median distance from ``air``."""
    out: list[Level] = []
    run: list = []
    for p, g in sorted(pg, key=lambda x: x[0].base_y) + [(None, None)]:
        if run and (p is None or p.base_y - run[-1][0].base_y > band):
            y = min(_st.multimode(round(q.base_y, 1) for q, _h in run))
            out.append(Level(round(float(y), 2), round(unary_union([h for _q, h in run]).area, 1),
                             len(run), round(_st.median(h.distance(air) for _q, h in run), 1)))
            run = []
        if p is not None:
            run.append((p, g))
    return out


def _contact_level(airport, ui: int, face, t: float, near_m: float, step: float
                  ) -> "float | None":
    """RUNG L0: the groundside level of pack unit ``ui`` read off its
    underside maps (``Airport.undersides``, ``geom/underside_map``): the
    contact heights ``h`` of its non-airside perimeter stations within
    ``near_m`` of its landside ``face`` standing a storey (``step``) or more
    off its airside floor ``t``, either sign -- their fullest 0.1 m plane
    (the lowest of a tie), or ``None`` where no such station stands."""
    maps = getattr(airport, "undersides", None) or {}
    if face is None or face.is_empty or not maps:
        return None
    uid = str(airport.partition.units[ui].id)
    band = face.buffer(float(near_m))
    shapely.prepare(band)
    hs = []
    for m in maps.values():
        if m.footless or not any(str(c).split("#", 1)[0] == uid
                                 for c in str(m.unit).split("+")):
            continue
        ok = ~np.asarray(m.airside, dtype=bool) & (np.abs(m.h - float(t)) >= float(step))
        ok &= np.asarray(shapely.contains_xy(band, m.e, m.n), dtype=bool)
        hs.extend(float(h) for h in m.h[ok])
    if not hs:
        return None
    return round(float(min(_st.multimode(round(h, 1) for h in hs))), 2)


def _band_m() -> float:
    from .split_level import BAND_M
    return BAND_M


def _unsupported(cand, pg, band: float) -> list:
    """The parts of ``cand`` no other part of ``pg`` carries: none whose plan
    meets theirs stands lower by more than ``band`` and reaches up to
    within ``band`` of their base.  A roof, a canopy deck or an upper
    floor slab stands on the unit's own walls, never on the ground, and
    states no groundside floor (``unit_floor``'s "elevated" rule, read
    from the parts themselves: MEASURED PHLI, LPHR, ELLX, the storey parts
    carry no ``Part.feet``)."""
    from shapely.strtree import STRtree
    if not cand:
        return []
    geoms = [g for _p, g in pg]
    tree = STRtree(geoms)
    out = []
    for p, g in cand:
        y = float(p.base_y)
        hit = False
        for j in tree.query(g):
            q = pg[int(j)][0]
            if q is p or not (float(q.base_y) < y - band
                              and float(q.base_y) + float(getattr(q, "height_m", 0.0) or 0.0)
                              >= y - band):
                continue
            inter = geoms[int(j)].intersection(g)
            if not inter.is_empty and (inter.area > 0.0 or g.area == 0.0):
                hit = True
                break
        if not hit:
            out.append((p, g))
    return out


def _open_sky(p, g, pg, tree, geoms) -> bool:
    """Whether no other part of ``pg`` stands over half of ``g`` at or above
    the top of ``p`` (a vehicle on the apron, not a desk under a roof)."""
    top = float(p.base_y) + float(getattr(p, "height_m", 0.0) or 0.0)
    for j in tree.query(g):
        q = pg[int(j)][0]
        if q is p or float(q.base_y) < top - 0.01:
            continue
        if geoms[int(j)].intersection(g).area >= 0.5 * g.area:
            return False
    return True


def _apron_floor(pg, t: float, near, apt, step: float) -> float:
    """THE AIRSIDE FLOOR WHERE THE APRON'S OWN OBJECTS STAND (lane lfront2,
    spec step-1 finding (a)): ``t`` (:func:`unit_floor`, the grounded
    parts' plane), or the plane the unit's OPEN APRON OBJECTS stand at --
    parts within ``near`` of the airside no other part carries
    (:func:`_unsupported`), half their plan or more on the apt.dat airside
    pavement ``apt`` and under the open sky (:func:`_open_sky`): the fire
    trucks, stairs, tents and apron slabs the author set on the apron --
    where that plane stands a storey (``step``) or more off ``t`` and holds
    more parts than ``t``'s grounded parts and open objects together.  The
    frame's zero is then another storey of the building, not the apron.

    MEASURED LDSP ``unit:5``: 12 grounded parts at 0 (pipes, a terminal
    wing) + 10 open objects at 0 against 238 open objects at +3.0 (the
    apron the pad meets; ``plan_low``'s ``top_level`` reads +3.00 too).
    PHLI ``unit:23`` (an open-air terminal over apt.dat pavement): 132
    grounded parts at 0 against 62 open roof trims at +7.3 -- ``t``
    stands; LPHR ``unit:8``: the open objects stand at 0.  The plane must
    also be the one ``planar/low_level.top_level`` reads at the airside
    (the modal base of the unit's parts there).  MEASURED, census over 29
    registered captures: six units re-read (LDSP ``unit:5`` +3.0, ELLX
    ``unit:138`` +3.4 and ``unit:8`` +4.6, KORD ``unit:17`` +4.3, KLAX
    ``unit:10`` +13.0, CYYZ ``unit:245`` +29.2); only LDSP's record is one
    the frontage law takes (:func:`frontage_held`)."""
    from shapely.strtree import STRtree
    if apt is None or apt.is_empty or not pg:
        return t
    band = _band_m()
    geoms = [g for _p, g in pg]
    tree = STRtree(geoms)
    nr = [(p, g) for p, g in pg if _meets(near, g)]
    opened = [(p, g) for p, g in _unsupported(nr, pg, band)
              if g.area > 0.0 and g.intersection(apt).area >= 0.5 * g.area
              and _open_sky(p, g, pg, tree, geoms)]
    planes = sorted(_planes(opened, apt, band), key=lambda lv: (-lv.parts, lv.y))
    if not planes or abs(planes[0].y - t) < step:
        return t
    # and the pad stage reads the same airside top: the base most of the
    # unit's parts at the airside stand at (``planar/low_level.top_level``'s
    # frontage level) -- one airside floor, read alike by both
    top = min(_st.multimode(round(p.base_y) for p, _g in nr)) if nr else None
    if top is None or abs(planes[0].y - top) > band:
        return t
    at_t = sum(1 for p, g in nr if getattr(p, "feet", ()) and round(p.base_y) == t) + sum(
        1 for p, _g in opened if abs(float(p.base_y) - t) <= band)
    return float(planes[0].y) if planes[0].parts > at_t else t


def _storey_parts(pg, t: float, near, air, law) -> list[Level]:
    """RUNG L1 (spec §1.3): the unit's solid parts off the airside-near
    band standing at least a storey off ``t``, either sign, as planes; the
    densest (most parts) first.  MEASURED PHLI ``unit:23``: the +4.10
    storey's parts carry no ground feet and 1.3-1.7 m height, so neither
    ``Part.feet`` nor ``[placement] chain_min_height_m`` can gate them."""
    step = float(law.tables.structures.building_pad.low_level_min_step_m)
    off = [(p, g) for p, g in pg if abs(p.base_y - t) >= step and not _meets(near, g)]
    return sorted(_planes(_unsupported(off, pg, _band_m()), air, _band_m()),
                  key=lambda lv: (-lv.parts, -lv.area_m2))


def _split_level(u, t: float, shells, step: float) -> list[Level]:
    """RUNG L2 (spec §1.3): a storey shell the map minted over the unit's
    members (``PlanarMap.storey_shells``): its levels off its airside block."""
    ids = {str(m.id) for m in u.members if getattr(m, "id", None) is not None}
    for sh in shells:
        if ids & {str(i) for i in sh.member_ids} and sh.block is not None:
            b = float(sh.levels[sh.block])
            return [Level(round(t + float(y) - b, 2), 0.0, 0, 0.0)
                    for k, y in enumerate(sh.levels)
                    if k != sh.block and abs(float(y) - b) >= step]
    return []


def _grounds(dem, plan, air, face, near_m: float, reach_m: float, at=None,
             ground=None) -> tuple:
    """``(g_air, g_land)`` (DEM medians; ``None`` where nothing is read).

    With ``at`` (the groundside floor's own parts, rung L1): the airside
    within reach of them (of the plan where none is), and the ground that floor meets -- the map's
    groundside pavement under and within ``near_m`` of them (``ground``),
    else their own plan there off the airside's near band.  MEASURED PHLI
    ``unit:23`` (+4.10 storey): airside 47.12 by the storey, 48.86 round
    the whole plan; the kerb lots under the storey 49.27, the storey's own
    plan 48.04, the face's runs 45.9-46.8 (the building's ends).

    Without: the airside within reach of the plan, and the ground within
    reach outside the face (outside the plan's outline where no face
    qualifies), off the plan and the airside's near band."""
    if at is not None and not at.is_empty:
        za = (dem_samples(dem, air.intersection(at.buffer(reach_m)))
              or dem_samples(dem, air.intersection(plan.buffer(reach_m))))
        zone = at.buffer(near_m).difference(air.buffer(near_m))
        if ground is not None and not (gz := ground.intersection(zone)).is_empty:
            zone = gz
    else:
        za = dem_samples(dem, air.intersection(plan.buffer(reach_m)))
        line = face if not face.is_empty else plan.boundary
        zone = line.buffer(reach_m).difference(plan).difference(air.buffer(near_m))
    zl = dem_samples(dem, zone)
    return (round(_st.median(za), 2) if za else None,
            round(_st.median(zl), 2) if zl else None)


def _confirmed_first(levels, pg, t: float, near, dem, plan, air, face, near_m: float,
                     reach: float, ground) -> tuple:
    """``(levels, (g_air, g_land))``: rung L1's planes with the one the
    ground confirms best first -- same sign, at least half its rise
    (:func:`_grounds` read at its own parts), and the rise nearest the
    ground's step -- else the densest plane; and the ground medians read
    at it.  MEASURED KATL ``building32``: the densest unsupported plane is
    +4.0 (upper floors) over level ground; -5.5, -15.0 and -18.8 are all
    confirmed by a 12.9 m fall, and -15.0 is today's lower level."""
    first, best = None, None
    for lv in levels:
        at = unary_union([g for p, g in pg if abs(p.base_y - lv.y) <= _band_m()
                          and not _meets(near, g)])
        gr = _grounds(dem, plan, air, face, near_m, reach, at, ground)
        first = first or (lv, gr)
        rise = lv.y - t
        if None in gr:
            continue
        d = gr[1] - gr[0]
        if d * rise > 0.0 and abs(d) >= 0.5 * abs(rise) \
                and (best is None or abs(rise - d) < best[0]):
            best = (abs(rise - d), lv, gr)
    if best is None:
        return levels, first[1]
    return [best[1]] + [x for x in levels if x is not best[1]], best[2]


def _verdict(t: float, levels, ground, span, step: float) -> str:
    """THE VERDICT (spec §1.5, owner 25h Q1): ``held`` where the ground
    shows half the rise of the densest plane, the same sign, and lies
    within a storey of what the pack explains -- its planes and, below the
    airside, the foot of the groundside face (a face several storeys tall
    explains a ground several storeys down); ``far`` beyond that;
    ``unconfirmed`` where the ground does not show it."""
    if not levels:
        return SINGLE
    g_air, g_land = ground
    if g_air is None or g_land is None:
        return UNCONFIRMED
    rise, d = levels[0].y - t, g_land - g_air
    if d * rise <= 0.0 or abs(d) < 0.5 * abs(rise):
        return UNCONFIRMED
    rels = [lv.y - t for lv in levels]
    if d < 0.0:
        lo = min(rels + ([span[0] - t] if span else []))
        return FAR if d < lo - step else HELD
    return FAR if d > max(rels) + step else HELD


#: a pack deck of the unit (``planar/landing``'s viaduct test): the
#: unit's kerb deck, rung L3
_DECK_KINDS = ("flag", "signature")


def frontage_held(rec: UnitLevels, airport, law) -> bool:
    """Whether the frontage law takes ``rec`` (spec §3.1; lane lfront2):
    verdict ``held``; no rung L3 -- the unit carries no pack deck of its
    own (a kerb deck or viaduct: the deck top is the upper kerb, an
    object, and the kerb road under it gets no ground rows, spec §1.3 L3,
    §3.2) and no mapped bridge road runs along its face (``upper_roads``,
    §1.4); and a storey-parts floor (L1) is a floor -- its parts cover a
    pad's worth of plan (``[building_pad] min_area_m2``).  MEASURED HECA
    (identity airport): ``unit:46`` -4.0 carries the terminal's viaduct
    (``deck_kind`` flag, 4 bridge roads on its face); ``unit:44`` +7.5 is
    two parts over 0.9 m2."""
    if rec.verdict != HELD or rec.land_y is None:
        return False
    if rec.clues.get("upper_roads"):
        return False
    u = airport.partition.units[rec.unit]
    if any(str(getattr(m, "deck_kind", "") or "") in _DECK_KINDS for m in u.members):
        return False
    if rec.witness == _L1:
        pmin = float(law.tables.structures.building_pad.min_area_m2)
        lv = [x for x in rec.levels if abs(float(x.y) - float(rec.land_y)) < 0.005]
        return bool(lv) and lv[0].area_m2 >= pmin
    return True


def carried_by(rec: UnitLevels, P) -> bool:
    """Whether the pad (or block) ``P`` carries the record's building: half
    the unit's plan or more stands on it (lane lfront2).  A unit spread over
    many pads is a GROUP (``planar/group_low``, ``group_up`` read those);
    the frontage law reads the building its block carries.  MEASURED HECA
    ``unit:45`` (226,860 m2 over a hillside, +17.7): its block
    ``building155`` carries a sliver of it; LDSP ``building1`` carries 95 %
    of ``unit:5``."""
    if P is None or P.is_empty or not P.intersects(rec.plan):
        return False
    return P.intersection(rec.plan).area >= 0.5 * rec.plan.area


def unit_levels(airport, law, air, *, ground=None, shells=()) -> list[UnitLevels]:
    """THE UNIT LEVELS (spec §1.2): one record per pack unit of ``airport``
    standing at airside pavement ``air`` whose solid plan is at least
    ``[placement] cluster_pad_min_m2`` (the commercial-terminal test), or
    over whose members the map minted a storey shell (today's R7 read it
    two-level at any size: LPHR's terminal is 1,800 m2).

    The ladder (spec §1.3), first rung that holds: L1 the unit's storey
    parts (:func:`_storey_parts`); L2 a storey shell over its members
    (``shells``: ``PlanarMap.storey_shells``); L6 the ground alone where the
    inset is credible lidar (``law.inset_class.lidar_credible``) and the
    landside ground stands a storey off the airside (owner 25h Q2).  L3-L5
    (kerb decks, skirts, linked buildings) are step 2's; their witnesses
    are published as clues, with ``air_planes``: the planes of the
    unit's parts at the airside no other part carries (most parts first)
    -- MEASURED LDSP ``unit:5``: :func:`unit_floor` reads 0 (four grounded
    parts), while the apron's own objects (fire vehicles, stairs, the
    apron slab) stand at +3.0 with no ground feet; ``air_y`` is then
    :func:`_apron_floor`'s +3.0 (lane lfront2).  ``ground``: the map's
    groundside pavement (the face's second test), ``None`` to skip it."""
    part = getattr(airport, "partition", None)
    frame = getattr(airport, "frame", None)
    if part is None or frame is None or air is None or air.is_empty:
        return []
    bp = law.tables.structures.building_pad
    step = float(getattr(bp, "low_level_min_step_m", 0.0) or 0.0)
    if step <= 0.0:
        return []
    from ..law.inset_class import lidar_credible
    from .frontage_face import face_clues, landside_face
    near_m = _near_m(law)
    reach = float(law.tables.emit.road_contact.contact_reach_m)
    min_m2 = float(law.tables.structures.placement.cluster_pad_min_m2)
    near, to_xy, dem = _near(air, near_m), frame.entry(), getattr(airport, "dem", None)
    from .airside_floor import airside_union
    credible, apt = None, airside_union(airport)
    plans = _plans_of(part, frame, to_xy)
    out: list[UnitLevels] = []
    for ui, u in enumerate(part.units):
        t0 = _plan_floor(plans.solid[ui], near)
        if t0 is None:
            continue
        plan = unary_union([g for _p, g in plans.solid[ui]])
        shell = _split_level(u, t0, shells, step)
        if plan.is_empty or (plan.area < min_m2 and not shell):
            continue                       # a storey shell is read at any size (LPHR)
        t = _apron_floor(plans.solid[ui], t0, near, apt, step)
        if t != t0:
            shell = _split_level(u, t, shells, step)
        levels, witness = _storey_parts(plans.solid[ui], t, near, air, law), _L1
        face = landside_face(plan, air, ground, near_m, reach)
        if levels:
            levels, g = _confirmed_first(levels, plans.solid[ui], t, near, dem, plan, air,
                                         face, near_m, reach, ground)
        else:
            levels, witness = shell, _L2
            g = _grounds(dem, plan, air, face, near_m, reach, None, ground)
        # L3 (kerb decks), L4 (the author's ground sheet, ``airport/ground_rim``,
        # lane lpartshell2: ELLX's skirt) and L5 (linked buildings) slot in here
        # in step 2; their witnesses are published as clues meanwhile
        if not levels and None not in g and abs(g[1] - g[0]) >= step:
            credible = lidar_credible(airport, law) if credible is None else credible
            if credible:
                levels, witness = [Level(round(t + g[1] - g[0], 2), 0.0, 0, 0.0)], _L6
        clues = face_clues(ui, plan, face, airport, plans, reach, near_m, dem_samples)
        nr = [(p, q) for p, q in plans.solid[ui] if _meets(near, q)]
        clues["air_planes"] = [[lv.y, lv.parts, lv.area_m2] for lv in sorted(
            _planes(_unsupported(nr, plans.solid[ui], _band_m()), air, _band_m()),
            key=lambda lv: -lv.parts)]
        out.append(UnitLevels(
            ui, plan, float(t), levels[0].y if levels else None,
            tuple(sorted(levels, key=lambda lv: lv.dist_m)), witness if levels else None,
            face, g, _verdict(t, levels, g, clues["face_span"], step), clues,
            _contact_level(airport, ui, face, t, near_m, step)))
    return out
