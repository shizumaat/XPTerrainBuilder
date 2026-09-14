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

THE PAD IS ONE PLANE FITTED TO ITS FRONTAGE (owner RULINGS
2026-09-10l "Pad takes the apron edge level", refined by 2026-09-10y).
Until 10l a pad had NO level of its own beyond flatness: its plane found
whatever level minimised bending against everything it touched, and at
LEMD's T4S pit corner that dragged apron ``pav16``'s own hole ring 1.1 m
below the apron it belongs to — the apron tiered DOWN into the terminal
(10k: the rim "held by bending alone").  Round 1 answered it by letting
each pad vertex follow the frontage NEAREST IT; that made the pad stop
being one plane (``pad_flat`` rows 5 -> 38) and was REFUTED and deleted
(10y).  Under 10y:

* :func:`pad_flats` — THE PAD IS ONE PLANE, TARGETING FLAT (09c): every
  pair of its rim at cap 0, priced at ``[design] pad_flat``, the vertices
  it SHARES with its frontage included.  That near-rigid plate is what
  makes the rows below a PLANE FIT instead of a per-vertex pull.  Two
  round-2 alternatives were measured and REFUTED: dropping the pairs
  footed on a contact (round 1 — the pad stopped being one plane,
  ``pad_flat`` rows 5 -> 38, 10y), and stating the plane as HARD
  coplanarity identities against three basis vertices — at
  ``hard_weight`` those transmit whatever ELSE a pad's rim touches (LEMD
  T4S: 49 rim vertices on a basin's retaining wall against 11 on the
  apron it fronts) a hundred times harder than a level row can answer,
  and the pad came out 0.34 m BELOW the round-0 surface.
* :func:`pad_frontage_level` — THE FIT (10y): one ONE-WAY row per
  frontage CONTACT, the contact against THE PAVEMENT'S OWN VALUE THERE
  (:func:`pad_frontage_leaders`, read in a band so the pad cannot read a
  level it has itself pulled).  A contact is welded into the plate, so
  many such rows over one pad are the least-squares fit of its plane —
  level, and tilt inside the hard 1 % ceiling — to its frontage.  The
  SENIOR frontage's rows carry ``pad_flat`` and a junior's the law's own
  weight, so where one plane cannot meet both the pad follows the senior
  and the miss is the ``pad_level`` family's reported residual.
* the pad's own DEM DATUM (09p (3)) applies ONLY to a pad that fronts no
  pavement — ``solve/design`` §9b drops the vertices of a FRONTING pad
  (:func:`pad_datum_withdrawn`) from every per-body mean.
"""
from __future__ import annotations

import math
import typing as _t

from shapely.geometry import LineString, Point, Polygon
from shapely.strtree import STRtree

from ..law import Law
from ..law.tables import (design as design_law, is_rigid_role, pavement_roles,
                          role_cap, rolled_on_roles, senior_role)
from ..model.airport import Airport
from ..model.constraints import Diff, Linear, Row, Source
from ..model.planar import PlanarMap
from .pad_relief import pad_relief_offsets
from .precedence import view

__all__ = ["pad_flats", "pad_slope_ceiling", "rigid_roles",
           "frontage_near_miss", "frontage_contacts", "pad_frontage_level",
           "pad_shared", "pad_datum_withdrawn", "pad_frontage", "FLAT_RULING",
           "CEILING_RULING", "pad_frontage_leaders", "LEVEL_MIN_BAND_M",
           "LEVEL_RULING", "LEVEL_JUNIOR_RULING", "GEN_LEVEL",
           "frontage_leaders", "_two_sided", "frontage_radius_m",
           "pad_fronts_airside",
           "pad_relief_offsets"]

GEN = "pads"
#: The generator's own statistics (``constraints.generate`` publishes them
#: beside its row count as ``pad_flats.<key>``).
STATS: dict[str, dict[str, int]] = {}
#: The LEVEL rows carry their own generator so ``DesignReport.families``
#: reports their residual as its own line (owner 2026-09-10l: "reports
#: the residual"), never lumped with the flatness target.
GEN_LEVEL = "pad_level"

#: The ruling HEAD ``[design] pad_flat_rulings`` names (everything before
#: the first parenthesis, ``solve.design.ruling_head``).
FLAT_RULING = "structures.building_pad flat"
#: §16g (10) (8) THE PAD IS DROPPED AT THE RIM (owner RULINGS
#: 2026-09-14aj): the head a pad row carries when ONE of its two vertices
#: belongs to an AIRSIDE face.  It is in ``[design] one_way_rulings`` —
#: the airside vertex is the LEADER and never moves for a pad — and in
#: ``hard_rulings``, because what the row states is the pad's own SLOPE
#: CEILING (``pad_slope_max``, 1 %) reaching down to a pinned edge: a
#: BENT SKIRT, not a step and not a free edge.
AIRSIDE_RULING = "structures.building_pad airside skirt"
#: The ruling HEAD ``[design] hard_rulings`` names for the 1 % tilt ceiling.
CEILING_RULING = "structures.building_pad pad_slope_max ceiling"
#: THE SENIOR CLAUSE (owner 2026-09-10y): the ONE one-way row per fronting
#: pad that puts the plane's level at its SENIOR frontage's edge mean
#: where the plane cannot meet every frontage.  Named by ``[design]
#: pad_flat_rulings`` (the pad's own plane weight), ``one_way_rulings``
#: (the pad follows, never pulls) and ``pad_level_rulings`` (the per-body
#: datum withdrawal, §9b).
LEVEL_RULING = "structures.building_pad frontage_level"
#: THE SAME ROW against a JUNIOR fronting pavement, at the LAW's own
#: weight: where one plane cannot meet both frontages it follows the
#: SENIOR one and the miss here is the reported residual.  Named by
#: ``one_way_rulings`` and ``pad_level_rulings``, NOT by
#: ``pad_flat_rulings``.
LEVEL_JUNIOR_RULING = "structures.building_pad frontage_level junior"

#: The basis triangle must be at least this wide and this tall (metres)
#: for its barycentric coordinates to carry a plane.  A SOLVER
#: CONDITIONING guard, not a law value: a pad whose rim is a collinear
#: sliver has no plane to fit and keeps the pairwise FLAT target instead.
_PLANE_MIN_SPAN_M = 1.0

#: A pad with more rim vertices than this is priced over a DECIMATED
#: representative set (every k-th vertex) PLUS every consecutive pair,
#: so the pair count stays O(n): the plane's tilt is already witnessed
#: by a well-spread subset, and a solver constant is not a law value.
_MAX_PAIRWISE = 40


def rigid_roles(law: Law) -> tuple[str, ...]:
    """Every role the register marks rigid (data, never a list here)."""
    return tuple(sorted(r for r in law.tables.precedence.roles
                        if is_rigid_role(law, r)))


#: §16g (10) (8): how many SKIRT rows the pass minted (one-way, at the
#: pad's slope ceiling, against an airside leader) and how many pairs it
#: dropped for having both ends on the airside.  The generator publishes
#: them as ``pads.pad_flats.*``.
AIRSIDE_LED: dict[str, int] = {}


def airside_vertices(planar: PlanarMap, law: Law) -> frozenset[int]:
    """§16g (10) (8): every vertex an AIRSIDE face carries —
    ``law.tables.rolled_on_roles`` (the runway family, the taxi family and
    the apron), so a new pavement role joins with no code change.  ONE
    derivation, read by :func:`_pad_rows`."""
    vw = view(planar, law)
    out: set[int] = set()
    for f in vw.faces_of_role(tuple(sorted(rolled_on_roles(law)))):
        for ring in [vw.rings[f.id], *vw.holes[f.id]]:
            out.update(ring)
    return frozenset(out)


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


def frontage_radius_m(law: Law) -> float:
    """THE PROXIMITY HORIZON (owner RULINGS 2026-09-10ax (1)): ``[design]
    pad_frontage_m``.  A pad EDGE within this of a pavement EDGE fronts
    it, shared vertex or not.  ONE derivation site; a law value, never a
    literal here."""
    return float(design_law(law).pad_frontage_m)


def _pad_polys(planar: PlanarMap, law: Law) -> list[tuple[int, str, list[int], Polygon]]:
    """``(face id, ref, rim vertices, plan polygon)`` per pad — the pad's
    own outline, for the PROXIMITY read.  A pad whose outer ring is a
    sliver (< 3 vertices) has no polygon and is skipped: it can still
    front by a shared vertex."""
    vw = view(planar, law)
    out: list[tuple[int, str, list[int], Polygon]] = []
    for fid, ref, group in _pad_groups(planar, law):
        ring = vw.rings[fid]
        if len(ring) < 3:
            continue
        poly = Polygon([vw.xy[v] for v in ring],
                       [[vw.xy[v] for v in h] for h in vw.holes[fid] if len(h) >= 3])
        if poly.is_empty:
            continue
        if not poly.is_valid:
            poly = poly.buffer(0.0)
            if poly.is_empty or not isinstance(poly, Polygon):
                continue
        out.append((fid, ref, group, poly))
    return out


def _pavement_geoms(planar: PlanarMap, law: Law
                    ) -> list[tuple[str, set[int], Polygon]]:
    """``(role, vertices, plan polygon)`` per PAVEMENT face — the same
    face set as :func:`_pavement_faces`, carrying the outline the
    PROXIMITY read measures against (owner RULINGS 2026-09-10ax (1))."""
    vw = view(planar, law)
    rigid = set(rigid_roles(law))
    out: list[tuple[str, set[int], Polygon]] = []
    for f in vw.faces_of_role(tuple(r for r in pavement_roles(law) if r not in rigid)):
        vs = {v for ring in [vw.rings[f.id], *vw.holes[f.id]] for v in ring}
        ring = vw.rings[f.id]
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
        out.append((f.role, vs, poly))
    return out


def _fronting(planar: PlanarMap, law: Law
              ) -> dict[int, dict[str, tuple[set[int], set[int]]]]:
    """THE ONE DERIVATION OF "WHAT DOES THIS PAD FRONT" (owner RULINGS
    2026-09-10ax (1)): pad face id -> ``{pavement role: (CONTACTS, the
    pavement's OWN vertices along that frontage)}``.

    A pad fronts a pavement face two ways, and the ruling makes them one
    law:

    * BY IDENTITY — it SHARES a rim vertex with it (09-01g, the pre-10ax
      reading).  The contacts are those shared vertices; the pavement's
      own vertices are the face's rest.
    * BY PROXIMITY — its EDGE stands within ``[design] pad_frontage_m``
      of the pavement's edge (:func:`frontage_radius_m`).  LEMD
      ``building4`` (way −10936, 66,257 m², 40.4603701 −3.5756711) stands
      1.60 m from ``pav124`` and shared NOTHING, so before 10ax it had no
      frontage row at all and kept its DEM datum while the apron trend
      lifted the pavement — the pad ended 1.58 m BELOW the apron it faces
      and the building floated over the drop (owner's 1.0.310 read,
      RULINGS 2026-09-10aw).  16 of LEMD's 43 pads are in that class.
      The contacts are then the pad's OWN rim vertices within the radius
      of that pavement face, and every one of the face's vertices is its
      own.

    A pad fronting neither way is absent here and keeps its DEM datum
    (09p (3)), exactly as ruled.

    A GROUNDSIDE FACE IS A FRONTAGE ONLY WHERE NOTHING AIRSIDE IS (owner
    RULINGS 2026-09-12r, spec §28 (2): "the apron frontage (§20's senior)
    still sets it; a groundside neighbour never pulls a pad — airside is
    king").  Until §28 a car park or a service road entered here as a
    JUNIOR frontage and PULLED the pad: measured on the twin fixture, a
    lot standing 3 m above its pad moved the pad 0.032 m through exactly
    these two rows.  §28 states the same relation the other way — the
    face follows the pad (:mod:`constraints.pad_frontage_gs`) — so where
    a pad has ANY airside frontage the groundside roles are dropped here
    and the pull is gone.  Where it has NONE they are KEPT: that pad's
    only frontage is its groundside neighbour, 10l's "the pad takes the
    pavement's edge level" is all the level it has, and §28 in turn mints
    no row back against it, so the pair is stated ONCE and in one
    direction, never as a circular lag."""
    from ..law.tables import role_side
    geoms = _pavement_geoms(planar, law)
    r = frontage_radius_m(law)
    tree = STRtree([g[2] for g in geoms]) if geoms else None
    xy = {v: vx.xy for v, vx in planar.vertices.items()}
    out: dict[int, dict[str, tuple[set[int], set[int]]]] = {}
    for fid, _ref, group, poly in _pad_polys(planar, law):
        pad_vs = set(group)
        by_role: dict[str, tuple[set[int], set[int]]] = {}
        cand = ([] if tree is None else
                (tree.query(poly, predicate="dwithin", distance=r)
                 if r > 0.0 else tree.query(poly, predicate="intersects")))
        for gi in cand:
            role, vs, gpoly = geoms[int(gi)]
            hit = vs & pad_vs
            if not hit and r > 0.0:
                # BY PROXIMITY: the pad's own edge vertices facing it
                hit = {v for v in pad_vs - vs
                       if gpoly.distance(Point(*xy[v])) <= r}
            if not hit:
                continue
            c, own = by_role.setdefault(role, (set(), set()))
            c.update(hit)
            own.update(vs - pad_vs)
        by_role = _airside_only(by_role, law)
        if by_role:
            out[fid] = by_role
    # A pad with no polygon of its own (a sliver rim) still fronts by
    # identity — the pre-10ax read, unchanged.
    have = set(out)
    faces = _pavement_faces(planar, law)
    for fid, _ref, group in _pad_groups(planar, law):
        if fid in have:
            continue
        pad_vs = set(group)
        by_role: dict[str, tuple[set[int], set[int]]] = {}
        for role, vs in faces:
            hit = vs & pad_vs
            if hit:
                c, own = by_role.setdefault(role, (set(), set()))
                c.update(hit)
                own.update(vs - pad_vs)
        by_role = _airside_only(by_role, law)
        if by_role:
            out[fid] = by_role
    return out


def pad_fronts_airside(planar: PlanarMap, law: Law) -> set[int]:
    """The pad face ids whose frontage is AIRSIDE pavement — §28 (2)'s
    test, read from :func:`_fronting`'s own output so the two directions
    of the relation cannot disagree.  A pad NOT here either fronts nothing
    (its DEM datum, 09p (3)) or fronts only a groundside face, in which
    case IT follows the face under 10l and ``constraints.pad_frontage_gs``
    mints nothing back against it."""
    from ..law.tables import role_side
    return {fid for fid, by_role in _fronting(planar, law).items()
            if any(role_side(law, r) == "airside" for r in by_role)}


def _airside_only(by_role: dict[str, tuple[set[int], set[int]]], law: Law
                  ) -> dict[str, tuple[set[int], set[int]]]:
    """§28 (2): drop the GROUNDSIDE roles from a pad's frontage wherever
    something AIRSIDE fronts it too (see :func:`_fronting`).  Where
    nothing airside does, the groundside frontage is all the pad has and
    is kept unchanged."""
    from ..law.tables import role_side
    if any(role_side(law, r) == "airside" for r in by_role):
        return {r: v for r, v in by_role.items()
                if role_side(law, r) == "airside"}
    return by_role


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
    """THE PAVEMENT EACH PAD FRONTS (owner RULINGS 2026-09-10l/10y), as
    data: pad face id -> ``{pavement role: the CONTACT vertices it shares
    with that role}``.

    A pad FRONTS a pavement face when it SHARES a rim (or hole-rim) vertex
    with it — identity is the weld (09-01g) — and the face's role is a
    PAVEMENT role: ``law.tables.pavement_roles`` (every value role that is
    not a structure) minus the rigid roles, so a pad touching only another
    pad fronts nothing.  The near-miss case, where a sub-metre source
    offset leaves a sliver instead of a shared vertex, is
    :func:`frontage_near_miss`'s and is unchanged.

    THE VERTICES RETURNED ARE THE CONTACTS THEMSELVES — one vertex with
    one value, a pad vertex AND a pavement vertex.  They are what the
    pad's plane is fitted to (10y), and what the pavement's own laws put
    where they are.  Round 1's leaders — the pavement's own vertices one
    ring in — were REFUTED and deleted: they carry the pavement's local
    slope inward, and following them per pad vertex overshot the frontage
    by 0.4 m at LEMD T4S and stopped the pad being one plane.

    A pad that fronts no pavement never appears here and keeps its own DEM
    datum (09p (3))."""
    return {fid: {role: sorted(c) for role, (c, _own) in by_role.items()}
            for fid, by_role in _fronting(planar, law).items()}


def pad_datum_withdrawn(planar: PlanarMap, law: Law) -> set[int]:
    """THE VERTICES OF EVERY FRONTING PAD (owner RULINGS 2026-09-10l):
    ``solve/design`` §9b drops them from every per-body DEM datum mean —
    a fronting pad's level is its frontage's, not the building's terrain.
    The SHARED vertices are NOT withdrawn: they are the pavement's own
    edge (09-01g) and belong in the pavement body's mean.  A PROXIMITY
    contact (owner RULINGS 2026-09-10ax (1)) is a pad vertex and nothing
    else, so it IS withdrawn — the pad's whole plane follows.  A pad that
    fronts nothing is not here and keeps its datum, exactly as ruled."""
    front = pad_frontage(planar, law)
    shared = pad_shared(planar, law)
    out: set[int] = set()
    for fid, _ref, group in _pad_groups(planar, law):
        if not front.get(fid):
            continue
        sh = shared.get(fid, set())
        out.update(v for v in group if v not in sh)
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
              airport: Airport | None = None, relief: bool = True) -> list[Row]:
    """One ``Diff`` at ``cap`` over every priced pair of every pad — the
    hard 1 % tilt ceiling's row set (09c).  Over EVERY pair, the contacts
    included: "the plane's tilt" is exactly "no two points of the pad
    differ by more than 1 % of their separation", and a contact is a point
    of the pad.

    THE RELIEF TARGET (owner RULINGS 2026-09-11j; spec §11a (2)): where a
    pad stands under a BODY whose ground-contact feet are authored at
    different ``y``, each vertex carries an OFFSET above the pad's level
    (``pad_relief.pad_relief_offsets``, the one derivation) and the row is
    priced on the LEVEL plane — ``rel = offset[a] - offset[b]``.  A
    flat-footed body has every offset 0 and the rows are exactly today's.

    ONLY THE TARGET CARRIES THE RELIEF (owner RULINGS 2026-09-12u, spec
    §30 (1); ``relief=False``).  Until 12u the hard 1 % CEILING read the
    offsets too, and that made the authored relief a DEMAND on the
    surface: at LEMD T4S an apron rim vertex inheriting a foot's −2.20 m
    put a 2.20 m step over 3.0 m of apron into the active set against the
    5 % pavement ceiling's 0.15 m — a mutually infeasible pair no surface
    satisfies, which shipped as 725 violated hard rows (365 pad ceiling /
    357 pavement ceiling) and a worst residual of 1.3037 m.  The ceiling
    says exactly what its own docstring says — "no two points of the pad
    differ by more than 1 % of their separation" — and the relief stays
    expressed by the ``pad_flat`` TARGET (weight 3,000, ten times
    ``law``), which is where a target belongs."""
    xy = {v: vx.xy for v, vx in planar.vertices.items()}
    off = (pad_relief_offsets(planar, law, airport)
           if (relief and airport is not None) else {})
    rows: list[Row] = []
    # §30 (4): a TERMINAL CLUSTER's faces are ONE plane — one plate, one
    # ceiling.  Every other pad is its own entry, exactly as before.
    from .cluster_pad import cluster_pairs, plane_groups
    # §16g (8) AS NARROWED BY (10) (owner RULINGS 2026-09-14x): 14u's
    # derived pads WITHIN a cluster are withdrawn and mint no row here.
    # A touching body at a different authored floor is now a different
    # CLUSTER with its own pad at its own level (``plan_clusters``'s
    # floor split), so there is no cluster spanning pads to derive
    # across; the step between two touching clusters' pads is the ground
    # law's declared terrace joint (§23) and is PUBLISHED, not priced
    # (``cluster_pad.cluster_offsets`` / ``TOUCHING_STEPS``, read by
    # ``pipeline/publication``).  ``off`` therefore carries §30 (6)'s
    # per-vertex relief alone, as it did before 14u.
    # §30 (4) (RULINGS 2026-09-13cc/13ce): a CLUSTER's plane is priced
    # per-face-complete PLUS cross-links, never over the concatenated rim
    # — the merged reading was measured inert (see ``cluster_pairs``).
    # §16g (10) (8) THE PLATE IS DROPPED AT AN AIRSIDE RIM (owner RULINGS
    # 2026-09-14aj, resolving the trilemma this lane measured in round 3:
    # a derived pad cannot be one hard plane AND welded to the apron AND
    # forbidden to move it).  A vertex the pad SHARES with an airside face
    # is ONE unknown (09-01g, contact = value), so a TWO-SIDED pad row
    # touching it moves the airside: MEASURED, 345,016 m2 of new pad
    # beside the apron moved 17,482 of 29,465 airside vertices, worst
    # 12.15 m, with the pads already clipped out of airside ground.
    #
    # So along an airside-sharing edge the pad's rim vertices are ONE-WAY
    # FOLLOWERS of the airside — the airside leads and never moves — and
    # what binds them to the plate is the pad's own SLOPE CEILING
    # (``pad_slope_max``), not the cap-0 flat target.  The pad is FLAT
    # across its interior and its non-airside rim and BENDS to meet the
    # pavement it touches: a skirt.  ``pad_airside_weld`` (14ai) then
    # fires only where even the ceiling cannot reach.
    air = airside_vertices(planar, law)
    ceiling = float(law.tables.emit.within_shape.pad_slope_max)
    AIRSIDE_LED.clear()
    _led = _dropped = _whole = 0
    per_face = {q: g for q, _r, g in _pad_groups(planar, law)}
    n_cross = 0
    for fid, ref, group, fids in plane_groups(planar, law, airport):
        src = Source(GEN, ruling, (f"face:{fid}", ref))
        # §16g (10) (8): the SKIRT row carries the SAME face inputs as the
        # plate it belongs to — every reader that asks "which rows are
        # this pad's" (the twins, the report, ``pad_flat``) must find them
        src_air = Source(GEN, AIRSIDE_RULING
                         + " (owner 2026-09-14aj; spec §16g (10) (8))",
                         (f"face:{fid}", ref))
        # A PAD WHOLLY INSIDE PAVEMENT HAS NO RIM OF ITS OWN and the
        # skirt would leave it with no law at all: every pair would have
        # both ends on the airside.  That is the OSM pad-in-an-apron
        # class (09-01g's own shape), not the derived pad (5) mints, so
        # it keeps the two-sided plate it has always had and is COUNTED.
        skirt = air
        if len([v for v in group if v not in air]) < 2:
            skirt = frozenset()
            _whole += 1
        if len(fids) > 1:
            prs, k = cluster_pairs(planar, [per_face[q] for q in fids
                                            if q in per_face])
            n_cross += k
        else:
            prs = _pairs(group)
        for a, b in prs:
            if a == b:
                continue
            d = math.hypot(xy[a][0] - xy[b][0], xy[a][1] - xy[b][1])
            if d <= 0.0:
                continue
            if a in skirt or b in skirt:
                # §16g (10) (8): the SKIRT row.  A pair with an end on the
                # airside is priced at the pad's own SLOPE CEILING
                # however this call was asked, never at the cap-0 flat
                # target: the pad is FLAT across its interior and its
                # non-airside rim and BENDS to meet the pavement it
                # touches.  At ``cap == ceiling`` it is the row the
                # ceiling pass would have minted anyway, so the ceiling
                # is unchanged and only the FLAT target is dropped here.
                #
                # THE ONE-WAY FORM WAS MEASURED AND REFUTED (round 4): a
                # plate whose every binding is one-way has no rigid
                # relation to anything in the first lag round and does not
                # chase back — the §30 twin's pad collapsed from 703.56 to
                # 640.89 m.  09-10l's one-way precedent is a LEVEL row (a
                # mean against a leader band), not a whole plate, and the
                # difference is that a level row leaves the plate holding
                # the pad rigid while this would leave nothing.
                _led += 1
                if cap >= ceiling:
                    rows.append(Diff(a, b, cap, d, src,
                                     rel=off.get(a, 0.0) - off.get(b, 0.0)))
                else:
                    rows.append(Diff(a, b, ceiling, d, src_air,
                                     rel=off.get(a, 0.0) - off.get(b, 0.0)))
                continue
            rows.append(Diff(a, b, cap, d, src,
                             rel=off.get(a, 0.0) - off.get(b, 0.0)))
    STATS.setdefault("pad_flats", {})["cluster_cross_links"] = n_cross
    AIRSIDE_LED.update(airside_skirt_rows=_led, both_airside_dropped=_dropped,
                       pads_wholly_on_airside=_whole)
    STATS.setdefault("pad_flats", {}).update(AIRSIDE_LED)
    return rows


def pad_flats(planar: PlanarMap, law: Law, airport: Airport) -> list[Row]:
    """THE PAD IS ONE PLANE, TARGETING FLAT (owner RULINGS 2026-09-09c;
    10y "09c stands"): every pair of the pad's rim at cap 0, priced at
    ``[design] pad_flat`` — over the WHOLE rim, the vertices it shares
    with the pavement it fronts included.

    Over every pair this is what MAKES the pad one plane: a cap-0 row per
    pair at a weight an order above the law's is a near-rigid plate, and
    the plate is what carries a per-contact level row (:func:`pad_frontage_
    level`) into a LEVEL AND A TILT for the whole pad instead of a dent at
    one vertex.  Round 1 dropped the pairs footed on a contact and the pad
    stopped being one plane (``pad_flat`` rows 5 -> 38, RULINGS 10y);
    round 2 tried the coplanarity identity as HARD rows instead and that
    was REFUTED too — at ``hard_weight`` the identity transmits whatever
    a pad's OTHER neighbour pulls with (LEMD T4S: 49 rim vertices on a
    basin's retaining wall against 11 on the apron it fronts) a hundred
    times harder than any level row can answer, and the pad came out
    0.34 m BELOW the round-0 surface.  The plate is soft on purpose."""
    return _pad_rows(planar, law, 0.0, FLAT_RULING + " (2026-09-09c; "
                     "09-01g weld = value; 03h pads yield)", airport)


#: THE FRONTAGE IS READ IN A BAND (owner RULINGS 2026-09-10y, measured by
#: this lane): the pavement's value at a contact cannot be read from the
#: pavement's nearest own vertex — that vertex is a metre from the pad and
#: the pad has already pulled it there (MEASURED: with the nearest own
#: vertex as the leader the LEMD T4S rows read a level the pad itself had
#: lowered and lifted nothing).  It is read from the pavement's own
#: vertices between these plan distances of the contact — far enough out
#: that the pavement stands at its own level, near enough to be the same
#: edge.  Solver constants, not law values; the one-way LAG is what makes
#: the read exact, since the pavement's grade INTO the pad — the whole
#: defect 10l names — falls to zero as the pad rises to meet it.
_LEADER_MIN_M = 10.0
#: The twins read the band's inner edge by name.
LEVEL_MIN_BAND_M = _LEADER_MIN_M
_LEADER_MAX_M = 50.0
#: At most this many own vertices carry one contact: an index constant.
_LEADER_K = 8
#: THE LEADER MUST STAND ON THE FRONTAGE (lane ``v2green2``, RULINGS
#: 2026-09-10bb round; the defect the ground datum of 10av exposed).  The
#: radial band above answers "how far from the contact", and says nothing
#: about WHICH WAY.  Since 10av every adjacent-ground vertex carries a
#: weak DEM datum, so a pavement face now TILTS ACROSS ITS WIDTH between
#: its two ground edges — and for an apron 40 m wide the 10..50 m band of
#: a contact at its middle contains ONLY the FAR EDGE, 40 m away and at
#: the OTHER ground's level.  MEASURED, the two-pavement twin: the apron
#: stood at 700.44 m where the pad fronts it and the band read it at
#: 699.32 m, 1.1 m below, and pulled the pad 0.16 m UNDER the lower of
#: its two frontages — under 10l/10k-1 (A) the pad takes the pavement's
#: EDGE level, which is the one level the far band cannot see.
#:
#: So a leader is first sought among the pavement's own vertices that
#: stand ON the frontage: its NEAREST RING to the pad — every own vertex
#: whose plan distance to the pad is within this of the nearest own
#: vertex's — taken nearest-first and still no nearer than
#: ``_LEADER_MIN_M`` to the contact (10y arm B's protection is the MIN,
#: and it is kept).  A ring measured from the pad's own nearest own
#: vertex SCALES: it is the hole ring for a pad cut out of an apron
#: (2 m), the facing kerb for a pad fronting by proximity (a few m), the
#: edge continuation past the pad's corners for the twin's 120 m pad
#: against a 40 m apron (11 m) — and in every case it excludes the face's
#: FAR edge, which is at least the face's own width away.  The radial
#: band is the fallback where a face has no such ring (it is all edge:
#: the 10y case, unchanged).
_LEADER_NEAR_M = _LEADER_MIN_M


def pad_frontage_leaders(planar: PlanarMap, law: Law
                         ) -> dict[int, dict[str, list[tuple[int, list[tuple[int, float]]]]]]:
    """THE FIT'S ROWS AS DATA (owner RULINGS 2026-09-10y): pad face id ->
    ``{pavement role: [(contact vertex, [(leader vertex, weight), ...])]}``
    — THE PAVEMENT'S OWN VALUE AT EACH CONTACT, read in the band
    ``_LEADER_MIN_M .. _LEADER_MAX_M`` and inverse-distance weighted (the
    weights sum to 1, so the row is stated in metres of surface).

    Never the CONTACT itself, which is a pad vertex too — the plane passes
    through it, so a row against it says only that the plane equals itself
    (MEASURED, round 2 arm A: the LEMD T4S pad sank 0.9 m with its
    frontage and its basin wall pulling it equally).  Never the nearest
    own vertex either (arm B, above).  A pavement face with no own vertex
    in the band falls back to its nearest ``_LEADER_K`` — a face smaller
    than the band is all edge, and its own level is the only one it has."""
    polys = {fid: poly for fid, _ref, _g, poly in _pad_polys(planar, law)}
    out: dict[int, dict[str, list[tuple[int, list[tuple[int, float]]]]]] = {}
    for fid, by_role in _fronting(planar, law).items():
        poly = polys.get(fid)
        got: dict[str, list[tuple[int, list[tuple[int, float]]]]] = {}
        for role, (contacts, own) in by_role.items():
            near = None
            if poly is not None and own:
                dist = {v: poly.distance(Point(*planar.vertices[v].xy))
                        for v in own}
                cut = min(dist.values()) + _LEADER_NEAR_M
                near = {v for v, dd in dist.items() if dd <= cut}
            per = frontage_leaders(planar, contacts, own, near=near)
            if per:
                got[role] = per
        if got:
            out[fid] = got
    return out


def frontage_leaders(planar: PlanarMap, contacts: _t.Iterable[int],
                     own: _t.Iterable[int],
                     near: _t.Optional[_t.Set[int]] = None
                     ) -> list[tuple[int, list[tuple[int, float]]]]:
    """THE PAVEMENT'S OWN VALUE BESIDE EACH CONTACT — ``[(contact vertex,
    [(leader vertex, weight), ...])]``, the leaders read from ``own`` in
    the band ``_LEADER_MIN_M .. _LEADER_MAX_M`` of the contact and
    inverse-distance weighted (the weights sum to 1, so a row stated over
    them reads in METRES OF SURFACE).

    ONE derivation site (owner ruling 7e90032, extend a near-fit): the pad
    frontage level (10l/10y) and the STRUCTURE RIM's flush contact
    (2026-09-10an, ``constraints.structures.rim_level``) ask the same
    question — where does the pavement stand beside this vertex — and a
    second implementation of the band would be the census-wrapper defect
    in miniature.  ``own`` with no member in the band falls back to its
    nearest ``_LEADER_K``: a face smaller than the band is all edge, and
    its own level is the only one it has.

    ``near`` — the subset of ``own`` that STANDS ON THE FRONTAGE (see
    ``_LEADER_NEAR_M``) — is preferred wherever the caller can name it:
    its members ≥ ``_LEADER_MIN_M`` from the contact, NEAREST FIRST and
    with no outer bound, because along a frontage the pavement holds one
    level for a long way while ACROSS it 40 m already reaches the other
    ground.  The radial band is what remains where ``near`` is unknown or
    empty."""
    own_l = sorted(own)
    if not own_l:
        return []
    near_l = sorted(near) if near else []
    xy = {v: planar.vertices[v].xy for v in {*own_l, *contacts}}
    per: list[tuple[int, list[tuple[int, float]]]] = []
    for c in sorted(contacts):
        qx, qy = xy[c]
        band: list[tuple[float, int]] = []
        if near_l:
            dn = sorted(((math.hypot(xy[v][0] - qx, xy[v][1] - qy), v)
                         for v in near_l))
            band = [(dd, v) for dd, v in dn if dd >= _LEADER_MIN_M][:_LEADER_K]
        d = sorted(((math.hypot(xy[v][0] - qx, xy[v][1] - qy), v) for v in own_l))
        if not band:
            band = [(dd, v) for dd, v in d
                    if _LEADER_MIN_M <= dd <= _LEADER_MAX_M][:_LEADER_K]
        if not band:
            band = d[:_LEADER_K]
        inv = [1.0 / max(1e-3, dd) for dd, _v in band]
        tot = sum(inv)
        per.append((c, [(v, w / tot) for (_dd, v), w in zip(band, inv)]))
    return per


def pad_frontage_level(planar: PlanarMap, law: Law, airport: Airport
                       ) -> list[Row]:
    """THE PLANE IS FITTED TO ITS FRONTAGE (owner RULINGS 2026-09-10l,
    10k-1 = (A) "Pad takes the apron edge level"; the fit is 10y's).

    ONE row per fronting pad and role: the pad's OWN MEAN — every rim
    vertex at weight ``1/n``, so the row moves the pad's LEVEL and warps
    nothing — against THE PAVEMENT'S OWN VALUE AT ITS CONTACTS
    (:func:`pad_frontage_leaders`, the mean over the contacts of the
    pavement's own level in a band beside each).  ONE-WAY with the pad as
    the follower: the pad follows the pavement and never pulls it.

    A LEVEL ROW, NOT A PER-VERTEX PULL.  Round 1 minted one row per pad
    VERTEX and the pad stopped being one plane (10y).  Round 2 tried one
    per CONTACT — welded into the plate (:func:`pad_flats`) they are the
    least-squares fit of the plane in principle, but the plate is finite
    and they warp it: MEASURED at LEMD, the worst pad's residual from its
    own least-squares plane went 0.077 -> 0.569 m and the ``pad_flat``
    verify rows 6 -> 11.  A row on the pad's own mean cannot warp it at
    all, and the pad's LEVEL is what 10l is about.

    SENIORITY (10y): the SENIOR frontage's row (``precedence.toml``:
    runway family > taxi > apron > road) is priced at ``[design]
    pad_flat`` and a junior frontage's at the law's own weight, so a pad
    between two frontages follows the senior and the miss against the
    junior is the reported residual of the ``pad_level`` family.

    A pad that fronts no pavement mints nothing here and keeps its own DEM
    datum (09p (3))."""
    lead = pad_frontage_leaders(planar, law)
    shared = pad_shared(planar, law)
    rows: list[Row] = []
    # §30 (4): a CLUSTER is ONE plane, so it takes ONE level fit — its
    # whole rim against the leaders of EVERY face's frontage, seniority
    # read over the union.  The frontage relation itself is per face and
    # untouched (the consumer census): a cluster fronts what its faces
    # front.
    from .cluster_pad import plane_groups
    for fid, ref, group, fids in plane_groups(planar, law, airport):
        by_role: dict[str, list[tuple[int, list[tuple[int, float]]]]] = {}
        for q in fids:
            for role, pairs in (lead.get(q) or {}).items():
                by_role.setdefault(role, []).extend(pairs)
        if not by_role:
            continue                       # fronts nothing: its DEM datum
        sh: set[int] = set()
        for q in fids:
            sh |= shared.get(q, set())
        top = senior_role(law, sorted(by_role))
        # §9b reads the FOLLOWERS: a fronting pad's own vertices carry no
        # DEM datum (10l).  Its CONTACTS are the pavement's edge and stay
        # in the pavement body's mean.
        own = tuple(sorted(set(group) - sh))
        if not own:
            continue        # every rim vertex IS the pavement's: nothing follows
        for role, pairs in by_role.items():
            terms: dict[int, float] = {v: 1.0 / len(group) for v in group}
            for _c, lw in pairs:
                for j, wj in lw:
                    terms[j] = terms.get(j, 0.0) - wj / len(pairs)
            src = Source(GEN_LEVEL,
                         (LEVEL_RULING if role == top else LEVEL_JUNIOR_RULING)
                         + f" ({role}; owner 2026-09-10l 10k-1 = A; "
                         "10y the plane's level from its frontage)",
                         (f"face:{fid}", ref, f"pavement:{role}"))
            # THE ROW IS ONE-WAY IN CONSTRUCTION (owner RULINGS
            # 2026-09-10ax (1), answering 10at): the followers are the
            # PAD'S OWN PLANE — its non-shared vertices.  A vertex the pad
            # SHARES with the pavement is a PAVEMENT vertex (09-01g: one
            # vertex, one value) and enters as a LEADER, on the right-hand
            # side at its previous outer-round value (§9b).  Until 10ax
            # the follower set was the whole rim, contacts included, so a
            # pad's own mean reached back into the shared vertices and
            # MOVED the pavement: `why` read `pad_frontage_level` +1.30 m
            # on LEMD's T4S apron corner (10at).  The row now moves the
            # pad up OR down to the pavement and the pavement never feels
            # it — proved against a no-pad-row arm.
            rows.extend(_two_sided(tuple(terms.items()), src, own))
    return rows


def _two_sided(terms: tuple[tuple[int, float], ...], src: Source,
               follows: tuple[int, ...]) -> list[Row]:
    """An EQUALITY as the solve's own vocabulary: two one-sided ``Linear``
    targets at 0 (``solve/rows._law_sides`` reads a ``lo == hi`` row as a
    two-sided equality priced at the LAW's weight, which is not what a pad
    row is priced at)."""
    return [Linear(terms, None, 0.0, src, follows=follows),
            Linear(tuple((v, -c) for v, c in terms), None, 0.0, src,
                   follows=follows)]


def pad_slope_ceiling(planar: PlanarMap, law: Law, airport: Airport) -> list[Row]:
    """THE HARD 1 % TILT CEILING (owner RULINGS 2026-09-09c): the same
    pairs at ``emit.within_shape.pad_slope_max``, a constraint of the
    design solve's active set (``[design] hard_rulings``).

    IT CARRIES NO AUTHORED RELIEF (owner RULINGS 2026-09-12u, spec §30
    (1)): ``rel = 0`` on every row — see :func:`_pad_rows`."""
    cap = float(law.tables.emit.within_shape.pad_slope_max)
    return _pad_rows(planar, law, cap, CEILING_RULING + " (owner 2026-09-09c; "
                     "no authored relief 2026-09-12u)", airport, relief=False)


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

