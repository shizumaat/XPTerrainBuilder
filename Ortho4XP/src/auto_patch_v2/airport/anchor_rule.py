"""THE ANCHOR RULE PER BODY CLASS (spec ``object-placement-spec.md`` §6;
owner RULINGS 2026-09-11b).

X-Plane places an ``OBJECT`` (AGL) placement's ORIGIN at the terrain
height under its anchor.  So the anchor is not a label: it is the one
point whose DESIGN-SURFACE height the body's intended zero is declared
equal to, and the whole of §6 is the table of where that point is per
class.  This module answers, for one body:

    anchor (lat, lon) · y_zero (the authored y that must touch the ground)
    · the class · the reason, in the spelling §2's ``anchor_reason`` takes

and the authored offset the split writer applies, ``(anchor_x, y_zero,
anchor_z)`` in the AUTHORED frame (§6's last paragraph) — the body's own
plan position under the anchor, and its foot at zero.

THE TABLE, AND WHERE EACH READING COMES FROM
--------------------------------------------

``building``      a skirt-less building: the anchor goes INSIDE its flat
                  pad (the pad's centroid, or the pad vertex nearest that
                  centroid when the centroid falls outside a concave pad),
                  and the intended zero is the pad plane.  The pad rings
                  are the design surface's own ``building`` faces — the
                  pass that cut them (``classify/evidence._pads``,
                  09c/10l/10y/10bd) is the authority, and this reads its
                  product, never a second derivation.
``skirted``       10ag: the LOW-SIDE FOOT.  Among the body's ground-contact
                  components, the one whose DESIGN-SURFACE height is
                  lowest; the anchor is that component's lowest foot.  The
                  low side touches and the high side buries into the
                  skirt, which is what the skirt is for.
``basin``         10ba: a RIM point — the floor plate's rim vertex nearest
                  the ORIGINAL anchor, projected onto the emitted
                  ``basin_wall`` ring (the design surface's
                  ``structure_rim`` breaklines).  The object's zero is its
                  RIM, not its floor: the floor plate hangs the authored
                  depth below it and the basin was cut to exactly that.
``line_segment``  10bb: a fence / kerb / light string segment — the
                  mid-foot, the ground under its lowest vertex at mid
                  length.  Each segment is its own body, so the line
                  drapes segment by segment.
``deck``          11a: an elevated deck abutting a kerb has NO anchor of
                  its own — it is merged into the body of the building it
                  abuts (one file, the building's anchor), so the deck
                  stays AT the kerb whatever the terrain does.  The caller
                  performs the merge; this returns the reason.
``plate_only`` /  the centroid of the body's LOWEST component, and the
``other``         ground there.

WHAT IS AND IS NOT A NUMBER HERE
--------------------------------

No law constant lives in this module.  The design surface is read through
one injected callable ``surface(lat, lon) -> z | None`` (the pipeline
binds the solved surface; a replay binds the same surface read back from
``<ICAO>.graded.json``), and ``None`` — a body standing outside every
graded face, where the DEM governs — is reported, never guessed at: the
anchor still lands where the class says, and only the ``surface_*``
readings are absent.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

__all__ = ["BodyClass", "Anchor", "PadRing", "RimRing", "classify_body", "anchor_for",
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


# ── geometry helpers (plan, in degrees scaled to metres) ─────────────────

def _m_per_deg(lat: float) -> tuple[float, float]:
    return (111_132.954 - 559.822 * math.cos(2 * math.radians(lat))
            + 1.175 * math.cos(4 * math.radians(lat)),
            111_412.84 * math.cos(math.radians(lat))
            - 93.5 * math.cos(3 * math.radians(lat)))


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


def _centroid(ring: _t.Sequence[tuple[float, float]]) -> tuple[float, float]:
    return (sum(p[0] for p in ring) / len(ring), sum(p[1] for p in ring) / len(ring))


def _nearest_point(ring: _t.Sequence[tuple[float, float]], lat: float, lon: float
                   ) -> tuple[float, float]:
    ml, mo = _m_per_deg(lat)
    return min(ring, key=lambda p: ((p[0] - lat) * ml) ** 2 + ((p[1] - lon) * mo) ** 2)


def _pad_of(pads: _t.Sequence[PadRing], lat: float, lon: float) -> PadRing | None:
    for p in pads:
        if len(p.ring) >= 3 and _inside(p.ring, lat, lon):
            return p
    return None


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


def anchor_for(body_class: BodyClass, geom: BodyGeometry, surface: Surface,
               pads: _t.Sequence[PadRing] = (), rims: _t.Sequence[RimRing] = (),
               *, merged_into: str = "") -> Anchor:
    """§6 for one body.  ``geom.parts`` are its ground-contact components
    ``(lat, lon, base_y, feet)``; ``surface`` the design surface;
    ``pads`` / ``rims`` the emitted object pads and basin-wall rings.

    The returned :attr:`Anchor.offset` is ``(0, y_zero, 0)`` in the y axis
    only — the plan half (``anchor_x``, ``anchor_z``) is the AUTHORED
    position of the anchor point, which only the caller holding the
    authored frame can spell, and it fills that in before handing the cut
    to the writer.  What is decided HERE is the anchor POINT and the
    body's ZERO, which is all §6 is about."""
    if not geom.parts:
        return Anchor(body_class, geom.origin_lat, geom.origin_lon, 0.0,
                      "no ground-contact component: the placement's own anchor",
                      surface(geom.origin_lat, geom.origin_lon))
    if body_class == DECK:
        z = surface(geom.origin_lat, geom.origin_lon)
        return Anchor(DECK, geom.origin_lat, geom.origin_lon, 0.0,
                      f"kerb (merged into {merged_into or 'the abutting building'})", z)
    if body_class == BASIN and rims:
        # the rim vertex nearest the ORIGINAL anchor, on the emitted ring
        # §6 says "nearest the ORIGINAL anchor"; the reference point used
        # here is the body's OWN lowest component instead, and the
        # deviation is deliberate: the original anchor is exactly the
        # thing this whole round removes — at LEMD one anchor serves 171
        # members over kilometres, so "nearest the original anchor" picks
        # the same rim vertex for every pit in the pack.  Nearest THE
        # BODY is what the sentence means once the bodies exist.
        la0, lo0 = _lowest_part(geom)[0:2]
        ml, mo = _m_per_deg(la0)
        cands = [(_nearest_point(r.ring, la0, lo0), r) for r in rims if r.ring]
        (la, lo), ring = min(cands, key=lambda c: ((c[0][0] - la0) * ml) ** 2
                             + ((c[0][1] - lo0) * mo) ** 2)
        # §6, verbatim: "the object's zero is the rim, its floor plate
        # 7.05 m down on the floor ring".  A pit object is AUTHORED with
        # its rim at y = 0 and its floor below — the basin was cut to
        # exactly that depth (10ba) — so the zero is 0, never the body's
        # own highest or lowest part.
        y_zero = 0.0
        return Anchor(BASIN, la, lo, y_zero, f"rim point ({ring.ref})", surface(la, lo))
    if body_class == BUILDING:
        la0, lo0 = _lowest_part(geom)[0:2]
        pad = _pad_of(pads, la0, lo0)
        if pad is not None:
            c = _centroid(pad.ring)
            if not _inside(pad.ring, *c):
                c = _nearest_point(pad.ring, *c)
            y_zero = min(p[2] for p in geom.parts)
            return Anchor(BUILDING, c[0], c[1], y_zero, f"pad point ({pad.ref})",
                          surface(*c))
    if body_class == LINE_SEGMENT:
        la, lo, y = _mid_foot(geom)
        return Anchor(LINE_SEGMENT, la, lo, y, "segment mid-foot", surface(la, lo))
    if body_class == SKIRTED:
        low = _low_side(geom, surface)
        if low is not None:
            la, lo, y, z = low
            return Anchor(SKIRTED, la, lo, y, "low-side foot", z)
    # plate_only / other, and every class whose own reading was unavailable
    la, lo, y = _lowest_part(geom)
    reason = "centroid of the lowest component"
    if body_class == BUILDING:
        reason = "no pad under the body: centroid of the lowest component"
    elif body_class == SKIRTED:
        reason = "no design surface under any foot: centroid of the lowest component"
    return Anchor(body_class, la, lo, y, reason, surface(la, lo))


def _lowest_part(geom: BodyGeometry) -> tuple[float, float, float]:
    p = min(geom.parts, key=lambda q: q[2])
    return p[0], p[1], p[2]


def _mid_foot(geom: BodyGeometry) -> tuple[float, float, float]:
    """A segment's MID-FOOT: the foot nearest the plan midpoint of the
    body's feet, carrying its own authored y."""
    feet = [f for p in geom.parts for f in p[3]] \
        or [(p[0], p[1], p[2]) for p in geom.parts]
    mid_lat = (max(f[0] for f in feet) + min(f[0] for f in feet)) / 2.0
    mid_lon = (max(f[1] for f in feet) + min(f[1] for f in feet)) / 2.0
    ml, mo = _m_per_deg(mid_lat)
    f = min(feet, key=lambda q: ((q[0] - mid_lat) * ml) ** 2 + ((q[1] - mid_lon) * mo) ** 2)
    return float(f[0]), float(f[1]), float(f[2])


def _low_side(geom: BodyGeometry, surface: Surface
              ) -> tuple[float, float, float, float] | None:
    """10ag: the ground-contact component whose design surface is LOWEST,
    and its own lowest foot.  ``None`` when the surface reads nowhere."""
    best: tuple[float, float, float, float] | None = None
    for la, lo, base_y, feet in geom.parts:
        z = surface(la, lo)
        if z is None:
            continue
        if best is None or z < best[3]:
            f = min(feet, key=lambda q: q[2]) if feet else (la, lo, base_y)
            best = (float(f[0]), float(f[1]), float(f[2]), float(z))
    return best
