"""ROAD ↔ CORE PROFILE AGREEMENT (RULINGS 2026-09-04t-4; M3c).

The contract this reads: a road-family vertex's solved value equals the
core's clamped, laterally-levelled road profile (``PlanarMap.preferred_z``)
except where a law row binds — so the mean |z − profile| per road face
is the measure of "v2 smoothing added", and a face with no binding row
reads 0 within materiality.  A report figure, not a census family: the
profile is a PREFERENCE, never a cap (the caps are priced by
``within_shape`` / ``road_cross_section`` / ``lateral_contiguity``).
"""
from __future__ import annotations

import typing as _t

from ..law import Law
from ..model.planar import PlanarMap

__all__ = ["road_profile_agreement"]


def road_profile_agreement(pm: PlanarMap, law: Law, z: _t.Sequence[float],
                           roles: _t.Iterable[str] | None = None
                           ) -> dict[str, _t.Any]:
    """Per road-family face: vertices with a preferred value, mean and
    max |z − preferred|, vertices off the profile beyond materiality;
    plus the whole-population figures.  ``roles`` defaults to the faces
    that own a preferred vertex."""
    tol = law.tables.emit.materiality.elevation_m
    pref = pm.preferred_z
    faces: dict[int, dict[str, _t.Any]] = {}
    want = set(roles) if roles is not None else None
    for fid, f in pm.faces.items():
        if want is not None and f.role not in want:
            continue
        vs = set()
        for cyc in (f.ring, *f.holes):
            for eid in cyc:
                e = pm.edges[eid]
                vs.add(e.a)
                vs.add(e.b)
        devs = [abs(z[v] - pref[v]) for v in vs if v in pref]
        if not devs:
            continue
        faces[fid] = {"role": f.role, "ref": f.ref, "vertices": len(vs),
                      "preferred": len(devs),
                      "mean_m": round(sum(devs) / len(devs), 4),
                      "max_m": round(max(devs), 4),
                      "off": sum(1 for d in devs if d > tol)}
    all_devs = [abs(z[v] - pv) for v, pv in pref.items()]
    return {"faces": faces,
            "vertices": len(all_devs),
            "mean_m": round(sum(all_devs) / len(all_devs), 4) if all_devs else 0.0,
            "max_m": round(max(all_devs), 4) if all_devs else 0.0,
            "off": sum(1 for d in all_devs if d > tol),
            "faces_off": sum(1 for r in faces.values() if r["off"])}
