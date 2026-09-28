"""THE COURTYARD (spec-author ruling 2026-09-28, lane ``islands``; issues
#77 / #73): an apron ISLAND inside a pad HOLE takes its level from the PAD
RIM around it — it is a courtyard of the pad — never its own DEM plane and
never the main apron's trend.

THE DEFECT.  RULINGS 2026-09-23a cuts the apron back to the pad, so a pad
laid over an apron keeps the apron pieces inside its holes (KCLT terminal
pad ``building84``: 42 holes holding 24 pieces of apron ``pav14``).  Since
issue #67 stage 1 forms its bodies over the airside alone, so each piece
had no airside neighbour and took its OWN DEM plane: two island vertices
40 m apart solved 1.78 m apart, and the pad plate that meets them at the
hole ring was bent by them (the pad FRONTED its own islands).

THE RULE, at ONE derivation site (this module) read by every consumer:

* a COURTYARD face is an apron-role face (``law.tables.apron_roles``)
  whose every vertex stands on or inside ONE hole ring of ONE rigid face
  (the pad) — geometrically, so a hole holding several pieces (or a piece
  with interior vertices) is read whole;
* its vertices leave stage 1 (``solve.design_roles.airside_stage_vertices``)
  — they are solved in stage 2 WITH the pad, whose hole ring they share;
* they carry no DEM datum (``solve.design`` §9b) and no apron trend
  (``constraints.apron_trend._apron_bodies``): their level is the rim's;
* they are not pavement the pad FRONTS (``constraints.pads`` frontage and
  the airside-led pair drop): a courtyard follows its pad, the pad never
  follows its courtyard.

A vertex a courtyard face shares with a NON-courtyard airside face is not a
courtyard vertex (it stays airside; stage 1 owns it)."""
from __future__ import annotations

import typing as _t
import weakref as _weakref

__all__ = ["courtyard_faces", "courtyard_vertices"]

#: tolerance (m) for "on the hole ring" — the planar map's vertices ON a
#: hole ring are the ring's own, so this only absorbs float noise
_ON_RING_M = 0.05

#: per planar map (by identity, held weakly — a frozen dataclass of dicts is
#: not hashable): the derived sets, computed once per map
_CACHE: dict[int, tuple[_t.Any, dict]] = {}


def _cache(pm: _t.Any) -> dict:
    got = _CACHE.get(id(pm))
    if got is not None and got[0]() is pm:
        return got[1]
    try:
        ref = _weakref.ref(pm, lambda _r, k=id(pm): _CACHE.pop(k, None))
    except TypeError:                             # not weak-referenceable
        return {}
    d: dict = {}
    _CACHE[id(pm)] = (ref, d)
    return d


def courtyard_faces(pm: _t.Any, law: _t.Any) -> frozenset[int]:
    """Face ids of every COURTYARD face (module docstring)."""
    c = _cache(pm)
    key = ("faces", id(law))
    if key in c:
        return c[key]
    from shapely.geometry import Point, Polygon
    from shapely.strtree import STRtree
    from ..law.tables import apron_roles, is_rigid_role

    aprons = apron_roles(law)
    holes: list = []
    for f in pm.faces.values():
        if not f.holes or not is_rigid_role(law, f.role):
            continue
        for h in f.holes:
            vs = pm.ring_vertices(h)
            if len(vs) < 3:
                continue
            poly = Polygon([pm.vertices[v].xy for v in vs])
            if not poly.is_valid:
                poly = poly.buffer(0.0)
            if poly.is_empty:
                continue
            holes.append(poly.buffer(_ON_RING_M))
    out: set[int] = set()
    if holes:
        tree = STRtree(holes)
        for f in pm.faces.values():
            if f.role not in aprons:
                continue
            vs = [v for ring in (f.ring, *f.holes) for v in pm.ring_vertices(ring)]
            if not vs:
                continue
            pts = [Point(*pm.vertices[v].xy) for v in vs]
            for hi in tree.query(pts[0]):
                hp = holes[int(hi)]
                if all(hp.contains(p) for p in pts):
                    out.add(f.id)
                    break
    got = frozenset(out)
    c[key] = got
    return got


def courtyard_vertices(pm: _t.Any, law: _t.Any) -> frozenset[int]:
    """Every vertex of a courtyard face that no NON-courtyard airside-stage
    face carries — the vertices whose level is the pad rim's."""
    c = _cache(pm)
    key = ("vertices", id(law))
    if key in c:
        return c[key]
    from ..law.tables import airside_stage_roles
    court = courtyard_faces(pm, law)
    if not court:
        c[key] = frozenset()
        return c[key]
    roles = airside_stage_roles(law)
    cv: set[int] = set()
    other: set[int] = set()
    for f in pm.faces.values():
        vs = [v for ring in (f.ring, *f.holes) for v in pm.ring_vertices(ring)]
        if f.id in court:
            cv.update(vs)
        elif f.role in roles:
            other.update(vs)
    got = frozenset(cv - other)
    c[key] = got
    return got
