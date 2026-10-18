"""THE UNIT PLATFORM families (unit-platform spec §4 (5) / §1 (2); RULINGS
2026-09-28a (1)): ``platform_rim_relief`` and ``platform_refused``, both
SIDECAR-DECLARED from ``platforms`` — REPORT.  Moved verbatim from
``check_grade.py`` (issue #857)."""
from __future__ import annotations

from typing import List, Tuple

from check_grade_lib.rows import Violation, Way

LAW_FAMILY_ROWS: Tuple[Tuple[str, str, str], ...] = (
    # THE UNIT PLATFORM (unit-platform spec §4 (5); RULINGS 2026-09-28a
    # (1)).  SIDECAR-DECLARED like the strip above: ``platforms`` carries
    # each platform's solved plane and its welded rim's relief; REPORT.
    ("platform_rim_relief",
     "PLATFORM rim relief the collar carries (one row per platform)",
     "within"),
    ("platform_refused",
     "UNIT PAD that got NO platform (erosion left no inner ring)",
     "within"),
)


def _platform_way(ref: str, kind: str) -> "Way":
    return Way(kind, "building", f"{kind}:{ref}", "", [], [], {"role": "building"})


def _check_platform_rim_relief(platforms_ll) -> List[Violation]:
    """THE UNIT PLATFORM'S RIM RELIEF (unit-platform spec §4 (5); owner
    RULINGS 2026-09-28a (1)) — REPORT, one row per platform.

    SIDECAR-DECLARED like ``jetway_strip``: the build publishes per
    platform its SOLVED plane and the relief its welded (airside) rim
    carries against it (``platforms``: ``rim_relief_max_m``, ``worst_ll``,
    ``collar_m``, ``collar_needed_m``); this reports exactly that, so a
    platform whose relief outgrows its collar is read here and never
    silently.  A record with no ``rim_relief_max_m`` is no row.  A patch
    with no key reports nothing."""
    out: List[Violation] = []
    for rec in platforms_ll or ():
        if (not isinstance(rec, dict) or rec.get("refused")
                or rec.get("rim_relief_max_m") is None):
            # a record with no ``rim_relief_max_m`` carries no bank against
            # airside (spec §56 (3): a unit pad has no collar; master ruling
            # 2026-10-08 R3 (6)) — only a landing's welded bank reads here
            continue
        ref = str(rec.get("ref", ""))
        mx = float(rec.get("rim_relief_max_m", 0.0) or 0.0)
        ll = rec.get("worst_ll") or rec.get("centroid_ll") or (0.0, 0.0)
        lvl = float(rec.get("level", 0.0) or 0.0)
        way = _platform_way(ref, "platform_rim_relief")
        v = Violation(grade_pct=0.0, excess_pct=0.0,
                      distance_m=float(rec.get("collar_m", 0.0) or 0.0),
                      de_m=mx, way_a=way, way_b=way,
                      pt_a=(0.0, 0.0), pt_b=(0.0, 0.0),
                      elev_a=float(rec.get("worst_z", lvl) or lvl), elev_b=lvl)
        v.lat, v.lon = float(ll[0]), float(ll[1])
        out.append(v)
    return out


def _check_platform_refused(platforms_ll) -> List[Violation]:
    """A UNIT PAD THE PLATFORM REFUSED (unit-platform spec §1 (2)) — REPORT,
    one row per refusal (its erosion by the collar left no inner ring of
    ``cluster_pad_min_m2``; it keeps the welded plate).  Sidecar-declared;
    the row carries the pad's area in ``distance_m``'s place of honour
    (``de_m`` 0: a refusal has no height)."""
    out: List[Violation] = []
    for rec in platforms_ll or ():
        if not isinstance(rec, dict) or not rec.get("refused"):
            continue
        way = _platform_way(str(rec.get("ref", "")) + ":" + str(rec["refused"]),
                            "platform_refused")
        v = Violation(grade_pct=0.0, excess_pct=0.0,
                      distance_m=float(rec.get("pad_m2", 0.0) or 0.0),
                      de_m=0.0, way_a=way, way_b=way,
                      pt_a=(0.0, 0.0), pt_b=(0.0, 0.0), elev_a=0.0, elev_b=0.0)
        v.lat, v.lon = 0.0, 0.0
        out.append(v)
    return out
