"""ROADS ALONG A LOT ARE THE LOT, SETTLED ONCE AT THE RAMP (owner RULINGS
2026-10-14a (2); issue #684, owner Q366 "A" 2026-11-03: "where a road along
a lot is climbing to a raised pad or structure, that stretch stays road and
keeps its climb; the rest of the road along the lot still joins the lot").

``classify/lot_roads`` splits a mapped road's stretch along a lot off as a
LOT CANDIDATE — a ribbon cell, so every reader up to here (the planar
arrangement, the road profile, the ramp's own derivation) reads it as the
road it is (``PlanarMap.lot_candidates``: candidate ref -> lot ref).
Whether the road CLIMBS there is §37 (6)'s answer, so the candidate is
settled HERE, once, inside ``road_ramp.with_road_ramp`` right after
``road_ramp_targets`` and before anything is published from it; the build
and the replay share it by construction:

* a candidate face with a vertex on the ramp (over its floor,
  ``road_ramp.STAND_M``: ``report['_on_ramp']``) STAYS ROAD;
* so does one with a vertex on a declared wall terrace — the terrace's
  foot, a wall's upper or lower side (10-03c) — or between two levels
  (29x), while ``[road_contact] lot_road_wall_keeps`` (the owner's Q-wall;
  HECA ``small_roads:-18656`` at #507's ``metal_strip_2``);
* every other candidate face becomes its LOT: the lot's role, side and
  code, ref ``<lot ref>#road<k>`` (``model.planar.is_lot_road_ref``), its
  ramp targets, route frame and contacts withdrawn from every vertex no
  road owns any more, and the road profile's fit from every one no face
  with a road axis carries.  A candidate whose lot has no standing face
  stays road (``lot_gone``).

MEASURED HECA (lane f684, arm X): ``dsf:pol10``'s strip of
``small_roads:-3964`` (climbing 91 -> 100 m to ``building5``'s landing
run-outs) and ``dsf:objpav3``'s of ``small_roads:-18656`` held under lot
law minted 63 hard conflicts and moved ``runout:building5/landing2#collar``
1.25 m; left road, 817 hard conflicts against the base's 829 and the
collar 0.23 m."""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

from ..law import Law
from ..model.planar import LOT_ROAD_MARK, PlanarMap, is_lot_road_ref

__all__ = ["settle_lot_candidates"]


def settle_lot_candidates(pm: PlanarMap, law: Law, tg, report: dict | None = None, *,
                          walls: _t.Sequence = (), service=None):
    """``(pm, tg)`` with every lot candidate face settled (module doc): the
    map with the settled faces as their lots, and the ramp targets
    (``road_ramp.RampTargets``) less every vertex that left the road.
    ``walls`` / ``service``: the ramp's own wall pieces and ``[service]``
    thresholds (the wall-terrace read).  ``report`` gets ``lot_candidates``,
    ``lot_settled``, ``lot_kept_road``, ``lot_gone`` and ``lot_kept_refs``."""
    from .road_ramp import _owned, _road_roles
    on = tg.report.pop("_on_ramp", None) or frozenset()
    cands = {fid: f for fid, f in pm.faces.items() if f.ref in pm.lot_candidates}
    rep: dict[str, _t.Any] = {"lot_candidates": len(cands), "lot_settled": 0,
                              "lot_kept_road": 0, "lot_gone": 0, "lot_kept_refs": []}
    if report is not None:
        report.update(rep)
    if not cands:
        return pm, tg
    held = set(on)
    if law.tables.emit.road_contact.lot_road_wall_keeps:
        held |= _wall_held(pm, law, tg, walls, service)
    stand: dict[str, _t.Any] = {}
    for fid in sorted(pm.faces):
        stand.setdefault(pm.faces[fid].ref, pm.faces[fid])
    serial = _lot_serials(pm)
    faces, kept, named = dict(pm.faces), [], {}
    for fid, f in sorted(cands.items()):
        lot = stand.get(pm.lot_candidates[f.ref])
        if lot is None:
            rep["lot_gone"] += 1
        elif any(v in held for v in _face_vertices(pm, f)):
            kept.append(f.ref)
        else:
            if f.ref not in named:      # a candidate's faces settle under one ref
                k = serial.get(lot.ref, 0)
                serial[lot.ref] = k + 1
                named[f.ref] = f"{lot.ref}{LOT_ROAD_MARK}{k}"
            faces[fid] = _dc.replace(f, role=lot.role, ref=named[f.ref],
                                     side=lot.side, code_number=lot.code_number,
                                     code_letter=lot.code_letter)
            rep["lot_settled"] += 1
    rep["lot_kept_road"] = len(kept)
    rep["lot_kept_refs"] = sorted(set(kept))[:6]
    if report is not None:
        report.update(rep)
    if not rep["lot_settled"]:
        return pm, tg
    standing = {f.ref for f in faces.values()}
    out = _dc.replace(pm, faces=faces, pad_roads=frozenset(pm.pad_roads & standing),
                      lot_candidates={r: lot for r, lot in pm.lot_candidates.items()
                                      if r in standing})
    roads = _road_roles(law)
    lost = set(_owned(pm, roads, law)) - set(_owned(out, roads, law))
    out = _dc.replace(out, preferred_z=_profiled(out, law, cands))
    return out, _without(tg, lost)


def _face_vertices(pm: PlanarMap, f) -> list[int]:
    return [v for ring in (f.ring, *f.holes) for v in pm.ring_vertices(ring)]


def _lot_serials(pm: PlanarMap) -> dict[str, int]:
    """Per lot ref, one past the largest ``#road<k>`` a face already carries."""
    out: dict[str, int] = {}
    for f in pm.faces.values():
        if is_lot_road_ref(f.ref):
            lot, _sep, k = str(f.ref).rpartition(LOT_ROAD_MARK)
            out[lot] = max(out.get(lot, 0), int(k) + 1)
    return out


def _wall_held(pm: PlanarMap, law: Law, tg, walls, service) -> set[int]:
    """The road vertices on a declared wall terrace or between two levels,
    read on the map with every candidate still a road (Q-wall)."""
    from .road_ramp import _owned, _road_roles, between_levels, road_terrace, wall_terraces
    owned = _owned(pm, _road_roles(law), law)
    out = set(between_levels(pm, law, owned).get("road") or {})
    retaining = tuple(w.poly for w in walls if w.retains)
    terr = road_terrace(pm, law, owned, tg.frame, tuple(w.poly for w in walls), retaining)
    out |= set(terr.get("foot") or {})
    if walls and service is not None:
        for rec in wall_terraces(pm, law, walls, terr,
                                 float(service.retaining_wall_reach_m)).values():
            out |= set(rec.get("upper", ())) | set(rec.get("lower", ()))
    return out


def _profiled(pm: PlanarMap, law: Law, cands) -> dict[int, float]:
    """``pm.preferred_z`` less every vertex of a settled face that no face
    with a road axis (``road_profile.axis_roles``: a parking lot has none)
    carries any more — the core's fit it had only as the road."""
    from .road_profile import axis_roles
    axis = set(axis_roles(law))
    gone = set()
    for fid in cands:
        if pm.faces[fid].ref in pm.lot_candidates:
            continue
        for v in _face_vertices(pm, pm.faces[fid]):
            if not any(pm.faces[g].role in axis for g in pm.vertices[v].incident_faces
                       if g in pm.faces):
                gone.add(v)
    return {v: z for v, z in pm.preferred_z.items() if v not in gone}


def _without(tg, lost: _t.AbstractSet[int]):
    """The ramp targets ``tg`` less every vertex in ``lost``."""
    if not lost:
        return tg
    rep = dict(tg.report)
    for key in ("_contact_edge", "_contact_gap"):
        if key in rep:
            rep[key] = {v: x for v, x in rep[key].items() if v not in lost}
    return tg._replace(targets={v: z for v, z in tg.targets.items() if v not in lost},
                       report=rep,
                       frame={v: x for v, x in tg.frame.items() if v not in lost})
