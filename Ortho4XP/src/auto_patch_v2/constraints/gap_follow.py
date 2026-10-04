"""A GAP PIECE FOLLOWS ITS STANDING NEIGHBOURS ACROSS THE STAND-OFF (spec
§53 (13); owner RULINGS 2026-10-04o, master 2026-10-04) — the LAST STAGE's
own generator.

A §53 gap piece stands off every standing cell but the apron it welds to and
the ribbons solved with it (``classify/gap_mint``), so no generator that
reads a shared rim ties it to the pad, road, lot or band beside it: alone it
follows the terrain and the stand-off becomes a step.  This is §28's
relation read for a gap piece: every piece vertex within reach of a FIXED
standing ring is bound to that ring's level at its nearest point,

    |z_piece - z_ring| <= cap x distance,

``cap`` the tighter of the two faces' own longitudinal caps.  Beside a PAD
the piece meets the pad AT the pad's level: the distance is counted from the
pad's set-back (the facade strip's rule), so at the stand-off the allowance
is one identity cell of grade.  The ring's level is a CONSTANT of the
earlier stages, so the row is a ``Band`` on the piece's vertex — between an
unknown and a constant only, and nothing standing can move for it.

WHERE TWO FIXED NEIGHBOURS DISAGREE by more than the piece can span, no
level satisfies both: the vertex is bound BETWEEN them (the interval from
the lower neighbour's ceiling to the upper neighbour's floor) and the pair
is REPORTED with both levels — a conflict of the standing ground that the
piece exposes, never one it settles by moving a neighbour."""
from __future__ import annotations

import typing as _t

import shapely
from shapely.strtree import STRtree

from ..law import Law
from ..law.tables import is_rigid_role, role_cap, snap_margin_m
from ..model.constraints import Band, Source
from ..model.planar import PlanarMap, is_gap_ref, is_osm_ribbon_ref

__all__ = ["GEN", "RULING", "gap_follow_rows", "reach_m"]

GEN = "gap_follow"
RULING = "gap_piece follows its standing neighbour across the stand-off (owner 2026-10-04o)"
#: a ring nearer than this is the piece's OWN rim (the apron it welds to)
_OWN_RIM_M = 0.3


def reach_m(law: Law) -> float:
    """The stand-off (``classify/gap_mint``: pad set-back + snap margin + one
    identity cell) plus one more identity cell for the snap."""
    ident = float(law.tables.emit.identity.min_distinct_spacing_m)
    return float(law.tables.structures.building_pad.groundside_cutback_m) \
        + snap_margin_m(law) + 2.0 * ident


def _vertices(pm: PlanarMap, f) -> set[int]:
    out = {int(v) for v in pm.ring_vertices(f.ring)}
    for h in getattr(f, "holes", ()) or ():
        out.update(int(v) for v in pm.ring_vertices(h))
    return out


def _edges(f) -> set[int]:
    out = {int(e) for e in f.ring}
    for h in getattr(f, "holes", ()) or ():
        out.update(int(e) for e in h)
    return out


def gap_follow_rows(planar: PlanarMap, law: Law,
                    fixed: _t.Mapping[int, float]) -> tuple[list[Band], dict]:
    """The follow rows of every gap-piece vertex that is an UNKNOWN (not in
    ``fixed``), and the report: rows, vertices bound, conflicts (each with
    both neighbours and their levels)."""
    faces = planar.faces
    gap = [f for f in faces.values() if is_gap_ref(f.ref)]
    rep: dict = {"rows": 0, "conflicts": []}
    if not gap:
        return [], rep
    piece_cap = role_cap(law, gap[0].role)
    cap_p = float(piece_cap.longitudinal) if piece_cap else 0.0
    knife = float(law.tables.structures.building_pad.groundside_cutback_m) \
        + snap_margin_m(law)
    reach = reach_m(law)
    V = planar.vertices
    segs, meta = [], []
    for f in faces.values():
        if is_gap_ref(f.ref) or (f.role == "service_road" and is_osm_ribbon_ref(f.ref)):
            continue
        rc = role_cap(law, f.role)
        cap = min(cap_p, float(rc.longitudinal)) if rc and rc.longitudinal else cap_p
        pad = is_rigid_role(law, f.role)
        for e in _edges(f):
            ed = planar.edges[e]
            if ed.a in fixed and ed.b in fixed:
                segs.append([V[ed.a].xy, V[ed.b].xy])
                meta.append((f"{f.role}:{str(f.ref).split('#')[0]}",
                             float(fixed[ed.a]), float(fixed[ed.b]), cap, pad))
    if not segs:
        return [], rep
    lines = shapely.linestrings(segs)
    tree = STRtree(lines)
    src = Source(GEN, RULING, ())
    rows: list[Band] = []
    todo = sorted({v for f in gap for v in _vertices(planar, f)} - set(fixed))
    pts = shapely.points([V[v].xy for v in todo])
    hit = tree.query(pts, predicate="dwithin", distance=reach)
    near: dict[int, list[int]] = {}
    for i, k in zip(hit[0], hit[1]):
        near.setdefault(int(i), []).append(int(k))
    for i, ks in sorted(near.items()):
        v = todo[i]
        best: dict[str, tuple] = {}
        for k in ks:
            d = float(shapely.distance(lines[k], pts[i]))
            if d < _OWN_RIM_M:
                continue
            name, za, zb, cap, pad = meta[k]
            if name not in best or d < best[name][0]:
                length = float(shapely.length(lines[k]))
                t = float(shapely.line_locate_point(lines[k], pts[i])) / length \
                    if length else 0.0
                z = (1.0 - t) * za + t * zb
                allow = cap * (max(0.0, d - knife) if pad else d)
                best[name] = (d, z, allow)
        if not best:
            continue
        lo_n, lo = max(((z - a, n) for n, (_d, z, a) in best.items()))[::-1]
        hi_n, hi = min(((z + a, n) for n, (_d, z, a) in best.items()))[::-1]
        if lo > hi:
            # two fixed neighbours disagree: the piece stands BETWEEN them
            rep["conflicts"].append({
                "v": v, "xy": tuple(V[v].xy), "gap_m": round(lo - hi, 3),
                "upper": lo_n, "upper_m": round(best[lo_n][1], 3),
                "lower": hi_n, "lower_m": round(best[hi_n][1], 3)})
            lo, hi = hi, lo
        rows.append(Band(v, lo, hi, src))
    rep["rows"] = len(rows)
    rep["vertices_in_reach"] = len(near)
    return rows, rep
