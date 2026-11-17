"""THE CHANNEL'S DECLARED FLOOR AT A POINT — one function, four readers
(#2127 round 3, spec ``2127-R3.md`` §3 A4).

A channel's floor is its axis profile ``floor_z(s)`` everywhere but on an
EXIT RAMP — the part of the floor a road leaving the channel through its wall
climbs on (``planar/channel_ramp``).  A ramp face carries the floor's ref with
:data:`RAMP_MARK` and its number (``channel_floor:<k>#r<n>``), and its floor
is the ramp's own long section: ``(x, y, z)`` stations along its axis, read
at a point's station on that polyline (:func:`station_z`).  The ramp's TOP
end line is not declared — it meets the road it hands over to and takes the
design surface there (:data:`TOP_M`).

:func:`declared_floor_z` is the ONE answer: ``constraints/channel`` states
the pin with it, ``pipeline/publication`` publishes the ramps it reads,
``verify/channel`` and ``tools/check_grade.py`` judge the emitted floor with
it.  Every caller hands its points in its own metric frame.
"""
from __future__ import annotations

import math
import typing as _t

__all__ = ["RAMP_MARK", "TOP_M", "ramp_index", "station_z", "declared_floor_z"]

#: the ref mark of a ramp part of a channel's floor
RAMP_MARK = "#r"
#: a point within this far of a ramp's top end is not declared (the top line
#: hands over to the road, spec §3 A4)
TOP_M = 0.5


def ramp_index(ref: str) -> "int | None":
    """The ramp number a floor face's ``ref`` carries, or ``None`` for the
    main floor (``channel_floor:0#r1-2`` -> 1)."""
    k = ref.find(RAMP_MARK)
    if k < 0:
        return None
    digits = ""
    for ch in ref[k + len(RAMP_MARK):]:
        if not ch.isdigit():
            break
        digits += ch
    return int(digits) if digits else None


def station_z(stations: _t.Sequence[tuple[float, float, float]], x: float, y: float,
              top_m: "float | None" = TOP_M) -> "float | None":
    """``z`` of the station line ``stations`` (``(x, y, z)``, bottom first) at
    the point's own station: its nearest segment, linear along it, the end
    values beyond; ``None`` within ``top_m`` of the last station."""
    if not stations:
        return None
    if len(stations) == 1:
        return float(stations[0][2])
    ss = [0.0]
    for a, b in zip(stations, stations[1:], strict=False):
        ss.append(ss[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
    best_s, best_d = 0.0, math.inf
    for i, (a, b) in enumerate(zip(stations, stations[1:], strict=False)):
        dx, dy = b[0] - a[0], b[1] - a[1]
        L2 = dx * dx + dy * dy
        t = 0.0 if L2 <= 1e-12 else max(0.0, min(1.0, ((x - a[0]) * dx + (y - a[1]) * dy) / L2))
        d = math.hypot(a[0] + dx * t - x, a[1] + dy * t - y)
        if d < best_d:
            best_d, best_s = d, ss[i] + t * math.sqrt(L2)
    if top_m is not None and best_s >= ss[-1] - top_m:
        return None
    for i in range(len(ss) - 1):
        if ss[i] <= best_s <= ss[i + 1]:
            span = ss[i + 1] - ss[i]
            f = 0.0 if span <= 1e-9 else (best_s - ss[i]) / span
            return float(stations[i][2] + (stations[i + 1][2] - stations[i][2]) * f)
    return float(stations[-1][2])


def declared_floor_z(ref: str, x: float, y: float,
                     floor_at: _t.Callable[[float, float], "float | None"],
                     ramps: _t.Mapping[int, _t.Sequence[tuple[float, float, float]]]
                     ) -> "float | None":
    """The declared floor of the face ``ref`` at ``(x, y)``: on a ramp part
    its long section (:func:`station_z`), else ``floor_at(x, y)`` — the
    caller's own axis-profile reading.  ``None``: not declared there."""
    k = ramp_index(ref)
    if k is None or k not in ramps:
        return floor_at(x, y)
    return station_z(ramps[k], x, y)
