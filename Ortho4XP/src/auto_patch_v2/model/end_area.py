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
10.5 %, no 2 m deficit) and KDEN keep their 304.8 m."""
from __future__ import annotations

import math

from ..law import Law
from ..law.tables import runway_end_profile, runway_safety_area_length_m
from .airport import Airport

__all__ = ["end_area_lengths", "end_area_length"]


def end_area_length(dem, end_xy, unit, law: Law, cn, cl, instrument: bool = False) -> float:
    """The end area's length past one runway END (module docstring);
    ``unit`` points outward along the extended centreline; ``instrument``
    the runway's status (RULINGS 2026-10-15k)."""
    rsa = runway_safety_area_length_m(law, cn, cl, instrument)
    if dem is None or rsa <= 0.0:
        return rsa
    d_ = law.tables.emit.design
    step = float(d_.edge_grid_m)
    probe = float(d_.edge_probe_m)
    drop = float(d_.edge_min_drop_m)
    grade = float(law.tables.zones.adjacent_ground.end_drop_min_grade)
    prof = runway_end_profile(law, cn, cl, instrument)
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
            return crest
    return rsa


def _end_length(dem, end_xy, unit, law: Law, cn, cl, instrument: bool = False) -> float:
    """The end area's length past one END: the SHORTEST over the extended
    centreline and the RSA's two side lines (``zone2_half_width_m`` from it,
    the band's own edges) — an escarpment running OBLIQUELY across the end
    area reaches a side line first (measured CYXY 14L/32R: the centreline
    keeps 184 m while the band's corner stood 34 m over the valley floor)."""
    from ..law.tables import zone2_half_width_m
    hw = float(zone2_half_width_m(law, "runway", cn, cl) or 0.0)
    px, py = -unit[1], unit[0]
    lens = [end_area_length(dem, (end_xy[0] + px * t, end_xy[1] + py * t), unit, law, cn, cl,
                            instrument)
            for t in (0.0, -hw, hw)]
    return min(lens)


def end_area_lengths(airport: Airport, law: Law) -> dict[str, tuple[float, float]]:
    """``{runway id: (past ends[0], past ends[1])}`` — each end area's
    length from the runway END (module docstring)."""
    out: dict[str, tuple[float, float]] = {}
    dem = getattr(airport, "dem", None)
    for rw in airport.runways:
        a, b = rw.ends[0].xy, rw.ends[1].xy
        L = math.hypot(b[0] - a[0], b[1] - a[1])
        if L <= 0.0:
            continue
        ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
        cn, cl, ins = rw.code_number, rw.code_letter, bool(getattr(rw, "instrument", False))
        out[rw.id] = (_end_length(dem, a, (-ux, -uy), law, cn, cl, ins),
                      _end_length(dem, b, (ux, uy), law, cn, cl, ins))
    return out
