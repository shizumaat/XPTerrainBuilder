"""RUNWAY PEERS — what one runway's pins say about another's (owner RULINGS
2026-11-10b (2), (3), (4); issues #1912, #1945, #1928).

The end-pin rule (``airport/end_pins``) judges each runway alone.  Three
rulings let a runway's NEIGHBOUR speak:

* TOUCHING (2), #1912: two runways whose slabs (``Runway.slab_corners``)
  lie within ``runway_ends.peer_touch_m`` of each other share pavement
  (``geom/runway_contact.slabs_touch``).  A runway with no surveyed end
  beside a surveyed one takes its level — 22a's pull toward the surveyed
  pin reaches across (``constraints/runway_profile.end_pin_cases`` reads
  ``geom/runway_contact.touching_pins``; that rule lives there).  LSZI
  07L/25R (no CIFP) beside 07/25 (CIFP 544.98 m both ends): the lidar put
  it 1.93 m under its neighbour.
* CLOSE ENDS (3), #1945: two pinned ends of touching runways closer than
  ``runway_ends.peer_close_end_m`` whose difference the pavement between
  them cannot carry (the strictest cap of either end; along a runway
  whose slab carries both pins, that runway's own grade within the
  vertical-curve bound) each yield by an EQUAL share, just enough that the
  difference complies (:func:`split_close_ends`).  Owner verbatim:
  "split the distance equally bringing them close enough
  together in elevation to comply".  KCRS 14 / 20: 6 m apart, 0.31 m.
* PARALLEL CORROBORATION (4), #1928: a CIFP pair refused only by rule (b)
  (disagreement with the DEM) stands when a PARALLEL runway (axes within
  ``runway_ends.peer_parallel_deg``) whose CIFP stood agrees with it end
  for end within the DEM class's ``grade_disagree_m``
  (:func:`parallel_peer`).  LTFM 17s against 16s: 5.2 / 4.6 m on a coarse
  DEM the old mine land put 59.5 to 157 m.

No rule here names an airport (RULINGS 2026-10-05e).
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

from shapely.geometry import Point, Polygon

from ..geom.runway_contact import pin_xy, slabs_touch
from ..law import Law
from ..law.tables import (
    role_cap,
    runway_end_zone_cap,
    runway_ends,
    runway_transverse_max,
    runway_vertical_curve_bound,
)
from ..model.airport import Airport, Runway

__all__ = ["parallel_peer", "split_close_ends", "SPLIT"]

#: ``RunwayEnd.pin_flags`` of a CIFP end that yielded its share (3)
SPLIT = "split"


def _unit(rw: Runway) -> tuple[float, float]:
    (ax, ay), (bx, by) = rw.ends[0].xy, rw.ends[1].xy
    L = math.hypot(bx - ax, by - ay) or 1.0
    return (bx - ax) / L, (by - ay) / L


def parallel_peer(rw: Runway, cifp: dict[int, float],
                  stood: dict[str, tuple[Runway, dict[int, float]]],
                  tol_m: float, max_deg: float) -> str | None:
    """(4): the id of a runway in ``stood`` (id -> (runway, its standing
    CIFP by end index)) parallel to ``rw`` whose CIFP agrees with ``cifp``
    END FOR END within ``tol_m`` — ends paired by direction — else
    ``None``."""
    if len(cifp) != 2:
        return None
    ux, uy = _unit(rw)
    for rid, (peer, pc) in stood.items():
        if rid == rw.id or len(pc) != 2:
            continue
        px, py = _unit(peer)
        dot = ux * px + uy * py
        if math.degrees(math.acos(min(1.0, abs(dot)))) > max_deg:
            continue
        pair = (0, 1) if dot > 0.0 else (1, 0)      # rw end k <-> peer end pair[k]
        if all(abs(cifp[k] - pc[pair[k]]) <= tol_m for k in (0, 1)):
            return rid
    return None


def _end_cap(law: Law, rw: Runway, k: int) -> float | None:
    """The strictest grade the runway's own law allows near end ``k``: the
    longitudinal cap, the end-zone cap there, the transverse maximum."""
    caps = []
    cap = role_cap(law, "runway", rw.code_number, rw.code_letter)
    if cap is not None:
        caps.append(float(cap.longitudinal))
    ez = runway_end_zone_cap(law, rw.code_number, rw.code_letter,
                             bool(getattr(rw.ends[k], "cat_ii_iii", False)))
    if ez is not None:
        caps.append(float(ez))
    tm = runway_transverse_max(law, rw.code_letter, rw.code_number)
    if tm is not None:
        caps.append(float(tm))
    return min(caps) if caps else None


def _band(law: Law, rws: _t.Sequence[Runway], a: tuple[int, int], b: tuple[int, int],
          d: float, gap: float) -> tuple[float, float]:
    """The lawful range of ``z_b - z_a`` between two close pins: within the
    strictest cap of either end over their distance; and, on each runway
    whose slab carries BOTH pins, within that runway's own pin-line grade
    over their distance along its axis, give or take the vertical-curve
    bound (``runway_vertical_curve_bound`` at that spacing) along it and
    the transverse maximum across it — the pavement between them is that
    runway's surface.  An empty intersection meets at the middle of it."""
    caps = [c for c in (_end_cap(law, rws[a[0]], a[1]), _end_cap(law, rws[b[0]], b[1]))
            if c is not None]
    lo, hi = -min(caps) * d, min(caps) * d
    pa, pb = pin_xy(rws[a[0]], a[1]), pin_xy(rws[b[0]], b[1])
    for rw in {a[0]: rws[a[0]], b[0]: rws[b[0]]}.values():
        slab = Polygon(rw.slab_corners).buffer(gap)
        if not (slab.covers(Point(pa)) and slab.covers(Point(pb))):
            continue
        z0, z1 = (e.threshold_elev_m for e in rw.ends)
        bound = runway_vertical_curve_bound(law, d, rw.code_number, rw.code_letter)
        if z0 is None or z1 is None or bound is None or rw.length_m <= 0.0:
            continue
        ux, uy = _unit(rw)
        s = (pb[0] - pa[0]) * ux + (pb[1] - pa[1]) * uy
        lat = abs(-(pb[0] - pa[0]) * uy + (pb[1] - pa[1]) * ux)
        tmax = runway_transverse_max(law, rw.code_letter, rw.code_number) or 0.0
        g = (float(z1) - float(z0)) / rw.length_m
        slack = bound * abs(s) + float(tmax) * lat
        rlo, rhi = g * s - slack, g * s + slack
        lo, hi = (max(lo, rlo), min(hi, rhi)) if max(lo, rlo) <= min(hi, rhi) else (
            (max(lo, rlo) + min(hi, rhi)) / 2.0,) * 2
    return lo, hi


def _close_pairs(airport: Airport, law: Law
                 ) -> _t.Iterator[tuple[tuple[int, int], tuple[int, int], float]]:
    """Every pair of PINNED ends of two touching runways closer than
    ``peer_close_end_m``: ``((i, k), (j, l), distance)``."""
    t = runway_ends(law)
    rws = airport.runways
    for i in range(len(rws)):
        for j in range(i + 1, len(rws)):
            if not slabs_touch(rws[i], rws[j], float(t.peer_touch_m)):
                continue
            for ki in (0, 1):
                for kj in (0, 1):
                    if (rws[i].ends[ki].threshold_elev_m is None
                            or rws[j].ends[kj].threshold_elev_m is None):
                        continue
                    d = math.dist(pin_xy(rws[i], ki), pin_xy(rws[j], kj))
                    if 0.0 < d < float(t.peer_close_end_m):
                        yield (i, ki), (j, kj), d


def split_close_ends(airport: Airport, law: Law, records: _t.Sequence[dict] = ()
                     ) -> tuple[Airport, list[str]]:
    """(3) on ``airport``: every close pair (:func:`_close_pairs`) whose
    difference lies outside its lawful range (:func:`_band`) yields by an
    equal share toward each other, until the difference sits at the
    range's nearer edge.  ``records`` (``end_pins.verify``'s) are updated
    in place.  Returns the airport and one loud line per pair."""
    rws = list(airport.runways)
    gap = float(runway_ends(law).peer_touch_m)
    moved: dict[tuple[int, int], float] = {}
    lines: list[str] = []
    for a, b, d in _close_pairs(airport, law):
        if not [c for c in (_end_cap(law, rws[a[0]], a[1]), _end_cap(law, rws[b[0]], b[1]))
                if c is not None]:
            continue
        za = float(rws[a[0]].ends[a[1]].threshold_elev_m) + moved.get(a, 0.0)
        zb = float(rws[b[0]].ends[b[1]].threshold_elev_m) + moved.get(b, 0.0)
        lo, hi = _band(law, rws, a, b, d, gap)
        dz = zb - za
        target = min(max(dz, lo), hi)
        if abs(target - dz) <= 1e-9:
            continue
        share = (dz - target) / 2.0
        moved[a] = moved.get(a, 0.0) + share
        moved[b] = moved.get(b, 0.0) - share
        lines.append(f"CLOSE RUNWAY ENDS SPLIT (#1945, RULINGS 2026-11-10b (3)): {airport.icao} "
                     f"RWY {rws[a[0]].ends[a[1]].name} {za:.2f} m and RWY "
                     f"{rws[b[0]].ends[b[1]].name} {zb:.2f} m lie {d:.1f} m apart on touching "
                     f"pavement; the lawful difference is {lo:+.3f} to {hi:+.3f} m, "
                     f"each yields {abs(share):.3f} m")
    for (i, k), dz in moved.items():
        ends = list(rws[i].ends)
        e = ends[k]
        raw = e.cifp_elev_m if e.cifp_elev_m is not None else e.threshold_elev_m
        ends[k] = _dc.replace(e, threshold_elev_m=float(e.threshold_elev_m) + dz,
                              cifp_elev_m=raw,
                              pin_flags=",".join(f for f in (e.pin_flags, SPLIT) if f))
        rws[i] = _dc.replace(rws[i], ends=(ends[0], ends[1]))
        for r in records:
            if r.get("runway") == rws[i].id and r.get("end") == e.name:
                r["pin_m"] = round(float(ends[k].threshold_elev_m), 3)
                r["flags"] = list(r.get("flags") or []) + [SPLIT]
    if not moved:
        return airport, lines
    return _dc.replace(airport, runways=tuple(rws)), lines
