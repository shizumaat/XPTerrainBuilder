"""A PUBLIC ROAD FOLLOWS ITS TERRAIN (owner RULINGS 2026-10-22h, Q111;
issue #1254) — which ribbon faces are public roads, and how steep their own
target runs.

The ruling: a mapped road of a PUBLIC class (not airside, not ``service`` or
another airport-internal road; read off the road classification, never a
geometry window) takes the DEM's grade wherever the DEM along it is steeper
than ``[common] road_max_grade``; airside and service roads keep the cap.

The PROFILE half lives in the core's clamp (``O4_Vector_Utils.
road_inside_cap``, read by ``airport/road_profile.core_profiles``): a public
way's in-band cap is ``[road_profile] cap_ceiling``, so the ramp floor
(:mod:`airport.road_ramp`) is the terrain itself.  This module is the ROW
half's derivation: the public faces whose target (``PlanarMap.road_ramp_z``)
runs steeper than the road cap, with that grade — published once as
``PlanarMap.public_road_lifted`` (face id -> grade) by
:func:`airport.road_ramp.with_road_ramp`.  Its readers:
``constraints/public_road_release`` (the solve's rows) and
``pipeline/publication.lifted_caps`` (the census, the §34 (9) lift).

THE ROAD ON STEEP GROUND (owner RULINGS 2026-11-17, #2122: "Looks like
there are real roads that go up to 20%, so when terrain demands it, we
should allow it. Raise our road grade limit to 20%."): every OTHER mapped
road (a ``highway`` class not public: ``service`` above all) follows its
terrain too, up to ``tables.road_terrain_cap`` — the core's clamp takes it
in band (``road_inside_cap``), and :func:`steep_road_lifts` names the faces
whose own target runs over the road cap somewhere, with the cap they take:
the steep-ground cap (the limit rises; the design grade stands).  Published as
``PlanarMap.steep_road_lifted``; its rows rise to it
(``constraints/public_road_release.steep_release``), the terrace's runs on
its routes climb at it (``constraints/road_ramp.terrace_rewrite``) and the
census lifts it (``pipeline/publication.lifted_caps``).  On ground under
the road cap no face is named and nothing changes.
"""
from __future__ import annotations

import typing as _t

from ..geom import exact
from ..law import Law
from ..law.tables import road_terrain_cap, role_cap
from ..model.airport import Airport
from ..model.grade_separation import road_key
from ..model.planar import OSM_RIBBON_FEEDS, PlanarMap, is_osm_ribbon_ref

__all__ = ["public_road_faces", "public_road_lifts", "public_routes",
           "steep_road_faces", "steep_road_lifts", "STEEP_SLACK"]

#: a face is on steep ground only where its target runs over the road cap
#: by more than this (a grade): a ramp built AT the cap reads a hair over it
#: off the targets' read grid, and is not the terrain demanding more
STEEP_SLACK = 1e-3


def _road_face_classes(pm: PlanarMap, law: Law, airport: Airport,
                       public: bool) -> dict[int, str]:
    """Face id -> ``highway`` class, for every OSM ribbon face of a road
    family role whose way's class is (``public``) or is not (not
    ``public``) in ``[road_profile] public_classes``."""
    pub = frozenset(law.tables.emit.road_profile.public_classes)
    if public and not pub:
        return {}
    cls: dict[str, str] = {}
    for w in getattr(airport, "osm_ways", ()) or ():
        feed = OSM_RIBBON_FEEDS.get(getattr(w, "kind", ""))
        hw = (getattr(w, "tags", None) or {}).get("highway")
        if feed and hw and (hw in pub) == public:
            cls[f"{feed}:{w.id}"] = str(hw)
    from ..law.tables import family
    roads = frozenset(family(law, "road_cross_section").roles)
    return {fid: cls[road_key(f.ref)] for fid, f in pm.faces.items()
            if f.role in roads and is_osm_ribbon_ref(f.ref)
            and road_key(f.ref) in cls}


def public_road_faces(pm: PlanarMap, law: Law, airport: Airport
                      ) -> dict[int, str]:
    """Face id -> ``highway`` class, for every OSM ribbon face of a road
    family role whose way's class is in ``[road_profile] public_classes``."""
    return _road_face_classes(pm, law, airport, True)


def steep_road_faces(pm: PlanarMap, law: Law, airport: Airport
                     ) -> dict[int, str]:
    """Face id -> ``highway`` class, for every OSM ribbon face of a road
    family role whose way is a road (a ``highway`` class) NOT in
    ``[road_profile] public_classes`` — the roads 2026-11-17 lets climb to
    :func:`tables.road_terrain_cap` where their ground demands it."""
    return _road_face_classes(pm, law, airport, False)


def _steepest(pm: PlanarMap, faces: _t.Iterable[int],
              targets: _t.Mapping[int, float]) -> dict[int, float]:
    """Face id -> the steepest grade its own target runs at between two
    consecutive ring vertices (0.0 where no pair carries targets)."""
    out: dict[int, float] = {}
    for fid in faces:
        f = pm.faces[fid]
        worst = 0.0
        for ring in (f.ring, *f.holes):
            cyc = pm.ring_vertices(ring)
            for i, a in enumerate(cyc):
                b = cyc[(i + 1) % len(cyc)]
                if a == b or a not in targets or b not in targets:
                    continue
                (xa, ya), (xb, yb) = pm.vertices[a].xy, pm.vertices[b].xy
                d = exact.hypot(xa - xb, ya - yb)
                if d > 0.0:
                    worst = max(worst, abs(targets[a] - targets[b]) / d)
        out[int(fid)] = worst
    return out


def public_road_lifts(pm: PlanarMap, law: Law, faces: _t.Iterable[int],
                      targets: _t.Mapping[int, float]) -> dict[int, float]:
    """Face id -> the steepest grade its own target runs at between two
    consecutive ring vertices, for every face of ``faces`` where that grade
    is over the road cap (``role_cap(service_road).longitudinal``).  A face
    whose target stays under the cap is absent: nothing about it changes."""
    rc = role_cap(law, "service_road")
    if rc is None:
        return {}
    cap = float(rc.longitudinal)
    return {fid: round(g, 6) for fid, g in _steepest(pm, faces, targets).items()
            if g > cap}


def steep_road_lifts(pm: PlanarMap, law: Law, faces: _t.Iterable[int],
                     targets: _t.Mapping[int, float]) -> dict[int, float]:
    """Face id -> the cap a road on steep ground takes (owner RULINGS
    2026-11-17: "when terrain demands it, we should allow it. Raise our
    road grade limit to 20%"): :func:`tables.road_terrain_cap`, for every
    face of ``faces`` whose own target runs over the road cap (by more than
    :data:`STEEP_SLACK`) somewhere.  A face whose target stays under the
    road cap is absent: nothing about it changes."""
    rc = role_cap(law, "service_road")
    if rc is None:
        return {}
    cap, top = float(rc.longitudinal), road_terrain_cap(law)
    if top <= cap:
        return {}
    return {fid: top for fid, g in _steepest(pm, faces, targets).items()
            if g > cap + STEEP_SLACK}


def public_routes(route_ways: _t.Mapping[int, _t.Any], law: Law,
                  airport: Airport) -> dict[int, str]:
    """Route id -> its OSM way's ref (``osm:<id>``), for every route of
    §37 (7)'s frame whose way is a mapped road of a public class.

    OWNER RULINGS 2026-10-27f (Q186): a pair across a JUNCTION MOUTH
    between two DIFFERENT public roads is the minor road's longitudinal
    grade into the major road's kerb, never a 2 % cross-section.  The frame
    names the route; this names the road the route belongs to, so the one
    pair reading (``constraints/roads.road_pair_reading``) can tell two
    roads from one carriageway (two route parts of ONE way share a ref)."""
    public = frozenset(law.tables.emit.road_profile.public_classes)
    if not public:
        return {}
    cls = {str(w.id) for w in getattr(airport, "osm_ways", ()) or ()
           if (getattr(w, "tags", None) or {}).get("highway") in public}
    out: dict[int, str] = {}
    for r, w in route_ways.items():
        ref = str(getattr(w, "ref", ""))
        if getattr(w, "kind", "") == "osm" and ref.split(":", 1)[-1] in cls:
            out[int(r)] = ref
    return out
