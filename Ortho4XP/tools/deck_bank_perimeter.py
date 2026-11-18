"""LIBRARY of ``tools/deck_probe.py --bank-perimeter`` (owner sim read
2026-11-18T13:58Z, ESSA 1.0.558: "we're cutting a strange jagged edge
around the corner of the bridge ... graded smoothly to ground the entire
width, with the same embankment the whole way"; #2141): THE BANK AROUND
EVERY BANKED DECK'S PERIMETER, off a ``--solved-out`` pickle.

Per banked deck (``model/deck_bank.banked``), the solved surface is walked
along OFFSET LINES round the deck's ring (``OFFSETS_M`` outside its edge,
round-joined -- a corner swept, the way a bank round it runs), sampled every
``STEP_M``; ``z`` there is linear in a Delaunay triangulation of the map's
vertices near the deck (an approximation of the emitted triangulation, which
adds its own diagonals).  Along the walk:

* ``step_m``: the largest rise between two samples ``STEP_M`` apart;
* ``grade``: that over ``STEP_M`` -- the bank's own face reads its slope
  (1:1.5 = 0.67) where the walk crosses it; a jag reads steeper;
* ``jags``: samples steeper than ``JAG_GRADE`` (1V:1H) -- a notch or a
  stair no 1:1.5 bank makes;
* ``break``: the largest change of grade between consecutive steps (a kink);
* ``off``: samples on no face of the map -- the base mesh at the DEM shows
  there, beside the patch's cut.

Pure: reads the pickle's map and ``z``; writes nothing.
"""
from __future__ import annotations

__all__ = ["OFFSETS_M", "STEP_M", "JAG_GRADE", "bank_perimeter"]

#: the offset lines outside the ring the walk follows (m)
OFFSETS_M = (0.5, 1.0, 2.0, 3.0, 5.0)
#: the walk's sample spacing (m)
STEP_M = 0.5
#: a grade along the walk steeper than this is a jag (1V:1H)
JAG_GRADE = 1.0


def _interp(pm, z, region):
    """``f(xs, ys) -> zs``: linear over each map face inside ``region``,
    triangulated on its own ring (constrained Delaunay, the way the mesh
    takes the patch's faces); ``nan`` off every face -- outside the patch,
    where the base mesh stands at the DEM."""
    import numpy as np
    import shapely
    from shapely.geometry import Polygon
    from shapely.strtree import STRtree
    at = {tuple(vx.xy): v for v, vx in pm.vertices.items()}
    tris: list = []
    for f in pm.faces.values():
        ring = [pm.vertices[v].xy for v in pm.ring_vertices(f.ring)]
        if len(ring) < 3:
            continue
        poly = Polygon(ring, [[pm.vertices[v].xy for v in pm.ring_vertices(h)]
                              for h in f.holes])
        if not poly.intersects(region):
            continue
        for t in shapely.get_parts(shapely.constrained_delaunay_triangles(poly)):
            c = list(t.exterior.coords)[:3]
            vs = [at.get(tuple(p)) for p in c]
            if None not in vs:
                tris.append((t, np.array(c, float), np.array([float(z[v]) for v in vs])))
    tree = STRtree([t for t, _c, _z in tris])

    def f(xs, ys):
        out = np.full(len(xs), np.nan)
        for k, (x, y) in enumerate(zip(xs, ys)):
            for i in tree.query(shapely.Point(x, y)):
                _t, c, zz = tris[i]
                (x0, y0), (x1, y1), (x2, y2) = c
                det = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
                if abs(det) < 1e-12:
                    continue
                a = ((y1 - y2) * (x - x2) + (x2 - x1) * (y - y2)) / det
                b = ((y2 - y0) * (x - x2) + (x0 - x2) * (y - y2)) / det
                if min(a, b, 1.0 - a - b) >= -1e-9:
                    out[k] = a * zz[0] + b * zz[1] + (1.0 - a - b) * zz[2]
                    break
        return out
    return f


def _walk(line, f):
    """``(points, zs)`` every :data:`STEP_M` along ``line``."""
    import numpy as np
    n = max(2, int(line.length / STEP_M) + 1)
    pts = [line.interpolate(k * line.length / (n - 1)) for k in range(n)]
    return pts, f(np.array([p.x for p in pts]), np.array([p.y for p in pts]))


def deck_perimeter(pm, z, deck) -> dict:
    """One banked deck's walk (module doc): per offset and overall, the
    worst step, grade, jag count and slope break, with where."""
    import numpy as np
    from shapely.geometry import Polygon
    ring = Polygon(deck.ring)
    f = _interp(pm, z, ring.buffer(max(OFFSETS_M) + 15.0))
    out = {"object": deck.object_id, "offsets": {}, "step_m": 0.0, "grade": 0.0,
           "jags": 0, "break": 0.0, "off": 0, "worst_at": None}
    for d in OFFSETS_M:
        line = ring.buffer(d).exterior
        pts, zs = _walk(line, f)
        ok = ~np.isnan(zs)
        dz = np.diff(zs)
        good = ok[1:] & ok[:-1]
        dz = np.where(good, dz, 0.0)
        g = np.abs(dz) / STEP_M
        brk = np.abs(np.diff(dz / STEP_M)) if len(dz) > 1 else np.zeros(1)
        brk = np.where(good[1:] & good[:-1], brk, 0.0) if len(dz) > 1 else brk
        k = int(np.argmax(g)) if len(g) else 0
        q = {"step_m": round(float(np.max(np.abs(dz), initial=0.0)), 3),
             "grade": round(float(np.max(g, initial=0.0)), 3),
             "jags": int(np.sum(g > JAG_GRADE)),
             "break": round(float(np.max(brk, initial=0.0)), 3),
             "off": int(np.sum(~ok)),
             "at": (round(pts[k].x, 2), round(pts[k].y, 2))}
        out["offsets"][d] = q
        out["jags"] += q["jags"]
        out["off"] += q["off"]
        out["break"] = max(out["break"], q["break"])
        if q["grade"] > out["grade"]:
            out["grade"], out["step_m"], out["worst_at"] = q["grade"], q["step_m"], q["at"]
    return out


def bank_perimeter(pm, z, airport) -> list[dict]:
    """Every banked deck's walk; ``ll`` on each worst sample."""
    from auto_patch_v2.model.deck_bank import banked
    out = [deck_perimeter(pm, z, d) for d in getattr(pm, "decks", ()) or () if banked(d)]
    if airport is not None and getattr(airport, "frame", None) is not None:
        _xy, to_ll = airport.frame.transformers()
        for q in out:
            if q.get("worst_at"):
                la, lo = to_ll(*q["worst_at"])
                q["ll"] = (round(la, 7), round(lo, 7))
    return out
