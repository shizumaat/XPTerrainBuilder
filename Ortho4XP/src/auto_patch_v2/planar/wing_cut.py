"""THE CUT BESIDE A GROUPED MOUTH'S WINGS (#2099 R2; spec
``docs/specs/2099-R2-wing-cut.md``; the group: ``airport/mouth_group``,
spec ``docs/specs/2099-mouth-groups.md``).

A tunnel mouth's WING WALLS are a ramp witness: the pack authored each one
standing on the road it lines, so its FOOT -- the lowest solid y of its
cross-section, station by station, over the mouth's floor -- is the floor
line along it (never under the mouth's own floor: a wall's footing below
the road is buried by design).  :func:`wing_cuts` reads, per mouth group
the load partition forms (the planar readers' mouths; every hard deck's
members and every piece co-placed with a mouth ``taken``: they are the
mouth's own frame, which its own record seats):

* THE FEET (:func:`_feet`): per wing, every ``[tunnel.object]
  wall_sample_m`` along its long axis from the end nearest the mouth, the
  foot and the point of its INNER face (the face nearer the mouth's
  opening axis);
* THE REGION (:func:`_ribbon`): from each inner-face point straight across
  the opening to its far edge (the mouth's plan half-width either side of
  its axis) -- so a wing lining one side cuts the whole road beside it, and
  a splayed wing the fan between it and the axis -- less the mouth's plan
  grown by ``[tunnel] wall_gap_m`` (the deck's own ground and end lines keep
  their law);
* THE GROUND (:func:`_cells`): the region's FREE ground (no cell owns it)
  becomes ``graded_strip`` cells ``wing_cut:<mouth>[#k]`` -- ground, never
  pavement, like a deck's own ground.

The level is ``constraints/wing_cut``'s, off the record
(``model/wing_cut.WingCut``).  Nothing here names a pack, a resource or an
airport; every number is a law value.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import types
import typing as _t

import numpy as np
from shapely.geometry import Point, Polygon
from shapely.ops import unary_union

from ..airport import mouth_group as _mg
from ..airport import obj8 as _obj8
from ..classify.roles import Cell
from ..geom.fixed_overlay import canonical_union, fixed_difference, is_hairline
from ..geom.parts import polygon_parts_with_area
from ..law.tables import role_side
from ..model.wing_cut import WING_CUT_REF, WingCut
from .deck_bridge import co_placed, deck_polygon

__all__ = ["wing_cuts"]

XY = tuple[float, float]


def _feet(o, cache, step: float, mouth_plan, centre: XY, r: XY
          ) -> list[tuple[float, float, float]]:
    """``[(x, y, foot y)]`` along wing ``o``'s long axis every ``step`` from
    its end nearest ``mouth_plan``: the foot is the cross-section's lowest
    solid y (an exact triangle cut), the point its inner face's -- the face
    nearer the opening axis through ``centre`` along ``r``."""
    g = cache.geometry(o.resolved)
    tris = np.concatenate([c.tris for c in cache.genuine(o.resolved)])
    a, b, d, e, xo, yo = _obj8.placement_affine(o.xy, o.heading_deg)
    v = g.vertices
    X, Y = a * v[:, 0] + b * v[:, 2] + xo, d * v[:, 0] + e * v[:, 2] + yo
    edges = np.concatenate([tris[:, [0, 1]], tris[:, [1, 2]], tris[:, [2, 0]]])
    ids = np.unique(tris)
    pts = np.column_stack([X[ids], Y[ids]])
    u = _long_axis(pts)
    n = np.array([-u[1], u[0]])
    T, N = X * u[0] + Y * u[1], X * n[0] + Y * n[1]
    lo, hi = float(T[ids].min()), float(T[ids].max())
    nm = float(N[ids].mean())
    near_lo = mouth_plan.distance(Point(*(u * lo + n * nm))) <= \
        mouth_plan.distance(Point(*(u * hi + n * nm)))
    sgn, start = (1.0, lo) if near_lo else (-1.0, hi)
    ta, tb = T[edges[:, 0]], T[edges[:, 1]]
    out = []
    k = 0.0
    while k <= hi - lo + 1e-9:
        t = start + sgn * min(k, hi - lo)
        m = ((ta - t) * (tb - t) <= 0.0) & (ta != tb)
        if m.any():
            f = (t - ta[m]) / (tb[m] - ta[m])
            i0, i1 = edges[m, 0], edges[m, 1]
            ys = v[i0, 1] + f * (v[i1, 1] - v[i0, 1])
            ns = N[i0] + f * (N[i1] - N[i0])
            cands = [u * t + n * float(ns.min()), u * t + n * float(ns.max())]
            q = min(cands, key=lambda p: abs((p[0] - centre[0]) * -r[1] + (p[1] - centre[1]) * r[0]))
            out.append((float(q[0]), float(q[1]), float(ys.min())))
        k += step
    return out


def _long_axis(pts: np.ndarray) -> np.ndarray:
    """The unit direction of a plan's largest spread (its principal axis)."""
    c = pts - pts.mean(axis=0)
    w, vec = np.linalg.eigh(c.T @ c)
    ax = vec[:, int(np.argmax(w))]
    return ax / (np.hypot(*ax) or 1.0)


def _ribbon(feet: _t.Sequence[tuple[float, float, float]], centre: XY, r: XY, half: float):
    """The plan from each foot point straight across the opening (the line
    through ``centre`` along ``r``) to its far edge ``half`` beyond the axis."""
    if len(feet) < 2:
        return None
    nx, ny = -r[1], r[0]
    pairs = []
    for x, y, _f in feet:
        uq = (x - centre[0]) * nx + (y - centre[1]) * ny
        dist = -(1.0 if uq >= 0.0 else -1.0) * half - uq
        pairs.append(((x, y), (x + dist * nx, y + dist * ny)))
    # one quad per pair of stations: a splayed wing's ribbon never folds
    quads = [Polygon([a0, a1, b1, b0]).buffer(0.0)
             for (a0, b0), (a1, b1) in zip(pairs, pairs[1:])]
    return unary_union([q for q in quads if not q.is_empty])


def _end_line_dir(db) -> "XY | None":
    """The way the road under a hard deck runs: ALONG its two end lines (the
    carried route drives across them), end B's sense turned to end A's."""
    dirs = []
    for st in (db.seats_a, db.seats_b):
        if len(st) < 2:
            return None
        dx, dy = st[-1][0] - st[0][0], st[-1][1] - st[0][1]
        L = math.hypot(dx, dy)
        if L <= 1e-9:
            return None
        dirs.append((dx / L, dy / L))
    (ax, ay), (bx, by) = dirs
    if ax * bx + ay * by < 0.0:
        bx, by = -bx, -by
    L = math.hypot(ax + bx, ay + by) or 1.0
    return (ax + bx) / L, (ay + by) / L


def _mouth_frame(m, decks: _t.Mapping[str, _t.Any], tunnels) -> "tuple | None":
    """``(r, seat kwargs)`` of mouth ``m``: a hard deck's road direction and
    end lines, or a row-seated portal's bore direction and absolute floor."""
    db = decks.get(m.object_id)
    if db is not None:
        r = _end_line_dir(db)
        if r is None:
            return None
        return r, dict(seats=(tuple(db.seats_a), tuple(db.seats_b)),
                       tops=(float(db.top_a), float(db.top_b)))
    for tn in tunnels:
        if str(getattr(tn, "portal", "")) == m.object_id and getattr(tn, "portal_seat", ()) \
                and len(tn.axis) >= 2:
            (x0, y0), (x1, y1) = tn.axis[0], tn.axis[1]
            L = math.hypot(x1 - x0, y1 - y0) or 1.0
            return ((x1 - x0) / L, (y1 - y0) / L), dict(floor_z=float(tn.mouth_z))
    return None


def wing_cuts(airport, objects, cache, decks, tunnels, classification, law
              ) -> tuple[_t.Any, tuple[WingCut, ...], list[str]]:
    """``(classification with the wing-cut ground, the cuts, notes)`` (module
    doc)."""
    partition = getattr(airport, "partition", None)
    mouths = _mg.mouths_of(types.SimpleNamespace(decks=decks, structures=tunnels))
    if partition is None or not mouths:
        return classification, (), []
    # a mouth's own frame is no wing: a hard deck's members, and every piece
    # co-placed with a mouth (its frame record seats it -- one authority per row)
    taken = {str(i) for db in decks for i in db.members}
    tol = float(law.tables.structures.tunnel.object.cover_placement_tol_m)
    heads = [o for o in objects if str(o.id) in {m.object_id for m in mouths}]
    taken |= {str(o.id) for o in objects for h in heads if o is not h and co_placed(h, o, tol)}
    groups, _n = _mg.mouth_groups(partition, objects, mouths, cache, law, taken)
    if not groups:
        return classification, (), []
    tn_law = law.tables.structures.tunnel
    step = float(tn_law.object.wall_sample_m)
    spacing = float(law.tables.emit.identity.min_distinct_spacing_m)
    by_id = {str(o.id): o for o in objects}
    deck_of = {str(db.object_id): db for db in decks}
    cuts: list[WingCut] = []
    notes: list[str] = []
    for gr in groups:
        frame = _mouth_frame(gr.mouth, deck_of, tunnels)
        mo = by_id.get(gr.mouth.object_id)
        read = None if mo is None else _mg._solids(mo, cache, law)
        if frame is None or read is None:
            continue
        r, seat = frame
        mplan = read[0]
        # the opening: the deck's ring (its own plan) or the portal's solids
        band = deck_polygon(deck_of[gr.mouth.object_id]) if gr.mouth.object_id in deck_of \
            else mplan
        c = band.centroid
        centre = (c.x, c.y)
        half = max(abs((x - c.x) * -r[1] + (y - c.y) * r[0])
                   for q in getattr(band, "geoms", [band]) for x, y in q.exterior.coords)
        feet: list[tuple[float, float, float, str]] = []
        parts = []
        for wid, _res in gr.wings:
            fw = _feet(by_id[wid], cache, step, mplan, centre, r)
            fw = [(x, y, max(f, 0.0)) for x, y, f in fw]
            feet.extend((x, y, f, wid) for x, y, f in fw)
            rib = _ribbon(fw, centre, r, half)
            if rib is not None and not rib.is_empty:
                parts.append(rib)
        if not parts:
            continue
        region = unary_union(parts).difference(
            unary_union([band, mplan]).buffer(float(tn_law.wall_gap_m) + spacing,
                                                  join_style="mitre"))
        rings = tuple(tuple((float(x), float(y)) for x, y in q.exterior.coords[:-1])
                      for q in polygon_parts_with_area(region) if not is_hairline(q, spacing))
        if not rings:
            continue
        ref = f"{WING_CUT_REF}:{gr.mouth.object_id}"
        cuts.append(WingCut(gr.mouth.object_id, ref, rings, tuple(feet),
                            floor_y=float(gr.mouth.floor_y), **seat))
        notes.append(f"{gr.mouth.object_id}: wing cut over {len(gr.wings)} wing(s), "
                     f"{sum(Polygon(q).area for q in rings):.0f} m2, feet "
                     f"{min(f for *_xy, f, _w in feet):+.2f}..{max(f for *_xy, f, _w in feet):+.2f} "
                     f"over its floor (#2099 R2)")
    if not cuts:
        return classification, (), notes
    classification, minted = _cells(classification, cuts, law, spacing)
    notes.extend(minted)
    return classification, tuple(cuts), notes


def _cells(classification, cuts: _t.Sequence[WingCut], law, spacing: float
           ) -> tuple[_t.Any, list[str]]:
    """The cuts' FREE ground as ``graded_strip`` cells (module doc)."""
    cells = list(classification.cells)
    polys = [Polygon(c.ring, c.holes) for c in cells if len(c.ring) >= 3]
    taken = canonical_union([p if p.is_valid else p.buffer(0.0) for p in polys])
    out: list[Cell] = []
    notes: list[str] = []
    for cut in cuts:
        region = unary_union([Polygon(q) for q in cut.region])
        free = [q for q in polygon_parts_with_area(fixed_difference(region, taken))
                if not is_hairline(q, spacing)]
        for k, part in enumerate(free):
            out.append(Cell(0, "graded_strip", cut.ref + (f"#{k}" if k else ""),
                            tuple(part.exterior.coords)[:-1],
                            tuple(tuple(h.coords)[:-1] for h in part.interiors),
                            None, None, role_side(law, "graded_strip"), "structure",
                            {"wing_cut": 1.0, "area_m2": part.area}))
        if free:
            taken = canonical_union([taken, *free])
            notes.append(f"{cut.mouth}: {len(free)} wing-cut face(s) "
                         f"{sum(q.area for q in free):.0f} m2 of free ground")
    if not out:
        return classification, notes
    merged = [_dc.replace(c, id=i) for i, c in enumerate(cells + out)]
    return _dc.replace(classification, cells=tuple(merged)), notes
