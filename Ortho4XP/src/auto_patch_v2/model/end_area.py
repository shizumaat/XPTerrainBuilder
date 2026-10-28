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
drop (``planar/terrain_edge``), on the end's own axis.  The end area then
ends at the TOP of the drop: the station where the steep run it belongs to
began (the crest); below it the drop is raw DEM.  An end with
no drop keeps the RSA length.  ONE reading, published in the sidecar's
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
from ..law.reference_code import runway_status
from ..law.tables import runway_end_profile, runway_safety_area_length_m
from .airport import Airport

__all__ = ["end_area_lengths", "end_area_length"]


def end_area_length(dem, end_xy, unit, law: Law, cn, cl, status: int = 0,
                    cap_s: float | None = None) -> float:
    """The end area's length past one runway END (module docstring);
    ``unit`` points outward along the extended centreline; ``status`` the
    runway's instrument status (RULINGS 2026-10-15k; ``reference_code.
    runway_status``, #811).  ``cap_s`` (#1201): where a walled plate's inner
    edge crosses this line — a drop whose crest stands within
    ``edge_probe_m`` of it, or beyond, is the plate's OWN step (the wall it
    carries, 27t), not the ground falling away: the line keeps its length
    and the plate caps it."""
    rsa = runway_safety_area_length_m(law, cn, cl, status)
    if dem is None or rsa <= 0.0:
        return rsa
    d_ = law.tables.emit.design
    step = float(d_.edge_grid_m)
    probe = float(d_.edge_probe_m)
    drop = float(d_.edge_min_drop_m)
    grade = float(law.tables.zones.adjacent_ground.end_drop_min_grade)
    prof = runway_end_profile(law, cn, cl, status)
    try:
        z0 = float(dem.z(*end_xy))
    except Exception:                                    # pragma: no cover
        return rsa
    n = int(rsa // step)
    k = max(1, int(round(probe / step)))
    zs: list[float] = []
    crest = 0.0                 # where the current steep run began
    for i in range(n + 1):
        d = i * step
        z = float(dem.z(end_xy[0] + unit[0] * d, end_xy[1] + unit[1] * d))
        if not math.isfinite(z):
            return rsa
        zs.append(z)
        if i == 0 or (zs[i - 1] - z) / step <= grade:
            crest = d           # not falling steeply into this station
        deficit = (z0 - prof.fall_m(d)) - z
        if deficit > drop and i >= k and (zs[i - k] - z) / probe > grade:
            if cap_s is not None and crest >= cap_s - probe:
                return rsa          # the plate's own step (docstring)
            return crest
    return rsa


def _end_length(dem, end_xy, unit, law: Law, cn, cl, status: int = 0,
                plate=None) -> float:
    """The end area's length past one END: the SHORTEST over the extended
    centreline and the RSA's two side lines (``zone2_half_width_m`` from it,
    the band's own edges) — an escarpment running OBLIQUELY across the end
    area reaches a side line first (measured CYXY 14L/32R: the centreline
    keeps 184 m while the band's corner stood 34 m over the valley floor).
    ``plate``: the walled plate capping this end, whose inner edge caps
    each line (:func:`end_area_length`'s ``cap_s``)."""
    from ..law.tables import zone2_half_width_m
    hw = float(zone2_half_width_m(law, "runway", cn, cl, status) or 0.0)
    px, py = -unit[1], unit[0]
    lens = []
    for t in (0.0, -hw, hw):
        o = (end_xy[0] + px * t, end_xy[1] + py * t)
        lens.append(end_area_length(dem, o, unit, law, cn, cl, status,
                                    _inner_s_on_line(plate, o, unit)))
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
    for rw in airport.runways:
        a, b = rw.ends[0].xy, rw.ends[1].xy
        L = math.hypot(b[0] - a[0], b[1] - a[1])
        if L <= 0.0:
            continue
        ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
        cn, cl, ins = rw.code_number, rw.code_letter, runway_status(rw)
        cap = {p.end: p for p in plates if p.runway == rw.id}
        out[rw.id] = (_end_length(dem, a, (-ux, -uy), law, cn, cl, ins, cap.get(0)),
                      _end_length(dem, b, (ux, uy), law, cn, cl, ins, cap.get(1)))
    # owner RULINGS 2026-10-27t (#1201): A RUNWAY SAFETY AREA ENDS AT A
    # RECOGNISED WALLED PLATE'S INNER EDGE (``airport/walled_plate``)
    for p in plates:
        if p.runway in out:
            lens = list(out[p.runway])
            lens[p.end] = min(lens[p.end], float(p.inner_s))
            out[p.runway] = (lens[0], lens[1])
    return out
