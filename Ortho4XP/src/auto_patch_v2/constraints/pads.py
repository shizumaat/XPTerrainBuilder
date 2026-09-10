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

from shapely.geometry import LineString, Point, Polygon
from shapely.strtree import STRtree

from ..law import Law
from ..law.tables import is_rigid_role, pavement_roles, role_cap, senior_role
from ..model.airport import Airport
from ..model.constraints import Diff, Linear, Row, Source
from ..model.planar import PlanarMap
from .precedence import view

__all__ = ["pad_flats", "pad_slope_ceiling", "rigid_roles",
           "frontage_near_miss", "frontage_contacts", "pad_frontage_level",
           "pad_shared", "pad_datum_withdrawn", "pad_frontage", "FLAT_RULING",
           "CEILING_RULING", "pad_frontage_leaders", "LEVEL_MIN_BAND_M",
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
    faces = _pavement_faces(planar, law)
    out: dict[int, dict[str, list[int]]] = {}
    for fid, _ref, group in _pad_groups(planar, law):
        pad_vs = set(group)
        by_role: dict[str, set[int]] = {}
        for role, vs in faces:
            hit = vs & pad_vs
            if hit:
                by_role.setdefault(role, set()).update(hit)
        if by_role:
            out[fid] = {r: sorted(v) for r, v in by_role.items()}
    return out


def pad_datum_withdrawn(planar: PlanarMap, law: Law) -> set[int]:
    """THE VERTICES OF EVERY FRONTING PAD (owner RULINGS 2026-09-10l):
    ``solve/design`` §9b drops them from every per-body DEM datum mean —
    a fronting pad's level is its frontage's, not the building's terrain.
    The CONTACT vertices are NOT withdrawn: they are the pavement's own
    edge and belong in the pavement body's mean.  A pad that fronts
    nothing is not here and keeps its datum, exactly as ruled."""
    front = pad_frontage(planar, law)
    out: set[int] = set()
    for fid, _ref, group in _pad_groups(planar, law):
        by_role = front.get(fid)
        if not by_role:
            continue
        contacts = {v for vs in by_role.values() for v in vs}
        out.update(v for v in group if v not in contacts)
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
    """One ``Diff`` at ``cap`` over every priced pair of every pad — the
    hard 1 % tilt ceiling's row set (09c).  Over EVERY pair, the contacts
    included: "the plane's tilt" is exactly "no two points of the pad
    differ by more than 1 % of their separation", and a contact is a point
    of the pad."""
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
                     "09-01g weld = value; 03h pads yield)")


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
    faces = _pavement_faces(planar, law)
    xy = {v: vx.xy for v, vx in planar.vertices.items()}
    out: dict[int, dict[str, list[tuple[int, list[tuple[int, float]]]]]] = {}
    for fid, _ref, group in _pad_groups(planar, law):
        pad_vs = set(group)
        by_role: dict[str, tuple[set[int], set[int]]] = {}
        for role, vs in faces:
            hit = vs & pad_vs
            if not hit:
                continue
            c, own = by_role.setdefault(role, (set(), set()))
            c.update(hit)
            own.update(vs - pad_vs)
        got: dict[str, list[tuple[int, list[tuple[int, float]]]]] = {}
        for role, (contacts, own) in by_role.items():
            own_l = sorted(own)
            if not own_l:
                continue
            per: list[tuple[int, list[tuple[int, float]]]] = []
            for c in sorted(contacts):
                qx, qy = xy[c]
                d = sorted(((math.hypot(xy[v][0] - qx, xy[v][1] - qy), v)
                            for v in own_l))
                band = [(dd, v) for dd, v in d
                        if _LEADER_MIN_M <= dd <= _LEADER_MAX_M][:_LEADER_K]
                if not band:
                    band = d[:_LEADER_K]
                inv = [1.0 / max(1e-3, dd) for dd, _v in band]
                tot = sum(inv)
                per.append((c, [(v, w / tot)
                                for (_dd, v), w in zip(band, inv)]))
            if per:
                got[role] = per
        if got:
            out[fid] = got
    return out


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
    for fid, ref, group in _pad_groups(planar, law):
        by_role = lead.get(fid)
        if not by_role:
            continue                       # fronts nothing: its DEM datum
        top = senior_role(law, sorted(by_role))
        # §9b reads the FOLLOWERS: a fronting pad's own vertices carry no
        # DEM datum (10l).  Its CONTACTS are the pavement's edge and stay
        # in the pavement body's mean.
        own = tuple(sorted(set(group) - shared.get(fid, set())))
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
            rows.extend(_two_sided(tuple(terms.items()), src,
                                   tuple(sorted({*group, *own}))))
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
