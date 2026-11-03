"""A ROAD ALONG A LOT THAT CLIMBS TO A RAISED PAD STAYS ROAD (owner Q366 "A",
2026-11-03, issue #684): "where a road along a lot is climbing to a raised
pad or structure, that stretch stays road and keeps its climb; the rest of
the road along the lot still joins the lot."

``classify/lot_roads`` relabels a mapped road's stretch along a lot as that
lot (RULINGS 2026-10-14a (2)).  Whether the road is CLIMBING there is not
known at classify: the climb is §37 (6)'s ramp from the road's airside
contact (a pad, its landing fill, an apron) down to the floor
(``airport/road_ramp``), and its contact levels are the target channels
published in the prefix.  So it is read ONCE, here, right before the ramp's
own derivation (``pipeline/prefix``): the ramp is derived on the map with
every lot strip read as the road it was cut from — the road's course before
the relabel — and a strip any of whose vertices stands on that ramp (over
its floor, ``road_ramp.STAND_M``) is returned to its road: role
``service_road``, ref ``<feed>:<way id>#lot<k>`` (a ribbon ref, so every
road law reads it), before the ramp, the shapes and the generators run.

MEASURED HECA (lane f684, arm X): ``dsf:pol10#road2`` (60 m of
``small_roads:-3964``, climbing 91 -> 100 m to ``building5``'s landing
run-outs) and ``dsf:objpav3#road0`` (``small_roads:-18656`` beside
``building126``) held under lot law minted 63 hard conflicts and moved
``runout:building5/landing2#collar`` 1.25 m; left road, 817 hard conflicts
against the base's 829 and the collar 0.23 m."""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

from ..law import Law
from ..model.airport import Airport
from ..model.planar import PlanarMap, is_lot_road_ref

__all__ = ["with_lot_road_climbs"]

#: The role a strip returns to: the ribbon mint's own (``classify/ribbon_mint``).
ROAD_ROLE = "service_road"


def with_lot_road_climbs(pm: PlanarMap, law: Law, airport: Airport,
                         report: dict[str, _t.Any] | None = None, *,
                         service=None) -> PlanarMap:
    """``pm`` with every lot strip face on a road's climb returned to its
    road (module doc; a strip the map split is read face by face).
    ``report`` gets ``lot_strips`` / ``lot_strips_on_climb`` (faces) and
    the refs returned."""
    from .road_ramp import mouth_wall_pieces, road_ramp_targets, wall_pieces
    strips = {fid: f for fid, f in pm.faces.items()
              if is_lot_road_ref(f.ref) and f.ref in pm.lot_road_ways}
    rep: dict[str, _t.Any] = {"lot_strips": len(strips), "lot_strips_on_climb": 0,
                              "returned": []}
    if strips:
        as_road = _dc.replace(pm, faces={
            fid: (_dc.replace(f, role=ROAD_ROLE) if fid in strips else f)
            for fid, f in pm.faces.items()})
        walls = wall_pieces(airport, service) + mouth_wall_pieces(as_road)
        tg = road_ramp_targets(as_road, law, airport, None,
                               tuple(w.poly for w in walls if w.retains))
        on = tg.report.get("_on_ramp") or frozenset()
        climbing = [fid for fid, f in sorted(strips.items())
                    if any(v in on for ring in (f.ring, *f.holes)
                           for v in pm.ring_vertices(ring))]
        if climbing:
            pm = _returned(pm, climbing)
        rep["lot_strips_on_climb"] = len(climbing)
        rep["returned"] = [strips[fid].ref for fid in climbing]
    if report is not None:
        report.update(rep)
    return pm


def _returned(pm: PlanarMap, fids: _t.Sequence[int]) -> PlanarMap:
    """``pm`` with the strip faces ``fids`` given back to their roads."""
    serial: dict[str, int] = {}
    faces = dict(pm.faces)
    for fid in fids:
        f = faces[fid]
        way = pm.lot_road_ways[f.ref]
        k = serial.get(way, 0)
        serial[way] = k + 1
        faces[fid] = _dc.replace(f, role=ROAD_ROLE, ref=f"{way}#lot{k}")
    left = {f.ref for f in faces.values() if is_lot_road_ref(f.ref)}
    return _dc.replace(pm, faces=faces, lot_road_ways={
        r: w for r, w in pm.lot_road_ways.items() if r in left})
