"""§16g (10) (3) THE PAD IS THE CLUSTER family ``pad_cluster_mismatch``
(owner RULINGS 2026-09-14x), SIDECAR-DECLARED.  Moved verbatim from
``check_grade.py`` (issue #857), which re-exports it."""
from __future__ import annotations

from typing import List, Tuple

from check_grade_lib.rows import Violation, Way

LAW_FAMILY_ROWS: Tuple[Tuple[str, str, str], ...] = (
    # §16g (10) (3) THE PAD IS THE CLUSTER (owner RULINGS 2026-09-14x).
    # Sidecar-declared like the family above it: the build declares the
    # defect set over its whole cluster population and this prices it.
    ("pad_cluster_mismatch",
     "PAD <-> CLUSTER MISMATCH (a pad spanning two clusters, or a cluster "
     "spanning two pads)", "within"),
)


def _check_pad_cluster_mismatch(recs) -> List[Violation]:
    """§16g (10) (3) THE PAD IS THE CLUSTER, CRITICAL (owner RULINGS
    2026-09-14x, verbatim: *"pads must match building clusters, no
    building, or cluster can span multiple pads, if it does, it means we
    didn't identify the building shape or cluster correctly.  They should
    match exactly."*).

    SIDECAR-DECLARED, like ``basin_floor_declaration`` and
    ``eat_ceiling`` above it, and for the same reason: the relation is
    between the emitted ``building`` faces and the pack's CLUSTERS, and a
    cluster's footprint outlines live in the rebake plan, which no patch
    carries.  The build therefore declares the DEFECT SET over its whole
    cluster population (``constraints.cluster_pad.pad_cluster_mismatch``,
    the SAME ``_face_map`` the cluster pad itself is derived from — one
    reading, two readers) and this prices exactly it.  A patch with no
    key — v1's own output, or a v2 patch predating 14x — reports nothing,
    as it did before.

    One row per declared record.  There is no magnitude to report: a
    misidentified shape is not a grade excess, it is a shape that must
    never be seated over, so the row carries its counterparties in the
    way name and zero metres."""
    out: List[Violation] = []
    for rec in (recs or []):
        if not isinstance(rec, dict):
            continue
        kind = str(rec.get("kind") or "pad_cluster_mismatch")
        ref = str(rec.get("ref") or "")
        others = [str(q) for q in (rec.get("others") or [])]
        name = f"{kind}:{ref}" + (f" -> {','.join(others)}" if others else "")
        way = Way("pad_cluster_mismatch", "object_pad", name, "", [], [],
                  {"role": "object_pad"})
        v = Violation(grade_pct=0.0, excess_pct=0.0, distance_m=0.0,
                      de_m=float(max(0, len(others) - 1)),
                      way_a=way, way_b=way, pt_a=(0.0, 0.0), pt_b=(0.0, 0.0),
                      elev_a=0.0, elev_b=0.0)
        lat, lon = rec.get("lat"), rec.get("lon")
        if lat is not None and lon is not None:
            v.lat, v.lon = float(lat), float(lon)
        out.append(v)
    return out
