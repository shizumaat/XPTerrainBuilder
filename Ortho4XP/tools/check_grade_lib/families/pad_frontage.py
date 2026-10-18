"""THE FLAT-PAD FRONTAGE HOLD families ``pad_frontage_hold`` and
``pad_frontage_infeasible`` (flat-pad spec §1 (2) / §5 A1; spec-author RULINGS
2026-09-30u (c); spec §56 (3)), SIDECAR-DECLARED from ``platforms`` — REPORT.
Moved verbatim from ``check_grade.py`` (issue #857), which re-exports it."""
from __future__ import annotations

from typing import List, Tuple

from check_grade_lib.families.unit_platform import _platform_way
from check_grade_lib.rows import Violation

LAW_FAMILY_ROWS: Tuple[Tuple[str, str, str], ...] = (
    # THE FLAT-PAD FRONTAGE HOLD (flat-pad spec §1 (2); spec-author RULINGS
    # 2026-09-30u (c)).  SIDECAR-DECLARED like the two above: REPORT, one
    # row per held block — a HELD contact off its datum, and the UNHELD
    # (ramp / unreachable) contacts the collar carries.
    ("pad_frontage_hold",
     "FLAT-PAD block whose HELD frontage contact stands off its datum",
     "within"),
    ("pad_frontage_infeasible",
     "FLAT-PAD block with UNHELD frontage contacts (ramp / unreachable)",
     "within"),
)


def _check_pad_frontage(platforms_ll, held: bool) -> List[Violation]:
    """THE FLAT-PAD FRONTAGE HOLD (flat-pad spec §1 (2) / §5 A1; spec-author
    RULINGS 2026-09-30u (c); spec §56 (3)) — REPORT, one row per held BLOCK.

    SIDECAR-DECLARED like ``platform_rim_relief``: the build publishes per
    held block its solved datum and what the solve did with its frontage
    welds.  ``held=True`` is ``pad_frontage_hold``: a block one of whose
    HELD contacts stands off the datum by more than
    ``frontage_hold_margin_m`` (``held_over_margin`` > 0), ``de`` = the
    worst.  ``held=False`` is ``pad_frontage_infeasible`` (spec §56 (3)): a
    block with a frontage weld the elastic LP RELEASED (``released`` > 0) —
    the pad's rim carries the step; ``de`` = ``released_max_m``,
    ``distance`` = the count, the site the worst released contact, and
    ``reading`` says whether the user was WARNED (``"warned"``, over the
    bar), not (``"not_warned"``, under it) or OVER THE BAR WITH NO LINE
    (``"unsaid"``: the record lacks a slot of the fixed copy,
    ``warning_unsaid`` names it) — never a silent class."""
    out: List[Violation] = []
    kind = "pad_frontage_hold" if held else "pad_frontage_infeasible"
    for rec in platforms_ll or ():
        if not isinstance(rec, dict) or rec.get("refused") or "datum" not in rec:
            continue
        if held:
            if not int(rec.get("held_over_margin", 0) or 0):
                continue
            de = float(rec.get("held_miss_max_m") or 0.0)
            ll = rec.get("hold_worst_ll") or rec.get("centroid_ll") or (0.0, 0.0)
            n = int(rec.get("held_contacts", 0) or 0)
        else:
            n = int(rec.get("released", 0) or 0)
            if not n:
                continue
            de = float(rec.get("released_max_m") or 0.0)
            ll = ((rec.get("released_ll") or [None])[0]
                  or rec.get("centroid_ll") or (0.0, 0.0))
        way = _platform_way(str(rec.get("ref", "")), kind)
        dat = float(rec.get("datum", 0.0) or 0.0)
        v = Violation(grade_pct=0.0, excess_pct=0.0, distance_m=float(n),
                      de_m=de, way_a=way, way_b=way,
                      pt_a=(0.0, 0.0), pt_b=(0.0, 0.0), elev_a=dat, elev_b=dat)
        v.lat, v.lon = float(ll[0]), float(ll[1])
        if not held:
            v.reading = ("warned" if rec.get("warned") else
                         "unsaid" if rec.get("warning_unsaid") else "not_warned")
        out.append(v)
    return out
