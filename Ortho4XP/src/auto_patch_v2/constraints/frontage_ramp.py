"""ROADS RAMP TO THE FRONTAGE BAND (RULINGS 2026-11-25g (3) under the 25c
road law; spec ``docs/specs/terminal-frontage-split-level-20261125.md``
§3.2, step 3: C16, C17).

The frontage law (``constraints/kerb_frontage``) holds every groundside
vertex within ``[design] pad_frontage_m`` of a two-floor unit's landside
face at the unit's GROUNDSIDE floor ``G = z_D + y`` (``D`` the block's
datum column, ``y`` the signed rise).  A road whose ribbon enters that
band kept its §37 (6) ramp target and hard ceiling off its own ground
beyond it, so it stood off the band by what its ground stands off ``G``.

THE RULE.  The band's road vertices are the road's CONTACT at ``G``
(spec §3.2): from them, along the road's own graph (the route distance
``s``, :func:`band_seeds`), every road vertex beyond the band takes the
band's ramp as its §37 (6) target and ceiling --

    G above the target (the frontage a storey up): ``max(t, G - g s)``
    G below the target (the frontage a storey down): ``min(t, G + g s)``

``g`` the design grade (``[road_contact] ramp_grade``), the ceiling
``target + [cockpit] visual_m`` following it, exactly as the reach seed
(``road_ramp._reach_seed``) raises a road to stage 1's apron.  It is a
STAGE-2 REWRITE (:func:`frontage_ramp_rewrite`, bound in
``road_ramp.reach_seed_rewrite``): ``z_D`` is stage 1's constant there, so
AIRSIDE IS UNTOUCHED BY CONSTRUCTION.  A road vertex the band governs
leaves the airside: its §37 (10) contact rows on the wall (an airside or
pad edge the kerb law walls off, ``kerb_frontage.kerb_vertices``) are
withdrawn -- the road meets the building at the frontage, never at the
floor a storey off it.  The frontage never yields to the road (§3.2): a
road that cannot reach its ground within the design grade over its run
stands off it at its far end."""
from __future__ import annotations

import dataclasses as _dc
import heapq
import typing as _t

from ..geom import exact
from ..law import Law
from ..law.tables import family
from ..model.constraints import Band, ConstraintSet, Linear, Source
from ..model.map_memo import per_map
from ..model.planar import PlanarMap

__all__ = ["REPORT_KEY", "band_seeds", "frontage_ramp_rewrite"]

#: the stage-2 report key (``reach_seed_rewrite``'s report)
REPORT_KEY = "frontage_ramp"
_MEMO: dict[int, tuple[_t.Any, dict]] = {}


def _road_vertices(planar: PlanarMap, law: Law) -> set[int]:
    roads = frozenset(family(law, "road_cross_section").roles)
    return {v for f in planar.faces.values() if f.role in roads
            for cyc in (f.ring, *f.holes) for v in planar.ring_vertices(cyc)}


def _walk(planar: PlanarMap, src: _t.Mapping[int, tuple[float, tuple]],
          nodes: set[int]) -> dict[int, tuple[float, tuple]]:
    """``{v: (route distance, its source's (block, rise))}`` over the planar
    edges joining two of ``nodes``, from every source at its own starting
    distance (never source to source: the band is no route)."""
    adj: dict[int, list[tuple[int, float]]] = {}
    for e in planar.edges.values():
        if e.a in nodes and e.b in nodes and not (e.a in src and e.b in src):
            d = exact.dist(planar.vertices[e.a].xy, planar.vertices[e.b].xy)
            adj.setdefault(e.a, []).append((e.b, d))
            adj.setdefault(e.b, []).append((e.a, d))
    best = dict(src)
    heap = [(s, v) for v, (s, _k) in sorted(src.items())]
    heapq.heapify(heap)
    while heap:
        s, v = heapq.heappop(heap)
        if best[v][0] < s:
            continue
        for w, d in adj.get(v, ()):
            if s + d < best.get(w, (float("inf"), None))[0]:
                best[w] = (s + d, best[v][1])
                heapq.heappush(heap, (s + d, w))
    return best


def _landing_vertices(planar: PlanarMap) -> dict[int, tuple[str, float]]:
    """``{vertex: (block, rise)}`` of every face of a frontage block's
    LEVEL -- the landing minted on a block carrying a kerb record
    (``planar/kerb_frontage``) at the record's rise: the groundside floor
    inside the building, which a road meets where it enters it
    (``planar/frontage_roads``)."""
    from ..model.registries import LANDSIDE_KERB
    reg = getattr(planar, "registries", None)
    held = getattr(reg, "held", None) or {}
    refs: dict[str, tuple[str, float]] = {}
    for k, lv in sorted((getattr(reg, "landings", None) or {}).items()):
        recs = held.get(str(lv.get("block")), {}).get(LANDSIDE_KERB, ())
        for rec in recs:
            if lv.get("deck") is None and lv.get("y") is not None \
                    and abs(float(lv["y"]) - float(rec["y"])) < 0.01:
                refs[str(k)] = (str(lv["block"]), float(rec["y"]))
    return {v: refs[f.ref] for f in planar.faces.values() if f.ref in refs
            for cyc in (f.ring, *f.holes) for v in planar.ring_vertices(cyc)}


def _sources(planar: PlanarMap, law: Law, kerb, targets) -> dict[int, tuple[float, tuple]]:
    """THE ROAD'S CONTACTS WITH THE FRONTAGE: every band vertex on a road
    face, at route distance 0; and every road vertex within the stand-off
    of a frontage level's face (``[design] pad_frontage_m`` +
    ``groundside_cutback_m``), at its distance to the nearest of its
    vertices."""
    src = {k: (0.0, kerb[k]) for k in set(kerb) & _road_vertices(planar, law)}
    land = _landing_vertices(planar)
    free = [v for v in targets if v not in kerb and v in planar.vertices]
    if land and free:
        import numpy as np
        from scipy.spatial import cKDTree

        from ..law.tables import design as design_law
        reach = float(design_law(law).pad_frontage_m) + float(
            law.tables.zones.adjacent_ground.groundside_cutback_m)
        ls = sorted(land)
        tree = cKDTree(np.array([planar.vertices[u].xy for u in ls]))
        d, i = tree.query(np.array([planar.vertices[v].xy for v in free]),
                          distance_upper_bound=reach)
        for v, dv, iv in zip(free, d, i, strict=True):
            if np.isfinite(dv):
                src.setdefault(v, (float(dv), land[ls[int(iv)]]))
    return src


def band_seeds(planar: PlanarMap, law: Law
               ) -> dict[int, tuple[str, float, float]]:
    """``{road vertex: (block, rise, s)}``: every vertex carrying a §37 (6)
    target (``PlanarMap.road_ramp_z``) or a §37 (10) contact
    (``PlanarMap.road_contact_edge``) that the road's own graph joins to
    the frontage (:func:`_sources`), ``s`` the route distance to the
    nearest contact -- never through a wall vertex (the building's side)
    or a band vertex.  Read once per map."""
    memo = per_map(_MEMO, planar)
    if "seeds" in memo:
        return memo["seeds"]
    from .kerb_frontage import kerb_vertices
    kerb, wall = kerb_vertices(planar, law)
    # the road's own vertices: a §37 (6) target's, or a §37 (10) contact's
    # (the end group whose target the contact withdrew)
    targets = set(getattr(planar, "road_ramp_z", None) or {}) | set(
        getattr(planar, "road_contact_edge", None) or {})
    out: dict[int, tuple[str, float, float]] = {}
    src = _sources(planar, law, kerb, targets) if targets else {}
    if src:
        nodes = (targets - wall - set(kerb)) | set(src)
        for v, (s, (block, y)) in _walk(planar, src, nodes).items():
            if v in targets and v not in kerb:
                out[v] = (block, float(y), float(s))
    memo["seeds"] = out
    return out


def _vertex(src: Source) -> int | None:
    tag = src.inputs[0] if src.inputs else ""
    return int(tag[7:]) if tag.startswith("vertex:") else None


def _ramp_levels(planar: PlanarMap, law: Law, cs: ConstraintSet,
                 levels: _t.Mapping[int, float], seeds, wall, rep: dict
                 ) -> dict[int, float]:
    """``{v: the band's ramp}`` where it stands beyond the vertex's §37 (6)
    target (module docstring)."""
    from ..model.platform import datum_vertices
    from .road_ramp import GEN, RULING
    held = datum_vertices(planar, law, fills=True)
    contact = getattr(planar, "road_contact_edge", None) or {}
    g = float(law.tables.emit.road_contact.ramp_grade)
    target = {_vertex(r.source): float(r.hi) for r in cs.linears
              if r.source.generator == GEN and r.source.ruling == RULING and r.hi is not None}
    out: dict[int, float] = {}
    for v, (block, y, s) in sorted(seeds.items()):
        dv = held.get(block)
        if dv is None or dv not in levels:
            rep["unlevelled"] += 1
            continue
        t = target.get(v)
        if t is None:
            # a contact's end group carries no target (``airport/road_ramp.
            # with_road_ramp``): where the contact is the building's wall
            # (its rows leave, :func:`frontage_ramp_rewrite`) its own ground
            # is the floor of the band's ramp
            edge = contact.get(v)
            dem = planar.vertices[v].dem_z
            if dem is None or edge is None or not (edge[0] in wall or edge[1] in wall):
                continue
            t = float(dem)
        G = float(levels[dv]) + y
        z = max(t, G - g * s) if G > t else min(t, G + g * s)
        if abs(z - t) > 1e-9 or v not in target:
            out[v] = z
    return out


def frontage_ramp_rewrite(planar: PlanarMap, law: Law, cs: ConstraintSet,
                          levels: _t.Mapping[int, float]
                          ) -> tuple[ConstraintSet, dict[str, _t.Any]]:
    """THE STAGE-2 REWRITE (module docstring): every §37 (6) target and
    ceiling :func:`band_seeds` governs moves to the band's ramp where it
    stands beyond it, and the governed vertices' contact rows on the wall
    leave.  Returns the set and the report (``seeded``, ``raised``,
    ``lowered``, ``max_move_m``, ``unlevelled``, ``contacts_withdrawn``)."""
    seeds = band_seeds(planar, law)
    rep: dict[str, _t.Any] = {"seeded": len(seeds), "raised": 0, "lowered": 0,
                              "max_move_m": 0.0, "unlevelled": 0,
                              "contacts_withdrawn": 0, "targeted": 0, "worst": None}
    if not seeds:
        return cs, rep
    from .kerb_frontage import kerb_vertices
    from .road_ramp import CONTACT_RULING, GEN, RULING, RULING_CEILING
    wall = kerb_vertices(planar, law)[1]
    ramp = _ramp_levels(planar, law, cs, levels, seeds, wall, rep)
    if not ramp:
        return cs, rep
    vis = float(law.tables.emit.cockpit.visual_m)
    linears = []
    for r in cs.linears:
        v = _vertex(r.source) if r.source.generator == GEN else None
        if v in ramp and r.source.ruling == RULING:
            dz = ramp[v] - float(r.hi)
            rep["raised" if dz > 0 else "lowered"] += 1
            if abs(dz) > rep["max_move_m"]:
                rep["max_move_m"], rep["worst"] = abs(dz), v
            r = _dc.replace(r, lo=ramp[v], hi=ramp[v])
        elif v in ramp and r.source.ruling == CONTACT_RULING \
                and any(u in wall for u, _c in r.terms[1:]):
            rep["contacts_withdrawn"] += 1
            continue
        linears.append(r)
    bands = [_dc.replace(r, hi=ramp[v] + vis)
             if r.source.generator == GEN and r.source.ruling == RULING_CEILING
             and (v := _vertex(r.source)) in ramp else r for r in cs.bands]
    # a contact's end vertex the band governs takes the band's ramp as its
    # target and ceiling (it had none: the contact had withdrawn it)
    had = {_vertex(r.source) for r in cs.linears
           if r.source.generator == GEN and r.source.ruling == RULING}
    for v in sorted(set(ramp) - had):
        tag = (f"vertex:{v}", "frontage")
        linears.append(Linear(((v, 1.0),), ramp[v], ramp[v], Source(GEN, RULING, tag)))
        bands.append(Band(v, None, ramp[v] + vis, Source(GEN, RULING_CEILING, tag)))
        rep["targeted"] += 1
    rep["max_move_m"] = round(rep["max_move_m"], 4)
    return _dc.replace(cs, linears=tuple(linears), bands=tuple(bands)), rep
