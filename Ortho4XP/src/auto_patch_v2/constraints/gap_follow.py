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

from ..classify.gap_terrace import APRON, ROAD
from ..law import Law
from ..law.tables import is_rigid_role, role_cap, snap_margin_m
from ..model.constraints import Linear, Source
from ..model.planar import (PlanarMap, face_edge_ids as _edges,
                            face_vertex_set as _vertices, gap_follower_faces,
                            gap_part_kind, is_gap_ref)

__all__ = ["GEN", "RULING", "LOT_RULING", "PartStations", "gap_follow_rows",
           "reach_m"]

GEN = "gap_follow"
RULING = "gap_piece follows its standing neighbour across the stand-off (owner 2026-10-04o)"
LOT_RULING = "gap lot terrace holds the road's level across (owner 2026-10-06d)"
#: a ring nearer than this is the piece's OWN rim (the apron it welds to)
_OWN_RIM_M = 0.3


#: the station classes a lot part may meet and still take its lot rows
_LOT_CLASSES = frozenset({ROAD, APRON})


class PartStations(_t.NamedTuple):
    """THE CUT'S STATIONS AS ONE PART READS THEM (``classify/gap_terrace``:
    ``Part.stations`` and the level groups), keyed by the part's ref."""

    stations: _t.Sequence[_t.Any]   #: the PIECE's stations (``.xy .ring .cls``)
    mine: frozenset[int]            #: indices of the stations nearest this part
    own: frozenset[int]             #: of ``mine``, those in the part's own group

    @property
    def lot_rows(self) -> bool:
        """Q-G: every station of the part is a road's or an apron's."""
        return bool(self.mine) and all(
            self.stations[i].cls in _LOT_CLASSES for i in self.mine)


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


def reach_m(law: Law) -> float:
    """The stand-off (``classify/gap_mint``: pad set-back + snap margin + one
    identity cell) plus one more identity cell for the snap."""
    ident = float(law.tables.emit.identity.min_distinct_spacing_m)
    return float(law.tables.structures.building_pad.groundside_cutback_m) \
        + snap_margin_m(law) + 2.0 * ident


def gap_follow_rows(planar: PlanarMap, law: Law, fixed: _t.Mapping[int, float],
                    part_stations: _t.Mapping[str, PartStations] | None = None
                    ) -> tuple[list[Linear], dict]:
    """The follow rows of every gap-piece vertex that is an UNKNOWN (not in
    ``fixed``), and the report: rows, vertices bound, conflicts (each with
    both neighbours and their levels).  ``part_stations`` (the cut's, by
    part ref) narrows a part's bounds to its own group's rings and the lot
    rows to road+apron parts (module docstring); ``declared`` in the report
    lists every bound so refused."""
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
    reach = reach_m(law)
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
    for f in faces.values():
        if is_gap_ref(f.ref) or f.id in follower:
            continue
        rc = role_cap(law, f.role)
        cap = min(cap_p, float(rc.longitudinal)) if rc and rc.longitudinal else cap_p
        pad = is_rigid_role(law, f.role)
        for e in _edges(f):
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
