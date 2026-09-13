"""THE GENERIC ANCHOR RULE (owner RULINGS 2026-09-11e (2); spec
``object-placement-spec.md`` §9, superseding §6's per-class table).

X-Plane places an ``OBJECT`` (AGL) placement's ORIGIN at the design
surface under its anchor.  So the anchor is not a label and not a class:
it is THE FOOTPRINT POINT WHERE THE DESIGN SURFACE EQUALS THE BODY'S
INTENDED ZERO.  In one reading —

    the body's ZERO PLANE, in world height:
        D = median over its ground-contact vertices of (surface(v) - y_v)
    the ANCHOR: the ground-contact vertex v minimising |surface(v) - y_v - D|,
        ties to the vertex whose authored y is nearest the object's zero
    the body's y_zero: that vertex's own authored y

— because anchoring at ``v`` puts the body's authored ``y = y_v`` on the
ground there, i.e. its ``y = 0`` plane at ``surface(v) - y_v``, and every
other foot then renders ``zero(f) - zero(v)`` off its own ground.  So the
vertex whose GROUND IS AT THE OBJECT'S ZERO is the vertex whose reading of
the zero plane IS the body's, and the residual left over is the body's
AUTHORED RELIEF — exactly what 11e (2)'s "authored relief beyond its
skirt" names.  (Scoring ``|surface(v) - D|`` instead — the sentence read
without the vertex's own y — measures a body's SKIRT DEPTH, not its
relief: at LEMD it reported 1,012 of 1,403 bodies as having no point at
their zero because their feet are authored 0.6 m below it.)  It falls out
of nothing but the surface and the authored geometry:

* a PIT object (rim authored at ``y = 0``, floor plate 7 m down over a
  basin cut 7 m down) reads ``D = grade`` from both its rings and anchors
  on its RIM (``|grade - D| = 0``; the floor ring scores 7);
* a TUNNEL object whose zero is its ROAD LEVEL (the floor ring at
  ``y = 0`` over the cut floor, its wall crests 5 m up at grade) reads
  ``D = floor`` and anchors on its FLOOR RING;
* a building on a pad, a skirted building, a fence segment: every foot
  reads the same zero plane, and the tie goes to the foot whose authored
  ``y`` is nearest the object's own zero.

A body with NO such point within ``[placement] split_tol_m`` — authored
relief larger than its skirt, so no single terrain sample describes it —
anchors at its LOW-SIDE FOOT (the ground-contact foot whose design
surface is lowest) and is REPORTED with the residual (11e (2)).  A body
whose surface reads NOWHERE (outside every graded face, where the DEM
governs) is likewise reported, never guessed at.

THE CLASS IS NOW A LABEL.  :func:`classify_body` still names what a body
IS — the report and the census read by class, and 11a's elevated DECK
still takes no anchor of its own (it is merged into the building it
abuts) — but no class picks a different POINT any more: the per-class
table of §6 was the round-1 reading and is superseded.

WHAT IS AND IS NOT A NUMBER HERE
--------------------------------

No law constant lives in this module.  The design surface is read through
one injected callable ``surface(lat, lon) -> z | None``, and the
tolerance ``tol_m`` is passed in by the caller from
``[placement] split_tol_m``.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

__all__ = ["BodyClass", "Anchor", "Datum", "PadRing", "RimRing", "classify_body",
           "anchor_for", "datum_of", "keep_off_row", "rim_of",
           "BUILDING", "SKIRTED", "BASIN", "LINE_SEGMENT", "DECK", "PLATE_ONLY", "OTHER"]

BUILDING = "building"
SKIRTED = "skirted"
BASIN = "basin"
LINE_SEGMENT = "line_segment"
DECK = "deck"
PLATE_ONLY = "plate_only"
OTHER = "other"

BodyClass = str
#: ``surface(lat, lon) -> z | None`` — the design surface, or ``None``
#: where none was graded.
Surface = _t.Callable[[float, float], "float | None"]


@_dc.dataclass(frozen=True)
class PadRing:
    """One emitted object pad: its ``(lat, lon)`` ring and the face ref
    that named it (``building16``)."""

    ref: str
    ring: tuple[tuple[float, float], ...]


@_dc.dataclass(frozen=True)
class RimRing:
    """One emitted ``basin_wall`` / ``structure_rim`` ring."""

    ref: str
    ring: tuple[tuple[float, float], ...]
    #: §14a: the ring's own vertex HEIGHTS, in ring order.  §24 (1) puts
    #: the rim vertices at the APRON's level, so this is not a constant:
    #: LEMD's T4 pit runs 597.68 … 599.52 over its 59 nodes, and the arcs
    #: of ``basin_ring.arcs_of`` are cut on it.  Empty where the caller
    #: read the ring without its heights (every twin that builds a ring
    #: by hand, and the pre-§14a readers) — the arc cut is then not armed
    #: and §14 (2)'s single rim point stands.
    z: tuple[float, ...] = ()


@_dc.dataclass(frozen=True)
class Anchor:
    """Where the body's placement goes and what its zero is."""

    body_class: BodyClass
    lat: float
    lon: float
    y_zero: float
    reason: str
    #: the design surface under the anchor, ``None`` outside every face
    surface_z: float | None = None
    #: the authored-frame offset the split writer subtracts (§4.3)
    offset: tuple[float, float, float] = (0.0, 0.0, 0.0)
    #: §16e: this anchor came from a DATUM (a crest plate, a deck top) —
    #: an authored height the law puts AT the ground at named stations,
    #: not a foot the body stands on.  The keep test reads it: a
    #: one-body placement whose datum moved it off its authored row must
    #: be WRITTEN, and a kept row would put its zero back on the datum
    #: point it was moved off.
    datum: bool = False


# ── geometry helpers (plan, in degrees scaled to metres) ─────────────────

#: metres per degree, MEMOISED at 1e-4 deg of latitude (11 m): the value
#: changes by ~1e-5 m/deg over that, and §16b's cut asks for it three
#: million times per airport (2.6 s of the LEMD plan stage, measured).
_MPD: dict[int, tuple[float, float]] = {}


def _m_per_deg(lat: float) -> tuple[float, float]:
    k = int(lat * 10_000.0)
    hit = _MPD.get(k)
    if hit is None:
        r = math.radians(lat)
        hit = (111_132.954 - 559.822 * math.cos(2 * r)
               + 1.175 * math.cos(4 * r),
               111_412.84 * math.cos(r) - 93.5 * math.cos(3 * r))
        if len(_MPD) > 100_000:
            _MPD.clear()
        _MPD[k] = hit
    return hit


def _inside(ring: _t.Sequence[tuple[float, float]], lat: float, lon: float) -> bool:
    """Ray casting over a ``(lat, lon)`` ring."""
    n = len(ring)
    inside = False
    j = n - 1
    for i in range(n):
        ai, aj = ring[i], ring[j]
        if (ai[0] > lat) != (aj[0] > lat):
            x = ai[1] + (lat - ai[0]) * (aj[1] - ai[1]) / (aj[0] - ai[0])
            if lon < x:
                inside = not inside
        j = i
    return inside


def _pad_of(pads: _t.Sequence[PadRing], lat: float, lon: float) -> PadRing | None:
    for p in pads:
        if len(p.ring) >= 3 and _inside(p.ring, lat, lon):
            return p
    return None


def rim_of(rims: _t.Sequence[RimRing], lat: float, lon: float) -> RimRing | None:
    """The emitted ``structure_rim`` ring this point stands INSIDE, if
    any — the body's OWN ring (§14 (2))."""
    for r in rims:
        if len(r.ring) >= 3 and _inside(r.ring, lat, lon):
            return r
    return None


# ── §16e: THE DATUM (owner RULINGS 2026-09-13k; Fable 2026-09-13n) ───────

@_dc.dataclass(frozen=True)
class Datum:
    """AN AUTHORED HEIGHT THE LAW PUTS AT THE GROUND, AND WHERE IT READS IT.

    §16e's two datums are one rule with two readings, and both were
    already computed and stamped into the plan by the patch half while
    NOTHING in the placement path read them:

    * the CREST PLATE (§16e (1), ``plate_y`` / ``plate_stations``): a
      tunnel wall's top plate is flush with the ground at its wall band
      (``[tunnel.object] plate_datum = "ground"``, RULINGS 2026-09-05n-4).
    * the DECK TOP (§16e (2), ``deck_top_y`` / ``deck_end_stations``): a
      single-layer span over water meets the land at its END LINES
      (R12's abutment reading), and its feet land where they may.

    ``y`` is the AUTHORED y that must meet the ground — for a plate,
    ``plate_y`` less ``plate_clearance_m`` (§24 (2): a basin plate's
    stations lie on the trench floor, which stands that far under it) —
    and ``stations`` the points whose ground it must meet."""

    y: float
    stations: tuple[tuple[float, float], ...]
    label: str


def datum_of(m: _t.Any) -> "Datum | None":
    """§16e: the datum ONE MEMBER carries, or ``None``.

    Read off the plan's own member record by attribute, so that a twin
    can hand in any object with the fields and no model import comes
    into this module.

    THE CREST RULE KEYS ON ``plate_y``, NEVER ON THE BASIN
    CLASSIFICATION (§16e (1)).  ``plate_y <= 0`` is a FLOOR-plate basin —
    LEMD's pits, OTHH's 8 drainage basins — whose zero is its RIM by
    §14 (2), and those are left exactly where they are: the datum here is
    the CREST plate, the ``plate_y > 0`` reading that §5's MSL->AGL
    conversion left standing +5 … +10 m over the rim at OTHH's nine
    tunnel walls.

    THE DECK RULE asks the two conditions §16e (2) names: the ring stands
    over NO graded face (``deck_datum_z`` is ``None`` — a flyover with
    land under its ring is untouched) and the member's components reach
    NO ground within the ring (no part of it carries a foot).  A deck
    with feet is a deck that meets the ground somewhere and the generic
    rule reads it there."""
    plate_y = getattr(m, "plate_y", None)
    if plate_y is not None and float(plate_y) > 0.0:
        st = tuple(getattr(m, "plate_stations", ()) or ())
        if st:
            clear = float(getattr(m, "plate_clearance_m", 0.0) or 0.0)
            return Datum(float(plate_y) - clear, st, "crest plate")
    top = getattr(m, "deck_top_y", None)
    if (top is not None and getattr(m, "deck_datum_z", None) is None
            and getattr(m, "deck_kind", "") in ("flag", "signature")):
        st = tuple(getattr(m, "deck_end_stations", ()) or ())
        if st and not any(getattr(p, "feet", ()) for p in getattr(m, "parts", ())):
            return Datum(float(top), st, "deck top")
    return None


def keep_off_row(z_row: "float | None", anchor: "Anchor | None",
                 tol_m: float) -> bool:
    """§14 / §16e: MUST THIS ONE-BODY PLACEMENT BE WRITTEN rather than
    KEPT on its authored row?

    §14's reading: the keep is admitted only where the row and the anchor
    read the SAME design surface — on a shared-datum row the row IS the
    datum (LEMD: 73 of 104 one-body keeps draped more than 3 m from their
    own anchor's zero).

    §16e adds the case that reading cannot see: a body on a DATUM.  Two
    surfaces agreeing says nothing there — OTHH's `tunnel middle - east`
    reads the same ground at its wall band as at its row — because what
    the keep really asks is whether row and anchor give the body the same
    ZERO, and a datum's ``y_zero`` is +5 … +10 m by construction.  Kept,
    X-Plane drapes the object's ZERO on the ground and its crest stands
    +5 m over it."""
    if anchor is not None and anchor.datum:
        return True
    z_anchor = None if anchor is None else anchor.surface_z
    return (z_row is not None and z_anchor is not None
            and abs(float(z_row) - float(z_anchor)) > tol_m)


def _datum_anchor(body_class: BodyClass, geom: BodyGeometry, surface: Surface,
                  datum: "Datum") -> "Anchor | None":
    """§16e: the body anchored ON ITS DATUM — at the station whose ground
    is the MEDIAN of the datum's stations, with ``y_zero = datum.y``.

    Anchoring there puts the authored height ``datum.y`` on the ground at
    that station, which is what both readings ask for; every other point
    of the body then renders its own authored offset from it, and the
    feet land where they may (§16e (2)).  The median station is the same
    reading the retired seat took (``emit/rebake._plate_reading``: "the
    median of the mesh at the band's stations, land only") expressed as a
    POINT rather than as a delta, because a placement is anchored and
    never re-baked.

    A sample ON WATER IS DISCARDED (R12 amendment 1): water is a mesh
    datum at 0.00 and half of OTHH's Bridge_01 stands over the canal.
    The water bit rides the surface callable (``surface.water``, beside
    ``surface.roles`` / ``surface.many``); a caller that hands none in
    reads every sample as land, which is the old behaviour exactly — no
    reading is no evidence.

    ``None`` where no station reads a surface at all: nothing to anchor
    to, and the generic rule then reads as before."""
    water = getattr(surface, "water", None)
    zs: list[tuple[float, float, float]] = []
    wet = off = 0
    for la, lo in datum.stations:
        z = surface(la, lo)
        if z is None:
            off += 1
            continue
        if water is not None and water(la, lo):
            wet += 1
            continue
        zs.append((float(z), float(la), float(lo)))
    if not zs:
        return None
    zs.sort()
    z, la, lo = zs[len(zs) // 2]
    return Anchor(body_class, la, lo, datum.y,
                  f"§16e {datum.label} datum: the authored y {datum.y:+.2f} at "
                  f"the ground {z:.2f} ({len(zs)} station(s) on land, {wet} on "
                  f"water, {off} off-sheet)", z, datum=True)


# ── the class ────────────────────────────────────────────────────────────

def classify_body(*, skirted: bool, basin_member: bool, line: bool,
                  deck: bool, plate: bool, has_pad: bool) -> BodyClass:
    """§6's class for one body, in the order the spec's own table reads:
    a structure verdict (basin, deck, plate) outranks a shape verdict
    (line, skirt), and a building is a body with a pad and no skirt."""
    if basin_member:
        return BASIN
    if deck:
        return DECK
    if plate:
        return PLATE_ONLY
    if line:
        return LINE_SEGMENT
    if skirted:
        return SKIRTED
    if has_pad:
        return BUILDING
    return OTHER


# ── the anchor ───────────────────────────────────────────────────────────

@_dc.dataclass(frozen=True)
class BodyGeometry:
    """What the rule reads about one body, in one place so the twins can
    build it by hand: per ground-contact component its plan centroid, its
    lowest authored ``y`` and its FEET ``(lat, lon, authored y)``; the
    placement's original anchor; and the body's overall lowest ``y``."""

    parts: tuple[tuple[float, float, float, tuple[tuple[float, float, float], ...]], ...]
    origin_lat: float
    origin_lon: float


def _all_on_rolled(cands: _t.Sequence[tuple[float, float, float, float]],
                   surface: Surface, roles, rolled_on) -> bool:
    """§17: does EVERY ground contact of this body stand on a face the
    aircraft ROLLS on?

    ``roles`` answers ``roles_many(lats, lons)`` with the senior graded
    face role under each point (:class:`placement_boxes.GradedRoles`) and
    ``rolled_on`` is ``law.tables.rolled_on_roles`` — both CARRIED ON THE
    SURFACE SAMPLER (``surface.roles`` / ``surface.rolled_on``, beside
    ``surface.many``) so that no caller between here and the one place
    that builds the sampler has to grow an argument.  A caller with no
    roles reads FALSE and the low-side rule stands: no reading is no
    evidence.

    Asked ONLY in the low-side branch (LEMD: 782 of 11,133 bodies), which
    is what keeps it off the plan stage's critical path."""
    if roles is None:
        roles = getattr(surface, "roles", None)
    if roles is None:
        return False
    if rolled_on is None:
        rolled_on = getattr(surface, "rolled_on", None)
    if not rolled_on or not cands:
        return False
    got = roles.roles_many([c[0] for c in cands], [c[1] for c in cands])
    return all(r in rolled_on for r in got)


def anchor_for(body_class: BodyClass, geom: BodyGeometry, surface: Surface,
               pads: _t.Sequence[PadRing] = (), rims: _t.Sequence[RimRing] = (),
               *, merged_into: str = "", tol_m: float = 0.0,
               roles=None, rolled_on=None, datum: "Datum | None" = None) -> Anchor:
    """THE GENERIC RULE (module doc; 11e (2)) for one body.

    ``geom.parts`` are its ground-contact components
    ``(lat, lon, base_y, feet)``; ``surface`` the design surface;
    ``tol_m`` the admission (``[placement] split_tol_m``) — a body with no
    ground-contact vertex whose surface reads within it of the body's own
    ZERO PLANE anchors at its low-side foot and says so in
    :attr:`Anchor.reason`, carrying the residual.

    ``datum`` is §16e's: a crest plate or a deck top, read FIRST and
    from the member's own stations (:func:`datum_of`,
    :func:`_datum_anchor`).

    ``pads`` are accepted and unused: the per-class table they served is
    superseded.  ``rims`` are WIRED for the BASIN class (§14 (2)): the
    interior of the body's own ring is excluded from its anchor search
    and the anchor goes to the RIM, where the object's zero is
    (:func:`_basin_rim_anchor`).  An 11a DECK is still the one body with
    no anchor of its own (merged into the building it abuts).

    The returned :attr:`Anchor.offset` is ``(0, y_zero, 0)`` in the y axis
    only — the plan half (``anchor_x``, ``anchor_z``) is the AUTHORED
    position of the anchor point, which only the caller holding the
    authored frame can spell, and it fills that in before handing the cut
    to the writer."""
    # §16e: THE DATUM IS READ FIRST, and it needs nothing from the parts:
    # a crest plate and a deck top are heights the law puts AT the ground
    # at stations of their own, and the body's own feet are the thing
    # they are NOT read from.  It outranks the basin branch on purpose —
    # §16e (1) keys on ``plate_y``, never on the classification: OTHH's
    # tunnel walls classify BASIN (they stand inside their own emitted
    # ``tunnel_wall`` ring) and §14 (2)'s rim anchor, written for a floor
    # plate authored -depth, stood their crests +5 … +20 m over the rim.
    if datum is not None and datum.stations:
        a = _datum_anchor(body_class, geom, surface, datum)
        if a is not None:
            return a
    if not geom.parts:
        return Anchor(body_class, geom.origin_lat, geom.origin_lon, 0.0,
                      "no ground-contact component: the placement's own anchor",
                      surface(geom.origin_lat, geom.origin_lon))
    if body_class == DECK:
        z = surface(geom.origin_lat, geom.origin_lon)
        return Anchor(DECK, geom.origin_lat, geom.origin_lon, 0.0,
                      f"kerb (merged into {merged_into or 'the abutting building'})", z)
    if body_class == BASIN and rims:
        a = _basin_rim_anchor(geom, surface, rims)
        if a is not None:
            return a

    # every GROUND-CONTACT VERTEX of the body (a part with no feet stands
    # in for itself at its own base), read against the design surface
    cands: list[tuple[float, float, float, float]] = []
    for la, lo, base_y, feet in geom.parts:
        for f in (feet or ((la, lo, base_y),)):
            z = surface(f[0], f[1])
            if z is not None:
                cands.append((float(f[0]), float(f[1]), float(f[2]), float(z)))
    if not cands:
        la, lo, y = _lowest_part(geom)
        return Anchor(body_class, la, lo, y,
                      "no design surface under any foot: the lowest component",
                      None)
    # the body's ZERO PLANE in world height, and the vertex whose GROUND
    # is at it.  The tie (a body every foot of which reads the same plane
    # — the common case) goes to the foot whose authored y is nearest the
    # object's own zero, then to the southern/western one, so the rule is
    # deterministic over a pack.
    zero = _median(tuple(z - y for _la, _lo, y, z in cands))
    best = min(cands, key=lambda c: (round(abs(c[3] - c[2] - zero), 6),
                                     round(abs(c[2]), 6), c[0], c[1]))
    # THE RESIDUAL IS THE ZERO-PLANE SPREAD -- "TERRAIN SPREAD", never
    # "authored relief" ((E), owner RULINGS 2026-09-12ap).  It is the
    # spread of ``surface(foot) - authored y`` over the body's ground
    # contacts: what the DESIGN SURFACE does under a body whose own feet
    # are a rigid frame.  A body authored dead flat on a 1 m slope has a
    # 1 m residual and no authored relief at all, and printing it as the
    # model's relief sent 12ao's own attribution table the wrong way.
    # THE RESIDUAL IS THE BODY'S OWN SPREAD, not the anchor's distance to
    # the median: with an odd number of ground contacts some vertex always
    # attains the median exactly, so "the minimum is above the tolerance"
    # would fire on nothing but even counts.  What 11e (2) names — "no
    # such point ... (authored relief beyond its skirt)" — is a body that
    # has no ONE zero plane: some ground contact stands further than
    # ``tol_m`` from the anchor's.
    z_best = best[3] - best[2]
    residual = max(abs(z - y - z_best) for _la, _lo, y, z in cands)
    if tol_m > 0.0 and residual > tol_m:
        # §17 / owner RULINGS 2026-09-12am (2): A BODY WHOSE EVERY FOOT
        # STANDS ON ROLLED-ON PAVEMENT KEEPS THE MEDIAN.  The low-side
        # foot buys ZERO FLOAT at the low corner and pays the body's whole
        # relief as float at the high one; where the aircraft rolls, the
        # bar is 0.05 m and the pavement is graded flat to 1.5 %, so the
        # relief is small and SHARED: 5 cm of burial one side and 5 cm of
        # float the other reads better than 10 cm of float on the high
        # side.  Measured on the 1.0.320 LEMD frame before adopting
        # (§17 MEASURED): over the 309 bodies whose feet all stand on
        # pavement, the worst foot per body summed 168.8 -> 123.7 m.
        # Off pavement the low-side rule stands unchanged — 11e (2)'s
        # reading, where the eye and not the wheel is the judge.
        if _all_on_rolled(cands, surface, roles, rolled_on):
            return Anchor(body_class, best[0], best[1], best[2],
                          f"median foot: every foot on rolled-on pavement "
                          f"(§17, motion; terrain spread {residual:.2f} m)",
                          best[3])
        # 11e (2): authored relief beyond the body's skirt — no point on
        # the footprint stands where the surface equals the zero
        low = min(cands, key=lambda c: (c[3], c[2], c[0], c[1]))
        return Anchor(body_class, low[0], low[1], low[2],
                      f"low-side foot (no point within {tol_m:g} m of the body's "
                      f"zero plane: terrain spread {residual:.2f} m)", low[3])
    return Anchor(body_class, best[0], best[1], best[2],
                  "surface at the body's zero", best[3])


def _basin_rim_anchor(geom: BodyGeometry, surface: Surface,
                      rims: _t.Sequence[RimRing]) -> Anchor | None:
    """§6's BASIN row, WIRED (§14 (2); the ``rims`` argument was accepted
    and unused until 11v attributed the owner's "seated too low" read to
    exactly that).

    A basin object's zero IS THE RIM: the pit is cut to the object's own
    depth (10ba), its floor plate is authored ``-depth`` and its parapet
    ``+2.99``, and the wall must stand ABOVE the apron it rings.  Every
    ground-contact vertex the generic rule can see stands INSIDE the
    trench, on the floor — so the generic rule anchors the object down
    there and the parapet lands BELOW the rim (measured at LEMD: 1.35 m
    below for ``LEMD37`` b1).  The interior of the body's OWN ring is
    therefore excluded from the anchor search, and the anchor is the
    emitted rim ring's vertex nearest the body in plan, with
    ``y_zero = 0``: the object's own zero goes at the rim, its floor
    plate ``depth`` below it and its parapet its authored height above.

    ``None`` when the body stands inside no emitted ring — nothing to
    anchor to, and the generic rule then reads as before."""
    lowest = min(geom.parts, key=lambda q: q[2])
    ring = rim_of(rims, lowest[0], lowest[1])
    if ring is None:
        return None
    # §6 reads the rim vertex "nearest the ORIGINAL anchor" — the
    # placement's own row point, not the body's centroid — and that is
    # what makes a basin authored as SEVERAL resources on one row take
    # ONE zero: LEMD's pit is `Ground-FSX-LEMD36`, `-LEMD37` and
    # `T4STower-SWbaume`, and the emitted ring is not level (597.14 to
    # 597.86), so a per-body nearest vertex gave the three files three
    # zeros 0.49 m apart.  One row, one rim vertex, one zero.
    clat, clon = geom.origin_lat, geom.origin_lon
    ml, mo = _m_per_deg(clat)
    la, lo = min(ring.ring,
                 key=lambda v: (round(((v[0] - clat) * ml) ** 2
                                      + ((v[1] - clon) * mo) ** 2, 6), v[0], v[1]))
    return Anchor(BASIN, la, lo, 0.0,
                  f"basin rim ({ring.ref}): the object's zero is the rim",
                  surface(la, lo))


def _median(xs: _t.Sequence[float]) -> float:
    q = sorted(xs)
    n = len(q)
    return q[n // 2] if n % 2 else 0.5 * (q[n // 2 - 1] + q[n // 2])


def _lowest_part(geom: BodyGeometry) -> tuple[float, float, float]:
    p = min(geom.parts, key=lambda q: q[2])
    return p[0], p[1], p[2]
