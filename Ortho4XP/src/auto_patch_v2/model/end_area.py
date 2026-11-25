"""THE RUNWAY END AREA'S LENGTH, read from the DEM (owner RULINGS
2026-10-15c (2) "Full safety-area length", 2026-10-15g (C) "the band stops
at the top of the drop").

The end area runs the RSA length (``tables.runway_safety_area_length_m``)
from each runway END, unless the raw ground along it falls away past the
band's lawful fall first.  Along the extended centreline and the band's two
side lines (the shortest of the three wins), at a station every
``emit.design.edge_grid_m``, the lawful line is the line's own DEM at the end less
the end profile's fall (``tables.runway_end_profile``).  A DROP is the
first station where the ground stands ``emit.design.edge_min_drop_m``
below that line AND falls steeper than
``zones.adjacent_ground.end_drop_min_grade`` over the
``emit.design.edge_probe_m`` before it — the terrain edge's own probe and
drop (``planar/terrain_edge``), on the end's own axis.  A SECOND TIER (owner
2026-11-04, #1332): ground ``zones.adjacent_ground.end_drop_deep_m`` below
the line and falling steeper than ``end_drop_deep_grade`` is a drop too —
a long fall a little gentler than the first tier's grade (GCLA 36: 18 %,
14-17 m under the line), which the first tier read as fill.  The end area then
ends at the TOP of the drop: the station where the steep run it belongs to
began (the crest); below it the drop is raw DEM.  THE MIRROR, A RISE
(2026-11-25, #2276; RULINGS 2026-10-12q (1) (c): rising ground beyond an end
is governed by the climb surface): ground standing a tier's height ABOVE the
climb surface (``EndProfile.rise_m``) and rising steeper than that tier's
grade over the probe is a hill the end area does not cut — at an ICAO
CODE 1 runway on credible lidar ground only (owner RULINGS 2026-11-25b (1): "this should only apply
to very small airports like TFFJ or Lukla"; codes 2-4 keep the full graded
end area, the safety area rising ground is graded out of) — the end area ends
at the FOOT of the rise (where its steep run began), and the hill above is
raw DEM.  An end with neither keeps the RSA length.  A side line whose crest stands within one
probe of the end reads the slope beside the runway, not a drop across the
end area, and is not read (#2282) — a RISE there still ends it (#2276).
ONE reading, published in the sidecar's
``runway_axes`` rows so the census measures the same end area.

A general rule read from the DEM: no airport, no runway and no length is
named here.  Measured (lane rwyzone15c, 2026-10-15): CYXY 14R/32L and
14L/32R stop at 155-195 m on the escarpment; KBJC (steepest end ground
10.5 %, no 2 m deficit) and KDEN keep their 304.8 m.

AND AT A WALLED PLATE (owner RULINGS 2026-10-27t, #1201): an end capped by a
recognised runway-end walled plate (``Airport.walled_plates``) ends at the
plate's inner edge — KSEA 16R / 16C / 16L at 302.8 / 298.6 / 296.3 m."""
from __future__ import annotations

import math

from ..law import Law
from ..law.inset_class import lidar_credible
from ..law.reference_code import runway_status
from ..law.tables import runway_end_profile, runway_safety_area_length_m
from .airport import Airport

__all__ = ["end_area_lengths", "end_area_length"]


def end_area_length(dem, end_xy, unit, law: Law, cn, cl, status: int = 0,
                    cap_s: float | None = None, rises: bool = False) -> float:
    """The end area's length past one runway END (module docstring);
    ``unit`` points outward along the extended centreline; ``status`` the
    runway's instrument status (RULINGS 2026-10-15k; ``reference_code.
    runway_status``, #811).  ``cap_s`` (#1201): where a walled plate's inner
    edge crosses this line — a drop whose crest stands within
    ``edge_probe_m`` of it, or beyond, is the plate's OWN step (the wall it
    carries, 27t), not the ground falling away: the line keeps its length
    and the plate caps it.  ``rises``: whether a RISE may end it (the
    airport's ground is credible lidar, ``law.inset_class``; the code-1
    test is read here)."""
    rsa = runway_safety_area_length_m(law, cn, cl, status)
    if dem is None or rsa <= 0.0:
        return rsa
    d_ = law.tables.emit.design
    step = float(d_.edge_grid_m)
    probe = float(d_.edge_probe_m)
    ag = law.tables.zones.adjacent_ground
    # (deficit, grade) per tier: 15g (C)'s, and the deep one (#1332)
    tiers = ((float(d_.edge_min_drop_m), float(ag.end_drop_min_grade)),
             (float(ag.end_drop_deep_m), float(ag.end_drop_deep_grade)))
    prof = runway_end_profile(law, cn, cl, status)
    # RULINGS 2026-11-25b (1): a RISE ends the end area of a code-1 runway
    # only (the TFFJ / Lukla class), read on credible ground (``rises``)
    rises = rises and int(cn or 0) == 1
    try:
        z0 = float(dem.z(*end_xy))
    except Exception:                                    # pragma: no cover
        return rsa
    n = int(rsa // step)
    k = max(1, int(round(probe / step)))
    zs: list[float] = []
    # per tier and side: where the current steep run began — the CREST of
    # a fall (side 0), the FOOT of a rise (side 1)
    start = [[0.0, 0.0] for _ in tiers]
    for i in range(n + 1):
        d = i * step
        z = float(dem.z(end_xy[0] + unit[0] * d, end_xy[1] + unit[1] * d))
        if not math.isfinite(z):
            return rsa
        zs.append(z)
        rise = prof.rise_m(d) if rises else None
        # how far the ground stands OUTSIDE the lawful line: below the fall
        # (a drop), above the climb surface (a rise, 2026-11-25 #2276)
        off = ((z0 - prof.fall_m(d)) - z,
               None if rise is None else z - (z0 + rise))
        for t, (drop, grade) in enumerate(tiers):
            for side, sgn in ((0, 1.0), (1, -1.0)):
                if i == 0 or sgn * (zs[i - 1] - z) / step <= grade:
                    start[t][side] = d   # not steep into this station
                if (off[side] is not None and off[side] > drop and i >= k
                        and sgn * (zs[i - k] - z) / probe > grade):
                    if cap_s is not None and start[t][side] >= cap_s - probe:
                        return rsa       # the plate's own step (docstring)
                    return start[t][side]
    return rsa


def _end_length(dem, end_xy, unit, law: Law, cn, cl, status: int = 0,
                plate=None, rises: bool = False) -> float:
    """The end area's length past one END: the SHORTEST over the extended
    centreline and the RSA's two side lines (``zone2_half_width_m`` from it,
    the band's own edges) — an escarpment running OBLIQUELY across the end
    area reaches a side line first (measured CYXY 14L/32R: the centreline
    keeps 184 m while the band's corner stood 34 m over the valley floor).
    ``plate``: the walled plate capping this end, whose inner edge caps
    each line (:func:`end_area_length`'s ``cap_s``)."""
    from ..law.tables import zone2_half_width_m
    hw = float(zone2_half_width_m(law, "runway", cn, cl, status) or 0.0)
    probe = float(law.tables.emit.design.edge_probe_m)
    px, py = -unit[1], unit[0]
    lens = []
    for t in (0.0, -hw, hw):
        o = (end_xy[0] + px * t, end_xy[1] + py * t)
        cap = _inner_s_on_line(plate, o, unit)
        n = end_area_length(dem, o, unit, law, cn, cl, status, cap, rises)
        # A SIDE LINE ALREADY FALLING AT THE END READS THE GROUND BESIDE
        # THE RUNWAY, NOT A DROP ACROSS THE END AREA (#2282): its crest
        # within one probe of the end is the slope off the runway's own
        # platform, which runs on beside the slab — it never ends the area
        # (MEASURED EKVG: both side lines crest at 0-5 m into gullies
        # 75 m off the axis while the centreline holds 80 / 90 m to the
        # sea cliff; the end area read 0.0 m at both ends).  A side line
        # cut short by a RISE (#2276, TFFJ 10: the +30 m line climbs 30 %
        # from 5 m out) still ends it: only a drop-made crest is skipped.
        if t != 0.0 and n < probe:
            drop_only = (end_area_length(dem, o, unit, law, cn, cl, status,
                                         cap) if rises else n)
            if drop_only <= n:
                continue
        lens.append(n)
    return min(lens)


def _inner_s_on_line(plate, origin, unit) -> float | None:
    """The distance along the line from ``origin`` along ``unit`` at which
    ``plate``'s inner edge stands at that line's offset (the edge read in
    the end's own frame, held at its nearest end beyond it — a side line a
    little outside the plate's width reads the plate's corner); ``None``
    without a plate, its median ``inner_s`` without an inner edge."""
    if plate is None:
        return None
    pts = tuple(plate.inner or ())
    if len(pts) < 2:
        return float(plate.inner_s)
    ox, oy = origin
    st = sorted((-(x - ox) * unit[1] + (y - oy) * unit[0],
                 (x - ox) * unit[0] + (y - oy) * unit[1]) for x, y in pts)
    if st[0][0] >= 0.0:
        return st[0][1]
    if st[-1][0] <= 0.0:
        return st[-1][1]
    for (t0, s0), (t1, s1) in zip(st, st[1:], strict=False):
        if t0 <= 0.0 <= t1:
            return s0 if t1 == t0 else s0 + (s1 - s0) * (0.0 - t0) / (t1 - t0)
    return float(plate.inner_s)                          # pragma: no cover


def end_area_lengths(airport: Airport, law: Law) -> dict[str, tuple[float, float]]:
    """``{runway id: (past ends[0], past ends[1])}`` — each end area's
    length from the runway END (module docstring)."""
    out: dict[str, tuple[float, float]] = {}
    dem = getattr(airport, "dem", None)
    plates = tuple(getattr(airport, "walled_plates", ()) or ())
    # a RISE is read only on credible fine ground (2026-11-25b (1), #2276):
    # a coarse DEM's hill beyond an end is not evidence enough to keep it
    rises = lidar_credible(airport, law)
    for rw in airport.runways:
        a, b = rw.ends[0].xy, rw.ends[1].xy
        L = math.hypot(b[0] - a[0], b[1] - a[1])
        if L <= 0.0:
            continue
        ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
        cn, cl, ins = rw.code_number, rw.code_letter, runway_status(rw)
        cap = {p.end: p for p in plates if p.runway == rw.id}
        out[rw.id] = (_end_length(dem, a, (-ux, -uy), law, cn, cl, ins, cap.get(0), rises),
                      _end_length(dem, b, (ux, uy), law, cn, cl, ins, cap.get(1), rises))
    # owner RULINGS 2026-10-27t (#1201): A RUNWAY SAFETY AREA ENDS AT A
    # RECOGNISED WALLED PLATE'S INNER EDGE (``airport/walled_plate``)
    for p in plates:
        if p.runway in out:
            lens = list(out[p.runway])
            lens[p.end] = min(lens[p.end], float(p.inner_s))
            out[p.runway] = (lens[0], lens[1])
    return out
