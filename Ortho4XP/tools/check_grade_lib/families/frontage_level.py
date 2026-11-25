"""THE FRONTAGE LEVEL family ``frontage_level`` (RULINGS 2026-11-25g (2);
spec ``docs/specs/terminal-frontage-split-level-20261125.md`` §2 C28),
SIDECAR-DECLARED: the build publishes per terminal unit the frontage
vertices its frontage law held (``terminal_frontages`` ``band_ll``:
``[lat, lon, G]``, G = the block's solved datum + the kerb's rise), and
this prices each emitted vertex against its G."""
from __future__ import annotations

from typing import Dict, List, Tuple

from check_grade_lib.rows import Violation, Way

LAW_FAMILY_ROWS: Tuple[Tuple[str, str, str], ...] = (
    # THE FRONTAGE LEVEL (RULINGS 2026-11-25g (2): the groundside frontage
    # is a flat stretch along the building at its groundside floor).
    ("frontage_level",
     "FRONTAGE vertex off its unit's GROUNDSIDE FLOOR (block datum + rise)",
     "within"),
)

#: a frontage vertex off its G by more than this is a row (§31's visual
#: floor, the jetway strip's materiality)
FRONTAGE_LEVEL_TOL_M = 0.05


def check_frontage_level(terminal_frontages_ll, nodes, ways) -> List[Violation]:
    """One row per published frontage vertex whose emitted elevation stands
    more than :data:`FRONTAGE_LEVEL_TOL_M` off its ``G`` (module
    docstring).  A patch with no key, or no band, reports nothing."""
    if not terminal_frontages_ll:
        return []
    by_ll: Dict[Tuple[float, float], Tuple[float, Way]] = {}
    for w in ways:
        for nid, z in zip(w.nids, w.elevs):
            if z is None or nid not in nodes:
                continue
            lat, lon = nodes[nid]
            by_ll.setdefault((round(lat, 7), round(lon, 7)), (float(z), w))
    out: List[Violation] = []
    for rec in terminal_frontages_ll:
        if not isinstance(rec, dict):
            continue
        for b in rec.get("band_ll") or ():
            try:
                lat, lon, g = float(b[0]), float(b[1]), float(b[2])
            except (TypeError, ValueError, IndexError):
                continue
            got = by_ll.get((round(lat, 7), round(lon, 7)))
            if got is None:
                continue
            z, way = got
            if abs(z - g) <= FRONTAGE_LEVEL_TOL_M:
                continue
            v = Violation(grade_pct=0.0, excess_pct=0.0, distance_m=0.0,
                          de_m=abs(z - g), way_a=way, way_b=way,
                          pt_a=(0.0, 0.0), pt_b=(0.0, 0.0), elev_a=z, elev_b=g)
            v.lat, v.lon = lat, lon
            out.append(v)
    return out
