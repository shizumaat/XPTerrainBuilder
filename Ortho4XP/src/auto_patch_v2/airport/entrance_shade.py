"""A TUNNEL MOUTH IS NEVER A PAD (#1747; owner RULINGS 2026-11-06b (6)).

An ENTRANCE object — a pack trench object standing at a mapped tunnel's
end, read exactly as ``trench_objects.mouth_portals`` reads it (its face
within twice ``[tunnel.object] bore_end_tolerance_m`` of the end, its
solids there not standing over the ground) — is the mouth: the ground
meets its face and the ramp's ``tunnel_wall`` rim is the vertical wall
there.  Its walls and floor are no building, so no pad is minted from them.
MEASURED LOWS (lowsmouth1, 58e20d764): the cluster pads ``building18``
(west, 871 m2) and ``building26`` (east, 316 m2) were ``domiki_lows_48``'s
mouth components themselves, and the footprint-cache ring
``dsf:object373`` (``building25``, 1,898 m2) a v1 weld holding 23 of the
east mouth's wall triangles: all three levelled to their frontage, a
1.6 m bench at the east face.

THE SHADE is the plan of every solid COMPONENT of an entrance object that
reaches one of its mouths (within the face reach) and hangs at least
``shell_floor_min_m`` under the object's zero — a trench wall or floor,
never a house the same object carries.  It is derived ONCE, beside the
sunken ramps and the retaining walls (:func:`attach_entrance_shade`), and
travels as ``Airport.entrance_shade``: every pad reader takes it through
``geom.pad_shade_extra``, the one path, and the fallback mint refuses a
footprint-cache ring the shade reaches into (``classify/evidence``) —
that ring was welded from the mouth's walls and its members cannot be told
apart.  Nothing here names a pack, a resource or an airport.
"""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

import numpy as np
from shapely.ops import unary_union

from . import frame_entry as _fe
from . import obj8 as _obj8

__all__ = ["entrance_shade", "attach_entrance_shade"]


def _mouth_components(o: _obj8.PlacedObject, cache: _obj8.ResourceCache, ends, law) -> list:
    """The plans (airport frame) of ``o``'s MOUTH components: each solid
    component hanging ``shell_floor_min_m`` under its zero that comes
    within the face reach (``mouth_portals``') of one of ``ends``, or
    touches one that does within ``[placement] footprint_touch_m`` (a
    ramp's trench walls run on from its face)."""
    from .trench_objects import _near_solids, _outline
    g = cache.geometry(o.resolved)
    if g is None:
        return []
    ob = law.tables.structures.tunnel.object
    reach, floor_min = 2.0 * float(ob.bore_end_tolerance_m), float(ob.shell_floor_min_m)
    touch, q = float(law.tables.structures.placement.footprint_touch_m), _fe.quantum(law)
    hits = [got[2] for got in (_near_solids(o, g, xy, reach) for xy in ends) if got is not None]
    if not hits:
        return []
    near = np.unique(np.concatenate(hits))
    deep = [c for c in cache.components(o.resolved) if c.idx is not None and c.min_y <= -floor_min]
    plans = _fe.enter([_outline(g, q, c.idx) for c in deep],
                      _obj8.placement_affine(o.xy, o.heading_deg), q)
    keep = {k for k, c in enumerate(deep) if plans[k] is not None and np.isin(c.idx, near).any()}
    grow = list(keep)
    while grow:
        k = grow.pop()
        for j, p in enumerate(plans):
            if j not in keep and p is not None and p.distance(plans[k]) <= touch:
                keep.add(j)
                grow.append(j)
    return [plans[k] for k in sorted(keep)]


def entrance_shade(airport, objects: _t.Sequence[_obj8.PlacedObject],
                   cache: _obj8.ResourceCache, law):
    """The planar-frame union of every entrance object's mouth components
    (module doc), or ``None``."""
    from .deck_signature import is_tunnel_way
    from .trench_objects import mouth_portals, read_trench_objects
    dem = getattr(airport, "dem", None)
    if law is None or cache is None or not objects or dem is None:
        return None
    tunnel_ways = [w for w in airport.osm_ways
                   if is_tunnel_way(w.tags, law.tables.structures.tunnel.admitted_values)
                   and len(w.points) >= 2]
    if not tunnel_ways:
        return None
    trenches, _notes = read_trench_objects(objects, cache, law, tunnel_ways)
    pins = mouth_portals(trenches, objects, cache, law, tunnel_ways, dem.z)
    ends: dict[str, list] = {}
    for p in pins:
        ends.setdefault(p.object_id, []).append(p.end_xy)
    by_id = {o.id: o for o in objects}
    polys = [q for oid in sorted(ends) if oid in by_id
             for q in _mouth_components(by_id[oid], cache, ends[oid], law)]
    if not polys:
        return None
    got = unary_union(polys)
    if not got.is_valid:
        got = got.buffer(0.0)
    return None if got.is_empty else got


def attach_entrance_shade(airport, objects, cache, law):
    """``airport`` with :attr:`Airport.entrance_shade` derived — called once
    beside :func:`airport.wall_shade.attach_wall_shade` (``pipeline/build``,
    the replay)."""
    if getattr(airport, "frame", None) is None:
        return airport
    return _dc.replace(airport, entrance_shade=entrance_shade(airport, objects, cache, law))
