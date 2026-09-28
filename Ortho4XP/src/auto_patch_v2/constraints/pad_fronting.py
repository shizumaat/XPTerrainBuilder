"""§20 FRONTING ACROSS BARE GROUND (owner RULINGS 2026-09-27a (9), Q-11
option A as the spec author's decision; issue #11).

Owner (HECA-6): the cargo complex (``building52``, shapeID 201) "should
weld to the apron (30.1172704, 31.4094737) along its whole east edge".
The pads and the east apron (``pav37`` / ``dsf:objpav68#0``) never touch:
20–40 m of bare ground lies between them, so §20's frontage (a shared
vertex, or an edge within ``[design] pad_frontage_m`` 3 m) never saw the
east apron, and the whole 330 m plane followed the ONE apron it touches —
``dsf:objpav399`` at its north corner, 93.3 m — while the apron it faces
stands at 96.9–99.7 m (lane ``hecabodies``' Q-11 attribution).

THE RULE.  A pad FRONTS every apron (``[design] pad_fronting_roles``)
whose edge stands within ``[design] pad_fronting_reach_m`` (50 m) of the
pad's edge ACROSS BARE GROUND — the facing segment from a pad rim vertex
to its nearest point on the apron crosses no pavement face and no
building pad (``law.tables.pavement_roles``, the rigid roles included) —
and takes that apron edge's level.  The ground between is ordinary
ground: it grades between the two edges as a terrace (§31 (3)).

* NEAREST WINS per pad vertex: a vertex facing two aprons fronts the
  nearer one.
* HIGHER WINS between a TOUCHING frontage and a FACING one: where the pad
  also shares a weld with (or stands within 3 m of) another apron, the
  one whose edge stands HIGHER is the senior.  "Higher" is read on the
  only level a generator can see before the solve — the leaders' own
  fit target (``PlanarMap.preferred_z``, else ``Vertex.dem_z``), the §28
  (6) precedent for a DEM-frame seniority test.  When the FACING frontage
  is senior, the pad's plate and its 1 % ceiling release the vertices it
  SHARES with the junior touching apron (:func:`released`): those are the
  apron's own vertices (09-01g) and the pad no longer carries their level
  across its whole plane; the step at that weld is the ``pad_level``
  junior residual, reported, never hidden.

ONE-WAY, like every §20 row: the pad follows, the apron never moves for
it (airside is king, 14ai).  The rows carry §20's own ruling heads
(``pads.LEVEL_RULING`` / ``LEVEL_JUNIOR_RULING``), so the one-way,
pad-weight and datum-withdrawal registers (``[design] one_way_rulings`` /
``pad_flat_rulings`` / ``pad_level_rulings``) read them with no new
register entry.

THE CONSUMER CENSUS (owner 2026-08-30l).  The facing relation is kept OUT
of ``pads._fronting``: that relation's contacts are read as WELDS by
``no_step.pad_contacts`` and as §28's airside test, and a contact 40 m
from its apron is neither.  Its readers are exactly two: this module's
level rows (:func:`pad_fronting_level`) and the release set
(:func:`released`) that ``pads._pad_rows`` and ``pads.pad_frontage_level``
consult.
"""
from __future__ import annotations

import typing as _t

from shapely.geometry import LineString, Point, Polygon
from shapely.ops import nearest_points
from shapely.strtree import STRtree

from ..law import Law
from ..law.tables import design as design_law, pavement_roles
from ..model.airport import Airport
from ..model.constraints import Row, Source
from ..model.planar import PlanarMap
from .precedence import view

__all__ = ["reach_m", "facing", "analysis", "released", "pad_fronting_level",
           "FRONTING_NOTE", "STATS"]

#: The ruling note the rows carry after §20's head.
FRONTING_NOTE = "facing across bare ground; owner 2026-09-27a (9) Q-11 A"
#: The generator's statistics (published beside its row count).
STATS: dict[str, dict[str, int]] = {}
#: A facing segment may graze a blocker by this much plan length and still
#: be clear (the arrangement's 0.5 m identity lattice: a segment ending ON
#: the apron's ring shares a lattice cell with the ring's own edges).  A
#: geometric epsilon, not a law value.
_GRAZE_M = 0.5

_CACHE: dict[tuple[int, int, int], dict] = {}


def reach_m(law: Law) -> float:
    """``[design] pad_fronting_reach_m`` — the one derivation site."""
    return float(design_law(law).pad_fronting_reach_m)


def _polys(planar: PlanarMap, law: Law, roles: _t.Collection[str]
           ) -> list[tuple[int, str, set[int], Polygon]]:
    vw = view(planar, law)
    out: list[tuple[int, str, set[int], Polygon]] = []
    for f in vw.faces_of_role(tuple(sorted(roles))):
        ring = vw.rings[f.id]
        if len(ring) < 3:
            continue
        poly = Polygon([vw.xy[v] for v in ring],
                       [[vw.xy[v] for v in h] for h in vw.holes[f.id] if len(h) >= 3])
        if not poly.is_valid:
            poly = poly.buffer(0.0)
        if poly.is_empty or not isinstance(poly, Polygon):
            continue
        vs = {v for r in [ring, *vw.holes[f.id]] for v in r}
        out.append((f.id, f.role, vs, poly))
    return out


def facing(planar: PlanarMap, law: Law) -> dict[int, dict[int, list[int]]]:
    """THE RELATION AS DATA: pad face id -> ``{apron face id: the pad's
    own rim vertices FACING it}``.  A vertex faces an apron when the
    apron's edge is farther than ``[design] pad_frontage_m`` (nearer is
    §20's own frontage) and within :func:`reach_m`, the segment to its
    nearest point on the apron crosses no other pavement or pad face and
    does not run back through the pad itself, and no nearer apron is
    faced from that vertex (nearest wins)."""
    from .pads import _pad_polys, frontage_radius_m, rigid_roles
    r = reach_m(law)
    roles = tuple(design_law(law).pad_fronting_roles)
    if r <= 0.0 or not roles:
        return {}
    near = frontage_radius_m(law)
    aprons = _polys(planar, law, roles)
    if not aprons:
        return {}
    rigid = set(rigid_roles(law))
    blockers = _polys(planar, law, tuple(pavement_roles(law)))
    a_tree = STRtree([a[3] for a in aprons])
    b_tree = STRtree([b[3] for b in blockers])
    xy = {v: vx.xy for v, vx in planar.vertices.items()}
    out: dict[int, dict[int, list[int]]] = {}
    for fid, _ref, group, poly in _pad_polys(planar, law):
        pad_vs = set(group)
        cand = [aprons[int(i)] for i in
                a_tree.query(poly, predicate="dwithin", distance=r)]
        # an apron the pad already fronts (weld or 3 m) is §20's own
        cand = [a for a in cand if not (a[2] & pad_vs)
                and a[3].distance(poly) > near]
        if not cand:
            continue
        got: dict[int, list[int]] = {}
        for v in group:
            p = Point(*xy[v])
            best = None
            for afid, _role, _avs, apoly in cand:
                d = apoly.distance(p)
                if d <= near or d > r:
                    continue
                if best is None or d < best[0]:
                    best = (d, afid, apoly)
            if best is None:
                continue
            d, afid, apoly = best
            q = nearest_points(apoly, p)[0]
            seg = LineString([xy[v], (q.x, q.y)])
            if seg.intersection(poly).length > _GRAZE_M:
                continue            # the segment runs back through the pad
            clear = True
            for bi in b_tree.query(seg, predicate="intersects"):
                bfid, brole, _bvs, bpoly = blockers[int(bi)]
                if bfid in (fid, afid):
                    continue
                if seg.intersection(bpoly).length > _GRAZE_M:
                    clear = False
                    break
            if clear:
                got.setdefault(afid, []).append(v)
        if got:
            out[fid] = got
    return out


def _proxy(planar: PlanarMap, v: int) -> float | None:
    """The level a generator can see before the solve: the vertex's own
    fit target (``preferred_z``, else ``dem_z``)."""
    z = planar.preferred_z.get(v)
    return planar.vertices[v].dem_z if z is None else z


def _level(planar: PlanarMap,
           per: list[tuple[int, list[tuple[int, float]]]]) -> float | None:
    vals = []
    for _c, lw in per:
        zs = [(w, _proxy(planar, j)) for j, w in lw]
        zs = [(w, z) for w, z in zs if z is not None]
        tw = sum(w for w, _z in zs)
        if tw > 0:
            vals.append(sum(w * z for w, z in zs) / tw)
    return sum(vals) / len(vals) if vals else None


def _edge_len(vw, fids: _t.Iterable[int], contacts: set[int]) -> float:
    """Plan length of the pads' own ring edges whose two ends are both
    ``contacts`` — the LENGTH of a frontage, never its vertex count (a
    straight 250 m pad edge carries two vertices, a curved 27 m weld 20)."""
    import math
    tot = 0.0
    for q in fids:
        for ring in [vw.rings[q], *vw.holes[q]]:
            n = len(ring)
            for i in range(n):
                a, b = ring[i], ring[(i + 1) % n]
                if a in contacts and b in contacts and a != b:
                    tot += math.dist(vw.xy[a], vw.xy[b])
    return tot


def analysis(planar: PlanarMap, law: Law, airport: Airport | None) -> dict:
    """Per PLANE GROUP (§30 (4)): the facing contacts with their leaders,
    the facing and touching proxy levels, whether FACING is senior, and
    the RELEASED weld vertices.  Cached per (map, law, airport): three
    generators read it."""
    key = (id(planar), id(law), id(airport))
    hit = _CACHE.get(key)
    if hit is not None and hit["_pm"] is planar:
        return hit
    from .cluster_pad import plane_groups
    from .pads import (_pad_polys, frontage_leaders, pad_frontage_leaders,
                       pad_shared, rigid_roles, _LEADER_NEAR_M)
    fac = facing(planar, law)
    polys = {fid: poly for fid, _r, _g, poly in _pad_polys(planar, law)}
    vw = view(planar, law)
    face_vs = {fid: {v for r in [vw.rings[fid], *vw.holes[fid]] for v in r}
               for fid in {a for d in fac.values() for a in d}}
    touch = pad_frontage_leaders(planar, law) if fac else {}
    shared = pad_shared(planar, law) if fac else {}
    groups: dict[int, dict] = {}
    for gid, ref, group, fids in plane_groups(planar, law, airport):
        per: list[tuple[int, list[tuple[int, float]]]] = []
        for q in fids:
            for afid, contacts in (fac.get(q) or {}).items():
                own = face_vs[afid]
                poly = polys.get(q)
                near = None
                if poly is not None and own:
                    dist = {v: poly.distance(Point(*planar.vertices[v].xy)) for v in own}
                    cut = min(dist.values()) + _LEADER_NEAR_M
                    near = {v for v, dd in dist.items() if dd <= cut}
                per.extend(frontage_leaders(planar, contacts, own, near=near))
        if not per:
            continue
        t_roles = {role for q in fids for role in (touch.get(q) or {})}
        t_per = [pr for q in fids for prs in (touch.get(q) or {}).values() for pr in prs]
        lf, lt = _level(planar, per), _level(planar, t_per)
        # a touching RUNWAY/TAXI frontage outranks any faced apron (the
        # seniority of ``precedence.toml``); "higher wins" is between
        # aprons, and only where the faced edge is also the pad's LONGER
        # frontage — a terminal welded along 486 vertices never gives its
        # weld up to a 26-vertex glimpse of a higher apron (measured, HECA
        # T3; DEVIATION reported for the spec author: 27a (9) says
        # "higher/nearer wins", the length test is this lane's guard)
        t_c = {c for c, _lw in t_per}
        f_c = {c for c, _lw in per}
        lf_m, lt_m = (_edge_len(vw, fids, f_c), _edge_len(vw, fids, t_c))
        senior = lt is None or (lf is not None and lf > lt and lf_m > lt_m
                                and t_roles <= set(design_law(law).pad_fronting_roles))
        rel: set[int] = set()
        if senior and t_per:
            for q in fids:
                rel |= shared.get(q, set())
        groups[gid] = {"ref": ref, "group": group, "fids": fids, "per": per,
                       "facing_level": lf, "touching_level": lt,
                       "facing_m": lf_m, "touching_m": lt_m,
                       "senior": senior, "released": rel}
    # A SENIOR-FACING pad also lets go of the pads it merely TOUCHES and
    # that do not face up with it: a vertex shared with such a pad is that
    # pad's plate, and MEASURED at HECA it chained ``building52`` (201)
    # through ``building135`` down to the low apron it had just released
    # (arm 1: the cargo pads fell 93.5 -> 92.2).  Per group: the other
    # pad keeps the vertex in its own plate.
    rigid = set(rigid_roles(law))
    up = {q for g in groups.values() if g["senior"] for q in g["fids"]}
    for g in groups.values():
        if not g["senior"]:
            continue
        for v in g["group"]:
            if any(f not in up and planar.faces[f].role in rigid
                   for f in planar.vertices[v].incident_faces):
                g["released"].add(v)
    out = {"_pm": planar, "groups": groups,
           "released": {v for g in groups.values() for v in g["released"]},
           "released_by_group": {gid: g["released"] for gid, g in groups.items()
                                 if g["released"]},
           "senior_groups": {gid for gid, g in groups.items()
                             if g["senior"] and g["touching_level"] is not None}}
    _CACHE.clear()
    _CACHE[key] = out
    return out


def released(planar: PlanarMap, law: Law, airport: Airport | None
             ) -> dict[int, set[int]]:
    """Plane-group id -> the vertices THAT group's plate and ceiling no
    longer price: those it shares with a JUNIOR touching apron where a
    higher FACING apron is its senior, and those it shares with a touching
    pad that does not face up with it (module docstring)."""
    return analysis(planar, law, airport)["released_by_group"]


def pad_fronting_level(planar: PlanarMap, law: Law, airport: Airport
                       ) -> list[Row]:
    """ONE row per fronting PLANE GROUP: the pad's own mean (every rim
    vertex at ``1/n``) against the faced apron's own edge level at its
    facing contacts — exactly §20's :func:`pads.pad_frontage_level` row,
    with the facing contacts in place of the touching ones, ONE-WAY with
    the pad's own (non-shared) vertices as the followers.  Senior (the
    pad's plate weight) where the facing edge is the higher frontage or
    the only one; junior (the law's weight) otherwise."""
    from .pads import (GEN_LEVEL, LEVEL_JUNIOR_RULING, LEVEL_RULING,
                       _two_sided, pad_shared)
    an = analysis(planar, law, airport)
    shared = pad_shared(planar, law)
    rows: list[Row] = []
    n_sen = n_jun = n_contacts = 0
    for gid, g in an["groups"].items():
        group, per = g["group"], g["per"]
        sh: set[int] = set()
        for q in g["fids"]:
            sh |= shared.get(q, set())
        own = tuple(sorted(set(group) - sh))
        if not own:
            continue
        terms: dict[int, float] = {v: 1.0 / len(group) for v in group}
        for _c, lw in per:
            for j, wj in lw:
                terms[j] = terms.get(j, 0.0) - wj / len(per)
        head = LEVEL_RULING if g["senior"] else LEVEL_JUNIOR_RULING
        src = Source(GEN_LEVEL, head + f" (apron; {FRONTING_NOTE})",
                     (f"face:{gid}", g["ref"], "pavement:apron:facing"))
        rows.extend(_two_sided(tuple(terms.items()), src, own))
        n_sen += int(g["senior"])
        n_jun += int(not g["senior"])
        n_contacts += len(per)
    STATS["pad_fronting_level"] = {"senior": n_sen, "junior": n_jun,
                                   "contacts": n_contacts,
                                   "released": len(an["released"])}
    return rows
