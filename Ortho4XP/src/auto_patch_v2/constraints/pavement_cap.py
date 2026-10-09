"""THE UNIVERSAL PAVEMENT CAP (owner RULINGS 2026-09-29ac, issue #105).

"No pavement of any class may be steeper than the road grade cap (the
steepest cap in the law).  Class caps that are lower still apply; where a
class cap is absent, not applied, or a pavement pair is otherwise unpriced
(a step, a cliff 'judged as if welded', a corridor read as ground, an exit
mouth) the road cap binds as a HARD row."

The cap is ONE accessor, :func:`law.tables.pavement_fallback_cap` — the
``[common] road_max_grade`` itself, never a second number.

THE POPULATION IS GEOMETRIC, NOT THE LAW SET.  ``constraints/ceiling.py``
twins every pair a family already PRICES; the ruling's subject is the
pairs nobody prices, so this reads the planar map:

* every consecutive pair of one pavement face's ring (outer and holes) —
  the ring edges a pad, lot or apron ring carries with no family on them;
* every pair of vertices of two DIFFERENT pavement faces standing within
  ``WELD_M`` of each other without sharing the vertex (a shared vertex is
  one unknown) — the welded neighbours §31 (7) judges as if welded.

Pavement is :func:`law.tables.pavement_roles` (the value, non-structure
roles).  Exclusions, each a ruling: a platform COLLAR face
(``model.planar.is_collar_ref``) is a 1:3 bank (RULINGS 2026-09-28a (1))
— ground, not pavement — and a pair touching a collar vertex crosses that
bank; structure ramps carry their own ruled caps and are not pavement.
A welded pair of two different BUILDING pads is a STEP, not a grade: the
step families' ``building_to_building`` exemption (owner 2026-06-20)
carries into this family (RULINGS 2026-09-30l (2)) — the census copy
(``check_grade._check_pavement_over_road_cap``) skips the same pair, and
two copies of one law agree.  A welded pair of two parts of one gap piece
ACROSS A DECLARED KNIFE is a STEP likewise (spec §55 (2) 4, §55 (14) Q-D;
owner RULINGS 2026-10-04u): the knife's two rims stand 0.75 m apart, inside
``WELD_M``, and the knife exists to carry the step the cap cannot join —
ONE predicate, ``model.planar.gap_parts_across_knife``, read here and by
the census copy.  Pricing the pad|pad pair dragged the HECA cargo pads
``building51``/``building56`` 6.4 m under the apron they front, onto the
lower pad ``building129`` across their declared 28b terrace (issue #123).
A welded pair with a PAD'S OWN vertex (one no pavement face shares) at
either end is not this family's at all (spec §62 (5) R-F, owner RULINGS
2026-10-09d (1) / 08c (4)): the pad|pavement pair across the stand-off is the
SEAT relation — §20's level fit, §28's frontage, ``constraints.pad_seat`` for
a landside-only pad — stated ONE-WAY.  The two-sided weld at 10 % over 1 m
held a pad rim vertex on a road its ramp law fixes and the LP relaxed the
pad's hard plane instead (81 pad-tier rows on one pad at the airport that
showed it); it was also the de-facto seat of every landside-only pad, which
is why R-F lands with the seat's own hard row.  A vertex a pad SHARES with
pavement is the pavement's (09-01g) and keeps its pairs.

A pair ALREADY capped at or under the fallback by a hard ``Diff`` over the
same two vertices (the ceiling's twins, the road cross-section, …) mints
nothing — "one hard row family over every pavement pair not already capped
lower".  A pair whose two vertices are both PINNED mints nothing: two pins
are the law's own values, and a row between them constrains nothing the
solve can move.  A pair at zero plan distance (two stacked vertices) is a
weld the emitter owns, not a grade, and mints nothing.

HARD: the ruling head is in ``emit.toml [design] hard_rulings``.  Two-way
(a grade cap has no leader); AIRSIDE IS KING is kept by the staged solve —
stage 1 drops every row touching a groundside vertex, and stage 2 solves
the groundside against the airside's fixed values.
"""
from __future__ import annotations

import math
import typing as _t

from ..law import Law
from ..law.tables import pavement_fallback_cap, pavement_roles
from ..model.constraints import Diff, Pin, Row, Source
from ..model.planar import (PlanarMap, gap_parts_across_knife, is_bank_ref,
                            is_gap_ref)

__all__ = ["pavement_road_cap", "GEN", "RULING", "WELD_M", "PAD_ROLE"]

GEN = "pavement_road_cap"
#: The ruling HEAD ``[design] hard_rulings`` names (everything before the
#: first parenthesis, ``solve.design.ruling_head``).
RULING = ("rulesets.common.road_max_grade pavement fallback "
          "(owner RULINGS 2026-09-29ac)")
#: Two different pavement faces' vertices this close in plan are welded
#: neighbours (the census family ``pavement_over_road_cap`` reads the same
#: radius, ``check_grade.PAVCAP_WELD_M``).
WELD_M = 1.0
#: The pad role whose welded pad|pad pairs hold the ``building_to_building``
#: step exemption (the census predicate ``check_grade._step_exemption_for``).
PAD_ROLE = "building"


def pavement_road_cap(rows: _t.Sequence[Row], planar: PlanarMap, law: Law
                      ) -> list[Row]:
    """The fallback rows over ``planar``'s pavement pairs (module
    docstring), given the law set ``rows`` already minted."""
    cap = pavement_fallback_cap(law)
    pav = set(pavement_roles(law))
    face_vs: dict[int, tuple[int, ...]] = {}
    pad_faces: set[int] = set()
    part_ref: dict[int, str] = {}       # gap pieces and parts, by face
    road_faces: set[int] = set()
    rings: list[tuple[tuple[int, ...], bool]] = []
    collar_v: set[int] = set()
    from ..model.platform import structure_vertices
    struct = structure_vertices(planar, law)
    # issue #143 (``roads.road_pair_side``): a pair this fallback reads off
    # a ROAD's ring is a road row — one-way on the groundside foot of a
    # pair welded to airside
    from .roads import (PAIR_WELD, road_family_roles, road_pair_side,
                        stage_one_vertices)
    roads = set(road_family_roles(law))
    air = stage_one_vertices(planar, law)
    # issue #264 (CYXY 60.7137823, -135.0763504): a pad|groundside pair §28
    # (6) HOLDS AS A HILLSIDE TERRACE (owner RULINGS 2026-09-13o/13p, the
    # lot arriving at the second storey) is a STEP, not a grade — as the
    # pad|pad pair is (30l (2)).  Welding it here at 8 % over 1.0 m pulled
    # ``pav4``'s corner vertex onto ``building9``'s pad (695.01 m) and the
    # lot then climbed at its own cap 2.88 m back to its ground: the
    # owner's dip.  ONE derivation of "held": ``pad_frontage_gs``.
    from .pad_frontage_gs import held_terrace_pairs
    held = held_terrace_pairs(planar, law)
    held_faces: dict[int, set[int]] = {}
    for gid, pid in held:
        held_faces.setdefault(gid, set()).add(pid)
        held_faces.setdefault(pid, set()).add(gid)
    for f in planar.faces.values():
        if f.role not in pav:
            continue
        cyc = [planar.ring_vertices(r) for r in (f.ring, *f.holes)]
        if is_bank_ref(f.ref):
            collar_v.update(v for c in cyc for v in c)
            continue
        rings.extend((c, f.role in roads) for c in cyc if len(c) >= 2)
        face_vs[f.id] = tuple(dict.fromkeys(v for c in cyc for v in c))
        if f.role == PAD_ROLE:
            pad_faces.add(f.id)
            # a pad vertex a STRUCTURE face carries (a ramp cut into the
            # pad): the pair from it crosses the WALL, a declared step as
            # the collar's bank was (``model.platform.structure_vertices``)
            collar_v.update(v for c in cyc for v in c if v in struct)
        if is_gap_ref(f.ref):
            part_ref[f.id] = str(f.ref)
        if f.role in roads:
            road_faces.add(f.id)
    if not face_vs:
        return []
    # already capped at or under the fallback (a hard Diff over the pair)
    capped: set[tuple[int, int]] = set()
    pinned: set[int] = set()
    for r in rows:
        if isinstance(r, Diff) and r.soft is None and r.cap <= cap:
            capped.add((min(r.a, r.b), max(r.a, r.b)))
        elif isinstance(r, Pin):
            pinned.add(r.v)
    xy = {v: vx.xy for v, vx in planar.vertices.items()}
    src = Source(GEN, RULING, ())
    seen: set[tuple[int, int]] = set()
    out: list[Row] = []

    def _mint(a: int, b: int, road: bool = False) -> None:
        if a == b:
            return
        key = (min(a, b), max(a, b))
        if key in seen or key in capped:
            return
        follows = None
        if road:
            side, gs = road_pair_side(air, key)
            if side == PAIR_WELD:
                follows = gs
        seen.add(key)
        if a in collar_v or b in collar_v or (a in pinned and b in pinned):
            return
        (xa, ya), (xb, yb) = xy[a], xy[b]
        d = math.hypot(xa - xb, ya - yb)
        if d <= 0.0:
            return
        out.append(Diff(key[0], key[1], cap, d, src, follows=follows))

    for c, road in rings:
        for i, a in enumerate(c):
            _mint(a, c[(i + 1) % len(c)], road)
    # welded neighbours of two different faces
    owner: dict[int, set[int]] = {}
    for fid, vs in face_vs.items():
        for v in vs:
            owner.setdefault(v, set()).add(fid)
    verts = sorted(owner)
    if len(verts) >= 2:
        from scipy.spatial import cKDTree
        tree = cKDTree([xy[v] for v in verts])
        for i, j in sorted(tree.query_pairs(WELD_M)):
            a, b = verts[i], verts[j]
            if owner[a] == owner[b] and len(owner[a]) == 1:
                continue            # same single face: its ring pairs above
            if not (owner[a] - owner[b] or owner[b] - owner[a]):
                continue
            if owner[a] <= pad_faces or owner[b] <= pad_faces:
                # pad|pad: a step (30l (2)), not a grade.  A PAD'S OWN
                # vertex against a pavement vertex across the stand-off is
                # the SEAT relation's pair (spec §62 (5) R-F): one-way, §20
                # / §28 / the landside seat — never a two-sided hard weld
                continue
            if held_faces and any(
                    fb in held_faces.get(fa, ())
                    for fa in owner[a] for fb in owner[b]):
                continue            # a §28 (6) hillside terrace pair (#264)
            if part_ref and any(
                    gap_parts_across_knife(part_ref.get(fa), part_ref.get(fb))
                    for fa in owner[a] for fb in owner[b]):
                continue            # across a declared knife: a step (§55 Q-D)
            # a welded pair whose groundside foot is a road's alone is a
            # road pair (issue #143)
            _mint(a, b, (a not in air and owner[a] <= road_faces)
                  or (b not in air and owner[b] <= road_faces))
    return out
