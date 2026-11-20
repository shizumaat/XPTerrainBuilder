"""THE GENERATED STRUCTURES, PUBLISHED FOR THE OBJECT STAGE (spec
``docs/specs/2123.md`` A2 / B2; RULINGS 2026-11-16y).

The planar map carries the generated taxiway decks
(``planar/deck_generated``) and the generated road bridges
(``planar/road_bridge_gen``); the object stage, which writes them into the
airport's pack (``airport/generated_pack``), reads them off the graded
surface's provenance as ``generated`` -- in lon/lat, with each deck's
ZERO read off the SOLVED surface at its end lines (the stations the design
solve held flush, ``constraints/deck_lines``), so the object's top meets
the taxiway it carries.

Build-time impact: a few dozen coordinate conversions per airport.
"""
from __future__ import annotations

import statistics

__all__ = ["generated_records", "mapped_under"]


def _ll(to_ll, pts) -> list[list[float]]:
    """``pts`` (frame xy) as ``[lon, lat]`` (``to_ll`` answers lat, lon)."""
    return [[round(float(lo), 9), round(float(la), 9)]
            for la, lo in (to_ll(float(x), float(y)) for x, y in pts)]


def _zero(planar, law, db, z) -> "float | None":
    """The deck's zero: the solved surface at its end-line stations less
    the top there (``rebake_inputs._deck_plate``'s reading)."""
    from ..constraints.deck_lines import end_lines
    zs = []
    for e in end_lines(planar, law).get(db.object_id, ()):
        w = sum(wt for _v, wt in e.terms)
        if w <= 0.0:
            continue
        at = sum(float(z[v]) * wt for v, wt in e.terms) / w
        zs.append(at - (float(db.bottom_y) + float(e.depth)))
    return statistics.median(zs) if zs else None


def _roads(db, law, to_ll, airport=None) -> list[dict]:
    """The roads under a deck (#2132: its piers stand at their floors'
    edges): ``{"line": [[lon, lat], ...], "half_m": carriageway half}`` --
    every road it covers and every other mapped road or railway passing
    under its ring (:func:`mapped_under`)."""
    from ..planar.structure_approach import carriageway_width_m
    out = [{"line": _ll(to_ll, coords),
            "half_m": round(carriageway_width_m(dict(tags), law) / 2.0, 3)}
           for _id, tags, coords in getattr(db, "covered", ()) or () if len(coords) >= 2]
    if airport is None or len(getattr(db, "ring", ()) or ()) < 3:
        return out
    return out + mapped_under(db.ring, law, to_ll, airport)


def mapped_under(ring_xy, law, to_ll, airport) -> list[dict]:
    """Every mapped road or railway (no bridge, no aeroway) whose carriageway
    reaches under the ring ``ring_xy`` (frame), WHOLE (a covered road's
    record is its clip: KPHX ``-23745``, a column 0.3 m off its mapped
    way), as ``_roads`` records -- owner 2026-11-20T14:50Z: "pier placement
    takes into account roads and rails passing under the bridge and are
    only placed in between them never in a road or rail" (lane lcross20)."""
    from shapely.geometry import LineString, Polygon

    from ..planar.structure_approach import carriageway_width_m
    ring = Polygon(ring_xy).buffer(0.0)
    sh = float(law.tables.structures.deck_gen.shoulder_m)
    out = []
    for w in getattr(airport, "osm_ways", ()) or ():
        tags = dict(w.tags or {})
        if len(w.points) < 2 or tags.get("aeroway") or tags.get("bridge") not in (None, "no") \
                or not (tags.get("highway") or tags.get("railway")):
            continue
        half = carriageway_width_m(tags, law) / 2.0
        if LineString(w.points).intersection(ring.buffer(half + sh)).length > 1.0:
            out.append({"line": _ll(to_ll, w.points), "half_m": round(half, 3)})
    return out


def _ground_min(planar, db, z, reach: float = 5.0) -> "float | None":
    """The deepest solved ground under a deck: the lowest vertex within
    ``reach`` of its ring (owner 2026-11-20T14:50Z: "make sure the support
    piers all reach the ground under them, it's fine to simply note the
    deepest spot and make them all that length"; lane lcross20)."""
    from shapely.geometry import Point, Polygon
    from shapely.prepared import prep
    if len(getattr(db, "ring", ()) or ()) < 3 or z is None:
        return None
    near = prep(Polygon(db.ring).buffer(reach))
    zs = [float(z[v]) for v, vx in planar.vertices.items() if near.contains(Point(vx.xy))]
    return min(zs) if zs else None


def _surface(top: dict, to_ll) -> dict:
    """A deck's top (``constraints/deck_floor_follow``'s record, frame
    metres) in lon/lat: the corner ``o``, the corners ``o + u`` (end B) and
    ``o + w`` (along end A), and the four profiles (absolute metres)."""
    o, u, w = top["o"], top["u"], top["w"]
    corners = _ll(to_ll, [o, (o[0] + u[0], o[1] + u[1]), (o[0] + w[0], o[1] + w[1])])
    return {"o": corners[0], "ou": corners[1], "ow": corners[2],
            **{k: [[round(float(q), 6), round(float(zz), 4)] for q, zz in top[k]]
               for k in ("a", "b", "s0", "s1")}}


def _axis(db, to_ll) -> list:
    """The deck's axis, end A to end B along its carried route (RULINGS
    2026-11-19s (8) (b)), as two ``[lon, lat]`` -- read off its ring
    (``deck_floor_follow._deck_frame``) where no surface was published;
    ``[]`` for a ring of no frame."""
    from ..constraints.deck_floor_follow import _deck_frame
    fr = _deck_frame(db)
    if fr is None:
        return []
    o, u, _w = fr
    return _ll(to_ll, [o, (o[0] + u[0], o[1] + u[1])])


def _surface_at(planar, z, airport=None):
    """``z_at(xy)``: the solved surface at ``xy`` as the mesh takes it --
    linear over the map face holding it, triangulated on its own ring
    (constrained Delaunay) -- off every face the survey (the base mesh
    there), else ``None``."""
    if z is None or not getattr(planar, "faces", None):
        return None

    def z_at(p) -> "float | None":
        import numpy as np
        import shapely
        from shapely.geometry import Point, Polygon
        pt = Point(p)
        vs = planar.vertices
        for f in planar.faces.values():
            ring = [vs[v].xy for v in planar.ring_vertices(f.ring)]
            if len(ring) < 3:
                continue
            xs, ys = [q[0] for q in ring], [q[1] for q in ring]
            if not (min(xs) - 0.01 <= p[0] <= max(xs) + 0.01
                    and min(ys) - 0.01 <= p[1] <= max(ys) + 0.01):
                continue
            poly = Polygon(ring, [[vs[v].xy for v in planar.ring_vertices(h)] for h in f.holes])
            if not poly.buffer(0.01).contains(pt):
                continue
            at = {tuple(vs[v].xy): v for v in planar.ring_vertices(f.ring)}
            for h in f.holes:
                at.update({tuple(vs[v].xy): v for v in planar.ring_vertices(h)})
            for t in shapely.get_parts(shapely.constrained_delaunay_triangles(poly)):
                if not t.buffer(0.01).contains(pt):
                    continue
                c = list(t.exterior.coords)[:3]
                ids = [at.get(tuple(q)) for q in c]
                if None in ids:
                    continue
                (x1, y1), (x2, y2), (x3, y3) = c
                det = (y2 - y3) * (x1 - x3) + (x3 - x2) * (y1 - y3)
                if abs(det) < 1e-12:
                    continue
                l1 = ((y2 - y3) * (p[0] - x3) + (x3 - x2) * (p[1] - y3)) / det
                l2 = ((y3 - y1) * (p[0] - x3) + (x1 - x3) * (p[1] - y3)) / det
                zz = np.asarray(z, float)
                return float(l1 * zz[ids[0]] + l2 * zz[ids[1]] + (1 - l1 - l2) * zz[ids[2]])
        if getattr(airport, "dem", None) is not None:
            from ..airport.dem import dem_z_at
            got = dem_z_at(airport, p)
            return float(got) if got == got else None
        return None
    return z_at


def generated_records(planar, law, airport, z, offers=(), tops=None) -> dict[str, list]:
    """``{"decks": [...], "road_bridges": [...]}`` -- empty lists where
    the airport generated none (module doc) -- and, for an airport drawn
    by Global Airports alone, ``"offer"``: one note per structure refused
    only for that (#2169), which ``gateway_stage`` offers to install.
    ``tops``: each deck's top as stage 1 solved the pavement under it
    (RULINGS 2026-11-19s (1); ``reach_seed["generated_tops"]``) -- the
    object's top IS that surface, its zero the surface's lowest level."""
    from ..planar.deck_generated import is_generated
    _to_xy, to_ll = airport.frame.transformers()
    g = law.tables.structures.deck_gen
    decks = []
    for db in getattr(planar, "decks", ()) or ():
        if not is_generated(db):
            continue
        top = (tops or {}).get(db.object_id)
        surface = _surface(top, to_ll) if top is not None else None
        zero = min(zz for k in ("a", "b", "s0", "s1") for _q, zz in surface[k]) \
            if surface is not None else _zero(planar, law, db, z)
        if zero is None:
            continue
        decks.append({
            **({"surface": surface} if surface is not None else {}),
            "axis": [surface["o"], surface["ou"]] if surface is not None else _axis(db, to_ll),
            "object_id": db.object_id, "resource": db.resource,
            "ring": _ll(to_ll, db.ring), "seats_a": _ll(to_ll, db.seats_a),
            "seats_b": _ll(to_ll, db.seats_b),
            "top_a": 0.0 if surface else round(float(db.top_a), 4),
            "top_b": 0.0 if surface else round(float(db.top_b), 4),
            "zero_m": round(float(zero), 4), "family": db.family,
            "route": _ll(to_ll, db.route), "road": _ll(to_ll, db.road),
            "approach": [_ll(to_ll, q) for q in getattr(db, "approach", ()) or ()],
            "hides": [{"object_id": h[0], "resource": h[1], "lon": h[2][0], "lat": h[2][1]}
                      for h in getattr(db, "hides", ()) or ()],
            "thickness_m": float(g.thickness_m), "top_lift_m": float(g.top_lift_m),
            # #2132 the piers: the floor under the top and each covered road
            "floor_m": round(float(db.floor_min_m), 4),
            **({"ground_m": round(gm, 4)} if (gm := _ground_min(planar, db, z)) is not None
               else {}),
            "roads": _roads(db, law, to_ll, airport)})
    # #2183 item 5: a road bridge is a narrow flat deck, or rides a taxiway
    # deck (#2181 item 1) -- never an X-Plane road chain
    from .road_deck import road_deck_records
    riding = {str(r) for db in getattr(planar, "decks", ()) or () if is_generated(db)
              for r in getattr(db, "riders", ()) or ()}
    road_decks, bridges = road_deck_records(
        getattr(airport, "road_bridges", ()) or (), riding, law, airport,
        [db for db in getattr(planar, "decks", ()) or () if is_generated(db)],
        _surface_at(planar, z, airport), tops)
    decks += road_decks
    out: dict[str, list] = {"decks": decks, "road_bridges": bridges}
    if offers:
        out["offer"] = list(offers)
    return out
