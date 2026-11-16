"""THE NECK RELEASE (#1918 R4, owner RULINGS 2026-11-16e; spec
``docs/specs/1918-R4.md`` §2 R4-2).

In the pad roads' stage a pad road's ring is minted with ABEAM STATIONS
(``planar/chords.abeam_stations``): a station on the kerb its standing
vertex faces.  Where that kerb is a STANDING road's (a base edge), the
station is a rim node (``stage_one_map.late_rim_levels``) and stands on the
base edge's line — a row between two constants is dropped, so the step
between the pad's tip and the kerb station is never priced.  A NECK is such
a station facing a standing vertex of the pad road abeam it across a level
difference over ``[road_contact] neck_step_m``.

An edge carrying a neck is RELEASED — its stations become unknowns of the
pad roads' solve, its two ends stay constants — where its own law lets it:

* G1 REACH: every station of the edge keeps a non-empty interval under its
  HARD ``Diff`` rows against the constants;
* G2 OWN SECTION: on every standing face carrying a station of the edge, no
  other vertex of that face stands abeam a ring edge incident to the
  station (the standing road's own cross-section stays its own).

Otherwise the edge stands and is recorded as a WALL (``walls``).
"""
from __future__ import annotations

import math
import typing as _t

#: metres beyond the identity spacing a candidate stands from a base vertex
_IDENTITY_MARGIN_M = 0.001
#: metres: G1's interval tolerance
_REACH_TOL_M = 0.02


class Neck(_t.NamedTuple):
    """One neck: station ``s`` facing the pad road's standing vertex ``v``."""

    s: int
    v: int
    step: float     # fixed[v] - fixed[s]
    across: float   # metres, in the base edge's frame


def late_neck_release(pm_base, pm, fixed: dict[int, float], cs, law,
                      rim_edges: _t.Mapping[int, tuple[int, int]],
                      joined: _t.AbstractSet[int],
                      to_ll: _t.Callable[[float, float], tuple] | None = None
                      ) -> tuple[dict, list[Neck]]:
    """Release the necks of the pad roads' stage (module doc), IN PLACE on
    ``fixed``.  ``rim_edges``: ``{rim node: (a, b)}``, the base edge each
    node ``late_rim_levels`` levelled stands on; ``joined``: the full map's
    vertices joined to a base vertex (``late_fixed``).  ``(report, the
    released edges' necks)``; the report is ``{"released_edges",
    "released", "walls"}`` (lists of ``{lat, lon, ...}`` records)."""
    from ..model.planar import pad_road_faces
    rep: dict = {"released_edges": 0, "released": [], "walls": []}
    pads = {f.id for f in pad_road_faces(pm)}
    if not pads or not rim_edges:
        return rep, []
    rc = law.tables.emit.road_contact
    ident = float(law.tables.emit.identity.min_distinct_spacing_m)
    lateral, bar = float(rc.pair_lateral_m), float(rc.neck_step_m)
    cand = _candidates(pm_base, pm, fixed, cs, law, rim_edges, pads, ident)
    if not cand:
        return rep, []
    by_edge: dict[tuple[int, int], list[int]] = {}
    for j in cand:
        by_edge.setdefault(tuple(sorted(rim_edges[j])), []).append(j)
    polys: dict[int, _t.Any] = {}
    hard = _hard_rows(cs, law, set(cand))
    kept: list[Neck] = []
    for edge, js in sorted(by_edge.items()):
        u = _unit(pm_base, edge)
        necks = [n for s in js
                 for n in _necks(pm, fixed, s, u, pads, joined, polys, ident, lateral, bar)]
        if not necks:
            continue
        worst = max(necks, key=lambda n: abs(n.step))
        reason = ("unreachable" if not _reach(js, hard, fixed)
                  else "own_section" if _own_section(pm, js, pads, polys, ident, lateral)
                  else None)
        rec = {**_where(pm, worst.s, to_ll), "step": round(worst.step, 3),
               "across": round(worst.across, 2)}
        if reason:
            rep["walls"].append({**rec, "reason": reason})
            continue
        rep["released_edges"] += 1
        for s in js:
            rep["released"].append({**_where(pm, s, to_ll),
                                    "base_m": round(float(fixed[s]), 3)})
            del fixed[s]
        kept.extend(necks)
    return rep, kept


def _candidates(pm_base, pm, fixed, cs, law, rim_edges, pads, ident) -> list[int]:
    """The rim nodes a neck may release: carried by a pad-road face, every
    other face a groundside, non-rigid road-family face that is no LOT (a
    lot's edge stands, spec gate 8); farther than the identity spacing from
    every base vertex; no ``Pin``."""
    import numpy as np
    from scipy.spatial import cKDTree

    from ..classify.lot_roads import LOT_ROLES
    from ..law.tables import is_rigid_role, road_family_roles, role_side
    from ..model.constraints import Pin
    roads = frozenset(road_family_roles(law)) - frozenset(LOT_ROLES)
    pinned = {int(r.v) for r in cs.rows() if isinstance(r, Pin)}
    F = pm.faces
    out = []
    for j in rim_edges:
        if j not in fixed or j in pinned:
            continue
        fs = [F[q] for q in pm.vertices[j].incident_faces if q in F]
        others = [f for f in fs if f.id not in pads]
        if len(others) == len(fs) or not others:
            continue
        if all(f.role in roads and not is_rigid_role(law, f.role)
               and role_side(law, f.role) != "airside" for f in others):
            out.append(j)
    if not out:
        return out
    bv = pm_base.vertices
    xy = np.array([v.xy for v in (bv.values() if isinstance(bv, dict) else bv)])
    d, _ = cKDTree(xy).query(np.array([pm.vertices[j].xy for j in out]))
    return [j for j, dj in zip(out, d, strict=True) if dj > ident + _IDENTITY_MARGIN_M]


def _unit(pm_base, edge) -> tuple[float, float]:
    (ax, ay), (bx, by) = pm_base.vertices[edge[0]].xy, pm_base.vertices[edge[1]].xy
    n = math.hypot(bx - ax, by - ay) or 1.0
    return (bx - ax) / n, (by - ay) / n


def _inside(pm, fid, polys, p, q) -> bool:
    """Whether segment ``p``-``q`` lies in face ``fid`` (grown a hair, so a
    segment ON its ring is in)."""
    from shapely.geometry import LineString, Polygon
    if fid not in polys:
        rings = [[pm.vertices[v].xy for v in r] for r in _rings(pm, pm.faces[fid])]
        polys[fid] = Polygon(rings[0], rings[1:]).buffer(1e-6)
    return bool(polys[fid].covers(LineString([p, q])))


def _rings(pm, f) -> list[list[int]]:
    return [list(pm.ring_vertices(c)) for c in (f.ring, *f.holes)]


def _necks(pm, fixed, s, u, pads, joined, polys, ident, lateral, bar) -> list[Neck]:
    """The necks at station ``s``: a joined (base) vertex of a pad-road
    face's ring at ``s`` abeam it in the base edge's frame ``u``, the
    segment between them inside the face, over the bar."""
    sx, sy = pm.vertices[s].xy
    out, seen = [], set()
    for q in pm.vertices[s].incident_faces:
        if q not in pads:
            continue
        for v in (v for ring in _rings(pm, pm.faces[q]) for v in ring):
            if v == s or v in seen or v not in joined or v not in fixed:
                continue
            vx, vy = pm.vertices[v].xy
            along = (vx - sx) * u[0] + (vy - sy) * u[1]
            across = abs((vx - sx) * u[1] - (vy - sy) * u[0])
            if abs(along) > 1.5 * ident or not ident <= across <= lateral:
                continue
            step = float(fixed[v]) - float(fixed[s])
            if abs(step) > bar and _inside(pm, q, polys, (vx, vy), (sx, sy)):
                seen.add(v)
                out.append(Neck(s, v, step, across))
    return out


def _hard_rows(cs, law, nodes) -> dict[int, list[tuple[int, float, float]]]:
    """``{node: [(other, lo, hi)]}``: each HARD ``Diff`` row on a node of
    ``nodes`` read as ``z[other] + lo <= z[node] <= z[other] + hi``."""
    from ..model.constraints import Diff
    from ..solve.design_roles import hard_rulings, ruling_head
    heads = hard_rulings(law)
    out: dict[int, list] = {}
    for r in cs.rows():
        if not isinstance(r, Diff) or r.soft is not None or ruling_head(r) not in heads:
            continue
        a, b, w, rel = int(r.a), int(r.b), float(r.cap) * float(r.d), float(r.rel)
        if a in nodes:                    # z_a - z_b in [rel - w, rel + w]
            out.setdefault(a, []).append((b, rel - w, rel + w))
        if b in nodes:
            out.setdefault(b, []).append((a, -rel - w, -rel + w))
    return out


def _reach(js, hard, fixed) -> bool:
    """G1: every station keeps a non-empty interval against the constants
    (the edge's own stations are no constants once released)."""
    own = set(js)
    for j in js:
        lo, hi = -math.inf, math.inf
        for k, dlo, dhi in hard.get(j, ()):
            if k in fixed and k not in own:
                lo, hi = max(lo, float(fixed[k]) + dlo), min(hi, float(fixed[k]) + dhi)
        if lo > hi + _REACH_TOL_M:
            return False
    return True


def _own_section(pm, js, pads, polys, ident, lateral) -> bool:
    """G2 fails: on a standing face carrying a station, another vertex of
    that face stands abeam a ring edge incident to the station."""
    for j in js:
        for q in pm.vertices[j].incident_faces:
            if q in pads or q not in pm.faces:
                continue
            rings = _rings(pm, pm.faces[q])
            for ring in rings:
                if j not in ring:
                    continue
                i = ring.index(j)
                for n in (ring[i - 1], ring[(i + 1) % len(ring)]):
                    if _abeam_any(pm, q, j, n, rings, polys, ident, lateral):
                        return True
    return False


def _abeam_any(pm, q, j, n, rings, polys, ident, lateral) -> bool:
    """Whether a vertex of face ``q``'s ``rings`` stands abeam ring edge
    ``j``-``n``: its foot at least the identity spacing inside the edge,
    within the pair lateral across it, the segment to the foot in ``q``."""
    (ax, ay), (bx, by) = pm.vertices[j].xy, pm.vertices[n].xy
    L = math.hypot(bx - ax, by - ay)
    if L < 2.0 * ident:
        return False
    ux, uy = (bx - ax) / L, (by - ay) / L
    for w in (w for ring in rings for w in ring):
        if w in (j, n):
            continue
        x, y = pm.vertices[w].xy
        t = (x - ax) * ux + (y - ay) * uy
        c = abs((x - ax) * uy - (y - ay) * ux)
        if ident <= t <= L - ident and ident <= c <= lateral and \
                _inside(pm, q, polys, (x, y), (ax + t * ux, ay + t * uy)):
            return True
    return False


def _where(pm, v, to_ll) -> dict:
    x, y = pm.vertices[v].xy
    if to_ll is None:
        return {"x": round(x, 2), "y": round(y, 2)}
    lat, lon = to_ll(x, y)
    return {"lat": round(lat, 7), "lon": round(lon, 7)}


def necks_over(necks: _t.Sequence[Neck], z: _t.Sequence[float], bar: float
               ) -> list[tuple[int, int, float]]:
    """``(s, v, |z[v] - z[s]|)`` of each released neck still over ``bar``
    in the solved levels ``z``."""
    return [(n.s, n.v, abs(float(z[n.v]) - float(z[n.s]))) for n in necks
            if abs(float(z[n.v]) - float(z[n.s])) > bar]
