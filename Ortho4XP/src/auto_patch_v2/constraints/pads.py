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
"""
from __future__ import annotations

import math

from shapely.geometry import LineString, Point, Polygon
from shapely.strtree import STRtree

from ..law import Law
from ..law.tables import is_rigid_role, role_cap
from ..model.airport import Airport
from ..model.constraints import Diff, Row, Source
from ..model.planar import PlanarMap
from .precedence import view

__all__ = ["pad_flats", "pad_slope_ceiling", "rigid_roles",
           "frontage_near_miss", "frontage_contacts",
           "FLAT_RULING", "CEILING_RULING"]

GEN = "pads"

#: The ruling HEAD ``[design] pad_flat_rulings`` names (everything before
#: the first parenthesis, ``solve.design.ruling_head``).
FLAT_RULING = "structures.building_pad flat"
#: The ruling HEAD ``[design] hard_rulings`` names for the 1 % tilt ceiling.
CEILING_RULING = "structures.building_pad pad_slope_max ceiling"

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


def _pad_rows(planar: PlanarMap, law: Law, cap: float, ruling: str) -> list[Row]:
    """One ``Diff`` at ``cap`` over every priced pair of every pad."""
    xy = {v: vx.xy for v, vx in planar.vertices.items()}
    rows: list[Row] = []
    for fid, ref, group in _pad_groups(planar, law):
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
    pad's rim at cap 0, priced at ``[design] pad_flat``."""
    return _pad_rows(planar, law, 0.0, FLAT_RULING + " (2026-09-09c; "
                     "09-01g weld = value; 03h pads yield)")


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
