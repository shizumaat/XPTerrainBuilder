"""THE END-AROUND TAXIWAY CEILING family ``eat_ceiling`` (owner RULINGS
2026-09-13j item 2, ruled 13q item 2; spec §36), SIDECAR-DECLARED from
``eat_rects``.  Moved verbatim from ``check_grade.py`` (issue #857), which
re-exports it."""
from __future__ import annotations

from typing import Dict, List, Tuple

from check_grade_lib.rows import Violation, Way

LAW_FAMILY_ROWS: Tuple[Tuple[str, str, str], ...] = (
    # THE END-AROUND TAXIWAY CEILING (owner RULINGS 2026-09-13j item 2,
    # ruled 13q item 2; spec §36).  Sidecar-declared like the two families
    # above it: the accepted rects arrive as ``eat_rects`` and this prices
    # the pavement they govern against the regulation value the solve
    # pinned.  A patch with no key reports nothing.
    ("eat_ceiling",
     "END-AROUND TAXIWAY pavement ABOVE its departure-surface ceiling",
     "within"),
)


def _check_eat_ceiling(eat_rects, nodes, ways) -> List[Violation]:
    """EAT pavement standing ABOVE its departure-surface ceiling.

    Each published rect carries its regulation ``value_m`` and the
    ``[lat, lon]`` of every vertex it governs; the row is that vertex
    standing above the value by more than the elevation materiality.  The
    pin holds EXACTLY in the design solve (a pinned vertex is eliminated
    from the unknowns), so a row here means the EMITTED surface left the
    value the solve pinned — the only way this family can speak.

    The join is the canonical 11-dp lat/lon identity (memory
    ``canonical-identity-join``), never a proximity match; a rect vertex
    the patch does not carry is silently absent, which is what a vertex
    the rect law withdrew looks like.
    """
    if not eat_rects:
        return []
    by_ll: Dict[Tuple[float, float], float] = {}
    for w in ways:
        for nid, z in zip(w.nids, w.elevs):
            if z is None or nid not in nodes:
                continue
            lat, lon = nodes[nid]
            by_ll.setdefault((round(lat, 7), round(lon, 7)), float(z))
    out: List[Violation] = []
    for rec in (eat_rects or []):
        try:
            value = float(rec["value_m"])
        except (KeyError, TypeError, ValueError):
            continue
        ref = f"{rec.get('runway', '')}/{rec.get('end', '')}".strip("/")
        for ll in (rec.get("vertices") or []):
            try:
                lat, lon = float(ll[0]), float(ll[1])
            except (TypeError, ValueError, IndexError):
                continue
            z = by_ll.get((round(lat, 7), round(lon, 7)))
            if z is None or z - value <= _EAT_CEILING_TOL_M:
                continue
            way = Way(f"eat_rect:{rec.get('rect')}", "junction",
                      ref or "eat_rect", "taxiway", [], [],
                      {"role": "junction", "ref": ref or "eat_rect"})
            v = Violation(
                grade_pct=0.0, excess_pct=0.0, distance_m=0.0,
                de_m=z - value, way_a=way, way_b=way,
                pt_a=(0.0, 0.0), pt_b=(0.0, 0.0),
                elev_a=z, elev_b=value)
            v.lat, v.lon = lat, lon
            out.append(v)
    return out


#: The materiality the ceiling is read at: the same elevation quantum the
#: emitted surface carries (``emit.materiality.elevation_m``), so a row
#: here is surface, never rounding.
_EAT_CEILING_TOL_M = 0.01
