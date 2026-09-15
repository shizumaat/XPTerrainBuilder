"""§33 (6) C1' — THE PACK'S WALL PAIRS ARE MOUTH RAMPS (owner RULINGS
2026-09-15e items 3/4; Fable / RULINGS 2026-09-15x; lane `v2objcut`).

Split out of ``planar/structure_approach`` under the 1,000-line file law
(``tests/auto_patch_v2/test_planar.py``); ``apply_plates`` calls
:func:`pair_mouth` and nothing else moved with the split.

A pack marks a covered bore's two ends with a PAIR of thin surface walls
each (LEMD `Bridge3.obj`: 73.0 / 73.1 m walls 14.02 m apart at one end,
27.65 / 25.71 m and 24.88 / 29.00 m at the other, 224 m of the object's
354.2 m box carrying no solid at all).  Each pair — or each CHAIN of
pairs meeting end to end, which is how a bent ramp is drawn — is one
mouth ramp: the ramp lies between the inner faces, its MOUTH at the end
nearer the object's centre (the covered stretch runs from there) and its
top at the outer end, with the mapped road carrying it beyond.
"""
from __future__ import annotations

import math
import typing as _t

from shapely.geometry import LineString, Point

from ..law import Law
from ..model.airport import OsmWay
from ..model.frame import XY
from .structure_approach import NODE_TOL, Mouth, approach, unit

__all__ = ["pair_groups", "pair_mouth"]


def _pair_midline(q) -> "tuple[XY, XY]":
    """A pair's midline as its two end points, with the two bands read the
    same way round (a pack draws them in either order)."""
    A, B, _inner = q
    a0, a1 = A.axis.coords[0], A.axis.coords[-1]
    b0, b1 = B.axis.coords[0], B.axis.coords[-1]
    same = (((a0[0] + b0[0]) / 2.0, (a0[1] + b0[1]) / 2.0),
            ((a1[0] + b1[0]) / 2.0, (a1[1] + b1[1]) / 2.0))
    flip = (((a0[0] + b1[0]) / 2.0, (a0[1] + b1[1]) / 2.0),
            ((a1[0] + b0[0]) / 2.0, (a1[1] + b0[1]) / 2.0))
    return same if math.dist(*same) >= math.dist(*flip) else flip


def pair_groups(pairs: _t.Sequence, gap_m: float) -> "list[tuple[list[XY], float]]":
    """§33 (6) C1': the object's pairs CHAINED into mouth ramps —
    ``(midline polyline, the narrowest inner spacing on it)`` per group.

    A pack draws a bent mouth ramp as SEVERAL straight pairs meeting end
    to end: measured LEMD `Bridge3.obj`'s south end is two pairs (27.65 /
    25.71 m at 164.50 deg and 24.88 / 29.00 m at 174.23 deg) sharing a
    junction at 40.49584 — one ramp with a 9.7 deg bend, not two mouths.
    Chaining them is what puts the mouth at the owner's own 40.4960195
    (item 8) and the top at 40.4956011, whence the open ramp runs on
    toward his 40.4951833 (item 4); reading them apart put the mouth at
    the junction and climbed the wrong way, INTO the covered stretch
    (measured: top 40.4956981 -> 40.4975702, 190 m north)."""
    mids = [_pair_midline(q) for q in pairs]
    inner = [float(q[2]) for q in pairs]
    used: set[int] = set()
    out: list[tuple[list[XY], float]] = []
    for i in range(len(mids)):
        if i in used:
            continue
        used.add(i)
        chain = [mids[i][0], mids[i][1]]
        best = inner[i]
        grew = True
        while grew:
            grew = False
            for j in range(len(mids)):
                if j in used:
                    continue
                for e, o in ((mids[j][0], mids[j][1]), (mids[j][1], mids[j][0])):
                    if math.dist(chain[-1], e) <= gap_m:
                        chain.append(o)
                    elif math.dist(chain[0], e) <= gap_m:
                        chain.insert(0, o)
                    else:
                        continue
                    used.add(j)
                    best = min(best, inner[j])
                    grew = True
                    break
        out.append((chain, best))
    return out


def pair_mouth(m: Mouth, p, osm: list[OsmWay], law: Law, reach_m: float,
                admitted) -> "tuple[Mouth, str] | None":
    """§33 (6) C1': this mouth taken by the plate's nearest WALL-PAIR
    GROUP, or ``None`` where the object carries none.

    THE MOUTH IS THE GROUP'S INNER END — the end nearer the OBJECT'S OWN
    CENTRE, which is the end the covered stretch runs from (the author
    marks a mouth at each end of what he covers).  The owner named both
    of LEMD's: 14bl item 7 "the mouth should be here: 40.4980461,
    −3.5850118" is the north group's inner end (9.4 m) and item 8
    "between 40.4960195 and 40.4960167" the south group's (5 m).  The
    ramp then climbs between the inner faces to the OUTER end and the
    mapped road carries it beyond — item 4's "curving and extending out
    closer to 40.4951833"."""
    pairs = list(getattr(p, "pairs", ()) or ())
    if not pairs:
        return None
    groups = pair_groups(pairs, law.tables.structures.tunnel.object.merge_gap_m)
    pt = Point(m.xy)
    chain, inner = min(groups, key=lambda g: LineString(g[0]).distance(pt))
    c = p.plan.centroid
    mouth_xy, top_xy = (chain[0], chain[-1]) \
        if c.distance(Point(chain[0])) <= c.distance(Point(chain[-1])) \
        else (chain[-1], chain[0])
    ramp = chain if mouth_xy == chain[0] else list(reversed(chain))
    inward = unit(ramp[1], ramp[0])          # on into the covered stretch
    outward = (-inward[0], -inward[1])
    # THE APPROACH MUST NOT KINK AT THE GROUP'S TOP.  The ramp's rings are
    # the path OFFSET by half the corridor's width, so a path turning
    # tighter than that half width folds and the whole corridor is
    # refused ("the approach bends tighter than the corridor") — measured
    # on the first C1' arm: both LEMD `-5931` mouths were lost that way.
    # Beyond the top the mapped road is kept only while it stays within
    # ``approach_turn_max_deg`` of the group's own last direction.
    last = unit(ramp[-2], ramp[-1])
    cap = math.cos(math.radians(law.tables.structures.tunnel.approach_turn_max_deg))
    beyond = approach(top_xy, last, osm, reach_m, admitted,
                      law.tables.structures.tunnel.approach_turn_max_deg)
    kept: list[XY] = []
    prev = top_xy
    for q in beyond[1:]:
        if math.hypot(q[0] - prev[0], q[1] - prev[1]) <= NODE_TOL:
            continue
        u = unit(prev, q)
        if u[0] * last[0] + u[1] * last[1] < cap:
            break
        kept.append(q)
        prev = q
    if not kept:
        kept = [(top_xy[0] + last[0] * reach_m, top_xy[1] + last[1] * reach_m)]
    path = list(ramp) + kept
    # THE RAMP STANDS INSIDE THE WALLS, not on them: the emitted identity
    # snaps a ring vertex onto a ``min_distinct_spacing_m`` grid, so an
    # edge laid exactly on the inner face can land OUTSIDE it, and the
    # owner's words are "ramp should stay within the wall boundaries"
    # (15e item 6).  One materiality step (``placement.split_tol_m``) of
    # clearance each side.
    clear = law.tables.structures.placement.split_tol_m
    width = max(inner - 2.0 * clear, inner * 0.5)
    d = math.hypot(mouth_xy[0] - m.xy[0], mouth_xy[1] - m.xy[1])
    note = (f"mouth of bore {'+'.join(str(i) for i in m.ways)} taken by {p.id}'s WALL PAIR "
            f"(§33 (6) C1'): moved {d:.1f} m to the group's INNER end, width "
            f"{m.width_m:.1f} -> {width:.2f} m (the pair's inner spacing {inner:.2f} less "
            f"{clear:.2f} m of clearance each side), ramp climbing "
            f"{LineString(ramp).length:.1f} m over {len(ramp) - 1} pair segment(s) to its "
            f"outer end and the mapped road beyond")
    return Mouth(m.bore, mouth_xy, inward, float(width), path, m.ways), note
