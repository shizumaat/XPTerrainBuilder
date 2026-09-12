"""§14a THE BASIN BODY FOLLOWS ITS RING (Fable, 2026-09-11; owner
RULINGS 2026-09-11ap item 6).

§24 (1) puts the apron's rim vertices ON the basin's cut ring AT THE
APRON'S LEVEL, so the ring follows the apron and is NOT level: LEMD's T4
landside pit (``basin_wall:0@851``, 59 nodes) runs 597.68 … 599.52, a
1.84 m spread.  §14 (2) wrote every basin body at ONE rim point (598.39),
so the wall base stood +0.71 m above the apron edge on one arc and
−1.13 m below it on another — the owner's "small gap between wall and
apron", read from 1.0.315 through 1.0.319 while the §14 ``spread`` bar
read 0.01 (it measures the bodies' agreement with EACH OTHER, not with
the ring).

Two rules, and they partition the pit's members:

1. :func:`arcs_of` — THE RING'S OWN STATIONS.  The ring is walked once
   and cut into contiguous ARCS over which its z agrees within
   ``split_tol_m``; each arc carries a RIM POINT (the arc's own node
   nearest its mid-level) and that point's z.  A basin body's WALL BAND
   (the triangles standing within :data:`WALL_BAND_M` of the ring in
   plan) is then cut by those arcs, one piece per arc, each anchored at
   its arc's rim point — the line-object cut of §10 read on the ring
   instead of on a fence's own axis.
2. :func:`member_kind` — A MEMBER INSIDE THE RING IS A FLOOR BODY.  A
   body of the basin resource whose vertices are mostly INTERIOR to the
   ring is not part of the pit's shell at all: it STANDS IN the pit, and
   the trench was dug out from under it.  ``Ground-FSX-LEMD13__b0``
   (5 × 18 m, its base authored 0.08 m under the rim plane) rode the rim
   at 598.31 with the floor at ~591 — the owner's loose white slab in
   the garden.  It takes no rim anchor: the generic rule of §9 anchors
   it on the ground under its own footprint, which inside the ring IS
   the floor.

WHAT IS AND IS NOT A NUMBER HERE
--------------------------------

``split_tol_m`` and the arc cap are passed in by the caller from
``[placement] split_tol_m`` / ``[rebake] line_object_stations_max``.
:data:`WALL_BAND_M`, :data:`FLOOR_MARGIN_M` and :data:`SHELL_TOL_M` are
GEOMETRIC RESOLUTIONS, each documented where it stands and each measured
insensitive at the site (see their comments): they say which triangles
read as "at the ring" and which vertices read as "inside it", never how
high anything sits.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

__all__ = ["BASIN_WALL_REF", "Arc", "is_basin_ring", "arcs_of", "arc_of_node",
           "member_kind", "ring_ref_of", "arc_index_of", "bind_key_of", "ring_bar",
           "ring_reading", "ring_arcs", "arc_anchor", "floor_bodies", "plan_counts",
           "carrier_targets",
           "wall_arc_key", "wall_arcs_of", "WALL_ARC_KEY",
           "FLOOR_MARK",
           "REASON_RIM", "REASON_ARC",
           "WALL_BAND_M", "FLOOR_MARGIN_M", "RING", "FLOOR"]

#: the ref prefix ``planar/basins`` mints for a pit's void face
#: (``planar/basins.py``: ``wall_ref = f"basin_wall:{k}"``).  The same
#: literal ``constraints.foot_rows.BASIN_WALL_REF`` carries, and a twin
#: holds the two together: §14a is the BASIN ring's law and must never
#: fire on a ``tunnel_wall`` ring, whose object anchors on its FLOOR ring
#: by §6 (11v deviation (a)).
BASIN_WALL_REF = "basin_wall:"

#: HOW FAR FROM THE RING A TRIANGLE STILL READS AS THE WALL.  §24 (1)
#: puts every rim vertex within ``emit.weld_spacing_m`` (1.0 m) of the
#: object's outer wall face, so a metre would do; 3 m is taken because
#: the cut reads triangle CENTROIDS, and a wall panel two metres tall
#: whose base stands on the ring has its centroid a metre inside it.
#: MEASURED at the site (LEMD ``basin_wall:0@851``, bands 1.0 / 1.5 /
#: 2.0 / 3.0 / 5.0 m): the bar reads 0.18 m at EVERY band — what the band
#: moves is only how many of the ring's nodes have a piece at all
#: (45 / 49 / 50 / 51 / 51 of 59) and how many pieces are written
#: (9 / 11 / 11 / 13 / 14).  A resolution, not a law.
WALL_BAND_M = 3.0

#: A VERTEX ON THE RING IS NOT INSIDE IT.  The pit's own wall stands ON
#: the ring, so plain containment reads the wall as interior (LEMD's
#: ``LEMDzaun`` 60 % "inside" by ray casting, median distance to the ring
#: 0.35 m) and (2) would send the wall to the floor.  A vertex counts as
#: INTERIOR only when it stands inside AND further than this from the
#: ring — ``emit.weld_spacing_m``'s own identity spacing, the distance
#: §24 (1) already guarantees between a rim vertex and the wall face.
#: MEASURED: with it, ``LEMDzaun`` reads 0 % interior (a ring body) and
#: ``LEMD13`` 76 % (a floor body).
FLOOR_MARGIN_M = 1.0

#: THE PIT'S OWN SHELL IS NEVER A FLOOR BODY, and what tells the two
#: apart is the RIM PLANE.  The shell is authored INTO the pit (LEMD's
#: T4S members reach −3.2 … −7.05, OTHH's drainage bowls −1.4 … −15.0);
#: a body that merely STANDS IN the pit is authored at the rim plane
#: like anything else on the ground and only dips under it by its own
#: kerb (``Ground-FSX-LEMD13`` −0.08 m).  The admission is therefore
#: ``[placement] split_tol_m``, passed in — the same materiality every
#: other placement verdict is taken at — and no depth reading is needed
#: at all.  MEASURED: at LEMD it admits ``LEMD13`` alone of the pit's
#: members (the trees, the radar and the T4S tower stay on the rim); at
#: OTHH it admits NONE, and the 21 basin carriers are untouched.
RING = "ring"
FLOOR = "floor"


@_dc.dataclass(frozen=True)
class Arc:
    """One contiguous run of the ring's nodes whose z agrees within the
    tolerance, and the RIM POINT a piece cut to it anchors on."""

    index: int
    total: int
    #: the ring-node indices this arc holds, in ring order
    nodes: tuple[int, ...]
    lat: float
    lon: float
    #: the rim point's own design-surface height — the arc's zero
    z: float

    @property
    def reason(self) -> str:
        return f"arc {self.index + 1}/{self.total}"


def is_basin_ring(ref: str) -> bool:
    """Is this emitted ``structure_rim`` ring a BASIN's (and not a
    tunnel's)?  §14a is the basin ring's law; §6's tunnel row requires a
    tunnel object to anchor on its FLOOR ring, which lies inside its own
    ring (11v deviation (a))."""
    return str(ref or "").startswith(BASIN_WALL_REF)


def arcs_of(z: _t.Sequence[float], ring: _t.Sequence[tuple[float, float]],
            tol_m: float, cap: int) -> tuple[Arc, ...]:
    """§14a (1): the ring cut into arcs over which its z agrees within
    ``tol_m``.

    The walk is a closed loop, so it needs a seam: it starts at the node
    whose z differs MOST from its predecessor (ties to the lower index),
    which puts the cut where the apron itself steps and is the same
    answer whatever order the emitter wrote the ring in.  The greedy run
    extends while the whole run's spread stays within ``tol_m``, so an
    arc is never wider than the tolerance and the wall base it carries is
    within half of it of every node it covers.

    ``cap`` (``[rebake] line_object_stations_max``) bounds the arcs: past
    it the node joins the arc it is nearest in z rather than founding one
    more piece.  ``cap <= 0`` is UNCAPPED, the convention §16a (1)'s
    carrier pieces already take — never "one arc", which silently
    disarmed the cut wherever the LINE machinery was off and is a
    coupling §14a has no business carrying.  ``tol_m <= 0`` disarms the
    cut and returns ONE arc — §14 (2)'s single rim point, unchanged."""
    n = len(z)
    if n == 0 or len(ring) != n:
        return ()
    if cap <= 0:
        cap = n
    if tol_m <= 0.0 or n == 1:
        return (_arc(0, 1, tuple(range(n)), z, ring),)
    start = max(range(n), key=lambda i: (round(abs(z[i] - z[i - 1]), 6), -i))
    order = [(start + k) % n for k in range(n)]
    runs: list[list[int]] = [[order[0]]]
    for i in order[1:]:
        run = runs[-1]
        lo = min(min(z[j] for j in run), z[i])
        hi = max(max(z[j] for j in run), z[i])
        if hi - lo <= tol_m:
            run.append(i)
        elif len(runs) >= cap:
            # the cap is reached: the node joins the run nearest it in z
            # rather than founding an arc nothing bounds
            best = min(range(len(runs)),
                       key=lambda k: min(abs(z[i] - z[j]) for j in runs[k]))
            runs[best].append(i)
        else:
            runs.append([i])
    return tuple(_arc(k, len(runs), tuple(r), z, ring)
                 for k, r in enumerate(runs))


def _arc(index: int, total: int, nodes: tuple[int, ...],
         z: _t.Sequence[float], ring: _t.Sequence[tuple[float, float]]) -> Arc:
    """The arc's RIM POINT: its own node nearest the arc's mid-level, so
    the piece's zero is at most half the arc's spread from every node it
    covers (the bar of §14a (4) read the other way round)."""
    lo = min(z[j] for j in nodes)
    hi = max(z[j] for j in nodes)
    mid = 0.5 * (lo + hi)
    j = min(nodes, key=lambda q: (round(abs(z[q] - mid), 6), q))
    return Arc(index, total, tuple(nodes), ring[j][0], ring[j][1], float(z[j]))


def arc_of_node(arcs: _t.Sequence[Arc], n: int) -> tuple[int, ...]:
    """``arcs[k].nodes`` inverted: the arc index of every ring node."""
    out = [0] * n
    for k, a in enumerate(arcs):
        for j in a.nodes:
            if 0 <= j < n:
                out[j] = k
    return tuple(out)


#: how a basin piece's anchor REASON spells its ring and its arc.  The
#: census reads the plan's own records, so the reason IS the wire between
#: the cut and the bar; a twin holds the two spellings together.
REASON_RIM = "basin rim ("
REASON_ARC = "basin rim arc "
#: §14a (2): what a FLOOR member's anchor reason carries, so the bind
#: keys and the report can both see the verdict without re-deriving it
FLOOR_MARK = " [§14a floor member of "


def ring_ref_of(reason: str) -> str:
    """The emitted ring ref a basin piece's anchor names, or ``""``."""
    r = str(reason or "")
    if not (r.startswith(REASON_RIM) or r.startswith(REASON_ARC)):
        return ""
    if "(" not in r or ")" not in r:
        return ""
    return r.split("(", 1)[1].split(")", 1)[0]


WALL_ARC_KEY = "basin_arc_wall:"


def wall_arc_key(ref: str, k: int) -> str:
    """The plan-``counts`` key saying "the pit's wall reaches arc ``k`` of
    ``ref``" — the one channel between the cut, which reads geometry, and
    the bar, which reads the plan."""
    return f"{WALL_ARC_KEY}{ref}#{k}"


def wall_arcs_of(counts: _t.Mapping[str, _t.Any], ref: str) -> "set[int] | None":
    """The arcs of ``ref`` the wall reaches, per :func:`wall_arc_key`, or
    ``None`` when the counts carry no such key at all (a plan written
    before §14a, whose bar then reads every node)."""
    pre = f"{WALL_ARC_KEY}{ref}#"
    if not any(str(k).startswith(WALL_ARC_KEY) for k in counts):
        return None
    out: set[int] = set()
    for k, v in counts.items():
        k = str(k)
        if k.startswith(pre) and v:
            try:
                out.add(int(k[len(pre):]))
            except ValueError:
                pass
    return out


def floor_bodies(raw: _t.Sequence) -> "set[int]":
    """§14a (2): the indices of one member's raw bodies marked as FLOOR
    members of a basin ring.

    A floor member takes NO carrier: its anchor is §16 (3)'s ground under
    its own footprint, and a carrier would put it straight back on the
    rim (measured: ``Ground-FSX-LEMD13`` rode ``LEMD03__b0`` at 598.39
    with the ground under its own base at 597.18-597.67)."""
    return {i for i, r in enumerate(raw) if FLOOR_MARK in r[2].reason}


def carrier_targets(raw: _t.Sequence, part_boxes: _t.Sequence,
                    elevated: _t.Iterable[int], footless: bool
                    ) -> "tuple[list, set[int]]":
    """§15's carrier search restricted by §14a (2): ``(targets, floor)``.

    A FLOOR member is dropped from every target — a footless placement's
    whole-placement group and an elevated body's own — and comes back in
    ``floor`` for the caller to send to §16 (3)'s own-ground anchor."""
    floor = floor_bodies(raw)
    grp0 = [i for i in range(len(raw)) if i not in floor]
    if footless:
        targets = ([(grp0, [b for i in grp0 for b in part_boxes[i]])]
                   if grp0 else [])
    else:
        targets = [([i], list(part_boxes[i]))
                   for i in sorted(elevated) if i not in floor]
    return (targets, floor)


def plan_counts(doc: _t.Mapping[str, _t.Any]) -> dict:
    """The SPLIT counts of a written ``o4_v2_placement_<ICAO>.json``.

    A written plan keeps the split half's tally under ``provenance``;
    its top-level ``counts`` is the WRITE half's.  §14a's bar needs the
    former (the ``basin_arc_wall`` keys), and a tool that read the wrong
    one reported a pit that follows its ring as one that does not — the
    two instruments must be one reading (CLAUDE.md)."""
    out = dict((doc.get("provenance", {}) or {}).get("counts", {}) or {})
    out.update(dict(doc.get("counts", {}) or {}))
    return out


def bind_key_of(reason: str) -> str:
    """§14a: the key that holds a body apart from the pit's group in
    ``bind_plan_overlaps`` — its ARC (§14a (1)), the ``interior``
    remainder an arc cut leaves, or ``floor`` for a member that merely
    STANDS IN the ring (§14a (2)).  Every other body of a BASIN ring
    keys on the rim, so the pit's own shell binds exactly as it did
    before; a body on a tunnel ring keys on nothing at all."""
    r = str(reason or "")
    if FLOOR_MARK in r:
        return f"{r.split(FLOOR_MARK, 1)[1].rstrip(')')}#floor"
    if r.startswith(REASON_ARC):
        k = arc_index_of(r)
        return "" if k is None else f"{ring_ref_of(r)}#arc{k}"
    ref = ring_ref_of(r)
    if not is_basin_ring(ref):
        return ""
    if ": interior" in r:
        return f"{ref}#interior"
    return f"{ref}#rim"


def arc_index_of(reason: str) -> "int | None":
    """The 0-based ARC index of a §14a (1) piece, or ``None`` for §14
    (2)'s single rim point (and for the INTERIOR remainder, whose zero
    says nothing about where the wall meets the apron)."""
    r = str(reason or "")
    if not r.startswith(REASON_ARC):
        return None
    head = r[len(REASON_ARC):].split(" ", 1)[0]
    k = head.split("/", 1)[0]
    try:
        return int(k) - 1
    except ValueError:
        return None


def member_kind(inside_frac: float, base_y: float, tol_m: float) -> str:
    """§14a (2): :data:`FLOOR` when this body merely STANDS IN the pit,
    :data:`RING` when it is part of the pit's own shell.

    ``inside_frac`` is the share of the body's DECISIVELY placed vertices
    standing inside the ring (see :data:`FLOOR_MARGIN_M`), ``base_y`` its
    lowest authored y and ``tol_m`` the placement materiality.  A body
    authored into the pit is the shell (see the note above
    :data:`FLOOR_MARGIN_M`)."""
    if base_y < -abs(tol_m):
        return RING
    return FLOOR if inside_frac > 0.5 else RING


def ring_bar(z: _t.Sequence[float], ring: _t.Sequence[tuple[float, float]],
             zero_of_arc: _t.Mapping[int, float], whole_zero: "float | None",
             tol_m: float, cap: int,
             wall_arcs: "set[int] | None" = None) -> dict:
    """§14a (4): THE BASIN ``spread`` BAR, RE-DEFINED — ``max |wall base −
    ring z|`` over the ring's own nodes.

    ``zero_of_arc`` is the zero of the piece written for each arc (the
    census reads it off the plan's anchors); ``whole_zero`` the zero of
    the ring's single §14 (2) piece where no arc was cut, which is how
    the bar reads the PRE-§14a frame: one piece covers every node, and
    LEMD's T4 pit comes out at +0.71 / −1.13.

    A node whose arc has no piece and for which there is no whole piece
    either is UNCOVERED — no basin object stands at that stretch of the
    ring, and nothing can be placed there.  It is counted and reported,
    never folded into the bar as a zero of 0."""
    arcs = arcs_of(z, ring, tol_m, cap)
    of_node = arc_of_node(arcs, len(z))
    off: list[float] = []
    fb: list[float] = []
    uncovered: list[int] = []
    for j in range(len(z)):
        zero = zero_of_arc.get(of_node[j])
        if zero is not None:
            off.append(float(zero) - float(z[j]))
            continue
        if whole_zero is None:
            uncovered.append(j)
            continue
        if wall_arcs is not None and of_node[j] not in wall_arcs:
            # NO BASIN OBJECT STANDS ON THIS STRETCH of the ring — there
            # is no wall base to put anywhere, so the node is reported
            # beside the bar and never inside it
            fb.append(float(whole_zero) - float(z[j]))
            continue
        # the wall is here but its arc piece was coarsened back into the
        # body's interior group: the wall base IS the interior zero
        off.append(float(whole_zero) - float(z[j]))
    return {"arcs": len(arcs), "nodes": len(z),
            "arcs_with_a_piece": len(zero_of_arc),
            "covered": len(off), "fallback": len(fb),
            "uncovered": len(uncovered),
            "uncovered_z": [round(float(z[j]), 2) for j in uncovered[:8]],
            "min": min(off) if off else 0.0, "max": max(off) if off else 0.0,
            "worst": max((abs(o) for o in off), default=0.0),
            "over_tol": sum(1 for o in off if abs(o) > tol_m),
            "fallback_worst": max((abs(o) for o in fb), default=0.0),
            "fallback_over_tol": sum(1 for o in fb if abs(o) > tol_m)}


# ── the geometry half: one basin body read against its ring ─────────────
#
# The parsed OBJ8 is handed in (``placement_cut._LineCutter`` already
# holds it and parses each member ONCE — two parses cost 42 s of OTHH's
# stage, measured at 11aj), so nothing here opens a file and nothing in
# the line cutter has to know what a ring is.


def _plan(geom, comps, parts, rim: "RimRing", lat: float, lon: float,
          heading_deg: float):
    """``(tris, ids, la, lo, d, inside, base_y)`` for one basin body
    against its ring — its triangles' vertices in world plan, each
    vertex's distance to the ring POLYLINE (not to its nodes: a wall
    standing mid-segment is on the ring) and whether it stands inside.
    ``None`` when the body has no readable component."""
    import numpy as np
    from . import anchor_rule as _ar
    tri_list = [comps[p.comp].tris for p in parts if 0 <= p.comp < len(comps)]
    if not tri_list:
        return None
    tris = np.concatenate(tri_list)
    v = geom.vertices
    ids = np.unique(tris.reshape(-1))
    ml, mo = _ar._m_per_deg(lat)
    h = math.radians(heading_deg)
    s, c = math.sin(h), math.cos(h)
    xs = v[ids, 0]
    zs = v[ids, 2]
    la = lat + (-(xs * s + zs * c)) / ml
    lo = lon + (xs * c - zs * s) / mo
    A = np.asarray([[r[0] * ml, r[1] * mo] for r in rim.ring], dtype=float)
    B = np.roll(A, -1, axis=0)
    P = np.stack([la * ml, lo * mo], axis=1)
    AB = B - A
    L2 = (AB ** 2).sum(1)
    L2[L2 == 0.0] = 1e-12
    d = np.empty(P.shape[0], dtype=float)
    step = max(1, (1 << 20) // max(1, A.shape[0]))
    for a in range(0, P.shape[0], step):
        b = min(a + step, P.shape[0])
        t = np.clip(((P[a:b, None, :] - A[None, :, :]) * AB[None, :, :]
                     ).sum(2) / L2[None, :], 0.0, 1.0)
        Q = A[None, :, :] + t[:, :, None] * AB[None, :, :]
        d[a:b] = np.sqrt(((P[a:b, None, :] - Q) ** 2).sum(2)).min(1)
    inside = np.asarray([_ar._inside(rim.ring, float(la[k]), float(lo[k]))
                         for k in range(P.shape[0])], dtype=bool)
    return (tris, ids, la, lo, d, inside, float(v[ids, 1].min()))


def ring_reading(geom, comps, parts, rim: "RimRing", lat: float, lon: float,
                 heading_deg: float) -> "tuple[float, float] | None":
    """``(interior fraction, base y)`` — §14a (2)'s two numbers, for
    :func:`member_kind`.

    THE VERTICES ON THE RING ARE NEITHER INSIDE NOR OUT: a body may
    straddle the ring (``Ground-FSX-LEMD13``'s gantry has half its
    vertices within 0.5 m of it), and counting those against the interior
    reads a body 76 % inside as 46 %.  The share is taken over the
    vertices that are DECISIVELY one side or the other — further than
    :data:`FLOOR_MARGIN_M` from the ring — which is the same reading
    §24 (1) uses to say a rim vertex is ON the wall face."""
    r = _plan(geom, comps, parts, rim, lat, lon, heading_deg)
    if r is None:
        return None
    _tris, _ids, _la, _lo, d, inside, base_y = r
    far = d > FLOOR_MARGIN_M
    n = int(far.sum())
    if n == 0:
        return None
    return (float((inside & far).sum()) / float(n), base_y)


def ring_arcs(geom, comps, parts, rim: "RimRing", arcs: _t.Sequence[Arc],
              band_m: float, lat: float, lon: float, heading_deg: float,
              foot_band_m: float, stations_max: int
              ) -> "tuple[list, tuple[int, ...]]":
    """§14a (1): ``(pieces, wall arcs)`` — one basin body's
    ``(arc index, triangles, feet)`` per piece.

    A triangle whose NEAREST VERTEX stands within ``band_m`` of a ring
    NODE belongs to the arc of that node; every other triangle is the
    body's INTERIOR and comes back as arc ``-1``, which the caller
    anchors at §14 (2)'s single rim point.

    * THE BAND IS READ ON THE VERTICES, not on the triangle centroid.
      The pit's floor plate is a handful of triangles hundreds of metres
      across whose edge lies ON the ring: read by centroid it has NO
      geometry at the ring at all (measured: LEMD's
      ``Ground-FSX-LEMD36`` 0 of 788 triangles in a 3 m centroid band,
      while its vertices stand 0.11 m from the rim nodes and are what
      those nodes' wall base actually reads).
    * AND TO THE RING'S NODES, not to its polyline: an arc is a run of
      NODES, so a vertex beside the middle of a 15 m segment is near the
      RING but belongs to no arc in particular — reading it as one put
      pieces on the two stretches of LEMD's pit where no basin object
      stands at all.
    * ONE ARC IS STILL A CUT.  A body standing wholly on one arc is not
      divided, but it must still take THAT arc's rim point rather than
      the pit's single one (LEMD's ``SWbaume`` sits entirely on the arc
      at 598.89 and rode 598.39 — the last node over the bar).

    Why the INTERIOR is not cut with the wall: the trench floor is ONE
    level (§24 (2) cut it to the plate MINUS ``[basin]
    floor_clearance_m``, from the pit's one zero), so a floor plate
    written per arc would step where the terrain under it does not and
    spend the clearance the plate renders in.  The wall is what meets the
    apron and the wall is what follows it.  §14a (1)'s "floor plate per
    arc" needs §24 (2) to cut the trench per arc as well; that is the
    DESIGN SURFACE's half and is reported, not decided here.

    The WALL ARCS are the arcs this body's band reaches at all, cut or
    not: an arc whose piece is later coarsened back into the body's
    interior group still HAS a wall, and the bar of §14a (4) must tell
    that apart from an arc where the pit simply has no object (3 of
    LEMD's 59 nodes, 8.6-15.8 m from the nearest basin vertex)."""
    if not arcs or band_m <= 0.0:
        return ([], ())
    r = _plan(geom, comps, parts, rim, lat, lon, heading_deg)
    if r is None:
        return ([], ())
    import numpy as np
    from . import anchor_rule as _ar
    from . import line_object as _lo
    from .placement_cut import authored_latlon
    tris, ids, la, lo, _d, _inside, _base = r
    ml, mo = _ar._m_per_deg(lat)
    pos = {int(q): k for k, q in enumerate(ids.tolist())}
    tk = np.asarray([[pos[int(q)] for q in row] for row in tris])
    A = np.asarray([[r0[0] * ml, r0[1] * mo] for r0 in rim.ring], dtype=float)
    V = np.stack([la * ml, lo * mo], axis=1)
    near = np.empty(V.shape[0], dtype=np.int64)
    dnode = np.empty(V.shape[0], dtype=float)
    step = max(1, (1 << 20) // max(1, A.shape[0]))
    for a in range(0, V.shape[0], step):
        b = min(a + step, V.shape[0])
        q = ((V[a:b, None, :] - A[None, :, :]) ** 2).sum(2)
        near[a:b] = q.argmin(1)
        dnode[a:b] = np.sqrt(q.min(1))
    of_node = np.asarray(arc_of_node(arcs, len(rim.ring)), dtype=np.int64)
    pick = tk[np.arange(tk.shape[0]), dnode[tk].argmin(axis=1)]
    who = np.where(dnode[pick] <= band_m, of_node[near[pick]], -1)
    keys = sorted(set(int(q) for q in np.unique(who).tolist()))
    wall = tuple(k for k in keys if k >= 0)
    if keys == [-1]:
        return ([], wall)
    v = geom.vertices
    out = []
    for k in keys:
        sel = np.nonzero(who == k)[0]
        if sel.shape[0] == 0:
            continue
        sub = tris[sel]
        vid = np.unique(np.asarray(sub).reshape(-1))
        yv = v[vid, 1]
        foot = vid[yv <= float(yv.min()) + foot_band_m]
        if foot.shape[0] == 0:
            foot = vid[:1]
        if 0 < stations_max < foot.shape[0]:
            foot = foot[_lo.farthest_point_stations(v[foot][:, [0, 2]],
                                                    stations_max)]
        feet = tuple(authored_latlon(float(v[i, 0]), float(v[i, 2]),
                                     lat, lon, heading_deg)
                     + (float(v[i, 1]),) for i in foot.tolist())
        out.append((k, tuple(tuple(int(q) for q in row)
                             for row in np.asarray(sub).tolist()), feet))
    return (out, wall)


def arc_anchor(k: int, arcs: _t.Sequence[Arc], whole, rim: "RimRing",
               surface):
    """The anchor of one §14a (1) piece: its ARC's rim point, or §14 (2)'s
    single rim point for the INTERIOR remainder (``k < 0``).

    The reason carries the arc so the census can tell the two apart — an
    interior piece's zero says nothing about where the wall meets the
    apron, and the bar of §14a (4) is read on the ARC pieces."""
    from . import anchor_rule as _ar
    if k < 0 or not (0 <= k < len(arcs)):
        return _ar.Anchor(_ar.BASIN, whole.lat, whole.lon, 0.0,
                          f"basin rim ({rim.ref}): interior, the object's "
                          f"zero is the rim", whole.surface_z)
    a = arcs[k]
    return _ar.Anchor(_ar.BASIN, a.lat, a.lon, 0.0,
                      f"basin rim {a.reason} ({rim.ref}): the wall follows "
                      f"the apron", surface(a.lat, a.lon))
