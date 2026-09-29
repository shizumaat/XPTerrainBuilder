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
* A TOUCHING FRONTAGE STAYS SENIOR.  Where the pad also shares a weld
  with (or stands within 3 m of) another pavement face, §20's touching
  row keeps the pad's plate weight and the facing row is JUNIOR (the law's
  weight; its miss is the ``pad_level`` family's reported residual).
  27a (9) asks "the higher/nearer apron wins where two front"; the HIGHER
  facing frontage overriding a touching weld was built and MEASURED at
  HECA and REFUTED twice (attempt cap, owner 2026-08-02 guard (b)) — see
  issue #11: releasing the junior apron weld from the pad's plate let
  ``building52`` fall through the pad it touches (``building135``) to the
  low apron (93.5 -> 92.2 m); releasing the touching lower pads too left
  a four-vertex face with no plate at all (118.6 m).  A pad whose facing
  apron must outrank a weld needs a TERRACE at the weld (split identity),
  which is a planar-map change, not a row: owner RULINGS 2026-09-28b made
  it (``planar/pad_terrace``) — a touching apron at ANOTHER level than
  the apron the pad fronts is split off there, so the weld this rule
  would have had to outrank no longer exists, and the pad never faces
  the split apron back (``PlanarMap.pad_terraces``).

ONE-WAY, like every §20 row: the pad follows, the apron never moves for
it (airside is king, 14ai).  The rows carry §20's own ruling heads
(``pads.LEVEL_RULING`` / ``LEVEL_JUNIOR_RULING``), so the one-way,
pad-weight and datum-withdrawal registers (``[design] one_way_rulings`` /
``pad_flat_rulings`` / ``pad_level_rulings``) read them with no new
register entry.

THE CONSUMER CENSUS (owner 2026-08-30l).  The facing relation is kept OUT
of ``pads._fronting``: that relation's contacts are read as WELDS by
``no_step.pad_contacts`` and as §28's airside test, and a contact 40 m
from its apron is neither.  Its one reader is this module's level rows
(:func:`pad_fronting_level`); ``pads`` is not edited.
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

__all__ = ["reach_m", "facing", "analysis", "pad_fronting_level",
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
    terr = getattr(planar, "pad_terraces", None) or {}
    ref_of = {f.id: str(f.ref) for f in planar.faces.values()}
    for fid, _ref, group, poly in _pad_polys(planar, law):
        pad_vs = set(group)
        cand = [aprons[int(i)] for i in
                a_tree.query(poly, predicate="dwithin", distance=r)]
        # a TERRACED apron (``planar/pad_terrace``, 28b) was split off this
        # pad at another level: the pad never faces it back
        split = terr.get(str(_ref), ())
        cand = [a for a in cand if ref_of.get(a[0]) not in split]
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
                       _LEADER_NEAR_M)
    fac = facing(planar, law)
    polys = {fid: poly for fid, _r, _g, poly in _pad_polys(planar, law)}
    vw = view(planar, law)
    face_vs = {fid: {v for r in [vw.rings[fid], *vw.holes[fid]] for v in r}
               for fid in {a for d in fac.values() for a in d}}
    touch = pad_frontage_leaders(planar, law) if fac else {}
    # SPEC-AUTHOR RULINGS 2026-09-29s (C) (#96): A JUNIOR FACING ROW NEVER
    # CROSSES A DECLARED PAD TERRACE.  A pad split off an upper pad by a
    # 28b terrace (``planar/pad_terrace``, kind ``pad``) sits at the LOWER
    # level, on the apron it touches (its senior); a junior facing row
    # toward an apron standing at the UPPER level — nearer the terrace's
    # front level than its other level — reaches across that terrace and
    # is report-only noise (#96: HECA ``building131`` -5.8 m against
    # ``pav37`` while ``building52|building131`` is declared at 97.7 vs
    # 92.6).  No surface change beyond the junior row itself (the law's
    # weight); a senior row is never dropped.  MEASURED before this form:
    # "the upper pad's front / faced aprons" matched nothing at HECA
    # (``building52`` faces ``dsf:objpav68#0``, ``building131`` faces
    # ``pav37`` — the same east apron under two refs).
    from ..planar.pad_terrace import TERRACES
    ref_of = {f.id: str(f.ref) for f in planar.faces.values()}
    lower: dict[str, list[tuple[float, float]]] = {}
    for t in TERRACES:
        if t.kind == "pad":
            lower.setdefault(t.other_ref, []).append((t.front_level, t.other_level))
    n_across = 0
    groups: dict[int, dict] = {}
    for gid, ref, group, fids in plane_groups(planar, law, airport):
        per: list[tuple[int, list[tuple[int, float]]]] = []
        junior = any(touch.get(q) for q in fids)
        levels = ([lv for q in fids for lv in lower.get(ref_of.get(q, ""), ())]
                  if junior else [])
        for q in fids:
            for afid, contacts in (fac.get(q) or {}).items():
                own = face_vs[afid]
                poly = polys.get(q)
                near = None
                if poly is not None and own:
                    dist = {v: poly.distance(Point(*planar.vertices[v].xy)) for v in own}
                    cut = min(dist.values()) + _LEADER_NEAR_M
                    near = {v for v, dd in dist.items() if dd <= cut}
                lead = frontage_leaders(planar, contacts, own, near=near)
                if levels:
                    la = _level(planar, lead)
                    if la is not None and any(abs(la - hi) < abs(la - lo)
                                              for hi, lo in levels):
                        n_across += 1          # across the terrace: upper side
                        continue
                per.extend(lead)
        if not per:
            continue
        t_per = [pr for q in fids for prs in (touch.get(q) or {}).values() for pr in prs]
        lf, lt = _level(planar, per), _level(planar, t_per)
        # a touching frontage stays senior (module docstring)
        senior = not t_per
        groups[gid] = {"ref": ref, "group": group, "fids": fids, "per": per,
                       "facing_level": lf, "touching_level": lt,
                       "senior": senior}
    STATS["pad_fronting_across_terrace"] = {"junior_dropped": n_across}
    out = {"_pm": planar, "groups": groups}
    _CACHE.clear()
    _CACHE[key] = out
    return out


def pad_fronting_level(planar: PlanarMap, law: Law, airport: Airport
                       ) -> list[Row]:
    """ONE row per fronting PLANE GROUP: the pad's own mean (every rim
    vertex at ``1/n``) against the faced apron's own edge level at its
    facing contacts — exactly §20's :func:`pads.pad_frontage_level` row,
    with the facing contacts in place of the touching ones, ONE-WAY with
    the pad's own (non-shared) vertices as the followers.  Senior (the
    pad's plate weight) where facing is the pad's only frontage; junior
    (the law's weight) where §20's touching frontage stands."""
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
                                   "contacts": n_contacts}
    return rows
