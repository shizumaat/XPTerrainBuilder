"""THE APPROACH CORRIDOR — ONE derivation (spec §31 (2), §29 (1);
owner RULINGS 2026-09-12al).

Owner (12ae-1): "if it would be visible from an arriving or departing
aircraft it should be cut, if not we can leave it raw DEM".  VISIBILITY
decides, not distance from the classified surfaces — and the region a
pilot sees on final and climb-out is, per RUNWAY END, a rectangle
``[cockpit] approach_km`` long beyond the threshold along the extended
centreline, ``[cockpit] approach_half_width_m`` to each side (on a 3°
final 5 km out the aircraft is ~260 m up and a portal 2 km off the nose
is in plain view).

THE ONE DERIVATION, imported by both readers, because two copies of a
region are two regions:

* the ENGINE — ``planar/structure_approach.FieldRegion``, the mouth gate
  of §29 (1): region = the classified cover ⊕ ``[tunnel]
  mouth_standoff_m`` ∪ THE CORRIDOR;
* the HARNESS — ``tools/check_grade.cockpit_geometry`` /
  ``cockpit_in_view``, the cockpit block's "in view" test.

The retired reading — "within ``approach_km`` of a runway axis", a
5 km disc around every runway vertex — admitted the whole airport and
everything for 5 km around it and discriminated nothing; it is DELETED,
not gated (§31 (2)).

Pure arithmetic: no shapely, no law import, no numeric literal that is a
law value.  Callers pass the two numbers from ``emit.toml [cockpit]``
and the runway ends from their own source (the engine ``airport.runways``
apt.dat thresholds; the harness the principal axis of the emitted runway
rings, ``grade_law.runway_axis_and_width``).  Both frames are the local
metre frame.
"""
from __future__ import annotations

import math as _math
import typing as _t

__all__ = ["ApproachCorridor", "corridor_rings", "CorridorEnd"]

XY = _t.Tuple[float, float]

#: A degenerate runway axis (both ends at one point) has no direction and
#: no corridor.  Not a law value — a divide-by-zero guard.
_EPS = 1e-9


class CorridorEnd(_t.NamedTuple):
    """One runway end's corridor, in the parametric frame that defines it.

    ``origin`` is the threshold, ``direction`` the OUTWARD unit vector
    (away from the runway, along the extended centreline): the corridor
    is ``0 <= s <= length_m`` along it and ``|t| <= half_width_m``
    across.  ``name`` is whatever the caller's source calls the end (an
    apt.dat end name, a runway ref) — carried for the report only.
    """

    origin: XY
    direction: XY
    length_m: float
    half_width_m: float
    name: str = ""

    def station(self, x: float, y: float) -> _t.Tuple[float, float]:
        """``(s, t)`` — along-corridor and lateral offset of a point."""
        dx, dy = x - self.origin[0], y - self.origin[1]
        ux, uy = self.direction
        return dx * ux + dy * uy, -dx * uy + dy * ux

    def holds(self, x: float, y: float) -> bool:
        s, t = self.station(x, y)
        return 0.0 <= s <= self.length_m and abs(t) <= self.half_width_m

    def distance_m(self, x: float, y: float) -> float:
        """Distance to the corridor's nearest EDGE; 0.0 inside it."""
        s, t = self.station(x, y)
        ds = max(0.0, -s, s - self.length_m)
        dt = max(0.0, abs(t) - self.half_width_m)
        return _math.hypot(ds, dt)

    def ring(self) -> _t.Tuple[XY, XY, XY, XY]:
        """The corridor's four corners, counter-clockwise from the
        threshold's right-hand side."""
        ox, oy = self.origin
        ux, uy = self.direction
        # the lateral unit is the left normal of the direction
        nx, ny = -uy, ux
        h, ln = self.half_width_m, self.length_m
        return ((ox - h * nx, oy - h * ny),
                (ox + ln * ux - h * nx, oy + ln * uy - h * ny),
                (ox + ln * ux + h * nx, oy + ln * uy + h * ny),
                (ox + h * nx, oy + h * ny))


def _ends_of_axis(a: XY, b: XY, length_m: float, half_width_m: float,
                  name: str) -> list[CorridorEnd]:
    """The TWO corridors of one runway axis ``a``–``b``: one beyond each
    threshold, each pointing AWAY from the runway."""
    ax, ay = float(a[0]), float(a[1])
    bx, by = float(b[0]), float(b[1])
    dx, dy = bx - ax, by - ay
    n = _math.hypot(dx, dy)
    if n < _EPS:
        return []
    ux, uy = dx / n, dy / n
    return [CorridorEnd((ax, ay), (-ux, -uy), length_m, half_width_m,
                        f"{name}:0" if name else ""),
            CorridorEnd((bx, by), (ux, uy), length_m, half_width_m,
                        f"{name}:1" if name else "")]


class ApproachCorridor:
    """The union of every runway end's corridor — §31 (2).

    ``axes`` is an iterable of runway axes as ``(a, b)`` endpoint pairs,
    or ``(a, b, name)``.  ``approach_m`` and ``half_width_m`` come from
    ``[cockpit] approach_km`` (× 1,000) and ``approach_half_width_m``;
    the caller reads them from the law tables, this module never does.

    An EMPTY corridor set (a patch or an airport with no runway geometry)
    holds nothing and is reported as such by its callers — never silently
    true, which would restore the buffer that admitted everything.
    """

    def __init__(self, axes: _t.Iterable[_t.Sequence], approach_m: float,
                 half_width_m: float) -> None:
        self.approach_m = float(approach_m)
        self.half_width_m = float(half_width_m)
        ends: list[CorridorEnd] = []
        for ax in axes:
            a, b = ax[0], ax[1]
            name = str(ax[2]) if len(ax) > 2 else ""
            ends.extend(_ends_of_axis(a, b, self.approach_m,
                                      self.half_width_m, name))
        self.ends: tuple[CorridorEnd, ...] = tuple(ends)

    def __bool__(self) -> bool:
        return bool(self.ends)

    def __len__(self) -> int:
        return len(self.ends)

    def holds(self, x: float, y: float) -> bool:
        """Is this point in view from an arriving or departing aircraft?"""
        return any(e.holds(x, y) for e in self.ends)

    def distance_m(self, x: float, y: float) -> float:
        """Distance to the NEAREST corridor edge (0.0 inside one, ``inf``
        when there is no corridor at all) — the report a dropped mouth
        and a beyond-view row are quoted with."""
        if not self.ends:
            return float("inf")
        return min(e.distance_m(x, y) for e in self.ends)

    def nearest(self, x: float, y: float) -> _t.Optional[CorridorEnd]:
        if not self.ends:
            return None
        return min(self.ends, key=lambda e: e.distance_m(x, y))

    def rings(self) -> list[_t.Tuple[XY, XY, XY, XY]]:
        """One four-corner ring per runway end — what a geometry engine
        (shapely, in the mouth gate) turns into polygons."""
        return [e.ring() for e in self.ends]


def corridor_rings(axes: _t.Iterable[_t.Sequence], approach_m: float,
                   half_width_m: float) -> list[_t.Tuple[XY, XY, XY, XY]]:
    """``ApproachCorridor(...).rings()`` — the shorthand for a caller that
    only wants the polygons."""
    return ApproachCorridor(axes, approach_m, half_width_m).rings()
