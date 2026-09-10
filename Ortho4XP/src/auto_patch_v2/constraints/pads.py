"""BUILDING-PAD generator (RULINGS 2026-09-03h "pads yield", 2026-09-03i
"seniority follows from being governed", 2026-09-01g "weld = value";
``law/structures.toml [building_pad]``, ``precedence.toml`` ``rigid``).

A rigid role's face (a pad) is ONE PLANE whose design target is FLAT
(owner RULINGS 2026-09-09c, verbatim: "building pads are targeting flat,
with up to 1 % allowance where no other solution exists").  Its LEVEL is
still set by what it touches — the shared vertices with the apron carry
the apron's own law, so the pad is levelled by its contact and never a
pin the apron must climb to (03h).  No seat pin exists in v2.

THE PAD IS NO LONGER A HARD ``Flat``.  Until 09c it was a ``Flat`` group,
which ``solve/rows._reduce`` merges into ONE COLUMN: the pad was exactly
flat and every surface welded to it was dragged to that one level, which
is strictly stronger than the owner's law and has no way to express
"where no other solution exists".  It is now:

* :func:`pad_flats` — the FLATNESS TARGET, ``|z_i - z_j| <= 0`` over
  every pair of the pad's rim (a ``Diff`` at cap 0), priced at
  ``[design] pad_flat`` (``pad_flat_rulings`` names this ruling head), a
  weight an order above the law's, so a pad comes out flat wherever the
  geometry allows one;
* :func:`pad_slope_ceiling` — the HARD CEILING, ``|z_i - z_j| <=
  pad_slope_max * d_ij`` over the same pairs, ruling head listed in
  ``[design] hard_rulings`` beside the runway rows and the 5 % pavement
  ceiling.  Over EVERY pair, because "the plane's tilt" is exactly "no
  two points of the pad differ by more than 1 % of their separation";
  over consecutive pairs alone a fan of small steps could add up.

``emit.within_shape.pad_slope_max`` is the ONE derivation site of the
1 % (``verify/pads.py`` reads the same value).

THE PAD TAKES THE PAVEMENT'S EDGE LEVEL (owner RULINGS 2026-09-10l,
answering 10k-1 = (A), verbatim: "Pad takes the apron edge level").
Until 10l a pad had NO level of its own beyond flatness: its plane found
whatever level minimised bending against everything it touched, and at
LEMD's T4S pit corner that dragged apron ``pav16``'s own hole ring 1.1 m
below the apron it belongs to — the apron tiered DOWN into the terminal
(10k: the rim "held by bending alone").  Under 10l:

* a pad that FRONTS PAVEMENT (shares a rim vertex with a face of a
  PAVEMENT role — every value role that is not a structure and not the
  pad itself, ``law.tables.pavement_roles``) takes THAT PAVEMENT'S EDGE
  LEVEL: :func:`pad_frontage_level` mints, per free pad vertex, a
  contact row (08t answer 5, flush) at cap 0 against the NEAREST contact
  vertex of each fronting role, ONE-WAY with the pad vertex as the
  FOLLOWER — so the pad follows the pavement and NEVER pulls it (the
  09b (2)/(3) idiom).  Two fronting pavements at different levels: one
  row each, so the pad TILTS within its 1 % to meet both where a plane
  can; where it cannot, the SENIOR pavement's rows are priced at
  ``[design] pad_flat`` and the junior's at the law's own weight
  (seniority from ``precedence.toml`` via ``senior_role``: runway family
  > taxi > apron > road), so the pad follows the senior and the residual
  is REPORTED — the rows carry their own generator ``pad_level``, so
  ``DesignReport.families`` counts them missed and names the worst.
* the pad's own FLATNESS rows never touch a contact vertex: a pair with
  a contact foot is DROPPED from :func:`pad_flats` (the pavement governs
  its own edge; the level rows carry the plane to it).
* the pad's own DEM DATUM (09p (3)) applies ONLY to a pad that fronts no
  pavement — enforced in ``solve/design`` §9b, which drops a FOLLOWER
  vertex of a ``[design] pad_level_rulings`` row from every body mean.
"""
from __future__ import annotations

import math

from shapely.geometry import LineString, Point, Polygon
from shapely.strtree import STRtree

from ..law import Law
from ..law.tables import is_rigid_role, pavement_roles, role_cap, senior_role
from ..model.airport import Airport
from ..model.constraints import Diff, Row, Source
from ..model.planar import PlanarMap
from .precedence import view

__all__ = ["pad_flats", "pad_slope_ceiling", "rigid_roles",
           "frontage_near_miss", "frontage_contacts", "pad_frontage_level",
           "pad_shared",
           "pad_frontage", "FLAT_RULING", "CEILING_RULING",
           "LEVEL_RULING", "LEVEL_JUNIOR_RULING", "GEN_LEVEL"]

GEN = "pads"
#: The LEVEL rows carry their own generator so ``DesignReport.families``
#: reports their residual as its own line (owner 2026-09-10l: "reports
#: the residual"), never lumped with the flatness target.
GEN_LEVEL = "pad_level"

#: The ruling HEAD ``[design] pad_flat_rulings`` names (everything before
#: the first parenthesis, ``solve.design.ruling_head``).
FLAT_RULING = "structures.building_pad flat"
#: The ruling HEAD ``[design] hard_rulings`` names for the 1 % tilt ceiling.
CEILING_RULING = "structures.building_pad pad_slope_max ceiling"
#: THE LEVEL ROW against the SENIOR fronting pavement (owner 2026-09-10l):
#: named by ``[design] pad_flat_rulings`` (the pad's own plane weight),
#: ``[design] one_way_rulings`` (the pad follows, never pulls) and
#: ``[design] pad_level_rulings`` (the datum suppression in §9b).
LEVEL_RULING = "structures.building_pad frontage_level"
#: THE LEVEL ROW against a JUNIOR fronting pavement: the same row at the
#: LAW's own weight, so a pad between two pavements a plane cannot both
#: meet follows the SENIOR one and the miss against the junior is the
#: reported residual.  Named by ``one_way_rulings`` and
#: ``pad_level_rulings`` but NOT by ``pad_flat_rulings``.
LEVEL_JUNIOR_RULING = "structures.building_pad frontage_level junior"

#: A pad with more rim vertices than this is priced over a DECIMATED
#: representative set (every k-th vertex) PLUS every consecutive pair,
#: so the pair count stays O(n): the plane's tilt is already witnessed
#: by a well-spread subset, and a solver constant is not a law value.
_MAX_PAIRWISE = 40


def rigid_roles(law: Law) -> tuple[str, ...]:
    """Every role the register marks rigid (data, never a list here)."""
    return tuple(sorted(r for r in law.tables.precedence.roles
                        if is_rigid_role(law, r)))


def _pad_groups(planar: PlanarMap, law: Law) -> list[tuple[int, str, list[int]]]:
    """``(face id, ref, rim vertices)`` per rigid face — ONE derivation of
    the pad's vertex set, read by both row generators."""
    vw = view(planar, law)
    out: list[tuple[int, str, list[int]]] = []
    for f in vw.faces_of_role(rigid_roles(law)):
        group: list[int] = []
        seen: set[int] = set()
        for ring in [vw.rings[f.id], *vw.holes[f.id]]:
            for v in ring:
                if v not in seen:
                    seen.add(v)
                    group.append(v)
        if len(group) >= 2:
            out.append((f.id, f.ref, group))
    return out


def _pavement_faces(planar: PlanarMap, law: Law) -> list[tuple[str, set[int]]]:
    """``(role, vertices)`` per PAVEMENT face — every value role that is
    not a structure (``law.tables.pavement_roles``) and not rigid, so a
    pad touching only another pad fronts nothing.  ONE derivation, read by
    :func:`pad_frontage` and :func:`pad_shared`."""
    vw = view(planar, law)
    rigid = set(rigid_roles(law))
    out: list[tuple[str, set[int]]] = []
    for f in vw.faces_of_role(tuple(r for r in pavement_roles(law) if r not in rigid)):
        vs = {v for ring in [vw.rings[f.id], *vw.holes[f.id]] for v in ring}
        if vs:
            out.append((f.role, vs))
    return out


def pad_shared(planar: PlanarMap, law: Law) -> dict[int, set[int]]:
    """Pad face id -> the vertices it SHARES with the pavement it fronts
    (identity is the weld, 09-01g).  Those vertices belong to the pavement
    too, so under owner RULINGS 2026-09-10l the pad's own flatness target
    never prices a pair footed on one."""
    faces = _pavement_faces(planar, law)
    out: dict[int, set[int]] = {}
    for fid, _ref, group in _pad_groups(planar, law):
        pad_vs = set(group)
        sh: set[int] = set()
        for _role, vs in faces:
            sh |= vs & pad_vs
        if sh:
            out[fid] = sh
    return out


def pad_frontage(planar: PlanarMap, law: Law) -> dict[int, dict[str, list[int]]]:
    """THE PAVEMENT EACH PAD FRONTS (owner RULINGS 2026-09-10l), as data:
    pad face id -> ``{pavement role: that pavement's OWN vertices}``.

    A pad FRONTS a pavement face when it SHARES a rim (or hole-rim) vertex
    with it — identity is the weld (09-01g) — and the face's role is a
    PAVEMENT role: ``law.tables.pavement_roles`` (every value role that is
    not a structure) minus the rigid roles, so a pad touching only another
    pad fronts nothing.  The near-miss case, where a sub-metre source
    offset leaves a sliver instead of a shared vertex, is
    :func:`frontage_near_miss`'s and is unchanged.

    THE VERTICES RETURNED ARE THE PAVEMENT'S OWN — the fronting faces'
    vertices that are NOT the pad's.  They are the LEVEL rows' LEADERS,
    and they have to be: a SHARED vertex is a pad vertex, welded into the
    pad's plane by the flatness target and the hard 1 % ceiling, so a row
    leading from one says only "the pad equals itself" and leaves the
    pad's level free (MEASURED, lane v2padlevel round 1: the LEMD T4S pad
    and pav16's edge fell together to 597.63, 0.86 m BELOW the round-0
    surface).

    A pad that fronts no pavement never appears here and keeps its own DEM
    datum (09p (3))."""
    faces = _pavement_faces(planar, law)
    out: dict[int, dict[str, list[int]]] = {}
    for fid, _ref, group in _pad_groups(planar, law):
        pad_vs = set(group)
        by_role: dict[str, set[int]] = {}
        for role, vs in faces:
            if vs & pad_vs:
                by_role.setdefault(role, set()).update(vs - pad_vs)
        by_role = {r: v for r, v in by_role.items() if v}
        if by_role:
            out[fid] = {r: sorted(v) for r, v in by_role.items()}
    return out


def _pairs(group: list[int]) -> list[tuple[int, int]]:
    """The pairs a pad's plane is priced over (module docstring): every
    pair while the rim is small, else every consecutive pair plus every
    pair of a decimated representative set."""
    n = len(group)
    if n <= _MAX_PAIRWISE:
        return [(group[i], group[j]) for i in range(n) for j in range(i + 1, n)]
    step = (n + _MAX_PAIRWISE - 1) // _MAX_PAIRWISE
    reps = group[::step]
    pairs = {(min(a, b), max(a, b))
             for i, a in enumerate(reps) for b in reps[i + 1:]}
    pairs.update((min(group[i], group[i + 1]), max(group[i], group[i + 1]))
                 for i in range(n - 1))
    pairs.add((min(group[-1], group[0]), max(group[-1], group[0])))
    return sorted(pairs)


def _pad_rows(planar: PlanarMap, law: Law, cap: float, ruling: str,
              skip_shared: bool = False) -> list[Row]:
    """One ``Diff`` at ``cap`` over every priced pair of every pad.  With
    ``skip_shared`` a pair with EITHER foot on a vertex the pad SHARES
    with the pavement it fronts is dropped (owner 2026-09-10l): such a row
    is two-way at ``pad_flat``, so it is the pad flattening the apron's own
    edge — the tier the ruling forbids.  MEASURED at LEMD T4S: with the
    shared feet still priced the transect kept 0.36 m of the pad's pull;
    without them it is the pad-free surface."""
    xy = {v: vx.xy for v, vx in planar.vertices.items()}
    shared = pad_shared(planar, law) if skip_shared else {}
    rows: list[Row] = []
    for fid, ref, group in _pad_groups(planar, law):
        sh = shared.get(fid)
        if sh:
            group = [v for v in group if v not in sh]
            if len(group) < 2:
                continue
        src = Source(GEN, ruling, (f"face:{fid}", ref))
        for a, b in _pairs(group):
            if a == b:
                continue
            d = math.hypot(xy[a][0] - xy[b][0], xy[a][1] - xy[b][1])
            if d <= 0.0:
                continue
            rows.append(Diff(a, b, cap, d, src))
    return rows


def pad_flats(planar: PlanarMap, law: Law, airport: Airport) -> list[Row]:
    """THE FLATNESS TARGET (owner RULINGS 2026-09-09c): every pair of a
    pad's rim at cap 0, priced at ``[design] pad_flat`` — over the pad's
    OWN vertices, never a vertex it shares with the pavement it fronts
    (owner 2026-09-10l: the pavement governs its own edge, and
    :func:`pad_frontage_level` carries the plane flush to it)."""
    return _pad_rows(planar, law, 0.0, FLAT_RULING + " (2026-09-09c; "
                     "09-01g weld = value; 03h pads yield)",
                     skip_shared=True)


def pad_frontage_level(planar: PlanarMap, law: Law, airport: Airport
                       ) -> list[Row]:
    """THE PAD TAKES THE PAVEMENT'S EDGE LEVEL (owner RULINGS 2026-09-10l,
    10k-1 = (A)): one FLUSH row (08t answer 5, cap 0) from every vertex of
    a fronting pad to the NEAREST vertex OF THAT PAVEMENT — the pavement's
    own, never a shared one (:func:`pad_frontage`) — ONE-WAY with the pad
    vertex as the FOLLOWER, so the pad follows the pavement and never
    pulls it and the apron does not tier down into the terminal it fronts.

    ONE row per pad vertex, against the frontage NEAREST IT — a pad
    vertex takes the level of the pavement it stands on, which is what
    makes a pad between two frontages TILT rather than split the
    difference everywhere (a row to EVERY frontage from EVERY vertex gives
    each vertex the same weighted target, so the plane comes out level at
    the senior's height however small the disagreement — MEASURED, lane
    v2padlevel: 0.00015 of tilt where the ruling asks for 0.5 %).  The
    plane then tilts within the hard 1 % (:func:`pad_slope_ceiling`) where
    it can meet both; where it cannot, the SENIOR frontage's rows
    (``pad_flat``, an order above the law's) win over the junior's and the
    miss is the reported residual of the ``pad_level`` family."""
    xy = {v: vx.xy for v, vx in planar.vertices.items()}
    front = pad_frontage(planar, law)
    rows: list[Row] = []
    for fid, ref, group in _pad_groups(planar, law):
        by_role = front.get(fid)
        if not by_role:
            continue                       # fronts nothing: its DEM datum
        top = senior_role(law, sorted(by_role))
        trees = {role: (vs, STRtree([Point(xy[v]) for v in vs]))
                 for role, vs in by_role.items()}
        src = {role: Source(
            GEN_LEVEL,
            (LEVEL_RULING if role == top else LEVEL_JUNIOR_RULING)
            + f" ({role}; owner 2026-09-10l 10k-1 = A; 08t flush contacts)",
            (f"face:{fid}", ref, f"pavement:{role}")) for role in by_role}
        for v in group:
            p = Point(xy[v])
            best: tuple[float, int, str] | None = None
            for role, (vs, tree) in trees.items():
                j = vs[int(tree.nearest(p))]
                d = math.hypot(xy[j][0] - xy[v][0], xy[j][1] - xy[v][1])
                if d > 0.0 and (best is None or d < best[0]):
                    best = (d, j, role)
            if best is None:
                continue
            d, j, role = best
            rows.append(Diff(v, j, 0.0, d, src[role], follows=v))
    return rows


def pad_slope_ceiling(planar: PlanarMap, law: Law, airport: Airport) -> list[Row]:
    """THE HARD 1 % TILT CEILING (owner RULINGS 2026-09-09c): the same
    pairs at ``emit.within_shape.pad_slope_max``, a constraint of the
    design solve's active set (``[design] hard_rulings``)."""
    cap = float(law.tables.emit.within_shape.pad_slope_max)
    return _pad_rows(planar, law, cap, CEILING_RULING + " (owner 2026-09-09c)")


def frontage_contacts(planar: PlanarMap, law: Law
                      ) -> list[tuple[int, int, int, float, float, int]]:
    """THE NEAR-MISS FRONTAGE PAIRS as data: ``(soft endpoint, nearest
    pad vertex, pad face, distance to the pad polygon, apron cap, soft
    face)`` per
    fired endpoint (module rule below; :func:`frontage_near_miss` mints
    the rows, ``routes`` the pad's CONTACT edge — RULINGS 2026-09-05ab:
    a pad attaches to the route graph at its contact, the frontage
    row's apron vertex).  A soft endpoint fires once per pad."""
    vw = view(planar, law)
    bp = law.tables.structures.building_pad
    near = bp.frontage_near_miss_m
    cap = role_cap(law, "apron")
    if cap is None or near <= 0.0:
        return []
    budget = cap.longitudinal
    rigid = rigid_roles(law)
    pads: list[tuple[int, Polygon, list[int]]] = []
    pad_vertices: set[int] = set()
    for f in vw.faces_of_role(rigid):
        ring = vw.rings[f.id]
        if len(ring) < 3:
            continue
        poly = Polygon([vw.xy[v] for v in ring],
                       [[vw.xy[v] for v in h] for h in vw.holes[f.id] if len(h) >= 3])
        if poly.is_empty:
            continue
        verts = list(ring)
        for h in vw.holes[f.id]:
            verts.extend(h)
        pads.append((f.id, poly, verts))
        pad_vertices.update(verts)
    if not pads:
        return []
    tree = STRtree([p[1] for p in pads])
    # A PAD NEVER FRONTS ACROSS A SHAPE JOINT (RULINGS 2026-09-06n, 08k): a
    # pad belongs to its own shape (``planar.shape_of_face``, the majority
    # label); a soft face of another shape across the joint is no frontage
    grp = planar.shape_of_face
    out: list[tuple[int, int, int, float, float, int]] = []
    for f in vw.faces_of_role(tuple(bp.frontage_soft_roles)):
        for ring in [vw.rings[f.id], *vw.holes[f.id]]:
            n = len(ring)
            if n < 3:
                continue
            spoly = Polygon([vw.xy[v] for v in ring])
            if spoly.is_empty:
                continue
            cand = tree.query(spoly, predicate="dwithin", distance=near)
            if len(cand) == 0:
                continue
            for pi in cand:
                pid, ppoly, pverts = pads[int(pi)]
                gp, gf = grp.get(pid), grp.get(f.id)
                if gp is not None and gf is not None and gp != gf:
                    continue
                pset = set(pverts)
                fired: set[int] = set()
                for i in range(n):
                    a, b = ring[i], ring[(i + 1) % n]
                    if a in pset or b in pset:
                        continue        # identity reconciles that corner
                    if LineString([vw.xy[a], vw.xy[b]]).distance(ppoly) > near:
                        continue
                    for e in (a, b):
                        if e in pad_vertices or e in fired:
                            continue
                        fired.add(e)
                        x, y = vw.xy[e]
                        d = float(ppoly.distance(Point(x, y)))
                        j = min(pverts, key=lambda v: (vw.xy[v][0] - x) ** 2
                                + (vw.xy[v][1] - y) ** 2)
                        out.append((e, j, pid, d, budget, f.id))
    return out


def frontage_near_miss(planar: PlanarMap, law: Law, airport: Airport
                       ) -> list[Row]:
    """THE NEAR-MISS FRONTAGE LAW (Appendix A §1 ``frontage_near_miss``;
    RULINGS 2026-08-08, cycle-5 instrument-fix item 6; v1
    ``near_miss_building_frontage_edges`` / ``check_grade._check_frontage_
    near_miss``, the one reader).  A pad outline and the soft pavement it
    fronts can be offset by a sub-metre SOURCE mismatch (SPJC building29
    vs its SW apron: 0.68 m — a DSF facade against an apt.dat apron),
    leaving a sliver no identity join closes.  The frontage binds ACROSS
    it: for a ``frontage_soft_roles`` ring edge within
    ``frontage_near_miss_m`` of a pad, with BOTH endpoints unshared with
    that pad, each endpoint unshared with ANY pad holds
    ``|z_endpoint − z_pad(nearest pad vertex)| ≤ apron cap · d`` with
    ``d`` its own distance to the pad polygon.  Under 03h the pad is the
    junior side: the row levels the pad by its frontage exactly as a
    shared vertex would, never the apron by the pad."""
    # THE TIERED APRON LAW (RULINGS 2026-09-06w): the budget is the HARD
    # apron cap; the 1 % preference rides beside it (``apron.tiered_rows``)
    from .apron import tiered_rows
    from ..law.tables import role_preferred_cap
    pref = role_preferred_cap(law, "apron")
    pref_l = None if pref is None else pref.longitudinal
    rows: list[Row] = []
    tiers: dict[int, object] = {}
    for e, j, pid, d, budget, fid in frontage_contacts(planar, law):
        f = planar.faces[fid]
        tier = tiers.get(fid)
        if tier is None:
            tier = tiers[fid] = tiered_rows(fid, f.ref, budget, pref_l, GEN)
        rows.extend(tier.rows(e, j, d, Source(
            GEN, "structures.building_pad frontage_near_miss "
            "(2026-08-08; 09-01g weld = value; 03h pads yield)",
            (f"face:{f.id}", f.ref, f"pad:{pid}", planar.faces[pid].ref))))
    return rows
