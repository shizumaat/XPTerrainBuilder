"""THE BAND STANDS OFF A ROAD INSIDE IT (owner 2026-10-19, rulings 19a/19i,
#951): "For roads in safety area, wall is correct."

A mapped-road ribbon inside an adjacent-ground band used to share its kerb
with the band (spec-author 30e (4)), so a road below the band's grade met it
in ONE welded vertex — a cliff inside the band face (KBUR building9 corner
2.36 m over 1 m; KLAX 33.945963, -118.436316 1.86 m).  Now the band yields a
STAND-OFF around the ribbon — ``groundside_cutback_m`` plus the snap margin,
the stand-off every groundside cell gets — and the gap terraces (the
declared step is the retaining wall).

It is cut in the ribbons' own pass (``planar/ribbons._ribbons_pass_c``),
never at the zone derivation site: pass A stays the arrangement WITHOUT
the ribbons, so the airside is identical with and without them (RULINGS
2026-09-30aa rules 2, 9-10).  The stand-off keeps off the finished
airside by the rim band (a ring touching the rim would mint a node on
it), and a band SLIVER left between ribbons — no wider than
``terrace.strip_min_width_m`` beyond the stand-off — yields to the roads
with it (a median between two carriageways is road ground, not a band
island standing between two walls)."""
from __future__ import annotations

import dataclasses as _dc

import shapely
from shapely.ops import unary_union

from ..law import Law
from ..law.tables import snap_margin_m

__all__ = ["standoff_geometry", "apply_standoff"]

_MITRE = dict(join_style="mitre", mitre_limit=2.0)


def standoff_geometry(ribs, regions, air, rim_band: float, law: Law):
    """The band ground the ribbons ``ribs`` take as their stand-off: around
    each ribbon, inside a zone region, off the airside ``air`` by
    ``rim_band``; plus every zone sliver that the stand-off leaves within
    ``strip_min_width_m`` of a ribbon.  ``None`` where there is none."""
    zone = [r.polygon for r in regions if r.source == "zone"]
    polys = [r.polygon for r in ribs if not r.polygon.is_empty]
    if not zone or not polys:
        return None
    cut = (float(law.tables.zones.adjacent_ground.groundside_cutback_m)
           + snap_margin_m(law))
    rib_u = unary_union(polys)
    zone_u = unary_union(zone)
    keep_off = air.buffer(float(rim_band), **_MITRE) if air is not None else None
    reach = rib_u.buffer(cut, **_MITRE)
    if not reach.intersects(zone_u):
        return None
    stand = reach.difference(rib_u).intersection(zone_u)
    # the sliver the stand-off leaves: zone ground that lies wholly within
    # the strip width of the ribbons beyond it
    w = float(law.tables.emit.terrace.strip_min_width_m)
    near = rib_u.buffer(cut + w, **_MITRE)
    left = zone_u.intersection(near).difference(stand).difference(rib_u)
    far = zone_u.difference(near)
    for p in shapely.get_parts(left):
        if p.geom_type == "Polygon" and not p.is_empty and p.distance(far) > 1e-6:
            stand = stand.union(p)
    if keep_off is not None:
        stand = stand.difference(keep_off)
    stand = shapely.set_precision(stand, 0.0)
    return None if stand.is_empty or stand.area <= 0.0 else stand


def apply_standoff(regions, stand):
    """``regions`` with every zone region's polygon less ``stand`` (the
    faces there are claimed by nothing: the terrace)."""
    if stand is None:
        return list(regions)
    out = []
    for r in regions:
        if r.source == "zone" and r.polygon.intersects(stand):
            g = r.polygon.difference(stand)
            parts = [p for p in shapely.get_parts(g)
                     if p.geom_type == "Polygon" and p.area > 0.0]
            for p in parts:
                out.append(_dc.replace(r, polygon=p))
            continue
        out.append(r)
    return out
