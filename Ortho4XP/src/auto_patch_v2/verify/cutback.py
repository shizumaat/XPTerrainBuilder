"""THE GROUNDSIDE CUT-BACK STRIP, read off the emitted product (issue #97
M1; the v2 twin of ``check_grade._check_groundside_cutback``).

``planar/zones.zone_regions`` cuts every adjacent-ground band back
``zones.adjacent_ground.groundside_cutback_m`` (+ the snap margin) from
groundside pavement, so a road and the zone beside it never share a
vertex and "the gap terraces".  Nothing in the SOLVE prices that terrace:
``constraints.groundside.groundside_ramps`` pairs APRON vertices only,
``adjacent_ground_step`` is within ONE zone face, and ``cross_shape``
reads a sub-metre strip as noise.

REPORT-ONLY, exactly as on the oracle: every row carries
:data:`OUT_OF_SCOPE`, because what the strip SHOULD carry is the owner's
Q-97 (#58) and no law governs it yet (``families.toml`` ``solver =
"diagnostic"``, ``cockpit = "grade"``).  The family is a READING of the
emitted rings — the road rings and the zone bands are both faces of the
graded surface — so verify owes it a reader and the parity hole it left
was issue #108, not a structural blindness.

THE POPULATIONS ARE LAW-DERIVED, never typed here (the census-wrapper
precedent): the near side is ``constraints.roads.road_family_roles``
(the road cross-section family's own roles) and the far side is the
``adjacent_ground:*`` refs plus ``emit.terrace.shape_roles`` minus apron
(apron is ``groundside_ramps``' own row).  NOTE (blast role-literal
hazard): both read role VALUES out of the law tables, so a role rename
moves with the tables and never silently empties a set.
"""
from __future__ import annotations

from ..law.tables import snap_margin_m
from .frame import Patch, Row, Shape, pair_side, row

__all__ = ["groundside_cutback", "FAMILY", "OUT_OF_SCOPE", "ZONE_REF_PREFIX",
           "horizon_m", "far_roles"]

FAMILY = "groundside_cutback"

#: The ``out_of_scope`` stamp every row carries — the SAME string the
#: oracle stamps (``check_grade.GROUNDSIDE_CUTBACK_OUT_OF_SCOPE``), so a
#: row diff by (family, roles, site) joins the two readers' rows.
OUT_OF_SCOPE = "cutback_intent_q97"

#: The ref prefix of an adjacent-ground zone band
#: (``check_grade.V2_ADJACENT_GROUND_REF_PREFIX``).
ZONE_REF_PREFIX = "adjacent_ground:"

#: The apron is the one aircraft-pavement role NOT on the far side: its
#: stand-off is ``constraints.groundside.groundside_ramps``' own row.
_APRON_ROLE = "apron"


def horizon_m(p: Patch) -> float:
    """THE STAND-OFF HORIZON — the ONE derivation
    ``constraints.groundside.groundside_ramps`` uses across the same
    stand-off (cut-back + weld spacing + the snap margin), which is also
    ``check_grade.groundside_cutback_frame``'s."""
    law = p.law
    return (float(law.tables.zones.adjacent_ground.groundside_cutback_m)
            + float(law.tables.emit.identity.weld_spacing_m)
            + snap_margin_m(law))


def far_roles(p: Patch) -> frozenset[str]:
    """The AIRCRAFT-pavement roles across the strip: the emitter's own
    ``emit.terrace.shape_roles`` less the apron."""
    return frozenset(r for r in p.law.tables.emit.terrace.shape_roles
                     if r != _APRON_ROLE)


def _is_far(sh: Shape, far: frozenset[str]) -> bool:
    if str(sh.ref or "").startswith(ZONE_REF_PREFIX):
        return True
    return sh.role in far


def groundside_cutback(p: Patch) -> list[Row]:
    """One row per road ring vertex whose terrace across the stand-off
    exceeds ``emit.terrace.groundside_ramp_max``.

    The pair is the road vertex and the NEAREST vertex of a zone band or
    a non-apron aircraft-pavement face within :func:`horizon_m`, by
    IDENTITY and not the census weld tolerance (the strip is 0.48-0.95 m
    at HECA, so a 0.5 m weld tolerance would drop its narrow half)."""
    import numpy as np
    from scipy.spatial import cKDTree

    from ..constraints.roads import road_family_roles

    far = far_roles(p)
    far_xy: list[tuple[float, float]] = []
    far_rec: list[tuple[str, str, float, int]] = []   # ref, role, z, vertex id
    for sh in (*p.shapes, *p.features):
        if not _is_far(sh, far):
            continue
        for vid, xy, z in zip(sh.ids, sh.xy, sh.z):
            far_xy.append(xy)
            far_rec.append((sh.ref, sh.role, float(z), int(vid)))
    if not far_xy:
        return []
    tree = cKDTree(np.asarray(far_xy))
    cap = float(p.law.tables.emit.terrace.groundside_ramp_max)
    horizon = horizon_m(p)
    roads = frozenset(road_family_roles(p.law))
    near_xy: list[tuple[float, float]] = []
    near_rec: list[tuple[Shape, int, float]] = []       # shape, vertex id, z
    for sh in p.shapes:
        if sh.role not in roads:
            continue
        for vid, xy, z in zip(sh.ids, sh.xy, sh.z):
            near_xy.append(xy)
            near_rec.append((sh, int(vid), float(z)))
    if not near_xy:
        return []
    # ONE BATCHED QUERY, not one per vertex: at 40k road vertices the
    # per-vertex Python call ran 1.10 s (1.8 % of the 60 s per-airport
    # budget) against 36 ms here, and the loop below walks only the pairs
    # inside the horizon.
    arr = np.asarray(near_xy)
    dist, idx = tree.query(arr)
    dist = np.asarray(dist, dtype=float)
    idx = np.asarray(idx, dtype=int)
    far_z = np.asarray([r[2] for r in far_rec], dtype=float)
    near_z = np.asarray([r[2] for r in near_rec], dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        grades = np.abs(near_z - far_z[idx]) / dist
    keep = np.flatnonzero((dist > 0.0) & (dist <= horizon) & (grades > cap))
    out: list[Row] = []
    seen: set[tuple[int, int]] = set()
    for i in keep.tolist():
        sh, vid, z = near_rec[i]
        ref_b, role_b, zb, vid_b = far_rec[int(idx[i])]
        key = (vid, vid_b)
        if vid_b == vid or key in seen:
            continue
        seen.add(key)
        d = float(dist[i])
        de = abs(z - zb)
        role_pair = (sh.role, role_b or sh.role)
        la, lo = p.ll.get(vid, (None, None))
        out.append(row(FAMILY, role_pair, pair_side(p, *role_pair),
                       de, de / d * 100.0, cap * 100.0, d,
                       near_xy[i], far_xy[int(idx[i])], sh.ref, ref_b,
                       out_of_scope=OUT_OF_SCOPE, lat=la, lon=lo))
    out.sort(key=lambda r: -float(r["magnitude_m"]))
    return out
