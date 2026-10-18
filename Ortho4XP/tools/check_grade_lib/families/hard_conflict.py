"""§5a THE LAW CONFLICT family ``hard_conflict`` (flat-pad spec v2 §5a;
RULINGS 2026-09-30be / 30bf), SIDECAR-DECLARED from ``hard_conflict`` —
REPORT.  Moved verbatim from ``check_grade.py`` (issue #857)."""
from __future__ import annotations

from typing import List, Tuple

from check_grade_lib.rows import Violation, Way

LAW_FAMILY_ROWS: Tuple[Tuple[str, str, str], ...] = (
    # §5a THE LAW CONFLICT (flat-pad spec v2 §5a; RULINGS 2026-09-30be /
    # 30bf).  SIDECAR-DECLARED: the hard rows the pre-solve feasibility LP
    # relaxed, each with the laws it conflicts with — REPORT; bar empty.
    ("hard_conflict",
     "HARD law row the pre-solve feasibility LP relaxed (a conflict between laws)",
     "within"),
)


def _check_hard_conflict(hard_conflict_ll) -> List[Violation]:
    """§5a THE LAW CONFLICT (flat-pad spec v2 §5a; owner RULINGS 2026-09-30be,
    ratified 30bf) — REPORT, one row per HARD row the pre-solve feasibility
    LP relaxed.

    SIDECAR-DECLARED like ``platform_rim_relief``: the solve publishes per
    relaxed row its law (``row``), the laws it conflicts with
    (``against``), its site and its relaxation ``s_m``; this reports
    exactly that.  The bar is an EMPTY list; a patch with no key reports
    nothing."""
    out: List[Violation] = []
    for rec in hard_conflict_ll or ():
        if not isinstance(rec, dict):
            continue
        site = rec.get("site") or (0.0, 0.0)
        against = ",".join(sorted((rec.get("against") or {}).keys()))[:80]
        # THE SIDE IS THE RECORD'S TIER (spec §55 (15)): a row the solve
        # relaxed in the GROUNDSIDE tier sides groundside (``row_side``
        # reads the ``role`` tag through ``effective_role``); the pad and
        # taxi tiers stay as they were — airside
        role = "groundside_pavement" if rec.get("tier") == "groundside" else "apron"
        way = Way("hard_conflict", role,
                  f"hard_conflict:{rec.get('tier', '')}:{rec.get('row', '')}",
                  "", [], [], {"against": against,
                               **({"role": role} if role != "apron" else {})})
        v = Violation(grade_pct=0.0, excess_pct=0.0, distance_m=0.0,
                      de_m=float(rec.get("s_m", 0.0) or 0.0), way_a=way, way_b=way,
                      pt_a=(0.0, 0.0), pt_b=(0.0, 0.0), elev_a=0.0, elev_b=0.0)
        v.lat, v.lon = float(site[0]), float(site[1])
        out.append(v)
    return out
