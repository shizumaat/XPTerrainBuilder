"""§28 THE GROUNDSIDE FRONTAGE TAKES THE PAD'S EDGE LEVEL (owner RULINGS
2026-09-11ai-1 -> 2026-09-12r, verbatim: "Grade frontages only" — keep the
one plateau; extend the frontage law so parking and service-road faces
meet the pad at its level; spec ``auto-patch-v2/design-surface-spec.md``
§28).

The reading (11ah/11ai): LEMD ``building4`` is ONE flat plateau (132,884 m²
after §25) and its car-park and service-road neighbours TERRACE against it —
measured again on the shipped 1.0.321 patch, ``pav124`` stands 0.71-1.50 m
away and 1.14-3.03 m ABOVE the pad over 20 vertices, ``route6`` +0.38.  The
apron joints have been 0.00 since 11af and §27 made ``pav137`` / ``pav146``
apron, so what is left is exactly the groundside frontage.  The owner chose
"grade frontages only": the plateau stays and the neighbours meet it.

THIS IS §20's FRONTAGE RULE, READ THE OTHER WAY.  A pad fronts a pavement
face by IDENTITY (a shared rim vertex, 09-01g) or by PROXIMITY (edges within
``[design] pad_frontage_m``, owner RULINGS 2026-09-10ax (1)) — the relation
is ``constraints.pads._pad_polys`` + ``frontage_radius_m``, and §28 asks the
REVERSE question of that SAME relation, so the two directions can never
disagree about what fronts what.  Only the FOLLOWER changes sides: under §20
the pad follows its apron; here the groundside face follows the pad, and the
PAD'S LEVEL IS UNCHANGED (§28 (2) — airside is king, and a groundside
neighbour never pulls a pad).

It lives apart from ``constraints/pads.py`` only because that file stands at
764 lines against the 1,000-line ceiling ``tests/auto_patch_v2/test_model.py``
enforces (the §27 precedent, ``classify/airside_edge.py``).  Every geometric
predicate it uses is imported from there: there is ONE derivation of a pad's
polygon, ONE of the frontage radius, and ONE of the groundside pavement roles
(``constraints/groundside.groundside_face_roles``).
"""
from __future__ import annotations

import math
import statistics
import typing as _t

from shapely.geometry import Point, Polygon
from shapely.strtree import STRtree

from ..law import Law
from ..law.tables import pavement_roles, role_side
from ..model.airport import Airport
from ..model.constraints import Row, Source
from ..model.planar import PlanarMap
from .groundside import groundside_face_roles
from .pads import (_pad_polys, _two_sided, design_law, frontage_radius_m,
                   pad_fronts_airside, rigid_roles)
from .precedence import view

__all__ = ["GEN_GS", "GS_LEVEL_RULING", "GS_LEVEL_JUNIOR_RULING",
           "STATS", "frontage_step_max_m", "pair_dem_step_m",
           "groundside_frontage", "groundside_frontage_level"]

#: THE GENERATOR'S OWN STATISTICS, published beside its row count by
#: ``constraints.build`` as ``groundside_frontage_level.<key>`` — the
#: design report's "frontage pairs held as terraces" line (§28 (6)).
STATS: dict[str, dict[str, int]] = {}

#: THE §28 FAMILY.  Its own generator name, so ``DesignReport.families`` and
#: ``solve/why`` name the PAD holding a lot's edge rather than the pad
#: generator at large, and a JUNIOR frontage's miss is a REPORTED residual
#: (§28 (1): "the step is reported at the junior edge").
GEN_GS = "groundside_frontage"
#: THE SENIOR PAD's head — the pad with the LARGEST contact (§28 (1)).
#: Named by ``[design] pad_flat_rulings`` (the pad's own plane weight, an
#: order above the law's, so the frontage is MET and the face grades away
#: from it at its own cap) and by ``one_way_rulings`` (the face follows the
#: pad and never pulls it).
GS_LEVEL_RULING = "structures.building_pad groundside_frontage"
#: THE SAME ROW against a JUNIOR pad, at the LAW's own weight: where the
#: face cannot grade between two pads under its own cap the senior sets the
#: level and THIS row's residual is the reported junior-edge step.  Named by
#: ``one_way_rulings``, NOT by ``pad_flat_rulings``.
GS_LEVEL_JUNIOR_RULING = "structures.building_pad groundside_frontage junior"

#: THE LEADER IS THE PAD'S NEAREST RIM, WITH NO MIN BAND — and the reason is
#: the one that made the band necessary for §20.  10y arm B rejected the
#: pavement's NEAREST own vertex as a PAD's leader because it stood a metre
#: from the pad and ALREADY CARRIED THE PAD'S OWN PULL, so the row read the
#: pad's value back.  Here the leader is a PAD vertex and the follower a
#: groundside one: the pad is a near-rigid plate (``pads.pad_flats``) under a
#: hard 1 % tilt ceiling whose own level comes from its APRON frontage (§20),
#: and this row is ONE-WAY, so ``solve/design`` strips the pad's columns out
#: of the matrix entirely — there is no pull to read back.  A band would only
#: trade the pad's EDGE level, which is what the ruling names, for its level
#: ten metres inboard.
_GS_LEADER_K = 8


def frontage_step_max_m(law: Law) -> float:
    """``[design] frontage_step_max_m`` — §28 (6)'s PER-PAIR DEM-step
    bound (owner RULINGS 2026-09-13o/13p).  ONE derivation site; a law
    value, never a literal here — the sibling of ``pad_frontage_m``, the
    radius of the same relation, and read the same way.

    IT IS A LAW KEY AND NOT A ``classify/rules.toml [lot]`` ONE (the
    brief's placement), because ``constraints`` MAY NOT IMPORT
    ``classify``: the layering is law <- model <- solve <- emit with
    ``constraints`` reading ``geom`` / ``law`` / ``model`` alone, and
    ``tests/auto_patch_v2/test_model.py::test_dependency_direction``
    enforces it by name.  §27's ``[lot] airside_edge_min_m`` is a
    classify key because CLASSIFY reads it; this one is read by a
    generator."""
    return float(design_law(law).frontage_step_max_m)


def pair_dem_step_m(planar: PlanarMap, front: _t.Iterable[int],
                    pad_rim: _t.Iterable[int]) -> float | None:
    """§28 (6)'s QUANTITY for one pad-face pair: the median over the
    face's frontage vertices of ``dem_z(vertex)`` minus the PAD
    FOOTPRINT's own median ``dem_z``.  ``None`` where either side has no
    DEM sample (planar invariant I7 says it always does; a missing one
    NEVER disarms — a pair is graded unless it is MEASURED to be a
    hillside).

    THE DEM IS THE PLANAR MAP'S OWN SAMPLE (``Vertex.dem_z``, the
    production DEM + insets taken once at map build), never a second
    reader: ``airport.dem.z`` would resample the same raster at the same
    points and a lane-private path is the census-wrapper defect.

    THE PAD'S SIDE IS ITS GROUND, NOT ITS LEVEL, and this is a DEVIATION
    from 13o's text, reported not decided here.  13o's medians (CYXY
    +4.08 / +3.02, LEMD ``building4`` +2.66) are against the pad's SOLVED
    level, which no generator can read — the level is what §20's rows
    produce, three lag rounds later.  The pad's own ground is the nearest
    thing the derivation has; measured in the engine's own frame, the
    same pairs read +3.76 / +3.43 (CYXY) against +3.00 (LEMD
    ``building4``) where 13o's solved-level frame reads +4.08 / +3.02
    against +2.66 — which is why the bound is 3.2 here and not 2.8 (see
    the law comment for the whole measured population)."""
    fd = [planar.vertices[v].dem_z for v in front]
    pd = [planar.vertices[v].dem_z for v in pad_rim]
    fd = [float(z) for z in fd if z is not None]
    pd = [float(z) for z in pd if z is not None]
    if not fd or not pd:
        return None
    return statistics.median(fd) - statistics.median(pd)


def _groundside_geoms(planar: PlanarMap, law: Law
                      ) -> list[tuple[int, str, str, set[int], Polygon]]:
    """``(face id, role, ref, ring vertices, plan polygon)`` per GROUNDSIDE
    PAVEMENT face — the §28 (1) candidate class read from its ONE derivation
    site ``constraints.groundside.groundside_face_roles`` (``parking_lot`` /
    ``groundside_pavement`` / ``service_road`` / ``service_junction``, as
    DATA rather than a literal list here).  Mirrors ``pads._pavement_geoms``
    for the reverse relation."""
    vw = view(planar, law)
    rigid = set(rigid_roles(law))
    out: list[tuple[int, str, str, set[int], Polygon]] = []
    for f in vw.faces_of_role(tuple(r for r in groundside_face_roles(law)
                                    if r not in rigid)):
        ring = vw.rings[f.id]
        vs = {v for cyc in [ring, *vw.holes[f.id]] for v in cyc}
        if not vs or len(ring) < 3:
            continue
        poly = Polygon([vw.xy[v] for v in ring],
                       [[vw.xy[v] for v in h] for h in vw.holes[f.id] if len(h) >= 3])
        if poly.is_empty:
            continue
        if not poly.is_valid:
            poly = poly.buffer(0.0)
            if poly.is_empty or not isinstance(poly, Polygon):
                continue
        out.append((f.id, f.role, f.ref, vs, poly))
    return out


def _airside_pavement_vertices(planar: PlanarMap, law: Law) -> set[int]:
    """Every vertex of an AIRSIDE pavement face — the vertices §28 may never
    make follow a pad.  One vertex has one value (09-01g): a groundside
    face's vertex that is ALSO an apron vertex is the APRON's, and the
    apron's own laws — plus §20, by which the pad already took that apron's
    edge level — are what put it where it is."""
    vw = view(planar, law)
    rigid = set(rigid_roles(law))
    roles = tuple(r for r in pavement_roles(law)
                  if r not in rigid and role_side(law, r) == "airside")
    return {v for f in vw.faces_of_role(roles)
            for cyc in [vw.rings[f.id], *vw.holes[f.id]] for v in cyc}


def groundside_frontage(planar: PlanarMap, law: Law
                        ) -> dict[int, list[tuple[int, str, float, list[int], list[int]]]]:
    """THE §28 RELATION AS DATA — groundside face id -> ``[(pad face id, pad
    ref, contact length in metres, the face's OWN frontage vertices, the
    pad's rim)]``, SENIOR (longest contact) FIRST.

    THE FRONTAGE VERTICES are the face's own ring vertices within
    ``[design] pad_frontage_m`` of the pad's polygon, MINUS the vertices it
    SHARES with the pad (one vertex, one value: a shared vertex already
    stands at the pad's level, joint 0.00 by construction) and MINUS every
    AIRSIDE pavement vertex (:func:`_airside_pavement_vertices`).

    THE CONTACT LENGTH is the length of the face's own ring edges with BOTH
    endpoints on the frontage — §28 (1)'s "largest shared edge", which is
    what decides SENIORITY where a face fronts two pads.

    A PAD THAT FRONTS NOTHING AIRSIDE IS NOT A LEADER HERE (§28 (2)).
    Its own level comes from the groundside face under 10l — that pad
    FOLLOWS the face — so a row the other way would state the same pair
    twice, in opposite directions, and the one-way lag would chase itself.
    ``pads.pad_fronts_airside`` is the single test, read from §20's own
    output so the two directions cannot disagree.

    A groundside face fronting no such pad is absent here and keeps every
    level it has today.

    A HILLSIDE TERRACE IS NOT A FRONTAGE (§28 (6), owner RULINGS
    2026-09-13o/13p).  A pair whose :func:`pair_dem_step_m` exceeds
    ``[lot] frontage_step_max_m`` is DROPPED here — the face keeps its own
    ground and the step is a lawful terrace.  The owner's reading (13l
    item 1): CYXY's ``building10`` / ``building9`` are cut into a hill
    with the lots arriving at the second storey, and grading those lots to
    the pads made ``dsf:pol129`` a 3.4 m excavation it can never climb out
    of at its 8 % cap.  The count of pairs held is published as
    ``groundside_frontage_level.pairs_held_as_terrace``."""
    pads = [p for p in _pad_polys(planar, law)
            if p[0] in pad_fronts_airside(planar, law)]
    if not pads:
        STATS["groundside_frontage_level"] = {"pairs_held_as_terrace": 0}
        return {}
    vw = view(planar, law)
    r = frontage_radius_m(law)
    tree = STRtree([p[3] for p in pads])
    xy = {v: vx.xy for v, vx in planar.vertices.items()}
    airside = _airside_pavement_vertices(planar, law)
    bound = frontage_step_max_m(law)
    held = 0
    out: dict[int, list[tuple[int, str, float, list[int], list[int]]]] = {}
    for gid, _role, _ref, gvs, gpoly in _groundside_geoms(planar, law):
        cand = (tree.query(gpoly, predicate="dwithin", distance=r) if r > 0.0
                else tree.query(gpoly, predicate="intersects"))
        got: list[tuple[int, str, float, list[int], list[int]]] = []
        for pi in cand:
            pid, pref, pgroup, ppoly = pads[int(pi)]
            front = {v for v in gvs - set(pgroup) - airside
                     if ppoly.distance(Point(*xy[v])) <= r}
            if not front:
                continue
            # §28 (6) A HILLSIDE TERRACE IS NOT A FRONTAGE (owner RULINGS
            # 2026-09-13o, refined 13p).  The bound is PER PAIR and it is
            # read HERE, in the ONE derivation of the relation, so every
            # consumer of `groundside_frontage` (the generator, and any
            # reader of the relation as data) sees the same population —
            # a per-consumer veto is the defect 08-30l names.
            step = pair_dem_step_m(planar, front, pgroup)
            if step is not None and abs(step) > bound:
                held += 1
                continue
            length = 0.0
            for cyc in [vw.rings[gid], *vw.holes[gid]]:
                for a, b in zip(cyc, cyc[1:] + cyc[:1]):
                    if a in front and b in front:
                        length += math.hypot(xy[a][0] - xy[b][0],
                                             xy[a][1] - xy[b][1])
            got.append((pid, pref, length, sorted(front), list(pgroup)))
        if got:
            got.sort(key=lambda t: (-t[2], t[0]))
            out[gid] = got
    STATS["groundside_frontage_level"] = {"pairs_held_as_terrace": held}
    return out


def groundside_frontage_level(planar: PlanarMap, law: Law, airport: Airport
                              ) -> list[Row]:
    """THE GROUNDSIDE FRONTAGE TAKES THE PAD'S EDGE LEVEL (owner RULINGS
    2026-09-11ai-1 -> 2026-09-12r; spec §28 (1)-(2)).  A generator
    (``constraints.GENERATORS``).

    ONE one-way row per FRONTAGE VERTEX of a ``parking_lot`` /
    ``groundside_pavement`` / ``service_road`` / ``service_junction`` face
    that fronts a building pad: that vertex against THE PAD'S OWN VALUE
    THERE — its nearest ``_GS_LEADER_K`` rim vertices, inverse-distance
    weighted, the weights summing to 1 so the row reads in METRES OF
    SURFACE.  The joint is 0.00.

    THE FACE BLENDS INTO ITS OWN BODY and NO BLEND ROW IS MINTED: the
    groundside terrace law is already the face's own within-shape cap
    (``rulesets.<role>.longitudinal`` — 8 % for a service road or an open
    page, 5 % for a lot, ``constraints/roads.road_within_shape``), and a
    second statement of it here would be the census-wrapper defect in
    miniature.  The bank is what that cap leaves once the frontage is held.

    ONE-WAY, THE FACE FOLLOWING (§28 (2), airside is king): ``follows`` is
    the groundside vertex ALONE, so ``solve/design`` strips the pad's
    columns out of the matrix that is factorised and no pad level can move
    at any lag round.

    TWO PADS (§28 (1)): each frontage vertex follows the pad it fronts —
    the NEAREST where it fronts more than one — so a face between two pads
    at different levels grades between them under its own cap; the SENIOR
    pad (the largest contact) carries ``[design] pad_flat`` and a junior one
    the law's own weight, so where the face cannot hold both it holds the
    SENIOR and the junior row's residual IS the reported junior-edge step
    (the ``groundside_frontage`` family's line in ``DesignReport``)."""
    rel = groundside_frontage(planar, law)
    if not rel:
        return []
    xy = {v: vx.xy for v, vx in planar.vertices.items()}
    rows: list[Row] = []
    for gid, fronted in sorted(rel.items()):
        gface = planar.faces[gid]
        senior = fronted[0][0]
        rim = {pid: pgroup for pid, _pr, _L, _fr, pgroup in fronted}
        ref_of = {pid: pref for pid, pref, _L, _fr, _g in fronted}
        # each frontage vertex follows the pad it fronts; where it fronts
        # more than one, the NEAREST — that is "its own pad's level" (§28 (1))
        claim: dict[int, tuple[float, int]] = {}
        for pid, _pref, _L, front, pgroup in fronted:
            for v in front:
                d = min(math.hypot(xy[v][0] - xy[u][0], xy[v][1] - xy[u][1])
                        for u in pgroup)
                if v not in claim or d < claim[v][0]:
                    claim[v] = (d, pid)
        by_pad: dict[int, list[int]] = {}
        for v, (_d, pid) in claim.items():
            by_pad.setdefault(pid, []).append(v)
        for pid, vs in sorted(by_pad.items()):
            src = Source(GEN_GS,
                         (GS_LEVEL_RULING if pid == senior
                          else GS_LEVEL_JUNIOR_RULING)
                         + f" ({gface.role}; owner 2026-09-12r 'grade "
                         "frontages only': the face takes the pad's edge "
                         "level along that edge)",
                         (f"face:{gid}", gface.ref, f"pad:{pid}", ref_of[pid]))
            pgroup = rim[pid]
            for v in sorted(vs):
                near = sorted((math.hypot(xy[v][0] - xy[u][0],
                                          xy[v][1] - xy[u][1]), u)
                              for u in pgroup)[:_GS_LEADER_K]
                inv = [1.0 / max(1e-3, dd) for dd, _u in near]
                tot = sum(inv)
                terms: dict[int, float] = {v: 1.0}
                for (_dd, u), w in zip(near, inv):
                    terms[u] = terms.get(u, 0.0) - w / tot
                rows.extend(_two_sided(tuple(terms.items()), src, (v,)))
    return rows
