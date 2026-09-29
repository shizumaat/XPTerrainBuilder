"""A PAD WELDS TO THE APRON IT FRONTS; A TOUCHING APRON AT ANOTHER LEVEL IS
A TERRACE (owner RULINGS 2026-09-28a (6) + 2026-09-28b, issue #11 HECA-6).

Owner (28b, verbatim in substance): ``dsf:objpav399`` stays with the LOWER
apron ``pav131``; "because of the hill there is a WALL/TERRACE between it
and the cargo pad" ``building52`` (today ``building50``, the whole cargo
complex), which stays with the HIGHER east apron ``pav37``; the lower pad
at the corner (``building135``, today ``building127``) sits at the lower
level.  "So: a pad welds to the apron it FRONTS at its level; a touching
apron at another level is separated by a declared terrace (retaining
edge), not a weld."

WHY THIS IS A GEOMETRY CHANGE AND NOT A ROW (lane ``hecaroad``, issue
#11, refuted twice at the attempt cap): a pad and an apron that share
vertices ARE one value there (09-01g, identity is the weld), so no row
can put a step between them — releasing the weld from the pad's plate
let the complex fall through its lower neighbour, or left a face with no
plate at all.  The step has to have two vertex sets.  So the split is
made HERE, at the one site the pad/apron weld is made
(:func:`planar.pad_cut.apron_cut_to_pads`, 23a), before pass A nodes the
airside.

THE RULE (:func:`pad_terrace_split`).  Per pad region, every ring sample
(``_STEP_M`` apart) is assigned to its NEAREST apron (``[design]
pad_fronting_roles``) within ``[design] pad_fronting_reach_m`` whose
facing segment does not run back through the pad (the §20 facing
relation, ``constraints.pad_fronting``, read the same way).  The FRONT is
the apron with the most facing length — the LONGEST facing edge.  Every
OTHER apron the pad TOUCHES (within ``[design] pad_frontage_m``, §20's
own horizon) is TOUCH-AT-ANOTHER-LEVEL when the two aprons' levels differ
by more than the pad could span welded to both: the pad's own hard
ceiling ``emit.within_shape.pad_slope_max`` times the distance between
the two contacts (the WELD BOUND), and never under ``[terrace]
pad_terrace_floor_m`` (1.0 m, owner RULINGS 2026-09-30i; was §31 (1)'s
``visual_m`` 0.5) — a gap under the floor WELDS, only a real terrace
splits; the DEM proxy is not trusted below it.  THE FRONT MUST NOT ITSELF TOUCH:
a pad touching the apron it fronts is §20's weld and is left exactly as
it was (measured: requiring only "longest facing" split 60+ HECA pads
touching two aprons on the hillside by DEM noise of 0.2-2 m — the #11
class is the pad whose longest face is ACROSS BARE GROUND).  Each level is the DEM (the only level
there is before the solve) along that apron's own ring within reach of
its contact — one derivation for both.

THE SPLIT.  A TOUCH-AT-ANOTHER-LEVEL apron is cut back from the pad by
``pad_frontage_m + identity.min_distinct_spacing_m``: beyond §20's
frontage horizon (so the pad no longer fronts it, by identity OR by
proximity) and one identity cell more (so no weld re-forms at the
arrangement).  The strip between is GROUND — the §31 terrace, graded
between the two levels.  23a's direction is kept: the APRON yields, the
pad keeps its footprint.  A PAD at the lower level (touching that same
apron, not of the same unit) that shares the upper pad's rim is cut back
from it by ``identity.weld_spacing_m`` — two pads front nothing of each
other, so only the identity split is needed.

The terraces are PUBLISHED (``TERRACES``, and the ``pad_terraces`` count
in ``overlay.PAD_AIRSIDE``) so the arrangement can declare each strip as a
shape joint (``terrace_joints``) and a reader can find them."""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

import numpy as np
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import nearest_points
from shapely.strtree import STRtree

from ..model.pad_terrace import TERRACES, Terrace

__all__ = ["pad_terrace_split", "Terrace", "TERRACES"]

#: The ring sampling step of the facing read (m): a geometric resolution,
#: not a law value (the pads' own chord caps are 5-60 m).
_STEP_M = 2.0
#: A facing segment may graze its own pad by this much and still face
#: out (``constraints.pad_fronting._GRAZE_M``'s reason: the 0.5 m lattice).
_GRAZE_M = 0.5


# ``Terrace`` / ``TERRACES`` live in ``model/pad_terrace`` (issue #104:
# ``constraints`` reads them and may not import ``planar``); re-exported.


def _polys(g) -> list[Polygon]:
    if g is None or g.is_empty:
        return []
    if isinstance(g, Polygon):
        return [g]
    return [q for q in getattr(g, "geoms", []) if isinstance(q, Polygon) and not q.is_empty]


def _samples(poly: Polygon) -> list[tuple[float, float]]:
    ring = poly.exterior
    n = max(4, int(ring.length // _STEP_M))
    return [tuple(ring.interpolate(i * ring.length / n).coords[0]) for i in range(n)]


def _level(dem, apoly: Polygon, near: list[tuple[float, float]], reach: float) -> float | None:
    """The apron's own level along its ring within ``reach`` of the
    contact samples ``near`` — DEM, the only level before the solve."""
    if not near:
        return None
    ring = apoly.exterior
    n = max(4, int(ring.length // _STEP_M))
    zone = LineString(near).buffer(reach) if len(near) > 1 else Point(near[0]).buffer(reach)
    zs = []
    for i in range(n):
        p = ring.interpolate(i * ring.length / n)
        if zone.contains(p):
            try:
                zs.append(float(dem.z(p.x, p.y)))
            except Exception:  # noqa: BLE001 — outside the raster: no witness
                continue
    return float(np.mean(zs)) if zs else None


def pad_terrace_split(base_regions, pad_regions, law, dem) -> tuple[list, list, dict]:
    """THE SPLIT (module docstring).  Returns ``(base_regions,
    pad_regions, counts)``; a no-op without a DEM."""
    from ..law.tables import design as design_law, pavement_roles
    TERRACES.clear()
    counts: dict = {"pad_terraces": 0}
    if dem is None or not pad_regions:
        return list(base_regions), list(pad_regions), counts
    dl = design_law(law)
    reach = float(dl.pad_fronting_reach_m)
    near = float(dl.pad_frontage_m)
    roles = set(dl.pad_fronting_roles)
    slope = float(law.tables.emit.within_shape.pad_slope_max)
    floor = float(law.tables.emit.terrace.pad_terrace_floor_m)
    ident = law.tables.emit.identity
    gap = near + float(ident.min_distinct_spacing_m)
    pad_gap = float(ident.weld_spacing_m)
    if reach <= 0.0 or not roles:
        return list(base_regions), list(pad_regions), counts
    base = list(base_regions)
    pads = list(pad_regions)
    ai = [i for i, r in enumerate(base) if r.source == "cell" and r.role in roles
          and r.polygon is not None and not r.polygon.is_empty]
    if not ai:
        return base, pads, counts
    a_tree = STRtree([base[i].polygon for i in ai])
    # the ground must be BARE (``constraints.pad_fronting``'s blocker test):
    # a facing segment crossing any other pavement or pad face faces nothing
    pav = set(pavement_roles(law))
    bi = [i for i, r in enumerate(base) if r.source == "cell" and r.role in pav
          and r.polygon is not None and not r.polygon.is_empty]
    b_geoms = [base[i].polygon for i in bi] + [p.polygon for p in pads]
    b_tree = STRtree(b_geoms)
    p_tree = STRtree([p.polygon for p in pads])
    cut_apron: dict[int, list] = {}      # base index -> [pad buffers]
    cut_pad: dict[int, list] = {}        # pad index -> [upper-pad buffers]
    for k, pr in enumerate(pads):
        P = pr.polygon
        if P is None or P.is_empty or not isinstance(P, Polygon):
            continue
        cand = [ai[int(j)] for j in a_tree.query(P, predicate="dwithin", distance=reach)]
        if len(cand) < 2:
            continue                   # one apron in reach: nothing to choose
        touching = [i for i in cand if base[i].polygon.distance(P) <= near]
        if not touching:
            continue
        per: dict[int, list[tuple[float, float]]] = {}
        for s in _samples(P):
            sp = Point(s)
            best = None
            for i in cand:
                d = base[i].polygon.distance(sp)
                if d <= reach and (best is None or d < best[0]):
                    best = (d, i)
            if best is None:
                continue
            d, i = best
            if d > near:
                q = nearest_points(base[i].polygon, sp)[0]
                seg = LineString([s, (q.x, q.y)])
                if seg.intersection(P).length > _GRAZE_M:
                    continue           # runs back through the pad: faces nothing
                own = base[i].polygon
                if any(g is not P and g is not own
                       and seg.intersection(g).length > _GRAZE_M
                       for g in (b_geoms[int(j)] for j in
                                 b_tree.query(seg, predicate="intersects"))):
                    continue           # the ground between is not bare
            per.setdefault(i, []).append(s)
        if not per:
            continue
        front = max(per, key=lambda i: (len(per[i]), -i))
        if front in touching:
            continue                   # it touches what it fronts: §20's weld, unchanged
        lf = _level(dem, base[front].polygon, per[front], reach)
        if lf is None:
            continue
        cf = np.mean(np.asarray(per[front]), axis=0)
        for i in touching:
            if i == front or i not in per:
                continue
            lt = _level(dem, base[i].polygon, per[i], reach)
            if lt is None:
                continue
            ct = np.mean(np.asarray(per[i]), axis=0)
            if len(per[i]) >= len(per[front]):
                continue               # not the longest facing edge
            span = slope * float(np.hypot(*(cf - ct)))
            bound = max(span, floor)
            if abs(lt - lf) < floor or abs(lt - lf) <= span:
                continue               # under the 30i floor, or the pad spans both within its ceiling: weld
            contact = P.exterior.intersection(base[i].polygon.buffer(near))
            line = tuple(tuple(c) for g in getattr(contact, "geoms", [contact])
                         for c in getattr(g, "coords", []))
            TERRACES.append(Terrace(str(pr.ref), str(base[front].ref), str(base[i].ref),
                                    "apron", round(lf, 3), round(lt, 3), round(bound, 3),
                                    gap, line))
            cut_apron.setdefault(i, []).append(P.buffer(gap))
            # A LOWER PAD at the terraced apron's level sharing this pad's rim
            A = base[i].polygon
            for j in p_tree.query(P, predicate="dwithin", distance=pad_gap):
                j = int(j)
                Q = pads[j].polygon
                if j == k or str(pads[j].ref) == str(pr.ref) or Q is None:
                    continue
                if Q.distance(A) > near or Q.distance(P) > pad_gap:
                    continue
                TERRACES.append(Terrace(str(pr.ref), str(base[front].ref), str(pads[j].ref),
                                        "pad", round(lf, 3), round(lt, 3), round(bound, 3),
                                        pad_gap, ()))
                cut_pad.setdefault(j, []).append(P.buffer(pad_gap))
    from shapely.ops import unary_union
    extra = []
    for i, bufs in cut_apron.items():
        r = base[i]
        ps = sorted(_polys(r.polygon.difference(unary_union(bufs))), key=lambda q: -q.area)
        if not ps:
            base[i] = None
            continue
        base[i] = _dc.replace(r, polygon=ps[0])
        extra.extend(_dc.replace(r, polygon=q) for q in ps[1:])
    for j, bufs in cut_pad.items():
        r = pads[j]
        ps = sorted(_polys(r.polygon.difference(unary_union(bufs))), key=lambda q: -q.area)
        pads[j] = _dc.replace(r, polygon=ps[0]) if ps else None
    counts["pad_terraces"] = len(TERRACES)
    counts["pad_terrace_list"] = "; ".join(
        f"{t.pad_ref}|{t.other_ref} front {t.front_ref} {t.front_level:.1f} vs "
        f"{t.other_level:.1f} bound {t.bound_m:.2f}" for t in TERRACES[:12])
    return ([r for r in base if r is not None] + extra,
            [p for p in pads if p is not None], counts)
