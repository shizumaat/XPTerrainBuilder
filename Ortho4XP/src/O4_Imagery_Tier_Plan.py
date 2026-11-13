"""Which imagery tier to fetch for which square, and by when (#1992 P3a).

Pure: no I/O, no clock, no network.  Given where the camera is and how it
moves, the tile's photo squares (each with its ``.ter`` ``LOAD_CENTER``
size S) and the tier each square already has on disk, :func:`plan` returns
the fetches the follow job should run, earliest deadline first
(spec ``Ortho4XP/docs/specs/local-imagery-cache-1992.md`` §2.5, §4.3).

THE READ MODEL (spec §2.5, measured on recorder flights 1-2): X-Plane asks
for a square's mip level by distance in units of S, d_k = c_k * S; every
step UP in resolution is a new open of the file and reads whatever is on
disk then.  So a tier must be on disk before the square's crossing of that
tier's distance.  Tiers are files whose top level is 512 / 1024 / 2048 /
4096 px (tier 0 = the build's placeholder, always on disk); a file of tier
j serves every crossing k <= j.

THE RULE (§4.3): from the camera position, ground track and groundspeed,
predict each square's closest approach within ``horizon_s`` (straight
line, plus a lateral margin of :data:`LATERAL_MARGIN_S` * S for turns).
The square's TARGET tier is the finest tier wanted there.  Each crossing
c_k * S on the way in is a DEADLINE; the fetch STARTS ``lead_s`` before it
(D_k = c_k * S + v * T_lead).  The 1024 crossing gets the 1024 file (the
cheap ring); a later crossing gets the target tier at once when it can
still arrive in time (so an on-track square goes 512 -> 1024 -> 4096 and
never shows a 2048 file where X-Plane wants 4096), else that crossing's
own tier.  A square passed abeam beyond 2.8 S therefore gets 1024 only.
A crossing already passed is LATE: still listed (it shows at the next
pass or reload) but last.

ALTITUDE (RULINGS 2026-11-12f and the owner's 17:56Z refinement, spec
§4.3 "Altitude"): the same apparent clarity the whole flight.  A crossing
is read at the eye, at the SLANT distance from a camera ``agl_m`` above the
ground: tier k is wanted while the next coarser file's texel would subtend
more than :data:`EYE_RAD` [k] (~1 arcmin), i.e. slant < c_k * S.  The
camera's path is predicted in 3-D (track, groundspeed and a descending
``vertical_ms``; level at h = 0 once the descent meets the ground; a climb
is planned level), so a descent schedules each finer tier before the
height that needs it.  On the ground the plan
is the horizontal one; high up it holds coarser tiers and never the full
file far below.

GROUNDSPEED is the camera's motion over the ground as the follow job
observes it between position samples, not ``sim/flightmodel/position/
groundspeed``: flight 2 was flown with X-Plane's ground-speed multiplier
and moved up to 8x faster than that dataref.

The constants c_k are the one place to update after spec §11 U2/U3.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Mapping

__all__ = [
    "CROSSING_S", "EYE_RAD", "TIER_WIDTH", "TIER_REQUESTS", "TIER_BYTES",
    "DEFAULT_LEAD_S", "HORIZON_S", "LATERAL_MARGIN_S",
    "Motion", "Square", "Fetch", "tier_for_mip", "tier_of_width",
    "texel_angle", "plan",
]

# Tier k -> top-level width (px), source-zoom requests, BC1+mips bytes (§4.3).
TIER_WIDTH = (512, 1024, 2048, 4096)
TIER_REQUESTS = (4, 16, 64, 256)
TIER_BYTES = (175_000, 700_000, 2_800_000, 11_200_000)
# Tier k is wanted inside CROSSING_S[k] * S (§2.5, flight 2 at 61 N).
# Tier 0 (512 px) is wanted inside ~10 S and is on disk from the build.
CROSSING_S = (10.0, 5.2, 2.8, 1.65)
# The eye angle per texel each crossing holds (RULINGS 2026-11-12f): tier k
# is wanted while the next coarser file's texel subtends more than
# EYE_RAD[k] = 1 / (c_k * W_{k-1}) at the SLANT distance -- ~1 arcmin, the
# same clarity at any height.  Derived, so CROSSING_S stays the one place
# to update.  (EYE_RAD[0]: the 256 px level X-Plane wants beyond 10 S.)
EYE_RAD = tuple(1.0 / (c * (TIER_WIDTH[k - 1] if k else 256))
                for k, c in enumerate(CROSSING_S))

DEFAULT_LEAD_S = 30.0       # T_lead: download + convert + queue (§4.3)
HORIZON_S = 300.0           # "closest approach in the next few minutes"
LATERAL_MARGIN_S = 0.5      # turn margin, in units of S

_M_PER_DEG = 111_320.0


@dataclass(frozen=True)
class Motion:
    """Camera position and its motion (track: degrees true); ``agl_m``:
    the camera's height above the ground (0 = on the ground);
    ``vertical_ms``: its climb (+) or descent (-) rate."""
    lat: float
    lon: float
    alt_m: float
    track_deg: float
    groundspeed_ms: float
    agl_m: float = 0.0
    vertical_ms: float = 0.0


@dataclass(frozen=True)
class Square:
    """One photo square: its texture name, centre and LOAD_CENTER size."""
    name: str
    lat: float
    lon: float
    size_m: float


@dataclass(frozen=True)
class Fetch:
    """One file to land: ``tier`` for ``square``, serving the crossing of
    tier ``crossing`` ``deadline_s`` from now; start ``start_in_s`` from
    now (<= 0: due).  ``late``: that crossing is already behind."""
    square: str
    tier: int
    crossing: int
    deadline_s: float
    start_in_s: float
    distance_m: float
    late: bool

    @property
    def due(self) -> bool:
        return self.start_in_s <= 0.0


def tier_for_mip(mip: int, full_width: int = 4096) -> int:
    """The tier whose top level is the mip level X-Plane loaded (mip 0 of
    a 4096 texture = tier 3; mip 3 and coarser = tier 0)."""
    width = full_width >> max(0, int(mip))
    for tier in range(len(TIER_WIDTH) - 1, -1, -1):
        if width >= TIER_WIDTH[tier]:
            return tier
    return 0


def tier_of_width(px) -> int:
    """The tier of a file ``px`` wide (an unknown width reads as 0)."""
    try:
        return TIER_WIDTH.index(int(px))
    except (TypeError, ValueError):
        return 0


def texel_angle(tier: int, size_m: float, slant_m: float) -> float:
    """Radians one texel of a ``tier`` file over a square of size
    ``size_m`` subtends at ``slant_m``: the apparent clarity the plan
    holds under :data:`EYE_RAD` (spec §4.3 "Altitude")."""
    return size_m / (TIER_WIDTH[tier] * max(1e-9, slant_m))


def _offset_m(motion: Motion, sq: Square) -> tuple[float, float]:
    """Square centre relative to the camera, metres east / north."""
    east = (sq.lon - motion.lon) * _M_PER_DEG * math.cos(math.radians(motion.lat))
    north = (sq.lat - motion.lat) * _M_PER_DEG
    return east, north


def _dot(a, b) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


def _first_inside(p, v, radius, horizon) -> float | None:
    """Earliest t in [0, horizon] with |p - v t| <= radius, else None
    (``p``, ``v``: vectors of any one dimension)."""
    c = _dot(p, p) - radius * radius
    if c <= 0.0:
        return 0.0
    a = _dot(v, v)
    if a <= 0.0:
        return None
    b = _dot(p, v)                       # > 0: closing
    disc = b * b - a * c
    if disc < 0.0 or b <= 0.0:
        return None
    t = (b - math.sqrt(disc)) / a
    return t if t <= horizon else None


def _legs(motion: Motion, sq: Square, horizon: float):
    """The camera's predicted path as straight legs ``(t0, p, v, span)``:
    ``p`` the square's centre relative to the camera at ``t0`` (east,
    north, down to the ground: -h), ``v`` the camera's velocity.  A
    descent meets the ground at ``h / -vz`` and goes on level at h = 0."""
    east, north = _offset_m(motion, sq)
    trk = math.radians(motion.track_deg)
    v = max(0.0, motion.groundspeed_ms)
    vx, vy = v * math.sin(trk), v * math.cos(trk)
    h = max(0.0, motion.agl_m)
    # Only a descent is predicted: a climb is planned level, so a level-off
    # never finds the camera lower than planned (h = 0: the ground plan).
    vz = min(0.0, motion.vertical_ms) if h > 0.0 else 0.0
    t_ground = h / -vz if vz < 0.0 else math.inf
    if t_ground >= horizon:
        return [(0.0, (east, north, -h), (vx, vy, vz), horizon)]
    p2 = (east - vx * t_ground, north - vy * t_ground, 0.0)
    return [(0.0, (east, north, -h), (vx, vy, vz), t_ground),
            (t_ground, p2, (vx, vy, 0.0), horizon - t_ground)]


def _closest(legs) -> tuple[float, float]:
    """(time, slant distance) of the closest approach along ``legs``."""
    best = (math.inf, 0.0)
    for t0, p, v, span in legs:
        a = _dot(v, v)
        t = 0.0 if a <= 0.0 else min(span, max(0.0, _dot(p, v) / a))
        d = math.sqrt(sum((pi - vi * t) ** 2 for pi, vi in zip(p, v, strict=True)))
        if d < best[0]:
            best = (d, t0 + t)
    return best[1], best[0]


def _crossings(motion: Motion, sq: Square, horizon: float, margin_s: float):
    """([(tier, deadline_s, late)] for every tier wanted within
    ``horizon``, coarsest first; the current slant distance)."""
    legs = _legs(motion, sq, horizon)
    now = math.sqrt(_dot(legs[0][1], legs[0][1]))
    t_close, closest = _closest(legs)
    out = []
    for tier in range(1, len(CROSSING_S)):
        radius = CROSSING_S[tier] * sq.size_m       # slant: the eye rule
        t = None
        for t0, p, v, span in legs:
            t = _first_inside(p, v, radius, span)
            if t is not None:
                t += t0
                break
        if t is None and closest <= radius + margin_s * sq.size_m:
            t = t_close                  # wanted only if the track bends
        if t is None:
            break                        # finer tiers lie further in
        out.append((tier, t, now <= radius))
    return out, now


def plan(motion: Motion, squares, on_disk: Mapping[str, int], *,
         lead_s: float = DEFAULT_LEAD_S, horizon_s: float = HORIZON_S,
         margin_s: float = LATERAL_MARGIN_S,
         fetch_s: Mapping[int, float] | None = None) -> list[Fetch]:
    """The ordered fetch list: on-time fetches by deadline (lower tier
    first on a tie), then late ones nearest first.

    ``on_disk`` maps a square name to the tier it has (missing = 0).
    ``fetch_s`` (tier -> seconds to land one file), when given, decides
    whether a crossing can take the square's target tier at once (it must
    land within ``min(deadline, lead_s)``: the fetch starts when due);
    without it the target is assumed to arrive in time."""
    on_time, late = [], []
    for sq in squares:
        have = int(on_disk.get(sq.name, 0))
        crossings, now = _crossings(motion, sq, horizon_s, margin_s)
        if not crossings or crossings[-1][0] <= have:
            continue
        target = crossings[-1][0]
        for tier_k, deadline, is_late in crossings:
            if tier_k <= have:
                continue
            tier = tier_k
            if tier_k >= 2 and target > tier_k and (
                    fetch_s is None
                    or fetch_s.get(target, 0.0) <= min(deadline, lead_s)):
                tier = target
            f = Fetch(sq.name, tier, tier_k, deadline, deadline - lead_s,
                      now, is_late)
            (late if is_late else on_time).append(f)
            have = tier
    on_time.sort(key=lambda f: (f.deadline_s, f.tier, f.square))
    late.sort(key=lambda f: (f.distance_m, f.tier, f.square))
    return on_time + late
