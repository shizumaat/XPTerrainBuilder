"""A ROAD OVERPASS MEETS THE GROUND AT ITS END LINES (#1214 round 3, R4;
owner RULINGS 2026-10-22m, 2026-10-22p).

Round 2 read each end's APPROACH as the highest land on a landward walk,
which picks a rise beyond the end rather than the road the deck meets:
KMCI ``road-bridge-6`` and ``-10`` floated 5-7 m and 2 m at both ends.
This module reads the ground AT each end line: the median of the end
line's land stations, taken over the stations on a mapped ROAD ribbon
(the design surface's road roles) when most of them lie on one, else over
all of them (the mesh).  The deck is seated FLUSH at the end nearer its
ground — the higher of the two, so the other end floats and never buries
(22m: "the still floating side, the terrain must grade up") — and the
other end's gap is the terrain's to close (#1138, held), listed by the
census and never chased here.

22p (Q118, owner 2026-10-23T01:18:55Z, "A"): a bridge whose end lines
show NO embankment — the road was graded flat on both sides — keeps its
AUTHORED CLEARANCE: the author's zero at his ``OBJECT_AGL`` over the
ground at the placement anchor, the road the bridge spans.  Its end gaps
are listed for #1138 and never chased.

THE EMBANKMENT WITNESS is geometry only: an end shows one when its ground
rises above the ground at the anchor by at least :data:`EMBANKMENT_SHARE`
of the authored clearance (the deck top's height over that ground) — the
midpoint between an approach at the road's level (no rise) and one at the
deck's (the full clearance).
"""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

__all__ = ["EMBANKMENT_SHARE", "ApproachSeat", "approach_seat"]

#: an end line whose ground rises at least this share of the authored
#: clearance over the anchor's ground is an embankment (the midpoint of
#: "at the road below" and "at the deck")
EMBANKMENT_SHARE = 0.5

Surface = _t.Callable[[float, float], "float | None"]


@_dc.dataclass(frozen=True)
class ApproachSeat:
    """Where a free-standing deck's zero goes: the anchor point
    ``(lat, lon)`` with the ground ``surface_z`` there, the world height
    of the authored ``y = 0`` (``zero``), and the reading."""

    lat: float
    lon: float
    surface_z: float
    zero: float
    reason: str
    #: the ground read at each end line, in end order
    ends: tuple[float, ...]


def _median(xs: _t.Sequence[float]) -> float:
    s = sorted(xs)
    return s[len(s) // 2]


def end_ground(line: _t.Sequence[tuple[float, float]], surface: Surface,
               water: _t.Any = None) -> "tuple[float, str] | None":
    """``(ground, source)`` at one end line's stations, or ``None`` where
    none reads land.  ``source`` is ``"road"`` when most land stations lie
    on a road face of the design surface (``surface.roles``), whose
    stations alone are read; else ``"mesh"``."""
    from ..model.planar import ROAD_ROLES
    kept = []
    for la, lo in line:
        z = surface(la, lo)
        if z is None or (water is not None and water(la, lo)):
            continue
        kept.append((float(z), float(la), float(lo)))
    if not kept:
        return None
    roles = getattr(surface, "roles", None)
    if roles is not None:
        got = roles.roles_many([q[1] for q in kept], [q[2] for q in kept])
        road = [q[0] for q, r in zip(kept, got, strict=True) if r in ROAD_ROLES]
        if 2 * len(road) > len(kept):
            return _median(road), "road"
    return _median([q[0] for q in kept]), "mesh"


def approach_seat(datum: _t.Any, surface: Surface, *,
                  origin: "tuple[float, float] | None" = None,
                  authored_agl_m: "float | None" = None) -> "ApproachSeat | None":
    """The seat of a deck carrying two END LINES (``datum.ends``, sampled
    at ``datum.step_m``), or ``None`` where the ends are not armed, an end
    reads no land or an end line touches water (§16e (2)/(6)'s station
    reading and its landward walk then stand).

    ``origin`` / ``authored_agl_m``: the placement anchor and its
    ``OBJECT_AGL`` lift — the authored clearance 22p keeps."""
    if len(getattr(datum, "ends", ()) or ()) < 2 or datum.step_m <= 0.0:
        return None
    from .rebake_plan import end_line_stations
    water = getattr(surface, "water", None)
    reads = []
    for a, b in datum.ends:
        line = end_line_stations([(a, b)], datum.step_m)
        if water is not None and any(water(la, lo) for la, lo in line):
            # an end line on a BANK: a span over water is no road
            # overpass, and §16e (6)'s landward walk (RULINGS 2026-09-13v,
            # OTHH's canal bridges) reads where it meets the graded road
            return None
        g = end_ground(line, surface, water)
        if g is None:
            return None
        mid = (0.5 * (a[0] + b[0]), 0.5 * (a[1] + b[1]))
        reads.append((g[0], g[1], mid))
    z_ends = tuple(r[0] for r in reads)
    ends_txt = " / ".join(f"{z:.2f} ({s})" for z, s, _m in reads)
    g0 = None if origin is None else surface(origin[0], origin[1])
    if g0 is not None and water is not None and water(origin[0], origin[1]):
        g0 = None             # a span over water has no road under it
    lift = float(authored_agl_m or 0.0)
    clearance = lift + float(datum.y)
    if g0 is not None and clearance > 0.0 and not any(
            z - float(g0) >= EMBANKMENT_SHARE * clearance for z in z_ends):
        return ApproachSeat(
            float(origin[0]), float(origin[1]), float(g0), float(g0) + lift,
            f"§16e {datum.label}: no embankment at either end line "
            f"({ends_txt}; the road under it {float(g0):.2f}) — the authored "
            f"clearance {clearance:.2f} m kept (RULINGS 2026-10-22p; the end "
            f"gaps are #1138's)", z_ends)
    k = max(range(len(reads)), key=lambda i: (reads[i][0], -i))
    z, _src, (la, lo) = reads[k]
    za = surface(la, lo)
    if za is None:
        za = z
    return ApproachSeat(
        float(la), float(lo), float(za), float(z) - float(datum.y),
        f"§16e {datum.label} datum: the authored y {datum.y:+.2f} flush with "
        f"the ground at end line {k + 1} of {ends_txt} (the end nearer its "
        f"ground; the other end's gap graded by the terrain, #1138; "
        f"RULINGS 2026-10-22m)", z_ends)
