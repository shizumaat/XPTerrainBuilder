"""THE END-AROUND TAXIWAY CEILING, read off the emitted product (owner
RULINGS 2026-09-13j item 2, ruled 13q item 2; spec §36).

The v2 twin of ``check_grade._check_eat_ceiling``: the ACCEPTED rects
arrive through the sidecar's ``eat_rects`` (``pipeline/publication``, off
the FINAL constraint set), each carrying the regulation value it was
pinned at and the ``[lat, lon]`` of every vertex it governs.  A row is a
governed vertex standing ABOVE that value by more than the emitted
surface's own elevation quantum.

Recognition is NOT re-derived here, in either instrument: it needs the
apt.dat route network and the runway ends, which the emitted product does
not carry, and a second spelling of it would be the census-wrapper
defect.  The join is the canonical lat/lon identity, never proximity.
"""
from __future__ import annotations

from .frame import Patch, Row, row

__all__ = ["eat_ceiling", "FAMILY"]

FAMILY = "eat_ceiling"

#: The dp the emitted patch writes its identity at (``emit.identity_dp``
#: is the same number the oracle rounds to).
_DP = 7


def eat_ceiling(p: Patch) -> list[Row]:
    """One row per governed vertex above its rect's regulation value."""
    rects = p.publication.get("eat_rects") or ()
    if not rects:
        return []
    tol = float(p.law.tables.emit.materiality.elevation_m)
    by_ll: dict[tuple[float, float], int] = {
        (round(la, _DP), round(lo, _DP)): vid for vid, (la, lo) in p.ll.items()}
    out: list[Row] = []
    for rec in rects:
        try:
            value = float(rec["value_m"])
        except (KeyError, TypeError, ValueError):
            continue
        ref = f"{rec.get('runway', '')}/{rec.get('end', '')}".strip("/")
        for ll in (rec.get("vertices") or ()):
            try:
                lat, lon = float(ll[0]), float(ll[1])
            except (TypeError, ValueError, IndexError):
                continue
            vid = by_ll.get((round(lat, _DP), round(lon, _DP)))
            if vid is None:
                continue      # withdrawn, or a rect from another build
            z = p.z.get(vid)
            if z is None or z - value <= tol:
                continue
            xy = p.xy.get(vid, (0.0, 0.0))
            out.append(row(FAMILY, ("junction",) * 2, "airside", z - value,
                           0.0, 0.0, 0.0, xy, xy, ref or "eat_rect", None,
                           lat=lat, lon=lon))
    return out
