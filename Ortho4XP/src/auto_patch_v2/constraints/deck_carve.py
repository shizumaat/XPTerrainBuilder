"""THE DECK'S CUT, LEVELLED IN STAGE 2 (owner RULINGS 2026-11-19s (2)-(4);
owner 2026-11-19T23:07Z / 23:09Z: the cut is the deck's, "the cut needs to
grade smoothly away from the bridge back to the natural terrain").

Between the stages (``constraints/deck_floor_follow``) each generated
deck's TOP is known -- the no-bridge pavement over its ring, a Coons patch
-- and so is its cut, as a surface ``z(x, y)``:

* THE FLOOR along its one cut (``model/deck_carve.CarvePath``): under
  each deck's stretch ``min(lidar road floor, underside - clearance)`` --
  the underside the top less ``[deck_gen] thickness_m`` over every point of
  the path under the ring, the clearance the road's
  (``model/road_clearance.design_clearance_m``); straight through the gap
  to the next deck over the same road; past the outermost deck the ramp
  back along the path at the grade cap (road law, rail 1.25 %) with
  vertical curves until it meets the surveyed ground
  (``geom/carve_profile.floor_profile``);
* ACROSS it the floor over the deck's full span less each abutment's
  embankment (never narrower than its roads), then the bank at
  the deck bank's slope (1V:1.5H, ``model/deck_bank``) to the ground
  (``Vertex.dem_z``): ``min(ground, floor + bank * beyond)``, the deepest
  of every path's;
* THE ABUTMENTS: never under the cone the airside pavement (a stage-2
  constant: the deck's end lines and every pavement edge beside the cut)
  throws down at the same slope -- the embankment from each end line to
  the floor, and no pavement edge undercut.

UNDER THE RING the rule is absolute (owner 2026-11-20T00:30Z): a vertex
on the floor stands at its deck's floor, any other on the embankment from
the nearer end line down to it.  Every groundside vertex in the cut takes
that level as a stage-2 CONSTANT
(``stage2_fixed``): on the cut's own cells, under the ring and its opened
approaches, and wherever the surface stands under the ground.  An airside
vertex is never touched (19s (1)).  Pure: no geometry library past numpy
and scipy's KD tree.  Nothing here names an airport.
"""
from __future__ import annotations

import math
import typing as _t

import numpy as np

from ..geom.carve_profile import PathFrame, floor_profile, lateral, ramp_lengths, smoothed
from ..model.deck_bank import deck_bank_slope
from ..model.deck_carve import CARVE_REF

__all__ = ["carve_levels"]

#: a ground vertex the cut stands this far under is the cut's (m)
_UNDER_M = 0.01
#: the top is read over a stretch this often (m)
_STEP_M = 2.0
#: the airside cone is read off this many nearest pavement vertices
_KERB_K = 24
#: the ramp is designed at this share of its cap: the mesh between the
#: floor's edge vertices (noded every ``planar/deck_carve.NODE_M``) reads a
#: few tenths of a per cent steeper over a short run than the profile
_CAP_SHARE = 0.95
#: a floor-edge vertex stands this far off its line at most (the planar
#: build snaps a vertex to its identity lattice, ``law.tables.snap_margin_m``)
_SNAP_M = 0.5


def _path_stations(p) -> tuple[np.ndarray, np.ndarray]:
    s = np.array([t[0] for t in p.terrain], dtype=np.float64)
    r = smoothed([t[1] for t in p.terrain])
    return s, r


def _stretch_floor(p, frame: PathFrame, s, r, a: float, b: float, top, inside, slab: float,
                   probe: float) -> "tuple[float, float, float] | None":
    """``(floor, lidar floor, least underside)`` the path asks of the
    stretch ``[a, b]``: the deeper of the lidar road -- the lowest surveyed
    road within ``probe`` of the stretch along the path (a bare-earth
    survey reads the deck or its fill under the bridge itself; the road
    stands open at its ends) -- and the underside less the road's clearance
    over every station under the ring (``inside``)."""
    lidar = [float(z) for sk, z in zip(s, r, strict=True) if a - probe <= sk <= b + probe]
    unders = []
    n = max(2, int((b - a) / _STEP_M) + 1)
    for k in range(n):
        (x, y), _u = frame.at(a + (b - a) * k / (n - 1))
        if inside(x, y):
            unders.append(top.z(x, y) - slab)
    if not unders:
        return None
    under = min(unders)
    floor = min([under - p.clearance_m] + lidar)
    return floor, (min(lidar) if lidar else math.inf), under


def _deck_floors(decks, tops, law) -> tuple[dict, dict]:
    """``({deck id: floor}, {(path id, s0): stretch report})``: ONE floor
    per deck, the deepest any road under it asks (a small road beside a
    primary is cut to the primary's floor, as ``deck_generated.
    _shared_depths`` sizes the deck)."""
    from shapely.geometry import Point
    from shapely.prepared import prep

    from ..planar.deck_bridge import deck_polygon
    slab = float(law.tables.structures.deck_gen.thickness_m)
    probe = float(law.tables.structures.deck_gen.level_probe_m)
    rings = {d.object_id: prep(deck_polygon(d)) for d in decks}
    floors: dict[str, float] = {}
    srep: dict = {}
    for d in decks:
        for p in getattr(getattr(d, "carve", None), "paths", ()) or ():
            if len(p.terrain) < 2:
                continue
            frame = PathFrame(p.coords)
            s, r = _path_stations(p)
            for a, b, oid in p.stretches:
                if tops.get(oid) is None or oid not in rings:
                    continue
                got = _stretch_floor(p, frame, s, r, a, b, tops[oid],
                                     lambda x, y, ring=rings[oid]: ring.contains(Point(x, y)),
                                     slab, probe)
                if got is None:
                    continue
                floors[oid] = min(floors.get(oid, math.inf), got[0])
                srep[(id(p), a)] = {"deck": oid, "s": [round(a, 1), round(b, 1)],
                                    "lidar_floor": round(got[1], 3),
                                    "underside": round(got[2], 3), "need": p.clearance_m}
    return _one_cut(decks, floors), srep


def _one_cut(decks, floors: dict[str, float]) -> dict[str, float]:
    """Decks one cut joins (owner 2026-11-20T00:33Z: two parallel bridges
    "closer than would allow a full ramp up to grade, then back down again
    ... get cut like a single bridge, full depth between them, only two
    ramps on the outside"; ``geom/carve_profile.merged``) take the deepest
    floor of the cut, so its floor is one level from deck to deck."""
    from ..geom.carve_profile import merged
    from ..geom.union_find import find_root
    ids = sorted(floors)
    at = {oid: k for k, oid in enumerate(ids)}
    parent = list(range(len(ids)))
    for d in decks:
        for p in getattr(getattr(d, "carve", None), "paths", ()) or ():
            st = sorted((a, b, oid) for a, b, oid in p.stretches if oid in at)
            if len(st) < 2 or len(p.terrain) < 2:
                continue
            s, r = _path_stations(p)
            for (_a0, a1, oa), (b0, _b1, ob) in zip(st, st[1:], strict=False):
                m = (s > a1) & (s < b0)
                peak = float(np.max(r[m])) if m.any() else -math.inf
                if b0 <= a1 or merged(b0 - a1, floors[oa], floors[ob], peak,
                                      p.cap * _CAP_SHARE):
                    parent[find_root(parent, at[ob])] = find_root(parent, at[oa])
    low: dict[int, float] = {}
    for oid in ids:
        r_ = find_root(parent, at[oid])
        low[r_] = min(low.get(r_, math.inf), floors[oid])
    return {oid: low[find_root(parent, at[oid])] for oid in ids}


def _hyp(u) -> float:
    from ..geom.exact import hypot
    return hypot(float(u[0]), float(u[1]))


def _floor_half(p, top, floor, law) -> float:
    """The floor's half width across the cut: the deck's full span between
    its end lines less each abutment's embankment (the end line's top down
    to the floor at the deck bank's slope), never narrower than the roads
    under it with their shoulders (``CarvePath.half_m``: there the bank is
    a wall, 19s (4) (a))."""
    span = float(getattr(p, "span_m", 0.0) or 0.0)
    if top is None or floor is None or span <= 0.0:
        return float(p.half_m)
    depth = max(0.0, 0.5 * (top.z_st(0.0, 0.5) + top.z_st(1.0, 0.5)) - floor)
    return max(float(p.half_m), span - depth / deck_bank_slope(law))


def _profiles(decks, tops, law) -> tuple[list, dict]:
    """Per path of every deck's cut: ``(path, frame, s, floor z)``, and the
    per-deck report."""
    floors, srep = _deck_floors(decks, tops, law)
    out, rep = [], {}
    for d in decks:
        dc = getattr(d, "carve", None)
        if dc is None:
            continue
        drep = rep.setdefault(d.object_id, {"evidence": list(dc.evidence),
                                            "direction": dc.direction,
                                            "floor": (round(floors[d.object_id], 3)
                                                      if d.object_id in floors else None),
                                            "paths": []})
        for p in dc.paths:
            st = [(a, b, floors[oid]) for a, b, oid in p.stretches if oid in floors]
            if len(p.terrain) < 2 or not st:
                continue
            frame = PathFrame(p.coords)
            s, r = _path_stations(p)
            z = floor_profile(s, r, st, p.cap * _CAP_SHARE, p.rate)
            half = _floor_half(p, tops.get(d.object_id), floors.get(d.object_id), law)
            ra, rb = ramp_lengths(s, z, r, st)
            g = np.abs(np.diff(z)) / np.maximum(np.diff(s), 1e-9)
            stretches = []
            for a, _b, oid in p.stretches:
                q = srep.get((id(p), a))
                if q is not None and oid in floors:
                    stretches.append({**q, "floor": round(floors[oid], 3),
                                      "clearance": round(q["underside"] - floors[oid], 3)})
            drep["paths"].append({"way": p.way, "kind": p.kind, "cap": p.cap,
                                  "half_m": round(half, 2), "need_m": p.clearance_m,
                                  "stretches": stretches,
                                  "ramp_m": [None if math.isinf(ra) else round(ra, 1),
                                             None if math.isinf(rb) else round(rb, 1)],
                                  "max_grade": round(float(g.max()) if len(g) else 0.0, 4)})
            out.append((p, frame, s, z, half))
    return out, rep, floors


def _kerb(pm, air, values) -> "tuple[_t.Any, np.ndarray] | None":
    """``(KD tree, z)`` of the airside vertices with a stage-2 level."""
    from scipy.spatial import cKDTree
    pts, zs = [], []
    for v in air:
        z = values.get(v)
        if z is not None:
            pts.append(pm.vertices[v].xy)
            zs.append(float(z))
    if not pts:
        return None
    return cKDTree(np.asarray(pts, dtype=np.float64)), np.asarray(zs, dtype=np.float64)


def _tunnel_regions(pm, gen: _t.AbstractSet[str]):
    """``(generated, pack)``: the corridors of the tunnels the structure
    pass cut under a GENERATED deck (the deck's cut takes them over: one
    cut, the deck's) and under a pack deck (its floor stays the object's),
    each a prepared region or ``None``."""
    from shapely.geometry import LineString, Polygon
    from shapely.ops import unary_union
    from shapely.prepared import prep
    parts: dict[bool, list] = {True: [], False: []}
    for tn in getattr(pm, "structures", ()) or ():
        oid = str(getattr(tn, "deck_bridge", "") or "")
        if not oid or len(getattr(tn, "axis", ()) or ()) < 2:
            continue
        reg = LineString(tn.axis).buffer(float(tn.half_width_m) + _SNAP_M, cap_style="flat")
        if len(tn.wall_path) >= 3:
            reg = reg.union(Polygon(tn.wall_path).buffer(0.0).buffer(_SNAP_M))
        parts[oid in gen].append(reg)
    return tuple(prep(unary_union(parts[k])) if parts[k] else None for k in (True, False))


def carve_levels(pm, decks, tops: _t.Mapping[str, _t.Any], air: _t.AbstractSet[int],
                 values: _t.Mapping[int, float], fixed: _t.Mapping[int, float], law
                 ) -> tuple[dict[int, float], dict]:
    """``({vertex: level}, report)``: the cut's stage-2 constants (module
    doc).  ``tops``: each generated deck's top (``geom/coons_patch``);
    ``air``: the airside vertices; ``values``: their stage-2 levels (and
    the join's); ``fixed``: the vertices already fixed (never re-levelled)."""
    from shapely.geometry import Point
    from shapely.ops import unary_union
    from shapely.prepared import prep

    from ..model.deck_bank import bank_past_m
    from ..planar.deck_bridge import deck_polygon
    profs, rep, floors = _profiles(decks, tops, law)
    if not profs:
        return {}, rep
    bank = deck_bank_slope(law)
    from shapely.geometry import Polygon
    own = prep(unary_union([unary_union([deck_polygon(d)] + [
        Polygon(q).buffer(0.0) for q in d.approach if len(q) >= 3]).buffer(
            bank_past_m(law), join_style="mitre")
        for d in decks if getattr(d, "carve", None) is not None]))
    # a vertex farther off every path than its floor and the deepest bank
    # can reach is never the cut's
    reach = max(h for _p, _f, _s, _z, h in profs) + 40.0
    vids = [v for v in pm.vertices if v not in air and v not in fixed]
    xs = np.array([pm.vertices[v].xy[0] for v in vids], dtype=np.float64)
    ys = np.array([pm.vertices[v].xy[1] for v in vids], dtype=np.float64)
    # THE FLOOR FIRST: a vertex on a road's floor takes that road's floor
    # (the lowest of the floors it stands on), never another road's bank
    # -- each road keeps its own ramp; off every floor, the deepest bank
    on_floor = np.full(len(vids), np.inf)
    t = np.full(len(vids), np.inf)
    for _p, frame, s, z, h in profs:
        x0, y0 = np.min(frame.a, axis=0) - reach
        x1, y1 = np.max(frame.a + frame.d, axis=0) + reach
        m = (xs >= x0) & (xs <= x1) & (ys >= y0) & (ys <= y1)
        if not m.any():
            continue
        sv, nv = frame.project(xs[m], ys[m])
        fz = np.interp(sv, s, z)
        half = h + _SNAP_M
        on_floor[m] = np.where(nv <= half, np.minimum(on_floor[m], fz), on_floor[m])
        t[m] = np.minimum(t[m], lateral(fz, nv, half, bank))
    floor_v = np.isfinite(on_floor)
    t = np.where(floor_v, on_floor, t)
    gen_tn, pack_tn = _tunnel_regions(pm, {d.object_id for d in decks
                                           if getattr(d, "carve", None) is not None})
    kerb = _kerb(pm, air, {**values, **fixed})
    rings = [(prep(deck_polygon(d)), tops[d.object_id], floors[d.object_id]) for d in decks
             if d.object_id in floors and tops.get(d.object_id) is not None]
    out: dict[int, float] = {}
    n_fill = 0
    for i in np.nonzero(np.isfinite(t))[0]:
        v = vids[int(i)]
        vx = pm.vertices[v]
        pt = Point(vx.xy)
        g = float(vx.dem_z) if vx.dem_z is not None else math.inf
        cut = min(g, float(t[i]))
        inside = own.contains(pt)
        if not inside and pack_tn is not None and pack_tn.contains(pt):
            continue            # a pack deck's own cut keeps its floor (19s (4))
        mine = inside or (gen_tn is not None and gen_tn.contains(pt)) or any(
            str(pm.faces[f].ref).startswith(CARVE_REF + ":") for f in vx.incident_faces)
        if not (mine or cut < g - _UNDER_M):
            continue
        ring_of = next((r for r in rings if r[0].contains(pt)), None)
        if ring_of is not None:
            # UNDER THE DECK THE FLOOR RULE IS ABSOLUTE (owner 2026-11-20T00:30Z):
            # on the floor its deck's floor; off it the abutment's embankment
            # from the nearer end line down to that floor, never over it
            _r, top, fl = ring_of
            sp, tp = top.st(*vx.xy)
            run = min(sp, 1.0 - sp) * _hyp(top.u)
            ab = top.z_st(0.0 if sp < 0.5 else 1.0, min(1.0, max(0.0, tp))) - bank * run
            cut = min(cut, fl) if floor_v[i] else max(fl, ab)
            out[v] = round(cut, 4)
            continue
        if kerb is not None and not floor_v[i]:
            # the bank never undercuts the airside: over the deck's opened
            # pavement it rises to it; beyond, never over the ground.  A
            # road's floor is never raised: where the road needs it, the
            # bank is a wall
            tree, kz = kerb
            d, j = tree.query(vx.xy, k=min(_KERB_K, len(kz)))
            lo = float(np.max(np.atleast_1d(kz[j]) - bank * np.atleast_1d(d)))
            if lo > cut:
                n_fill += 1
                cut = lo if inside else min(g, lo)
        out[v] = round(cut, 4)
    for r in rep.values():
        r["bank_slope"] = round(bank, 3)
    rep["_vertices"] = {"levelled": len(out), "abutment_raised": n_fill}
    return out, rep
