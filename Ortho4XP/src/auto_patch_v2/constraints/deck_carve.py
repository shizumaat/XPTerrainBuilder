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
  the floor, and no pavement edge undercut;
* THE ENDS LAND (owner RULINGS 2026-11-19s (8) (d): "The terrain on either
  end of each cut should be graded up to match the taxiway height"): past
  each end line, across the deck's whole width (its shoulders over the
  ground as well as its pavement), the ground stands at the end's level
  for ``[deck_gen] end_landing_m``, then falls at the bank's slope -- an
  embankment over the survey where the ground lies lower, so no deck end
  floats (KPHX 1.0.566: the ground 0.3 m past a shoulder 1 m under it);
  so does the ground past each end of a generated ROAD deck spanning the
  cut (``geom/road_span``), at the taxiway deck's end level there.

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
from ..model.deck_carve import CARVE_REF, floor_band

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
    # the floor is level under the whole deck: its lowest underside over the
    # ring (a road crossing nearer a lower end line needs it there)
    under = min(min(unders), top.low() - slab)
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


def _floor_band(p, top, floor, law) -> tuple[float, float]:
    """``model/deck_carve.floor_band`` with the depth from the end lines'
    top (the Coons patch at each end's middle) to the floor."""
    if top is None or floor is None:
        return floor_band(p, None, law)
    return floor_band(p, 0.5 * (top.z_st(0.0, 0.5) + top.z_st(1.0, 0.5)) - floor, law)


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
            band = _floor_band(p, tops.get(d.object_id), floors.get(d.object_id), law)
            ra, rb = ramp_lengths(s, z, r, st)
            g = np.abs(np.diff(z)) / np.maximum(np.diff(s), 1e-9)
            stretches = []
            for a, _b, oid in p.stretches:
                q = srep.get((id(p), a))
                if q is not None and oid in floors:
                    stretches.append({**q, "floor": round(floors[oid], 3),
                                      "clearance": round(q["underside"] - floors[oid], 3)})
            drep["paths"].append({"way": p.way, "kind": p.kind, "cap": p.cap,
                                  "floor_band_m": [round(band[0], 2), round(band[1], 2)],
                                  "need_m": p.clearance_m,
                                  "stretches": stretches,
                                  "ramp_m": [None if math.isinf(ra) else round(ra, 1),
                                             None if math.isinf(rb) else round(rb, 1)],
                                  "max_grade": round(float(g.max()) if len(g) else 0.0, 4)})
            out.append((p, frame, s, z, band))
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


def _road_ends(decks, tops, roads, law) -> list[tuple]:
    """``(end, outward, half width, level)`` of every generated road deck
    that spans a deck's cut (``geom/road_span``): its ends land at the
    taxiway deck's end level there (module doc); riders are the deck's."""
    from shapely.geometry import LineString

    from ..geom.road_span import DeckSpan, span_to_cut
    riding = {str(r) for d in decks for r in getattr(d, "riders", ()) or ()}
    spans = [DeckSpan(d.object_id, tuple(d.ring), [tuple(p.coords) for p in d.carve.paths],
                      (tops[d.object_id].o, tops[d.object_id].u, tops[d.object_id].w))
             for d in decks if getattr(d, "carve", None) is not None
             and tops.get(d.object_id) is not None]
    margin = float(law.tables.structures.deck_gen.edge_margin_m)
    out = []
    for b in roads:
        axis = LineString(b.get("axis_xy") or ())
        if str(b.get("id")) in riding or axis.length <= 1.0:
            continue
        got = span_to_cut(axis, spans)
        if got is None:
            continue
        ext, oid = got
        top = tops[oid]
        c = list(ext.coords)
        for p, q in ((c[0], c[1]), (c[-1], c[-2])):
            n = math.hypot(p[0] - q[0], p[1] - q[1]) or 1.0
            sp, tp = top.st(*p)
            level = top.z_st(0.0 if sp < 0.5 else 1.0, min(1.0, max(0.0, tp)))
            out.append((p, ((p[0] - q[0]) / n, (p[1] - q[1]) / n),
                        float(b.get("half_m") or 0.0) + margin, level))
    return out


def _road_landing(ends, xy, bank: float, landing: float) -> float:
    """The level the road decks' end landings ask of ``xy``: past an end,
    the end's level for ``landing`` and within the deck's half width, then
    falling at ``bank`` per metre past either; ``-inf`` off every end."""
    best = -math.inf
    for p, d, half, level in ends:
        dx, dy = xy[0] - p[0], xy[1] - p[1]
        past = dx * d[0] + dy * d[1]
        if past < 0.0:
            continue
        side = abs(dx * d[1] - dy * d[0])
        best = max(best, level - bank * (max(0.0, past - landing) + max(0.0, side - half)))
    return best


def _landing(rings, xy, bank: float, landing: float) -> float:
    """The highest level the END LANDINGS (module doc) ask of ``xy``: per
    deck, past an end line, the end's level less ``bank`` per metre past
    ``landing`` and per metre beside the deck's width (its corners fall
    away as a cone); ``-inf`` between the end lines of any deck within a
    deck's width of it (its cut: KRDU, one deck's landing stood in its
    neighbour's trench, 2.1 m of its 4.2 m clearance)."""
    st = [top.st(*xy) for _r, top, _fl in rings]
    if any(0.0 <= sp <= 1.0 and -1.0 <= tp <= 2.0 for sp, tp in st):
        return -math.inf
    best = -math.inf
    for (_r, top, _fl), (sp, tp) in zip(rings, st, strict=True):
        past = (-sp if sp < 0.0 else sp - 1.0) * _hyp(top.u)
        side = max(-tp, tp - 1.0, 0.0) * _hyp(top.w)
        z = top.z_st(0.0 if sp < 0.0 else 1.0, min(1.0, max(0.0, tp)))
        best = max(best, z - bank * (max(0.0, past - landing) + side))
    return best


def carve_levels(pm, decks, tops: _t.Mapping[str, _t.Any], air: _t.AbstractSet[int],
                 values: _t.Mapping[int, float], fixed: _t.Mapping[int, float], law,
                 roads: _t.Sequence[_t.Mapping] = ()) -> tuple[dict[int, float], dict]:
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
    reach = max(max(-b[0], b[1]) for _p, _f, _s, _z, b in profs) + 40.0
    vids = [v for v in pm.vertices if v not in air and v not in fixed]
    xs = np.array([pm.vertices[v].xy[0] for v in vids], dtype=np.float64)
    ys = np.array([pm.vertices[v].xy[1] for v in vids], dtype=np.float64)
    # THE FLOOR FIRST: a vertex on a road's floor takes that road's floor
    # (the lowest of the floors it stands on), never another road's bank
    # -- each road keeps its own ramp; off every floor, the deepest bank
    on_floor = np.full(len(vids), np.inf)
    # the surveyed ground along the path at a floor vertex: the cut's ramp
    # owns its floor to the meet point, whatever a corridor it took over
    # lowered the vertex's own ground to (KRDU 1.0.565 ``-239``: a tunnel
    # ramp's floor held 15 m of the ramp flat, then 14.6 %)
    on_ground = np.full(len(vids), -np.inf)
    t = np.full(len(vids), np.inf)
    for p_, frame, s, z, (lo, hi) in profs:
        # every point of the path, both ends (a path may run either way:
        # KPHX 1.0.565 ``-4247`` ran west, and the bounds of its segment
        # starts / ends dropped its two ends -- the ramp's vertices there
        # were never levelled, 10.7 %)
        ends = np.vstack([frame.a, frame.a + frame.d])
        x0, y0 = np.min(ends, axis=0) - reach
        x1, y1 = np.max(ends, axis=0) + reach
        m = (xs >= x0) & (xs <= x1) & (ys >= y0) & (ys <= y1)
        if not m.any():
            continue
        sv, nv = frame.project_signed(xs[m], ys[m])
        fz = np.interp(sv, s, z)
        lo_, hi_ = lo - _SNAP_M, hi + _SNAP_M
        on = (nv >= lo_) & (nv <= hi_)
        deeper = on & (fz < on_floor[m])
        on_ground[m] = np.where(deeper, np.interp(sv, s, _path_stations(p_)[1]), on_ground[m])
        on_floor[m] = np.where(on, np.minimum(on_floor[m], fz), on_floor[m])
        t[m] = np.minimum(t[m], lateral(fz, nv, lo_, hi_, bank))
    floor_v = np.isfinite(on_floor)
    t = np.where(floor_v, on_floor, t)
    gen_tn, pack_tn = _tunnel_regions(pm, {d.object_id for d in decks
                                           if getattr(d, "carve", None) is not None})
    kerb = _kerb(pm, air, {**values, **fixed})
    rings = [(prep(deck_polygon(d)), tops[d.object_id], floors[d.object_id]) for d in decks
             if d.object_id in floors and tops.get(d.object_id) is not None]
    out: dict[int, float] = {}
    n_fill = n_land = 0
    landing = float(law.tables.structures.deck_gen.end_landing_m)
    road_ends = _road_ends(decks, tops, roads, law) if roads else []
    for i in np.nonzero(np.isfinite(t))[0]:
        v = vids[int(i)]
        vx = pm.vertices[v]
        pt = Point(vx.xy)
        g = float(vx.dem_z) if vx.dem_z is not None else math.inf
        if floor_v[i]:
            g = max(g, float(on_ground[i]))
        cut = min(g, float(t[i]))
        inside = own.contains(pt)
        if not inside and pack_tn is not None and pack_tn.contains(pt):
            continue            # a pack deck's own cut keeps its floor (19s (4))
        refs = [str(pm.faces[f].ref) for f in vx.incident_faces]
        mine = inside or (gen_tn is not None and gen_tn.contains(pt)) or any(
            r.startswith(CARVE_REF + ":") for r in refs)
        # the trench's floor never lands; its banks past an end line do (they
        # ran out to the daylight line beyond it: KPHX o4gen_566de1cd, 1.9 m
        # under its end 0.6 m past it)
        trench = any(r.startswith(CARVE_REF + ":") and r.split(":")[2].split("#")[0] == "floor"
                     for r in refs)
        land = -math.inf if floor_v[i] or trench else max(
            _landing(rings, vx.xy, bank, landing),
            _road_landing(road_ends, vx.xy, bank, landing) if road_ends else -math.inf)
        if not (mine or cut < g - _UNDER_M or land > cut + _UNDER_M):
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
        if land > cut:
            # the end's landing: graded up over the survey (module doc)
            n_land += 1
            cut = land
        out[v] = round(cut, 4)
    for r in rep.values():
        r["bank_slope"] = round(bank, 3)
    rep["_vertices"] = {"levelled": len(out), "abutment_raised": n_fill, "end_landing": n_land}
    return out, rep
