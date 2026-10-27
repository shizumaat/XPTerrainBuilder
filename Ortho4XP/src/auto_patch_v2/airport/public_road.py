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
"""
from __future__ import annotations

import math
import typing as _t

from ..law import Law
from ..law.tables import role_cap
from ..model.airport import Airport
from ..model.planar import OSM_RIBBON_FEEDS, PlanarMap, is_osm_ribbon_ref

__all__ = ["public_road_faces", "public_road_lifts"]


def _way_key(ref: str) -> str:
    """``small_roads:-1190#2`` -> ``small_roads:-1190`` (the mint's own
    spelling, ``classify/ribbon_mint._mint_spans``)."""
    return str(ref).split("#", 1)[0]


def public_road_faces(pm: PlanarMap, law: Law, airport: Airport
                      ) -> dict[int, str]:
    """Face id -> ``highway`` class, for every OSM ribbon face of a road
    family role whose way's class is in ``[road_profile] public_classes``."""
    public = frozenset(law.tables.emit.road_profile.public_classes)
    if not public:
        return {}
    cls: dict[str, str] = {}
    for w in getattr(airport, "osm_ways", ()) or ():
        feed = OSM_RIBBON_FEEDS.get(getattr(w, "kind", ""))
        hw = (getattr(w, "tags", None) or {}).get("highway")
        if feed and hw in public:
            cls[f"{feed}:{w.id}"] = str(hw)
    from ..law.tables import family
    roads = frozenset(family(law, "road_cross_section").roles)
    return {fid: cls[_way_key(f.ref)] for fid, f in pm.faces.items()
            if f.role in roads and is_osm_ribbon_ref(f.ref)
            and _way_key(f.ref) in cls}


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
                d = math.hypot(xa - xb, ya - yb)
                if d > 0.0:
                    worst = max(worst, abs(targets[a] - targets[b]) / d)
        if worst > cap:
            out[int(fid)] = round(worst, 6)
    return out
