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
earlier stages, so the row is a one-term ``Linear`` on the follower's vertex
(a ``Band`` is the adjacent ground's soft window in the design solve —
MEASURED: 168 of 1,511 follow rows stated as ``Band`` were missed by up to
5.22 m with the hard set reported settled) — between an unknown and a
constant only, and nothing standing can move for it.  The followers are the
pieces AND the mapped-road ribbons sharing a ring edge with one.

WHERE TWO FIXED NEIGHBOURS DISAGREE by more than the piece can span, no
level satisfies both: the vertex is bound BETWEEN them (the interval from
the lower neighbour's ceiling to the upper neighbour's floor) and the pair
is REPORTED with both levels — a conflict of the standing ground that the
piece exposes, never one it settles by moving a neighbour.

THE LOT (spec §55 (3) 4; owner RULINGS 2026-10-06d).  A part of a cut piece
whose kind is ``lot`` (``model.planar.gap_part_kind``) holds the level of
the ROAD beside it flat across: every unknown vertex of the lot, however far
from the road, is bound to the nearest standing road's level within the
piece role's TRANSVERSE cap times its distance to that road — the road law's
own lateral window — and that level is its published target
(``report["lot_targets"]``, which the stage puts on ``preferred_z``).
WHICH LOTS (§55 (14) Q-G): only a lot part whose own stations are ROADS and
APRONS alone — a lot that also meets a pad, a standing lot, a band or a
structure takes no lot row and no target (its pads stand ``cap x d + floor``
away while the row would hold it within 2 % of the road).

A PART BESIDE A BELOW-GRADE STRUCTURE FOLLOWS ITS RIM, NEVER ITS FLOOR
(spec §60 (9) R1).  The cells BEHIND a declared step — a structure's floor
and ramp cells and its wall void (:class:`BehindStep`, the caller's: the two
sets live above this layer) — are never follow neighbours of a piece or a follower ribbon: the step is the
structure's own and no neighbour inherits a level across it.  What binds is
the structure's RIM at ground — an edge of the wall void whose other side is
none of those cells (the foot of the wall, shared with the floor, and the
seam between two wall parts are not rim).

A PART FOLLOWS ITS OWN GROUP (§55 (2) 5, §55 (14) Q-E).  The cut hands each
part its stations (:class:`PartStations`); a part vertex is bounded only by
a ring at whose nearest point the nearest station OF THAT RING is one of the
part's own level group.  A rim vertex beside a knife's end is within reach
of the other group's ring too — that step is the knife's, never the follow
row's; each bound so refused is reported (``report["declared"]``).  A
ribbon vertex's rows are unchanged (a ribbon has no part)."""
from __future__ import annotations

import typing as _t

import shapely
from shapely.strtree import STRtree

from ..law import Law
from ..law.tables import (gap_standoff_m, is_rigid_role, role_cap,
                          snap_margin_m)
from ..model.constraints import Linear, Source
from ..model.planar import (PlanarMap, face_edge_ids as _edges,
                            face_vertex_set as _vertices, gap_follower_faces,
                            gap_part_kind, is_gap_ref)

__all__ = ["GEN", "RULING", "LOT_RULING", "PartStations", "BehindStep",
           "gap_follow_rows", "reach_m"]

GEN = "gap_follow"
RULING = "gap_piece follows its standing neighbour across the stand-off (owner 2026-10-04o)"
LOT_RULING = "gap lot terrace holds the road's level across (owner 2026-10-06d)"
#: a ring nearer than this is the piece's OWN rim (the apron it welds to)
_OWN_RIM_M = 0.3


class PartStations(_t.NamedTuple):
    """THE CUT'S STATIONS AS ONE PART READS THEM (``classify/gap_terrace``:
    ``Part.stations`` and the level groups), keyed by the part's ref — the
    caller's (``pipeline/late_stage``), which knows the station classes."""

    stations: _t.Sequence[_t.Any]   #: the PIECE's stations (``.xy .ring``)
    own: frozenset[int]             #: the stations nearest this part that are in its own group
    lot_rows: bool                  #: Q-G: every station nearest the part is a road's or an apron's


class BehindStep(_t.NamedTuple):
    """THE ROLES BEHIND A DECLARED STEP (module docstring, R1) as the caller
    reads them from their owners — ``emit/graded.FLOOR_ROLES`` and the wall
    void's ``planar/basins.WALL_ROLE`` (``pipeline/late_stage.BEHIND_STEP``)."""

    floors: frozenset[str]   #: a structure's floor and ramp roles
    void: str                #: the wall void's role

    def edges_not_rim(self, faces) -> set[int]:
        """The edges that are NOT a structure's rim at ground: every edge of
        a floor / ramp cell, and every edge two cells behind the step share
        (the wall's foot, the seam between two wall parts)."""
        seen: set[int] = set()
        out: set[int] = set()
        for f in faces:
            if f.role in self.floors:
                out |= _edges(f)
            elif f.role == self.void:
                own = _edges(f)
                out |= own & seen
                seen |= own
        return out


class _OwnRings:
    """Q-E's one question: is the station of ``ring`` nearest ``xy`` one of
    the part's own?  (A ring with no station of the piece binds no part.)"""

    def __init__(self) -> None:
        self._trees: dict[tuple[int, str], tuple[list[int], STRtree | None]] = {}

    def allows(self, ps: PartStations, ring: str, xy) -> bool:
        key = (id(ps.stations), ring)
        if key not in self._trees:
            idx = [i for i, s in enumerate(ps.stations) if s.ring == ring]
            self._trees[key] = (idx, STRtree(shapely.points(
                [ps.stations[i].xy for i in idx])) if idx else None)
        idx, tree = self._trees[key]
        return tree is not None and idx[int(tree.nearest(shapely.Point(xy)))] in ps.own


def _part_of_vertex(planar: PlanarMap, gap) -> dict[int, str]:
    """A gap vertex's part ref (a breakline vertex is its lot's and its
    ramp's — one step part, one group, the same stations: the first by ref)."""
    out: dict[int, str] = {}
    for f in gap:
        ref = str(f.ref).split("#")[0]
        for v in _vertices(planar, f):
            if v not in out or ref < out[v]:
                out[v] = ref
    return out


def reach_m(law: Law, pad: bool = False) -> float:
    """The stand-off (``classify/gap_mint``: pad set-back + snap margin + one
    identity cell) plus one more identity cell for the snap.

    ``pad`` — THE REACH OF A PAD RING COVERS THE PIECE'S STAND-OFF AT THAT
    PAD (spec §62 (3) R-D rule 1; owner RULINGS 2026-10-09d (1) / 09f "a gap
    part welds to a pad wherever the pad's level is reachable inside the
    part's cap"): the stand-off itself (``law.tables.gap_standoff_m``, the
    mint's own value) plus the noding margin the mesh adds to it — the snap
    margin and two identity cells.  A pad's rim is a FIXED CONTACT of the
    part beside it, and the edge read found the nearest part vertex up to
    3 m off the rim, past the plain reach: with no follow row it followed
    its other stations and stood metres off the pad."""
    ident = float(law.tables.emit.identity.min_distinct_spacing_m)
    if pad:
        return gap_standoff_m(law) + snap_margin_m(law) + 2.0 * ident
    return float(law.tables.structures.building_pad.groundside_cutback_m) \
        + snap_margin_m(law) + 2.0 * ident


def gap_follow_rows(planar: PlanarMap, law: Law, fixed: _t.Mapping[int, float],
                    part_stations: _t.Mapping[str, PartStations] | None = None,
                    behind_step: BehindStep | None = None
                    ) -> tuple[list[Linear], dict]:
    """The follow rows of every gap-piece vertex that is an UNKNOWN (not in
    ``fixed``), and the report: rows, vertices bound, conflicts (each with
    both neighbours and their levels).  ``part_stations`` (the cut's, by
    part ref) narrows a part's bounds to its own group's rings and the lot
    rows to road+apron parts (module docstring); ``declared`` in the report
    lists every bound so refused.  ``behind_step``: the roles no follower
    follows across (R1) — floor cells bind nothing, a wall void its rim."""
    faces = planar.faces
    gap = [f for f in faces.values() if is_gap_ref(f.ref)]
    rep: dict = {"rows": 0, "conflicts": [], "declared": []}
    if not gap:
        return [], rep
    part_of = _part_of_vertex(planar, gap) if part_stations else {}
    own_rings = _OwnRings()
    piece_cap = role_cap(law, gap[0].role)
    cap_p = float(piece_cap.longitudinal) if piece_cap else 0.0
    knife = float(law.tables.structures.building_pad.groundside_cutback_m) \
        + snap_margin_m(law)
    reach, reach_pad = reach_m(law), reach_m(law, pad=True)
    V = planar.vertices
    segs, meta = [], []
    # THE FOLLOWERS (master 2026-10-04): the pieces, and the mapped-road
    # ribbons sharing a ring vertex with one — a ribbon is never lifted
    # above the fixed ground it runs beside.  A ribbon beside NO piece is
    # standing ground and binds as any ring does (spec §55 (13)).
    _gap, ribbons = gap_follower_faces(planar)
    follower = {f.id for f in ribbons}
    from .roads import road_family_roles
    road_roles = frozenset(road_family_roles(law))
    road_i: list[int] = []
    floors = behind_step.floors if behind_step else frozenset()
    not_rim = behind_step.edges_not_rim(faces.values()) if behind_step else set()
    for f in faces.values():
        if is_gap_ref(f.ref) or f.id in follower or f.role in floors:
            continue
        rc = role_cap(law, f.role)
        cap = min(cap_p, float(rc.longitudinal)) if rc and rc.longitudinal else cap_p
        pad = is_rigid_role(law, f.role)
        for e in _edges(f):
            if e in not_rim:
                continue
            ed = planar.edges[e]
            # a follower follows every FIXED point of a neighbouring ring:
            # an edge with one fixed end binds at that end
            ends = [v for v in (ed.a, ed.b) if v in fixed]
            if ends:
                p, q = ends[0], ends[-1]
                segs.append([V[p].xy, V[q].xy])
                meta.append((f"{f.role}:{str(f.ref).split('#')[0]}",
                             float(fixed[p]), float(fixed[q]), cap, pad))
                if f.role in road_roles:
                    road_i.append(len(segs) - 1)
    if not segs:
        return [], rep
    lines = shapely.linestrings(segs)
    tree = STRtree(lines)
    rows: list[Linear] = []
    todo = sorted({v for f in (*gap, *ribbons) for v in _vertices(planar, f)}
                  - set(fixed))
    pts = shapely.points([V[v].xy for v in todo])
    hit = tree.query(pts, predicate="dwithin", distance=max(reach, reach_pad))
    near: dict[int, list[int]] = {}
    for i, k in zip(hit[0], hit[1]):
        # each ring at its own reach: a pad's covers the stand-off (R-D)
        if meta[int(k)][4] or reach >= reach_pad or float(
                shapely.distance(lines[int(k)], pts[int(i)])) <= reach:
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
                at = shapely.line_interpolate_point(lines[k], t, normalized=True)
                best[name] = (d, z, allow, (at.x, at.y))
        ps = part_stations.get(part_of.get(v, "")) if part_stations else None
        if ps is not None:
            for name in sorted(best):
                if not own_rings.allows(ps, name, best[name][3]):
                    rep["declared"].append({"v": v, "ring": name,
                                            "z": round(best.pop(name)[1], 3)})
        if not best:
            continue
        lo_n, lo = max(((z - a, n) for n, (_d, z, a, _at) in best.items()))[::-1]
        hi_n, hi = min(((z + a, n) for n, (_d, z, a, _at) in best.items()))[::-1]
        if lo > hi:
            # two fixed neighbours disagree: the piece stands BETWEEN them
            rep["conflicts"].append({
                "v": v, "xy": tuple(V[v].xy), "gap_m": round(lo - hi, 3),
                "upper": lo_n, "upper_m": round(best[lo_n][1], 3),
                "lower": hi_n, "lower_m": round(best[hi_n][1], 3)})
            lo, hi = hi, lo
        # the row cites the two rings that bound it (the floor's, the ceiling's)
        rows.append(Linear(((v, 1.0),), lo, hi, Source(GEN, RULING, (lo_n, hi_n))))
    rep["rows"] = len(rows)
    rep["vertices_in_reach"] = len(near)
    lot_rows, rep["lot_targets"] = _lot_rows(
        planar, [f for f in gap if _takes_lot_rows(f, part_stations)], fixed,
        lines, meta, road_i, float(piece_cap.transverse) if piece_cap else 0.0)
    rep["lot_rows"] = len(lot_rows)
    return [*rows, *lot_rows], rep


def _takes_lot_rows(face, part_stations) -> bool:
    """A ``lot`` part — with the cut's stations in hand, one that meets
    roads and aprons alone (Q-G)."""
    if gap_part_kind(face.ref) != "lot":
        return False
    if part_stations is None:
        return True
    ps = part_stations.get(str(face.ref).split("#")[0])
    return ps is not None and ps.lot_rows


def _lot_rows(planar: PlanarMap, lots, fixed, lines, meta, road_i: list[int],
              c_t: float) -> tuple[list[Linear], dict[int, float]]:
    """THE LOT'S ROWS (module docstring): ``|z_v - L(v)| <= cT x d_R(v)`` on
    every unknown vertex of the ``lots`` (the lot parts that take them), ``L`` the level of the nearest
    standing road at its nearest point and ``d_R`` the distance to it.
    ``(rows, {vertex: L})``."""
    if not lots or not road_i:
        return [], {}
    V = planar.vertices
    todo = sorted({v for f in lots for v in _vertices(planar, f)} - set(fixed))
    if not todo:
        return [], {}
    roads = lines[road_i]
    pts = shapely.points([V[v].xy for v in todo])
    pi, ri = STRtree(roads).query_nearest(pts, all_matches=False)
    rows: list[Linear] = []
    target: dict[int, float] = {}
    for i, k in sorted(zip(pi.tolist(), ri.tolist())):
        name, za, zb, _cap, _pad = meta[road_i[k]]
        line = roads[k]
        length = float(shapely.length(line))
        t = float(shapely.line_locate_point(line, pts[i])) / length if length else 0.0
        level = (1.0 - t) * za + t * zb
        allow = c_t * float(shapely.distance(line, pts[i]))
        v = todo[i]
        if v in target:
            continue
        target[v] = level
        rows.append(Linear(((v, 1.0),), level - allow, level + allow,
                           Source(GEN, LOT_RULING, (name,))))
    return rows, target
