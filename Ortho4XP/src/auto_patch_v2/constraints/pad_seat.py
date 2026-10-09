"""THE LANDSIDE-ONLY PAD'S SEAT (spec ``auto-patch-v2/design-surface-spec.md``
§62 (2) R-C; owner RULINGS 2026-10-09d (1) "pavement touching a pad welds and
grades inside its own cap, else the SEAT is wrong", 2026-10-08c (4) "no step
between pad and pavement", 2026-10-09c (2a) "a pad takes a fixed contact's
level", 2026-10-09f "a pad with no airside frontage seats from the pavement
touching it").

A pad that fronts NO airside pavement and at least one groundside face (§20's
own relation, ``pads._fronting``) is a SEATED pad with ONE LEADER:

* the leader is ONE touching FACE, never a role's whole population — the
  SENIOR by ``precedence.toml`` (the road family, then ``groundside_pavement``,
  then ``parking_lot``), ties broken by the LONGEST CONTACT (§28 (1)'s
  "largest shared edge").  A road is senior because it is the face whose level
  another law fixes (its airside contact, its ramp): the pad takes the level
  of the contact that cannot give;
* the pad's plane takes that face's level through the ONE existing row
  (``pads.pad_frontage_level``: the pad's own mean against the face's value
  beside its contacts, one-way, the pad following) under :data:`SEAT_RULING`,
  which ``[design] hard_rulings`` names — a seat is not a preference;
* a second leader would be a second seat: the junior level rows a
  landside-only pad carried are not minted.

Until §62 a landside-only pad's de-facto seat was the 29ac fallback cap's
two-sided weld of a rim vertex to whichever pavement vertex stood within a
metre (``constraints/pavement_cap``); that weld is gone (R-F) and this is the
relation it stood in for.

A plane GROUP (``cluster_pad.plane_groups``: a pad, or the faces of one
terminal cluster — one plane) has one seat.  A group with any airside
frontage, a HELD block and a viaduct's ramp LANDING (held at its deck's
level, owner RULINGS 2026-10-03e) are another law's and are not here —
measured where it was found: seated on the lot beside it a landing's hard
seat stood 8 m against its hard deck row.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

from shapely.geometry import Point

from ..law import Law
from ..law.tables import authority_rank, role_side
from ..model.airport import Airport
from ..model.map_memo import per_map
from ..model.planar import PlanarMap

__all__ = ["SEAT_RULING", "Seat", "landside_seats", "seat_of_face",
           "seat_records"]

#: The head of a landside-only pad's ONE level row.  Named by ``[design]
#: hard_rulings`` (the seat), ``one_way_rulings`` (the pad follows, never
#: pulls) and ``pad_level_rulings`` (§9b: the pad's own vertices carry no
#: DEM datum).
SEAT_RULING = "structures.building_pad frontage_level seat"

#: one memo per planar map (``model.map_memo``)
_SEATS: dict[int, tuple[_t.Any, dict]] = {}

Leaders = tuple[tuple[int, tuple[tuple[int, float], ...]], ...]


@_dc.dataclass(frozen=True)
class Seat:
    """One plane group's seat: the leader FACE, the contact it was chosen
    on, and the level fit's rows as data (``pads.frontage_leaders``)."""

    #: the plane group's id and its pad faces
    group: int
    faces: tuple[int, ...]
    #: the leader — a groundside pavement face
    leader: int
    role: str
    ref: str
    contact_m: float
    #: ``((contact vertex, ((leader vertex, weight), ...)), ...)``
    pairs: Leaders


def _tier(law: Law, role: str, roads: frozenset[str]) -> int:
    """A role's seniority tier — its precedence rank, the whole road family
    standing at its most senior member's (a junction is a road)."""
    if role in roads:
        return min(authority_rank(law, r) for r in roads)
    return authority_rank(law, role)


def _contact_m(planar: PlanarMap, ring_cycles: _t.Iterable[_t.Sequence[int]],
               front: _t.AbstractSet[int]) -> float:
    """§28 (1)'s "largest shared edge": the length of the face's ring edges
    with BOTH endpoints on the frontage."""
    xy = planar.vertices
    total = 0.0
    for cyc in ring_cycles:
        cyc = list(cyc)
        for a, b in zip(cyc, cyc[1:] + cyc[:1]):
            if a in front and b in front:
                (xa, ya), (xb, yb) = xy[a].xy, xy[b].xy
                total += math.hypot(xa - xb, ya - yb)
    return total


def landside_seats(planar: PlanarMap, law: Law, airport: Airport | None
                   ) -> dict[int, Seat]:
    """THE SEATS AS DATA — plane-group id -> :class:`Seat`, for every plane
    group that fronts no airside pavement and at least one groundside face.
    ONE derivation per map (memoised): ``pads.pad_frontage_level`` mints the
    row from it, §28 reads the leader it must not make follow, the
    publication writes the record."""
    # the clusters are the airport's: an answer derived without it is kept
    # apart and never read as the pipeline's
    key = "seats" if airport is not None else "seats:no-airport"
    memo = per_map(_SEATS, planar)
    if key in memo:
        return memo[key]
    from .cluster_pad import plane_groups
    from ..model.planar import platform_ref_of
    from ..model.platform import LANDINGS, datum_vertices
    from .pads import (_LEADER_NEAR_M, _fronting, _pad_polys,
                       _pavement_geom_faces, frontage_leaders,
                       frontage_radius_m)
    from .precedence import view
    from .roads import road_family_roles
    out: dict[int, Seat] = {}
    memo[key] = out
    fronting = _fronting(planar, law)
    if not fronting:
        return out
    landside = {fid for fid, by_role in fronting.items()
                if not any(role_side(law, r) == "airside" for r in by_role)}
    if not landside:
        return out
    polys = {fid: (set(group), poly)
             for fid, _ref, group, poly in _pad_polys(planar, law)}
    geoms = [g for g in _pavement_geom_faces(planar, law)
             if role_side(law, g[0]) != "airside"]
    if not geoms:
        return out
    from shapely.strtree import STRtree
    tree = STRtree([g[2] for g in geoms])
    vw = view(planar, law)
    r = frontage_radius_m(law)
    roads = frozenset(road_family_roles(law))
    held = datum_vertices(planar, law)
    xy = {v: vx.xy for v, vx in planar.vertices.items()}
    for gid, ref, _group, fids in plane_groups(planar, law, airport):
        if held and platform_ref_of(str(ref)) in held:
            continue                  # a HELD block: its frontage hold
        if any(platform_ref_of(str(planar.faces[q].ref)) in LANDINGS for q in fids):
            continue                  # a ramp LANDING: its deck's level (10-03e)
        mine = [q for q in fids if q in fronting]
        if not mine or any(q not in landside for q in mine):
            continue                  # fronts nothing, or fronts airside
        # per candidate face: contact length and the level fit's pairs
        cand: dict[int, tuple[float, list]] = {}
        for q in mine:
            if q not in polys:
                continue              # a sliver rim: no polygon to measure
            pad_vs, poly = polys[q]
            hits = (tree.query(poly, predicate="dwithin", distance=r)
                    if r > 0.0 else tree.query(poly, predicate="intersects"))
            for gi in hits:
                _role, vs, gpoly, fid = geoms[int(gi)]
                contacts = vs & pad_vs
                if not contacts and r > 0.0:
                    contacts = {v for v in pad_vs - vs
                                if gpoly.distance(Point(*xy[v])) <= r}
                own = vs - pad_vs
                if not contacts or not own:
                    continue
                dist = {v: poly.distance(Point(*xy[v])) for v in own}
                front = {v for v, dd in dist.items() if dd <= r}
                cut = min(dist.values()) + _LEADER_NEAR_M
                near = {v for v, dd in dist.items() if dd <= cut}
                per = frontage_leaders(planar, contacts, own, near=near)
                if not per:
                    continue
                length = _contact_m(
                    planar, [vw.rings[fid], *vw.holes[fid]], front)
                got = cand.setdefault(fid, (0.0, []))
                cand[fid] = (got[0] + length, got[1] + per)
        if not cand:
            continue
        best = min(cand, key=lambda f: (_tier(law, planar.faces[f].role, roads),
                                        -cand[f][0], f))
        face = planar.faces[best]
        out[gid] = Seat(gid, tuple(fids), best, face.role, str(face.ref),
                        cand[best][0],
                        tuple((c, tuple(lw)) for c, lw in cand[best][1]))
    return out


def seat_of_face(planar: PlanarMap, law: Law, airport: Airport | None
                 ) -> dict[int, Seat]:
    """Pad FACE id -> the seat of its plane group (every face of a cluster
    shares the one seat)."""
    return {q: s for s in landside_seats(planar, law, airport).values()
            for q in s.faces}


def seat_records(planar: PlanarMap, law: Law, airport: Airport | None, z
                 ) -> list[dict[str, _t.Any]]:
    """THE SEATS AS PUBLISHED (spec §62 (2) rule 4) — one ``platforms[]``
    record per seated landside-only plane group, so a pad with a leader is
    never silent: its ref, ``seat: "landside"``, the leader face and the
    contact it was chosen on, the solved level against the leader's (the
    seat row's own two sides, in metres of surface), and the faces §28
    makes follow it or holds as a terrace (``pad_frontage_gs``)."""
    seats = landside_seats(planar, law, airport)
    if not seats:
        return []
    from .pad_frontage_gs import groundside_frontage, held_terrace_pairs
    rel = groundside_frontage(planar, law, airport)
    held = held_terrace_pairs(planar, law, airport)

    def name(fid: int) -> str:
        f = planar.faces[fid]
        return f"{f.role}:{f.ref}"
    out: list[dict[str, _t.Any]] = []
    for gid, seat in sorted(seats.items()):
        mine = set(seat.faces)
        rim = sorted({v for q in mine for v in planar.ring_vertices(planar.faces[q].ring)})
        level = sum(float(z[v]) for v in rim) / len(rim) if rim else None
        lead = (sum(w * float(z[v]) for _c, lw in seat.pairs for v, w in lw)
                / len(seat.pairs)) if seat.pairs else None
        rec: dict[str, _t.Any] = {
            "ref": str(planar.faces[gid].ref), "seat": "landside",
            "leader": name(seat.leader),
            "leader_contact_m": round(seat.contact_m, 2),
            "followers": sorted({name(g) for g, fronted in rel.items()
                                 if any(t[0] in mine for t in fronted)}),
            "held_pairs": sorted({name(g) for g, pid in held if pid in mine}),
        }
        if level is not None and lead is not None:
            rec["seat_level"] = round(level, 3)
            rec["leader_level"] = round(lead, 3)
        out.append(rec)
    return out
