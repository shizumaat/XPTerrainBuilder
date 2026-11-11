"""A RAIL MEETING A STATION IN A WALLED PIT STAYS GROUPED WITH IT (owner
RULINGS 2026-11-11f, #1949).

Owner, verbatim: "If the author intended the rail to connect to a station
in the pit then they need to stay grouped together if possible, but it
could be a challenge with long rails if distant stations are at different
elevations, the one most visible from airside areas should take priority."

A walled pit (``airport/walled_pit``) re-seats its frame so its rim lands on
the ground around it and writes that frame whole
(``object_floor.seat_records``).  A connected group its frame does not hold
-- a share of a §16g connected unit (``open_frame_seat.root_zeros``): the
rail track and the stations along it -- was seated by its own rule, so the
two authored frames stood apart (OMDB ``duong_ray`` 0.95 m over the pit's
platform frame).

THE WITNESS (geometry, never a name): a ground-contact foot of one of the
share's parts stands inside the pit's footprint, and that part's placement
is co-placed with the pit's floor (``hanging_objects._co_placed``: one
origin, one heading) -- the pack stated both elevations in one authored
frame.  Grouped, the share and the pit stand RIGIDLY: share zero = pit zero
+ (the share's authored zero - the pit's authored zero).

WHICH ONE MOVES -- "the one most visible from airside areas" (:func:`join_frame`):

* a share seated on the AIRSIDE floor (``airside_group_seat``: its walled
  feet on the apron -- a terminal station) outranks a pit, which stands
  under the ground; the PIT's frame moves to the share, and only where its
  rim then stands 0 .. ``[tunnel.object] authored_crest_max_m`` over the
  ground around it (the band the pit read itself keeps an authored rim in,
  object-placement spec §18 (3)) and its floor rises, never sinks under its
  own cut.  Otherwise the two stay apart ("if possible");
* any other share rides the pit; where its feet stand in several pits of
  different seats, the pit nearest an aircraft stand or jetway
  (``airside_group_seat.stands_of``) sets its zero, then the one holding
  the most of its feet.

The pit's records (patch half, :func:`stamp`) carry its frame's id, and the
floor's own record the authored zeros of its co-placed placements, its rim
and its footprint.  Nothing here names
a pack or an airport.
"""
from __future__ import annotations

import math
import typing as _t

__all__ = ["PIT_OF", "PIT_RING", "PIT_AUTHORED", "Pit", "stamp", "pits_of", "join_frame", "shifted"]

#: the ``authored_seats`` record key naming the walled pit a row's frame is
PIT_OF = "pit_of"
#: the floor record's footprint ring ``[[lat, lon], ...]``
PIT_RING = "pit_ring"
#: the floor record's ``{placement id: authored zero}`` of its frame
PIT_AUTHORED = "pit_authored"
#: the ring is written to this many metres (plan simplification)
_RING_TOL_M = 0.5
_M_PER_DEG = 111_320.0


class Pit(_t.NamedTuple):
    """One walled pit's frame as the object stage reads it: its id, written
    zero, the zero its floor was authored at, the authored zeros of the
    placements co-placed with it, its rim proud of the ground and its
    footprint (a shapely polygon in ``(lat, lon)``)."""

    id: str
    zero: float
    authored_zero: float
    mates: _t.Mapping[str, float]
    proud_m: float
    ring: _t.Any


def stamp(rec: dict, f: _t.Any, to_ll: "_t.Callable | None") -> None:
    """PATCH HALF: name ``f``'s pit on the seat record ``rec`` of one of its
    frame's rows; with ``to_ll`` (the floor object's own record) add the
    frame's authored zeros, its rim proud and its footprint ring."""
    rec[PIT_OF] = f.id
    if to_ll is None:
        return
    fp = f.footprint
    part = max(getattr(fp, "geoms", [fp]), key=lambda q: q.area)
    part = part.simplify(_RING_TOL_M, preserve_topology=True)
    rec[PIT_AUTHORED] = {str(pid): round(float(z), 6) for pid, z in f.authored}
    rec["rim_proud_m"] = round(float(f.rim_proud_m), 3)
    rec[PIT_RING] = [[round(a, 9), round(b, 9)] for a, b in
                     (to_ll(x, y) for x, y in part.exterior.coords)]


def pits_of(records: _t.Iterable[_t.Mapping[str, _t.Any]]) -> list[Pit]:
    """Every pit a :func:`stamp`-ed floor record of ``authored_seats`` states."""
    from shapely.geometry import Polygon
    out = []
    for r in records or ():
        if not hasattr(r, "get") or not r.get(PIT_RING) or r.get("elevation") is None:
            continue
        ring = Polygon([(float(a), float(b)) for a, b in r[PIT_RING]])
        ring = ring if ring.is_valid else ring.buffer(0)
        mates = {str(k): float(v) for k, v in (r.get(PIT_AUTHORED) or {}).items()}
        if not ring.is_empty and str(r.get("id")) in mates:
            out.append(Pit(str(r[PIT_OF]), float(r["elevation"]), mates[str(r["id"])], mates,
                           float(r.get("rim_proud_m") or 0.0), ring))
    return out


def _stand_m(p: Pit, stands: _t.Sequence[tuple[float, float]]) -> float:
    """Metres (roughly) from the pit's footprint to the nearest stand."""
    if not stands:
        return math.inf
    from shapely.geometry import Point
    mo = _M_PER_DEG * math.cos(math.radians(p.ring.centroid.x))
    return min(p.ring.distance(Point(la, lo)) for la, lo in stands) * mo


def _shares_in(u: _t.Any, plan_wide: _t.Mapping[int, tuple], merged: _t.Mapping[str, str],
               pits: _t.Sequence[Pit]) -> dict[str, dict[tuple[int, float], int]]:
    """``group key -> {(pit index, rigid zero): feet}``: frame ``u``'s
    connected-unit shares (keyed as ``open_frame_seat.group_zero`` reads
    them, through the frame's root ``merged`` map) with ground-contact feet
    of a placement co-placed with a pit inside its footprint, and the zero
    that stands the share rigidly in the pit's frame."""
    from shapely import STRtree
    from shapely.geometry import Point

    from .open_frame_seat import group_key, unit_root
    tree = STRtree([p.ring for p in pits])
    out: dict[str, dict[tuple[int, float], int]] = {}
    for m in u.members:
        mine = [k for k, p in enumerate(pits) if str(m.id) in p.mates]
        for p in m.parts if mine else ():
            seat = plan_wide.get(p.pid)
            if not seat or not seat[0] or getattr(p, "line", False):
                continue
            r = unit_root(seat[0])
            key = group_key(merged.get(r, r), str(u.id))
            for f in getattr(p, "feet", ()) or ():
                for j in tree.query(Point(float(f[0]), float(f[1])), predicate="intersects"):
                    if int(j) not in mine:
                        continue
                    pit = pits[int(j)]
                    z = round(pit.zero + pit.mates[str(m.id)] - pit.authored_zero, 3)
                    hit = out.setdefault(key, {})
                    hit[(int(j), z)] = hit.get((int(j), z), 0) + 1
    return out


def join_frame(u: _t.Any, plan_wide: _t.Mapping[int, tuple], merged: _t.Mapping[str, str],
               zeros: dict, airside: _t.Mapping[str, tuple[float, int]],
               pits: _t.Sequence[Pit], crest_max_m: float, shifts: dict, counts: dict,
               stands: _t.Sequence[tuple[float, float]] = ()) -> None:
    """Frame ``u``'s shares meeting a walled pit, grouped with it (module
    doc): a share riding a pit takes its zero in ``zeros`` (``root_zeros``'
    ``group key -> (zero, lift)``); a pit frame moving to an AIRSIDE share
    (``airside``: the keys ``root_zeros`` seated on the airside floor) gets
    ``shifts[pit id]`` = the metres it is raised.  ``counts`` gets
    ``pit_frame_shares`` / ``pit_frame_moved`` / ``pit_frame_apart``."""
    hits = _shares_in(u, plan_wide, merged, pits)
    for k in sorted(hits):
        if k not in zeros:
            continue
        zero, lift = zeros[k]
        # the pit (and the rigid zero) most of the share's feet in it read
        ranked = sorted(hits[k].items(), key=lambda kv: (-kv[1], kv[0]))
        if k in airside:
            for (i, rigid), _n in ranked:
                p = pits[i]
                d = zero - rigid
                ok = (p.id not in shifts and d >= 0.0
                      and p.proud_m + d <= crest_max_m)
                key = "pit_frame_moved" if ok else "pit_frame_apart"
                counts[key] = counts.get(key, 0) + 1
                if ok:
                    shifts[p.id] = d
            continue
        several = len({z for _i, z in hits[k]}) > 1
        (_i, rigid), _n = min(ranked, key=lambda kv: (
            _stand_m(pits[kv[0][0]], stands) if several else 0.0, -kv[1], kv[0]))
        zeros[k] = (rigid, lift)
        counts["pit_frame_shares"] = counts.get("pit_frame_shares", 0) + 1


def shifted(records: _t.Sequence[_t.Mapping[str, _t.Any]], shifts: _t.Mapping[str, float]
            ) -> tuple:
    """``records`` with every row of a pit frame :func:`join_frame` moved raised
    by its shift (the frame is one rigid world)."""
    if not shifts:
        return tuple(records)
    out = []
    for r in records:
        d = shifts.get(str(r.get(PIT_OF, ""))) if hasattr(r, "get") else None
        out.append(r if d is None else {**r, "elevation": round(float(r["elevation"]) + d, 3)})
    return tuple(out)
