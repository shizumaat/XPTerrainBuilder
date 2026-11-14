"""ONE READING OF A FREE-STANDING DECK'S ENDS: the ground each end line
meets and the deck's own top on it (owner RULINGS 2026-10-22m; spec
``othh-deck-round2-spec.md`` S2 / S3 / S5).

The seat (``free_bridge_seat``) and the censuses (``placement_coherence.
census_bridge_ends``, ``written_seat_census.deck_rows``) read a deck's ends
through :func:`deck_end_reads` alone, so a bar never judges a reading the
law did not make.

* THE GROUND at an end: ``bridge_approach.approach_seat``'s end-line
  reading (a road ribbon where most of the line lies on one, else the
  mesh); an end line on a bank walks landward (§16e (6),
  ``anchor_rule._walked_stations``; RULINGS 2026-09-13v).  A deck the 22p
  witness holds at its authored clearance reads that one zero instead.
* A FREE BRIDGE's deck (#2065 S3, ``free_bridge_seat.free_member``): its
  end lines and tops AS PUBLISHED (the route ends and the driven layer's
  top there, ``planar/free_bridge``) — no rectangle, no plate read.
* THE TOP at an end: the PLATE's own height on the end line
  (``deck_carry._plate_top``: the lowest plate triangle under each station,
  a hair inside the deck), never the maximum within a reach — a pylon or an
  upper surface near an end is not the deck the road meets (OTHH
  ``Bridge_01``'s ``LOD0_003`` stands 11.56 over an abutment top of 3.53).
  Where no plate triangle stands under any station, the slab's top near the
  end (``airside_deck_seat.end_tops``).

Nothing here names a pack, a resource or an airport.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import os
import typing as _t

import numpy as np

from ..model.free_bridge import FREE_PLATE
from . import anchor_rule as _ar

__all__ = ["deck_end_reads"]

#: how far inside the deck an end station is moved to read the plate (m)
HAIR_M = 0.05


@_dc.dataclass(frozen=True)
class _EndRead:
    """One end of a deck: the ground its end line meets, the deck's top
    there (authored y) and its end line's stations ``(lat, lon)``."""

    ground: float
    top: float
    line: tuple[tuple[float, float], ...]
    why: str


@_dc.dataclass(frozen=True)
class _DeckEnds:
    """A deck's ends (:class:`_EndRead`, in end order), or ``clearance``:
    the ``(zero, why)`` 22p keeps for a deck with no embankment at either
    end (its ends are then not read)."""

    ends: tuple[_EndRead, ...] = ()
    clearance: "tuple[float, str] | None" = None


def _plate_faces(m: _t.Any, origin: "tuple[float, float] | None") -> np.ndarray:
    """The AUTHORED hard-deck plate of a member as ``(n, 3, 3)`` triangles
    of ``(east, north, y)`` metres about the placement ``origin`` at its
    heading (``airside_deck_seat.slab_points``' map); empty where the file
    or the origin is not to hand."""
    path = getattr(m, "authored_path", "") or ""
    empty = np.zeros((0, 3, 3))
    if origin is None or not path or not os.path.isfile(path):
        return empty
    from . import obj8 as _obj8
    try:
        g = _obj8.parse_obj8(path)
    except (OSError, ValueError):
        return empty
    tri = np.asarray(g.hard_deck, int).reshape(-1, 3)
    if not len(tri):
        return empty
    v = np.asarray(g.vertices, float)[:, :3]
    h = math.radians(float(getattr(m, "heading_deg", 0.0) or 0.0))
    c, sn = math.cos(h), math.sin(h)
    x, y, z = v[:, 0], v[:, 1], v[:, 2]
    east, north = x * c - z * sn, -(x * sn + z * c)
    return np.stack([east, north, y], axis=1)[tri]


def _local(q: _t.Sequence[float], origin: tuple[float, float]) -> tuple[float, float]:
    """``(east, north)`` metres of ``(lat, lon)`` about ``origin``."""
    from .rebake_plan import _mpd
    ml, mo = _mpd(float(origin[0]))
    return ((float(q[1]) - float(origin[1])) * mo, (float(q[0]) - float(origin[0])) * ml)


def _plate_end_tops(m: _t.Any, lines: _t.Sequence[_t.Sequence[tuple[float, float]]],
                   origin: "tuple[float, float] | None", step_m: float
                   ) -> tuple[float, ...]:
    """The deck top AT each of two end lines (module doc, S3): the plate's
    own height there, a hair inside toward the other end; the slab's top
    near the end (``airside_deck_seat.end_tops``) where no plate triangle
    stands under any station."""
    from .airside_deck_seat import end_tops
    from .deck_carry import _plate_top
    plate = _plate_faces(m, origin)
    mids = [(sum(q[0] for q in ln) / len(ln), sum(q[1] for q in ln) / len(ln))
            for ln in lines]
    fallback = None
    out: list[float] = []
    for k, ln in enumerate(lines):
        top = math.nan
        if len(plate) and origin is not None:
            a, b = _local(mids[k], origin), _local(mids[1 - k], origin)
            d = math.hypot(b[0] - a[0], b[1] - a[1]) or 1.0
            inward = ((b[0] - a[0]) / d * HAIR_M, (b[1] - a[1]) / d * HAIR_M)
            # stations UNDER the plate only: a pack deck's plate carries
            # edge-on faces whose plane read off them runs away (OTHH
            # Bridge_01 LOD0_003 read -511 at 0.5 m off one)
            top = _plate_top(plate, [_local(q, origin) for q in ln], inward, edge_m=0.0)
        if not math.isfinite(top):
            if fallback is None:
                fallback = end_tops(m, (list(lines[0]), list(lines[1])), origin, step_m)
            top = fallback[k]
        out.append(float(top))
    return tuple(out)


def _walked(datum: _t.Any, surface: _ar.Surface, tops: _t.Sequence[float],
            lines: _t.Sequence[_t.Sequence[tuple[float, float]]]) -> tuple[_EndRead, ...]:
    """§16e (6)'s LANDWARD WALK read PER END (RULINGS 2026-09-13v): the
    median walked ground of each end, with that end's own top."""
    water = getattr(surface, "water", None)
    stations, note = _ar._walked_stations(datum, surface, water)
    sizes = [len(ln) for ln in lines]
    if sum(sizes) != len(stations):
        sizes, tops = [len(stations)], [max(tops)]
    out: list[_EndRead] = []
    k0 = 0
    for k, n in enumerate(sizes):
        walked = tuple(stations[k0:k0 + n])
        kept, _wet, _off = _ar._line_reading(walked, surface, water)
        line = tuple(lines[k]) if len(sizes) == len(lines) else walked
        k0 += n
        if not kept:
            continue
        zs = sorted(q[0] for q in kept)
        g = zs[len(zs) // 2]
        out.append(_EndRead(float(g), float(tops[k]), line,
                           f"§16e {datum.label} datum: the authored y {tops[k]:+.2f} flush "
                           f"with the walked ground {g:.2f} at end line {k + 1}{note} "
                           f"(RULINGS 2026-10-22m, 2026-09-13v)"))
    return tuple(out)


def deck_end_reads(m: _t.Any, surface: _ar.Surface, *, origin: tuple[float, float],
                   agl_m: float, step_m: float, walk_max_m: float = 0.0,
                   level_tol_m: float = 0.0, all_deck: bool = False) -> "_DeckEnds | None":
    """The ends of one free deck member (module doc), or ``None`` where it
    has no free-standing datum with two end lines.  ``all_deck``: the
    member's frame is all decks (``placement_family.frame_is_bridge``), whose
    seat is 22d / 22p's (``anchor_rule._datum_anchor``, spec S1): the deck
    top ``datum.y`` at both ends and 22p's road-under read wherever the
    anchor stands."""
    from .bridge_approach import approach_seat
    from .rebake_plan import end_line_stations
    datum = _ar.datum_of(m, abutment_step_m=step_m, abutment_walk_max_m=walk_max_m,
                         level_tol_m=level_tol_m, free_standing=True)
    if datum is None or len(datum.ends) < 2 or step_m <= 0.0:
        return None
    lines = tuple(end_line_stations([e], step_m) for e in datum.ends[:2])
    if all_deck:
        tops: tuple[float, ...] = (float(datum.y),) * len(lines)
    else:
        # 22p reads the road under the span only with the anchor under it
        datum = _dc.replace(datum, ring=tuple((float(q[0]), float(q[1]))
                                              for q in (getattr(m, "deck_ring", None) or ())))
        pub = tuple(getattr(m, "deck_end_tops", ()) or ())
        tops = (tuple(float(t) for t in pub[:len(lines)]) if len(pub) >= len(lines)
                and str(getattr(m, "plate_kind", "") or "") == FREE_PLATE
                else _plate_end_tops(m, lines, origin, step_m))
    seat = approach_seat(datum, surface, origin=origin, authored_agl_m=agl_m, tops=tops)
    if seat is not None and "authored clearance" in seat.reason:
        return _DeckEnds(clearance=(seat.zero, seat.reason))
    if seat is None:
        return _DeckEnds(ends=_walked(datum, surface, tops, lines))
    return _DeckEnds(ends=tuple(
        _EndRead(float(g), float(tops[k]), lines[k],
                f"§16e {datum.label} datum: the authored y {tops[k]:+.2f} flush with the "
                f"ground {g:.2f} at end line {k + 1} (the end nearer its ground; the other "
                f"end's gap graded by the terrain, #1138; RULINGS 2026-10-22m)")
        for k, g in enumerate(seat.ends)))
