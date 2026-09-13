"""THE CANOPY-AND-BUILDING GROUP — the ONE derivation site (owner
RULINGS 2026-09-11i; spec ``object-placement-spec.md`` §11).

Owner, 11i: *"a canopy on columns needs to stay connected to its columns,
and if it's adjacent to a building, like a roadway, then it needs to stay
connected to the building as well.  If it's a long thing like the railway
connecting two far buildings at HECA we accept disconnecting it so the
buildings can seat.  But if it's feasible, adapting the terrain to
accommodate the canopy and building group would be preferred."*

A GROUP is the set of BODIES that render as one object: a building and
the elevated decks — a canopy on columns, a kerbside roof, a viaduct —
abutting it in the authored frame.  §9/§17's membership law is NOT
restated here: the gate is ``Member.elevated_deck``
(``airport/deck_signature.elevated_deck``), the seniority is plan area,
the hop count is one, and buildings never group with buildings (10i).

**THE PARTITION IS THE INPUT** (owner RULINGS 2026-09-11j; spec §11a (3)).
:func:`derive` reads a ``PackPartition`` — the pack read ONCE at LOAD by
``airport/pack_partition.partition_pack`` — or, for a fixture, any object
carrying its ``units`` / ``contacts`` / ``abutments`` (a ``RebakePlan``
does).  That is what breaks round 1's cycle: the groups exist before
``classify``, so ``classify/evidence._pads`` can mint a body's pad from
its FEET.

**THE SPAN LAW IS PER BODY** (§11a (1)).  ``group_span_max_m`` binds a
CONNECTING body's own plan diagonal (``Group.body_span_m``), not the
group's footprint.  Round 1 priced it on the group and a canopy module
60 m long joining a terminal 200 m away came out "long"; the HECA railway
class is a body that is itself long.

**THE UNIT IS THE BODY, NOT THE PLACEMENT** — measured, and a deviation
from §11's own reading, which says "the bodies that share one object" but
then states the span law and the pad union as if a PLACEMENT were the
group.  At the owner's own site that reading does not survive contact
with the pack: Aerosoft LEMD authors hundreds of unrelated structures
into ONE placement file, so at placement level ``OldTerminal_FSX-LEMD38``
is a group spanning **2,654 m** with **48.90 m** of authored relief, and
``LEMD84`` / ``LEMD60`` — groups of a single placement — span 1,481 m and
1,003 m.  A pad over that union, levelled to one level, is not a terrain
the owner asked for; and under §11 (4)'s 150 m span law *eight of LEMD's
nine placement-level groups come out LONG and therefore RELEASABLE*,
including the canopy clusters 11i exists to keep connected.  Read at BODY
level — the intra-placement ε-contact component, which is what §9's split
writes a file for and what ``seat_feet_census`` measures a row of — the
same site reads 0–180 m spans and the span law separates exactly what the
owner described.  So the body is the unit here, and the spec's §11 (2)/(4)
should be read with "group" = a set of BODIES.

**ONE DERIVATION, MANY READERS** (§11 (3), and the consumer-census ruling
08-30l).  ``emit/abutment_group.groups`` (the seat path), the placement
plan and the pad law must all read THE SAME grouping; a second derivation
of "which bodies are one object" is the census-wrapper defect in
geometry.  The bodies themselves are ``airport/placement_plan._bodies_of``
— imported, never re-implemented.

**THE LONG SPAN** (§11 (4)).  A group whose plan span exceeds
``[placement] group_span_max_m`` (per airport in ``airports.toml`` where
needed) is the HECA railway class: where its pad turns out infeasible the
connecting deck is RELEASED — its own object at its own low-side foot,
and the buildings seat on their own pads.  A SHORT infeasible group is
never split; it is reported with its residual and the owner rules per
case.  This module states the span and the verdict; the feasibility
reading belongs to the pad law, which is the only thing that knows
whether the adapted surface stayed lawful.

No mesh, no environment, no shapely: the plan and the law, in and out.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

from ..model.ground_fit import GroundFit, ground_fit
from ..model.rebake import Member, Part, RebakePlan

__all__ = ["Foot", "Group", "GroupSet", "derive", "bodies_of_plan", "BODY_KEY"]

#: A body's address inside a plan: ``(unit index, member index, body
#: index)`` — the member half is the placement the body was cut from.
BODY_KEY = _t.Tuple[int, int, int]

#: metres per degree of latitude.  The plan's coordinates are degrees and
#: the spans here are metres; the same two lines ``airport/anchor_rule``
#: uses, and for the same reason (no pyproj in a law-shaped module).
_M_PER_DEG_LAT = 111_132.0


def _m_per_deg(lat: float) -> tuple[float, float]:
    return _M_PER_DEG_LAT, _M_PER_DEG_LAT * math.cos(math.radians(lat))


@_dc.dataclass(frozen=True)
class Foot:
    """One ground-contact vertex of a group: where it stands and the
    AUTHORED ``y`` it stands at.

    ``y`` is read in the member's own authored frame, which is the frame
    the whole group shares — §17's abutment test is lawful only inside one
    ANCHOR PLANE (one ``Unit``), so every member of a group carries the
    same ``anchor_z + agl`` and their authored ``y`` values are directly
    comparable.  That is what makes ``y - y_zero`` a RELIEF the terrain
    can be asked to reproduce (§11 (2)) rather than two packs' private
    zeros compared by accident."""

    lat: float
    lon: float
    y: float


@_dc.dataclass(frozen=True)
class Group:
    """One object: its bodies, its senior, its feet and its span."""

    #: a stable name: the senior body's own address, spelled the way the
    #: split writer names a file
    gid: str
    #: every body of the group, senior first
    bodies: tuple[BODY_KEY, ...]
    senior: BODY_KEY
    #: the group's own zero: the senior body's LOWEST ground-contact
    #: ``y``.  The terrain target under a foot is ``level + (y - y_zero)``
    #: (§11 (2)), so the level is the height of the senior's own low side
    #: and a flat-footed group asks for a flat pad exactly as today.
    y_zero: float
    feet: tuple[Foot, ...]
    #: the plan diagonal of the group's footprint, metres
    span_m: float
    #: the group joins two PLACEMENTS (a canopy and its building), as
    #: against one placement's own separated bodies
    cross_placement: bool
    #: the span exceeds ``[placement] group_span_max_m`` — the HECA
    #: railway class, the only group a failed feasibility may RELEASE
    long_span: bool
    #: the junior bodies a release would let go (the elevated decks); a
    #: single-body group has none and can never be released
    releasable: tuple[BODY_KEY, ...] = ()
    #: THE SPAN LAW IS PER BODY (owner RULINGS 2026-09-11j; spec §11a (1)):
    #: every body's OWN plan diagonal, in ``bodies`` order.  The group's
    #: ``span_m`` is a report figure; what ``group_span_max_m`` binds is a
    #: CONNECTING body's own span — a canopy module 60 m long joining a
    #: terminal is never the HECA railway, however far apart the two
    #: buildings' far corners stand.
    body_span_m: tuple[float, ...] = ()
    #: THE FEASIBILITY VERDICT (§11 (4)): the worst slope the group's own
    #: relief target asks of the terrain between two of its feet, as a
    #: fraction.  A group over ``pad_slope_max`` is INFEASIBLE — its pad
    #: cannot carry the authored relief and stay a lawful surface.
    relief_slope: float = 0.0
    #: the group is INFEASIBLE.  A LONG connecting body then RELEASES
    #: (§11 (4)); a short one is REPORTED with its residual and never
    #: split (11i).
    #:
    #: THE VERDICT NOW PRICES THE DEM'S FALL (owner RULINGS 2026-09-11q,
    #: amended 11x (2); spec §11b (3)), not the authored relief alone:
    #: with a ``dem_at`` sampler :func:`derive` fits the body's level to
    #: the ground under its feet (:func:`ground_fit`) and the verdict is
    #: read between NEIGHBOURING feet — ``|(target_a - target_b) -
    #: (dem_a - dem_b)|`` against ``bank_slope`` x their own spacing, the
    #: fall the sheet actually has to make between two rows.  So a body
    #: whose authored relief MATCHES the ground's fall is feasible at
    #: zero cost however steep both are, and one that fights the ground
    #: is infeasible however gentle it is.
    #: Without a sampler the pre-11q reading stands (``relief_slope``
    #: over ``pad_slope_max``), which is what every caller that has no
    #: DEM — the twins, the dry-run readers — still gets.
    infeasible: bool = False
    #: the fitted level and its worst residual where a DEM was sampled
    #: (``None`` / 0.0 otherwise) — the numbers the report quotes and
    #: ``constraints/foot_rows.py`` re-derives over the GROUND-CONTACT
    #: subset of the same feet.
    fit_level: float | None = None
    fit_residual_m: float = 0.0
    fit_limit_m: float = 0.0
    #: EVERY BODY'S OWN COMPONENTS, ``(unit, member, (comp, ...))`` in
    #: ``bodies`` order — the address ``classify/evidence._body_pads``
    #: reads the body's PLAN FOOTPRINT at (``airport/skirt.
    #: component_footprint``; spec §11a (3), measured round 5).  The pad
    #: of a body the OSM does not know is that footprint, so the group
    #: must carry which components the body is made of; nothing else here
    #: reads it.
    body_comps: tuple[tuple[int, int, tuple[int, ...]], ...] = ()
    #: the junior bodies actually RELEASED — long AND infeasible.  They
    #: are no longer members of this group; each is its own object at its
    #: own low-side foot (§6 deck row superseded, 10ay).
    released: tuple[BODY_KEY, ...] = ()

    @property
    def relief_m(self) -> float:
        """The authored relief the terrain is asked to carry — the spread
        of ``y`` over the group's feet.  Zero for the common case (every
        foot authored on the object's own zero), and the number the owner
        reads when a group's pad turns out infeasible."""
        if not self.feet:
            return 0.0
        ys = [f.y for f in self.feet]
        return float(max(ys) - min(ys))

    def target_at(self, lat: float, lon: float, level: float,
                  radius_m: float) -> float | None:
        """§11 (2)'s per-foot target read anywhere on the pad: ``level +
        (y_foot - y_zero)`` of the NEAREST foot within ``radius_m``,
        ``None`` where no foot is that close.

        Nearest, not interpolated: the object's own ground contacts are
        the only places the terrain is CONSTRAINED to a value, and an
        interpolation between two feet 40 m apart would invent a slope the
        object never authored.  Outside every foot's radius the pad has no
        target of its own and keeps the level — which is exactly today's
        flat pad."""
        if not self.feet:
            return None
        ml, mo = _m_per_deg(lat)
        best: Foot | None = None
        best_d2 = radius_m * radius_m
        for f in self.feet:
            d2 = ((f.lat - lat) * ml) ** 2 + ((f.lon - lon) * mo) ** 2
            if d2 <= best_d2:
                best_d2 = d2
                best = f
        if best is None:
            return None
        return level + (best.y - self.y_zero)


@_dc.dataclass(frozen=True)
class GroupSet:
    """Every group of a plan, plus the index every consumer reads it by."""

    groups: tuple[Group, ...]
    #: ``body key -> group index``
    of_body: _t.Mapping[BODY_KEY, int]
    counts: _t.Mapping[str, int]

    def group_of(self, key: BODY_KEY) -> Group | None:
        i = self.of_body.get(key)
        return None if i is None else self.groups[i]

    def to_dict(self) -> dict[str, _t.Any]:
        return {"counts": dict(self.counts),
                "groups": [{"gid": g.gid, "senior": list(g.senior),
                            "bodies": [list(b) for b in g.bodies],
                            "y_zero": round(g.y_zero, 3),
                            "feet": len(g.feet),
                            "relief_m": round(g.relief_m, 3),
                            "span_m": round(g.span_m, 1),
                            "body_span_m": [round(v, 1) for v in g.body_span_m],
                            "cross_placement": g.cross_placement,
                            "long_span": g.long_span,
                            "relief_slope": round(g.relief_slope, 5),
                            "infeasible": g.infeasible,
                            "released": [list(b) for b in g.released],
                            "releasable": [list(b) for b in g.releasable]}
                           for g in self.groups]}


# ── the bodies (imported, never re-implemented) ──────────────────────────

def bodies_of_plan(plan: "RebakePlan | _t.Any"
                   ) -> tuple[dict[BODY_KEY, tuple[int, ...]], dict[int, BODY_KEY]]:
    """``(body -> its part ids, part id -> its body)`` over the whole
    plan — §9's own body law, the intra-placement ε-contact component.

    THE DERIVATION MOVED to ``airport.placement_family`` (2026-09-13,
    lane ``v2clusterpad``): §16g's footprint unit needs the same bodies
    at LOAD time, and ``airport`` may not import ``planar`` (the
    layering twin).  Re-exported here because every caller and every
    twin reads it where it always was — one derivation, two names.
    """
    from ..airport.placement_family import bodies_of_plan as _b
    return _b(plan)


# ── the derivation ───────────────────────────────────────────────────────

def _feet_of(parts: _t.Sequence[Part]) -> list[Foot]:
    out: list[Foot] = []
    for p in parts:
        if p.feet:
            out.extend(Foot(float(a), float(b), float(y)) for a, b, y in p.feet)
        else:
            out.append(Foot(float(p.lat), float(p.lon), float(p.base_y)))
    return out


def _relief_slope(feet: _t.Sequence[Foot]) -> float:
    """THE FEASIBILITY READING (§11 (4)): the worst slope the per-foot
    relief target asks of the terrain, ``max |y_i - y_j| / d_ij`` over the
    group's own feet.

    A flat-footed body reads 0 and is always feasible — the common case
    and today's law.  A body whose authored relief needs a steeper rise
    between two contacts than a pad may carry is one the terrain CANNOT
    adapt to; §11 (4) then releases a LONG connecting body and reports a
    short one.  Over pairs, never over the extremes alone: two feet 2 m
    apart with 1 m between them is the infeasibility, and the group's
    outer diagonal would hide it."""
    n = len(feet)
    if n < 2:
        return 0.0
    ml, mo = _m_per_deg(sum(f.lat for f in feet) / n)
    worst = 0.0
    # over a decimated set when the body is large: the worst pair of a
    # well-spread subset plus every consecutive pair, the pad law's own
    # ``_pairs`` reasoning (a fan of small steps still shows up)
    ix = range(n) if n <= _MAX_FEET_PAIRWISE else range(0, n, max(
        1, n // _MAX_FEET_PAIRWISE))
    sub = [feet[i] for i in ix]
    for i, a in enumerate(sub):
        for b in sub[i + 1:]:
            d = math.hypot((a.lat - b.lat) * ml, (a.lon - b.lon) * mo)
            if d > 0.0:
                worst = max(worst, abs(a.y - b.y) / d)
    return worst


#: A body with more feet than this is read over a spread subset: a solver
#: / reader conditioning constant, not a law value.
_MAX_FEET_PAIRWISE = 48


def _span_m(feet: _t.Sequence[Foot]) -> float:
    if len(feet) < 2:
        return 0.0
    lats = [f.lat for f in feet]
    lons = [f.lon for f in feet]
    ml, mo = _m_per_deg(sum(lats) / len(lats))
    return math.hypot((max(lats) - min(lats)) * ml, (max(lons) - min(lons)) * mo)


def _eligible(m: Member) -> bool:
    """A body whose elevation ANOTHER LAW already governs is out of the
    class — ``emit/abutment_group``'s own ``_eligible``, restated at the
    member level: a deck plate at its abutment grade, a tunnel-wall or
    basin-floor plate (14.1 rule 4), and a LINE object, which binds
    nothing (10bb rule 2)."""
    if m.plate_y is not None:
        return False
    if m.deck_ring is not None or m.deck_kind in ("flag", "signature"):
        return False
    if m.parts and all(p.line for p in m.parts):
        return False
    return bool(m.parts)


def _body_comps(keys, bodies, part_of) -> tuple[tuple[int, int, tuple[int, ...]], ...]:
    """``(unit, member, (comp, ...))`` per body, in ``keys`` order — the
    address the pad law reads a body's plan footprint at (``Group.
    body_comps``).  One expression, three construction sites."""
    return tuple((k[0], k[1], tuple(sorted({part_of[q].comp for q in bodies[k]})))
                 for k in keys)


def derive(plan: "RebakePlan | _t.Any", span_max_m: float = 0.0,
           pad_slope_max: float = 0.0,
           dem_at: _t.Callable[[float, float], float | None] | None = None,
           bank_slope: float = 0.0) -> GroupSet:
    """Every group of ``plan`` (module doc).

    ``pad_slope_max`` is ``emit.within_shape.pad_slope_max`` — the hard
    tilt a pad may carry, and so the feasibility test of §11 (4): a group
    whose relief target asks more of the terrain between two of its feet
    is INFEASIBLE.  An infeasible group with a LONG connecting body
    RELEASES it (the HECA railway class); an infeasible SHORT group is
    reported with its residual and never split — 11i is explicit that the
    owner rules those per case.  ``0`` disarms the test (nothing is ever
    infeasible, so nothing is ever released).

    ``dem_at(lat, lon) -> metres | None`` and ``bank_slope`` arm 11q's
    reading of that same verdict: the level is FITTED to the ground under
    the feet (:func:`ground_fit`) and the residual between NEIGHBOURING
    feet (11x (2)) is judged against the bank the terrain may lawfully
    make over their own spacing.  Without a sampler the pre-11q
    reading stands, so every DEM-less caller is unchanged.

    ``span_max_m`` is ``law.tables.group_span_max_m`` — the airport's own
    where it states one; ``0`` disarms the long-span verdict entirely, so
    no release is ever lawful and an infeasible group is always reported.

    THE MEMBERSHIP LAW, unchanged from §17/11a and stated once:

    * abutments are read inside ONE ANCHOR PLANE (a ``Unit``) only — the
      plan's own ``abutments`` already carry that restriction;
    * ACROSS PLACEMENTS one side must be an ELEVATED DECK
      (``Member.elevated_deck``), and only THAT side may be the junior;
    * the junior joins the LARGEST body it abuts, and only when that one
      is strictly larger (a tie is two peers and no group);
    * ONE HOP: a junior never founds a group of its own.

    Every eligible body that joins nothing is STILL a group of one — it
    is one object, its feet are its own, and §11 (2)'s per-foot target is
    the same sentence for it.  That is what makes the group pad the
    general pad law rather than a canopy special case, and it is why the
    site's dominant residual (a single canopy body whose nine column feet
    are authored 2.63 m apart) is inside this law at all.
    """
    bodies, of_pid = bodies_of_plan(plan)
    members: dict[tuple[int, int], Member] = {
        (ui, mi): m for ui, u in enumerate(plan.units) for mi, m in enumerate(u.members)}
    part_of: dict[int, Part] = {p.pid: p for m in members.values() for p in m.parts}

    counts = {"bodies": len(bodies), "abutment_pairs": len(plan.abutments),
              "cross_pairs": 0, "refused_ineligible": 0, "refused_building": 0,
              "refused_peer": 0, "groups": 0, "cross_groups": 0, "long_span": 0,
              "released_candidates": 0, "infeasible": 0, "released": 0,
              "infeasible_short": 0, "relief_bodies": 0}

    area = {k: float(sum(part_of[q].area_m2 for q in ps)) for k, ps in bodies.items()}

    def _verdict(feet: _t.Sequence[Foot], y_zero: float
                 ) -> tuple[float, bool, float | None, float, float]:
        """``(relief_slope, infeasible, fit_level, residual, limit)`` —
        11q's DEM reading where a sampler was given, the pre-11q authored
        reading otherwise (``Group.infeasible``)."""
        slope = _relief_slope(feet)
        if dem_at is None:
            return slope, pad_slope_max > 0.0 and slope > pad_slope_max, None, 0.0, 0.0
        fit = ground_fit(feet, y_zero, dem_at, bank_slope)
        if fit is None:
            return slope, False, None, 0.0, 0.0
        return slope, not fit.feasible, fit.level, fit.residual_m, fit.limit_m

    cross: set[tuple[BODY_KEY, BODY_KEY]] = set()
    for a, b in plan.abutments:
        ba, bb = of_pid.get(a), of_pid.get(b)
        if ba is None or bb is None or ba[:2] == bb[:2]:
            continue                     # same placement: already one file
        ma, mb = members[ba[:2]], members[bb[:2]]
        if not (_eligible(ma) and _eligible(mb)):
            counts["refused_ineligible"] += 1
            continue
        if not (ma.elevated_deck or mb.elevated_deck):
            # BUILDINGS NEVER GROUP WITH BUILDINGS (11a/10i): each seats
            # on its own feet
            counts["refused_building"] += 1
            continue
        cross.add((ba, bb) if ba <= bb else (bb, ba))
    counts["cross_pairs"] = len(cross)

    abuts: dict[BODY_KEY, set[BODY_KEY]] = {}
    for ba, bb in cross:
        abuts.setdefault(ba, set()).add(bb)
        abuts.setdefault(bb, set()).add(ba)

    senior_of: dict[BODY_KEY, BODY_KEY] = {}
    for k in sorted(abuts):
        if not members[k[:2]].elevated_deck:
            continue                     # only a DECK may be a junior
        best = max(sorted(abuts[k]), key=lambda n: (area[n], n))
        if area[best] <= area[k]:
            counts["refused_peer"] += 1
            continue
        senior_of[k] = best

    by_senior: dict[BODY_KEY, list[BODY_KEY]] = {}
    for k, s in sorted(senior_of.items()):
        if s in senior_of:               # ONE HOP: a junior never founds
            continue
        by_senior.setdefault(s, []).append(k)

    groups: list[Group] = []
    seen: set[BODY_KEY] = set()
    for s, juniors in sorted(by_senior.items()):
        keys = (s, *sorted(juniors))
        feet = [f for k in keys for f in _feet_of([part_of[q] for q in bodies[k]])]
        if not feet:
            continue
        senior_feet = _feet_of([part_of[q] for q in bodies[s]])
        y_zero = min(f.y for f in (senior_feet or feet))
        span = _span_m(feet)
        # §11a (1): the span law binds a BODY's connecting span, never the
        # group's footprint diagonal.  Only a junior whose OWN body is long
        # is the HECA railway class, and only it may ever be released.
        bspan = tuple(_span_m(_feet_of([part_of[q] for q in bodies[k]])) for k in keys)
        long_of = {k: (span_max_m > 0.0 and sp > span_max_m)
                   for k, sp in zip(keys, bspan)}
        rel = tuple(k for k in sorted(juniors) if long_of[k])
        long_span = bool(rel)
        slope, infeasible, fit_level, fit_res, fit_lim = _verdict(feet, y_zero)
        released = rel if (infeasible and rel) else ()
        if released:
            # THE LONG SPAN LETS GO (§11 (4)): the released juniors leave
            # the group, and each becomes its own object below.
            keys = tuple(k for k in keys if k not in set(released))
            feet = [f for k in keys for f in _feet_of([part_of[q] for q in bodies[k]])]
            if not feet:
                continue
            bspan = tuple(_span_m(_feet_of([part_of[q] for q in bodies[k]])) for k in keys)
            span = _span_m(feet)
            slope, _inf2, fit_level, fit_res, fit_lim = _verdict(feet, y_zero)
        groups.append(Group(gid=_gid(members[s[:2]], s), bodies=keys, senior=s,
                            y_zero=float(y_zero), feet=tuple(feet), span_m=span,
                            cross_placement=len(keys) > 1, long_span=long_span,
                            releasable=rel, body_span_m=bspan,
                            relief_slope=slope, infeasible=infeasible,
                            fit_level=fit_level, fit_residual_m=fit_res,
                            fit_limit_m=fit_lim,
                            body_comps=_body_comps(keys, bodies, part_of),
                            released=released))
        seen.update(keys)
        counts["long_span"] += int(long_span)
        counts["released_candidates"] += len(rel)
        counts["infeasible"] += int(infeasible)
        counts["released"] += len(released)
        counts["infeasible_short"] += int(infeasible and not rel)
    counts["cross_groups"] = len(groups)

    for k in sorted(bodies):
        if k in seen or not _eligible(members[k[:2]]):
            continue
        feet = _feet_of([part_of[q] for q in bodies[k]])
        if not feet:
            continue
        sp = _span_m(feet)
        y0 = float(min(f.y for f in feet))
        slope, infeasible, fit_level, fit_res, fit_lim = _verdict(feet, y0)
        groups.append(Group(gid=_gid(members[k[:2]], k), bodies=(k,), senior=k,
                            y_zero=y0, feet=tuple(feet),
                            span_m=sp, cross_placement=False,
                            long_span=False, releasable=(), body_span_m=(sp,),
                            body_comps=_body_comps((k,), bodies, part_of),
                            fit_level=fit_level, fit_residual_m=fit_res,
                            fit_limit_m=fit_lim,
                            relief_slope=slope, infeasible=infeasible))
        counts["infeasible"] += int(infeasible)
        counts["infeasible_short"] += int(infeasible)

    # a RELEASED junior is its own object: it never reached ``seen``
    for g in list(groups):
        for k in g.released:
            feet = _feet_of([part_of[q] for q in bodies[k]])
            if not feet or k in seen:
                continue
            sp = _span_m(feet)
            y0 = float(min(f.y for f in feet))
            slope, r_inf, fit_level, fit_res, fit_lim = _verdict(feet, y0)
            groups.append(Group(gid=_gid(members[k[:2]], k), bodies=(k,), senior=k,
                                y_zero=y0, feet=tuple(feet),
                                span_m=sp, cross_placement=False, long_span=True,
                                releasable=(), body_span_m=(sp,),
                                body_comps=_body_comps((k,), bodies, part_of),
                                fit_level=fit_level, fit_residual_m=fit_res,
                                fit_limit_m=fit_lim,
                                infeasible=r_inf, relief_slope=slope))
            seen.add(k)
    counts["relief_bodies"] = sum(1 for g in groups if g.relief_m > 0.0)
    groups.sort(key=lambda g: g.senior)
    of_body: dict[BODY_KEY, int] = {}
    for i, g in enumerate(groups):
        for k in g.bodies:
            of_body[k] = i
    counts["groups"] = len(groups)
    return GroupSet(tuple(groups), of_body, counts)


def _gid(m: Member, key: BODY_KEY) -> str:
    base = m.resource.rsplit("/", 1)[-1]
    if base.endswith(".obj"):
        base = base[:-4]
    return f"{base}#b{key[2]}"
