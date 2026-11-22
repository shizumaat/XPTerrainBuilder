"""LIBRARY of ``tools/deck_probe.py --carve`` (owner RULINGS 2026-11-19s
(2)-(4); owner 2026-11-19T23:07Z / 23:09Z: the cut is the deck's and
grades smoothly back to the terrain): THE CUT UNDER EVERY GENERATED DECK,
read off a ``--solved-out`` pickle, per deck and per path of its cut
(``DeckBridge.carve``, ``planar/deck_carve``):

* EVIDENCE and DIRECTION: what put the deck there and which way its ramps
  run (the record's);
* CLEARANCE: at every metre and node of every road under the deck
  inside the ring (more than :data:`EDGE_M` inside its edge; the edge band
  is reported apart, ``edge_short_m``: a road leaving the deck under
  pavement meets a wall there), the deck's underside
  (its top -- the Coons patch of the solved airside on its ring,
  ``constraints/deck_floor_follow._patch`` -- less ``[deck_gen]
  thickness_m``) over the solved surface; bar ``>= `` the road's clearance;
* FLOOR: the solved floor under the deck against the rule
  ``min(lidar road floor, underside - clearance)`` (the lidar road its
  lowest survey within ``[deck_gen] level_probe_m`` of the stretch; the
  deck's one floor is the deepest any of its roads asks);
* RAMPS: from each outermost stretch outward, the solved surface along the
  path until it stands within :data:`MEET_M` of the surveyed ground -- the
  ramp's length (``None``: it never met it, the shortfall) and its steepest
  grade over :data:`GRADE_WINDOW_M`; bar ``<= `` the path's cap;
* EMBANKMENT: across the deck along its route through the path's
  crossing, the steepest solved slope over :data:`GRADE_WINDOW_M` between
  the end lines and the floor over :data:`BANK_WINDOW_M` (the abutment's
  bank, 1V:1.5H by law);
* PIERS (:func:`pier_bars`, lane lcross20): no column floating over the
  solved ground, none on a mapped road's or railway's carriageway;
* END GAP (lane lcross20, RULINGS 2026-11-19s (8) (d)): along each end
  line, across the deck's whole width every :data:`STEP_M`, the solved
  surface :data:`END_PAST_M` past it against the top at the end -- the
  step a deck end stands off the ground it lands on; bar ``<=``
  :data:`END_GAP_M`.

The surface is read over each map face within :data:`NEAR_M` of the path,
triangulated on its own ring (``tools/deck_bank_perimeter._interp``: the
way the mesh takes the patch's faces).  Pure: reads
the pickle's map and ``z``; writes nothing.
"""
from __future__ import annotations

import math

__all__ = ["STEP_M", "MEET_M", "END_PAST_M", "END_GAP_M", "EDGE_STEP_M", "GRADE_WINDOW_M",
           "BANK_WINDOW_M", "EDGE_M",
           "NEAR_M",
           "carve_bars", "end_gaps", "pier_bars", "road_deck_bars"]

#: a path is read this often (m)
STEP_M = 1.0
#: the ramp has met the terrain within this (m): the floor's vertical
#: curves ride a smoothed survey, a lidar road's noise is a few decimetres
MEET_M = 0.30
#: the patch's edge meets the base mesh within this (m)
EDGE_STEP_M = 0.25
#: grades are read over this run (m): a road's grade over a design
#: station (the mesh between the floor's edge vertices, noded every 4 m,
#: reads a per cent or so more over a 3 m run where the curves bend)
GRADE_WINDOW_M = 10.0
#: a road sample this near the ring's edge is the edge's (m): the snap
#: lattice (0.35 m) puts the pavement's own vertex there
EDGE_M = 0.5
#: the abutment's bank is read over this run (m)
BANK_WINDOW_M = 2.0
#: the surface is triangulated from the vertices this near the path (m)
NEAR_M = 60.0
#: the ground past a deck end is read this far past its end line (m)
END_PAST_M = 0.3
#: a deck end stands within this of the ground it lands on (m)
END_GAP_M = 0.05
#: a way inside a road deck within this of its axis (cosine, 30 deg) is the
#: deck's own road run on to the cut's ends, never a road under it
_ALONG_COS = 0.866


def end_gaps(pm, z, top) -> "list[dict] | None":
    """Per end (``s = 0`` end A, ``s = 1`` end B) of a deck's ``top`` the
    worst step between the top along it and the solved surface
    :data:`END_PAST_M` past it, across the deck's whole width (module doc):
    ``{"end", "gap_m", "at": [x, y], "t"}``; ``None`` with no top."""
    from deck_bank_perimeter import _interp
    from shapely.geometry import Polygon
    if top is None:
        return None
    (ox, oy), (ux, uy), (wx, wy) = top.o, top.u, top.w
    lu, lw = math.hypot(ux, uy), math.hypot(wx, wy)
    if lu < 1e-6 or lw < 1e-6:
        return None
    quad = Polygon([(ox, oy), (ox + ux, oy + uy), (ox + ux + wx, oy + uy + wy),
                    (ox + wx, oy + wy)])
    f = _interp(pm, z, quad.buffer(NEAR_M))
    out = []
    n = max(2, int(lw / STEP_M) + 1)
    for end, s in (("A", -END_PAST_M / lu), ("B", 1.0 + END_PAST_M / lu)):
        worst = None
        for k in range(n):
            t = k / (n - 1)
            x, y = ox + s * ux + t * wx, oy + s * uy + t * wy
            q = float(f([x], [y])[0])
            if q != q:
                continue
            gap = q - top.z_st(0.0 if end == "A" else 1.0, t)
            if worst is None or abs(gap) > abs(worst[0]):
                worst = (gap, (round(x, 2), round(y, 2)), round(t, 3))
        if worst is not None:
            out.append({"end": end, "gap_m": round(worst[0], 3), "at": list(worst[1]),
                        "t": worst[2]})
    return out


def _tin(pm, z, xs, ys):
    """``surf(x, y)``: the solved surface over the path's reach, each map
    face triangulated on its own ring (``deck_bank_perimeter._interp``,
    the way the mesh takes the patch); ``nan`` off every face."""
    from deck_bank_perimeter import _interp
    from shapely.geometry import LineString
    f = _interp(pm, z, LineString(list(zip(xs, ys, strict=True))).buffer(NEAR_M))
    return lambda x, y: float(f([x], [y])[0])


def _top(pm, z, db, law, rec=None):
    """The deck's top: its PUBLISHED surface ``rec`` (the solved pickle's
    ``generated_tops``, lane lbridge3), else read again off the final
    airside on its ring -- which misses a deck's shoulders over the ground
    (twice its taxiway, RULINGS 2026-11-19s (8) (a))."""
    if rec is not None:
        from auto_patch_v2.geom.coons_patch import CoonsPatch
        return CoonsPatch(tuple(rec["o"]), tuple(rec["u"]), tuple(rec["w"]),
                          *(tuple((float(q), float(zz)) for q, zz in rec[k])
                            for k in ("a", "b", "s0", "s1")))
    from auto_patch_v2.constraints.deck_floor_follow import _patch
    from auto_patch_v2.model.platform import stage_air_vertices
    air = stage_air_vertices(pm, law)
    patch, _n = _patch(db, None, pm, {v: float(z[v]) for v in air})
    return patch


def _grade(ss, zs, window: float = GRADE_WINDOW_M) -> float:
    best = 0.0
    j = 0
    for i in range(len(ss)):
        while j < len(ss) and ss[j] - ss[i] < window:
            j += 1
        if j < len(ss):
            best = max(best, abs(zs[j] - zs[i]) / max(ss[j] - ss[i], 1e-9))
    return best


def _ramp(frame, surf, terrain, start: float, sign: float) -> tuple:
    """``(length or None, steepest grade)`` from ``start`` outward."""
    import numpy as np
    ts = np.array([t[0] for t in terrain])
    tz = np.array([t[1] for t in terrain])
    ss, zs = [], []
    s = start
    while 0.0 <= s <= frame.length:
        (x, y), _u = frame.at(s)
        q = surf(x, y)
        if q != q:
            # off the patch: the base mesh at the DEM -- met there, with the
            # step the patch's edge stands off the ground
            if zs:
                step = abs(zs[-1] - float(np.interp(s, ts, tz)))
                return (round(abs(s - start), 1) if step <= EDGE_STEP_M else None,
                        round(_grade(ss, zs), 4) if len(ss) > 1 else 0.0)
            break
        ss.append(abs(s - start))
        zs.append(q)
        if abs(s - start) > 2.0 and q >= float(np.interp(s, ts, tz)) - MEET_M:
            return round(abs(s - start), 1), round(_grade(ss, zs), 4)
        s += sign * STEP_M
    return None, round(_grade(ss, zs), 4) if len(ss) > 1 else 0.0


def _bank(pm, surf, db, top, frame, s_mid: float) -> "float | None":
    """The steepest slope across the deck along its route through the
    path's point ``s_mid``, between the end lines (the abutments' banks)."""
    (x, y), (ux, uy) = frame.at(s_mid)
    if top is None:
        return None
    u = top.u
    lu = math.sqrt(u[0] * u[0] + u[1] * u[1])
    if lu < 1e-6:
        return None
    ex, ey = u[0] / lu, u[1] / lu
    ss, zs = [], []
    k = -lu
    while k <= lu:
        q = surf(x + ex * k, y + ey * k)
        if q == q:
            st, _t = top.st(x + ex * k, y + ey * k)
            if 0.0 <= st <= 1.0:
                ss.append(k)
                zs.append(q)
        k += 0.5
    return round(_grade(ss, zs, BANK_WINDOW_M), 3) if len(ss) > 2 else None


def carve_bars(pm, z, law, tops=None) -> list[dict]:
    """One row per path of every generated deck's cut (module doc);
    ``tops``: the published tops by deck id (:func:`_top`)."""
    from auto_patch_v2.geom.carve_profile import PathFrame, smoothed
    from auto_patch_v2.model.road_clearance import design_clearance_m
    from auto_patch_v2.planar.deck_bridge import deck_polygon
    from shapely.geometry import Point
    slab = float(law.tables.structures.deck_gen.thickness_m)
    probe = float(law.tables.structures.deck_gen.level_probe_m)
    decks = {d.object_id: d for d in getattr(pm, "decks", ()) or ()
             if getattr(d, "carve", None) is not None}
    tops = {oid: _top(pm, z, d, law, (tops or {}).get(oid)) for oid, d in decks.items()}
    gaps: dict = {}
    out = []
    for oid, d in sorted(decks.items()):
        dc = d.carve
        top = tops[oid]
        ring = deck_polygon(d)
        for p in dc.paths:
            frame = PathFrame(p.coords)
            xs = [c[0] for c in p.coords]
            ys = [c[1] for c in p.coords]
            surf = _tin(pm, z, xs, ys)
            r = smoothed([t[1] for t in p.terrain])
            terrain = [(t[0], float(q)) for t, q in zip(p.terrain, r, strict=True)]
            row = {"deck": oid, "evidence": list(dc.evidence), "direction": dc.direction,
                   "way": p.way, "kind": p.kind, "need_m": p.clearance_m, "cap": p.cap}
            own = [(a, b) for a, b, o in p.stretches if o == oid]
            clear, floors, unders, lidar, edge = [], [], [], [], []
            short = None
            # every road or rail under the deck, at every metre and node of
            # it inside the ring, against ITS clearance (the cut is one, the
            # roads lie on its floor)
            from shapely.geometry import LineString
            for _w, tags_items, coords in getattr(d, "covered", ()) or ():
                if len(coords) < 2 or top is None:
                    continue
                need = design_clearance_m(dict(tags_items), law)
                ln = LineString(coords).intersection(ring)
                for g in getattr(ln, "geoms", [ln]):
                    if g.is_empty or g.geom_type != "LineString":
                        continue
                    pts = list(g.coords) + [g.interpolate(k * STEP_M).coords[0]
                                            for k in range(int(g.length / STEP_M) + 1)]
                    for x, y in pts:
                        q = surf(x, y)
                        if q != q:
                            continue
                        under = top.z(x, y) - slab
                        if ring.exterior.distance(Point(x, y)) < EDGE_M:
                            # the ring's edge: where the road leaves the deck
                            # under pavement the cut meets it as a wall here
                            edge.append(under - q - need)
                            continue
                        clear.append(under - q)
                        floors.append(q)
                        unders.append(under - need)
                        if short is None or under - q - need < short[0]:
                            short = (under - q - need, need)
            if not clear and top is not None:       # no road mapped: the axis
                for a, b in own:
                    s = a
                    while s <= b:
                        (x, y), _u = frame.at(s)
                        if ring.contains(Point(x, y)):
                            q = surf(x, y)
                            if q == q:
                                under = top.z(x, y) - slab
                                clear.append(under - q)
                                floors.append(q)
                                unders.append(under - p.clearance_m)
                                if short is None or under - q - p.clearance_m < short[0]:
                                    short = (under - q - p.clearance_m, p.clearance_m)
                        s += STEP_M
            for a, b in own:
                lidar += [zz for ss, zz in terrain if a - probe <= ss <= b + probe]
            row["clearance_min_m"] = round(min(clear), 3) if clear else None
            row["edge_short_m"] = round(min(edge), 3) if edge else None
            row["clearance_short_m"] = round(short[0], 3) if short else None
            if short:
                row["need_m"] = short[1]
            row["floor_m"] = [round(min(floors), 3), round(max(floors), 3)] if floors else None
            row["floor_rule_m"] = round(min([min(unders)] + lidar), 3) if unders else None
            lo = min((a for a, _b, _o in p.stretches), default=None)
            hi = max((b for _a, b, _o in p.stretches), default=None)
            if lo is not None:
                row["ramp_before"] = _ramp(frame, surf, terrain, lo, -1.0)
                row["ramp_after"] = _ramp(frame, surf, terrain, hi, 1.0)
            if own:
                row["bank_slope_max"] = _bank(pm, surf, d, top, frame,
                                              0.5 * (own[0][0] + own[0][1]))
            g = [x for k in ("ramp_before", "ramp_after") if row.get(k) for x in [row[k][1]]]
            row["pass_clearance"] = row["clearance_short_m"] is not None and \
                row["clearance_short_m"] >= -0.05
            row["pass_grade"] = all(x <= p.cap + 0.005 for x in g)
            row["pass_meets"] = all(row.get(k) and row[k][0] is not None
                                    for k in ("ramp_before", "ramp_after"))
            if oid not in gaps:
                gaps[oid] = end_gaps(pm, z, top)
            row["end_gaps"] = gaps[oid]
            row["pass_ends"] = gaps[oid] is not None and all(
                abs(e["gap_m"]) <= END_GAP_M for e in gaps[oid])
            out.append(row)
    return out


def pier_bars(pm, z, law, airport, tops=None) -> list[dict]:
    """THE PIERS (owner 2026-11-20T14:50Z; lane lcross20): per generated
    deck, the columns the object stage draws (``airport/deck_objects.
    _structure`` on the deck's published record, ``pipeline/
    generated_publication``) -- each FLOATING where its bottom stands over
    the solved ground at any of its corners, and ON A ROAD where its plan
    meets a mapped road's or railway's carriageway (``model/road_clearance.
    carriageway_width_m``) under the deck.  ``{"deck", "columns",
    "floating": [[lon, lat, over m]...], "on_road": [[lon, lat, way]...]}``."""
    from auto_patch_v2.airport.deck_objects import _deck_frame as _obj_frame
    from auto_patch_v2.airport.deck_objects import _structure, ring_polygon
    from auto_patch_v2.model.road_clearance import carriageway_width_m
    from auto_patch_v2.pipeline.generated_publication import generated_records
    from deck_bank_perimeter import _interp
    from shapely.geometry import LineString, Polygon
    from shapely.ops import transform
    g = law.tables.structures.deck_gen
    to_xy = airport.frame.transformers()[0]
    recs = generated_records(pm, law, airport, z, (), tops).get("decks") or []
    ways = [(str(w.id), LineString(w.points), carriageway_width_m(dict(w.tags or {}), law) / 2.0)
            for w in getattr(airport, "osm_ways", ()) or ()
            if len(w.points) >= 2 and not (w.tags or {}).get("aeroway")
            and (w.tags or {}).get("bridge") in (None, "no")
            and ((w.tags or {}).get("highway") or (w.tags or {}).get("railway"))]
    out = []
    for rec in recs:
        frame = _obj_frame(rec, ())
        R = transform(lambda x, y, _z=None: frame.to_local(x, y), ring_polygon(rec["ring"]))
        ends = [[frame.to_local(lo, la) for lo, la in rec[k]] for k in ("seats_a", "seats_b")]
        cols = [p for p in _structure(R, rec, frame, ends, g) if p.name == "column"]
        ring = Polygon([to_xy(lo, la) for lo, la in rec["ring"]]).buffer(0.0)
        f = _interp(pm, z, ring.buffer(NEAR_M))
        floating, on_road = [], []
        for c in cols:
            pts = [to_xy(*frame.to_lonlat(x, y)) for x, y in c.poly.exterior.coords[:-1]]
            bottom = float(rec["zero_m"]) + float(c.floor_y)
            grounds = [float(f([x], [y])[0]) for x, y in pts]
            grounds = [q for q in grounds if q == q]
            lon, lat = frame.to_lonlat(c.poly.centroid.x, c.poly.centroid.y)
            if grounds and bottom > min(grounds) + 0.01:
                floating.append([round(lon, 7), round(lat, 7), round(bottom - min(grounds), 3)])
            plan = Polygon(pts)
            hit = [wid for wid, ln, half in ways if ln.distance(plan) < half - 1e-6]
            if hit:
                on_road.append([round(lon, 7), round(lat, 7), hit[0]])
        out.append({"deck": rec["object_id"], "columns": len(cols), "floating": floating,
                    "on_road": on_road})
    return out


def road_deck_bars(pm, z, law, airport, tops=None) -> list[dict]:
    """THE ROAD DECKS OVER A CUT (owner 2026-11-20T15:20Z; lane lcross20):
    per generated ROAD deck the object stage draws (``pipeline/road_deck``,
    its published record): the least CLEARANCE over every mapped road or
    railway under it (its top -- the published surface, else the plane
    between its ends -- less ``[deck_gen] thickness_m`` over the solved
    surface, every metre more than :data:`EDGE_M` inside the ring) against
    the way's class minimum (``model/road_clearance.design_clearance_m``);
    each END's step to the ground :data:`END_PAST_M` past it on its axis;
    and, spanning a taxiway deck's cut, its top against that deck's at the
    same stations (clamped onto it)."""
    from auto_patch_v2.airport.deck_objects import _deck_frame as _obj_frame
    from auto_patch_v2.airport.deck_objects import _top_fn
    from auto_patch_v2.model.road_clearance import design_clearance_m
    from auto_patch_v2.pipeline.generated_publication import generated_records
    from deck_bank_perimeter import _interp
    from shapely.geometry import LineString, Point, Polygon
    slab = float(law.tables.structures.deck_gen.thickness_m)
    lift = float(law.tables.structures.deck_gen.top_lift_m)
    to_xy = airport.frame.transformers()[0]
    recs = [r for r in generated_records(pm, law, airport, z, (), tops).get("decks") or []
            if r.get("family") == "road"]
    out = []
    for rec in recs:
        frame = _obj_frame(rec, ())
        top_y = _top_fn(rec, frame)
        zero = float(rec["zero_m"])

        def top(x, y, frame=frame, top_y=top_y, zero=zero):
            la_lo = airport.frame.transformers()[1](x, y)
            lx, lz = frame.to_local(la_lo[1], la_lo[0])
            return top_y(lx, lz) + zero - lift
        ring = Polygon([to_xy(lo, la) for lo, la in rec["ring"]]).buffer(0.0)
        f = _interp(pm, z, ring.buffer(NEAR_M))
        axis = [to_xy(lo, la) for lo, la in rec["route"]]
        ul = math.dist(axis[0], axis[-1]) or 1.0
        ux, uy = (axis[-1][0] - axis[0][0]) / ul, (axis[-1][1] - axis[0][1]) / ul
        short = None
        for w in getattr(airport, "osm_ways", ()) or ():
            tags = dict(w.tags or {})
            if len(w.points) < 2 or tags.get("aeroway") or tags.get("bridge") not in (None, "no") \
                    or not (tags.get("highway") or tags.get("railway")):
                continue
            x = LineString(w.points).intersection(ring)
            need = design_clearance_m(tags, law)
            for g in getattr(x, "geoms", [x]):
                if g.is_empty or g.geom_type != "LineString":
                    continue
                (gx0, gy0), (gx1, gy1) = g.coords[0], g.coords[-1]
                gl = math.hypot(gx1 - gx0, gy1 - gy0)
                if gl > 1e-6 and abs((gx1 - gx0) * ux + (gy1 - gy0) * uy) / gl > _ALONG_COS:
                    continue            # the deck's own road, run on to the cut's ends
                for k in range(int(g.length / STEP_M) + 1):
                    p = g.interpolate(k * STEP_M)
                    if ring.exterior.distance(p) < EDGE_M:
                        continue
                    q = float(f([p.x], [p.y])[0])
                    if q == q and (short is None or top(p.x, p.y) - slab - q - need < short[0]):
                        short = (round(top(p.x, p.y) - slab - q - need, 3), str(w.id), need)
        ends = []
        for a_, b_ in ((axis[0], axis[1]), (axis[-1], axis[-2])):
            n = math.dist(a_, b_) or 1.0
            px = a_[0] + (a_[0] - b_[0]) / n * END_PAST_M
            py = a_[1] + (a_[1] - b_[1]) / n * END_PAST_M
            q = float(f([px], [py])[0])
            ends.append(None if q != q else round(q - top(*a_), 3))
        match = None
        tp = (tops or {}).get(rec.get("spans_cut"))
        if tp is not None:
            patch = _top(pm, z, None, law, tp)
            ln = LineString(axis)
            for k in range(int(ln.length / STEP_M) + 1):
                p = ln.interpolate(k * STEP_M)
                sp, tq = patch.st(p.x, p.y)
                dz = top(p.x, p.y) - patch.z_st(min(1.0, max(0.0, sp)), min(1.0, max(0.0, tq)))
                match = dz if match is None or abs(dz) > abs(match) else match
        out.append({"deck": rec["object_id"], "road_bridge": rec.get("road_bridge"),
                    "spans_cut": rec.get("spans_cut"), "clearance_short": short,
                    "end_gaps": ends, "top_vs_taxiway_m": None if match is None
                    else round(match, 3)})
    return out
