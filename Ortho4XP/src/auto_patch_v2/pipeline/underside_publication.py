"""THE ``unit_undersides`` AND ``perimeter_unserved`` SIDECAR KEYS (owner
RULINGS 2026-11-25m, 25n; spec ``docs/specs/underside-height-map-20261125.md``
§4 U25, step 1).

``unit_undersides``: one record per footprint unit with a ground contact
(``Airport.undersides``): its first row and row count, unit id(s), the
plan centre, station counts (all / airside / airside more than
``underside_admission.MIS_ZEROED_M`` off ``t``, 25n (2)), ``t`` and where
it was read, ``base``, the storey levels, relief, the below-grade
interiors by kind, the composite flag, and against the SOLVED surface:
the pad block under its ground contacts (``pad``; the airside contacts
first when it touches airside, 25n (2)), its level ``D`` (the median of
the pad's vertices), the S3 verdict and its numbers
(``underside_admission.admit``).  ``perimeter_unserved``: the perimeter
stations our ground does not reach (step 3 fills it; empty here).

REPORT keys: nothing in the solve or the census reads them (step 1)."""
from __future__ import annotations

import typing as _t

import numpy as np

__all__ = ["underside_records"]


def _pad_levels(planar, maps: _t.Sequence, z) -> list[tuple["str | None", "float | None"]]:
    """``(pad ref, level)`` per map: the ``building`` face holding most of
    its sampled contacts (``airport/underside_seat.contact_samples``) and
    the median solved height of its vertices; ``(None, None)`` off every pad or without ``z``."""
    import shapely
    from shapely.geometry import Polygon

    from ..airport.underside_seat import contact_samples
    faces = [(f.ref, planar.ring_vertices(f.ring)) for f in planar.faces.values()
             if f.role == "building"]
    polys = [Polygon([planar.vertices[v].xy for v in vs]).buffer(0.0) for _r, vs in faces]
    if not polys or z is None:
        return [(None, None)] * len(maps)
    tree = shapely.STRtree(polys)
    out = []
    for m in maps:
        e, n = contact_samples(m)
        if not len(e):
            out.append((None, None))
            continue
        _pi, fi = tree.query(shapely.points(e, n), predicate="within")
        if not len(fi):
            out.append((None, None))
            continue
        k = int(np.bincount(fi).argmax())
        vs = faces[k][1]
        out.append((str(faces[k][0]),
                    round(float(np.median([float(z[v]) for v in vs if v < len(z)])), 3)))
    return out


def underside_records(planar, airport, z=None) -> dict[str, list]:
    """``{"unit_undersides": [...], "perimeter_unserved": []}`` (module doc)."""
    from ..airport.underside_admission import MIS_ZEROED_M, admit
    from ..airport.underside_composite import dem_many
    maps = [m for m in (getattr(airport, "undersides", None) or {}).values()
            if not m.footless]
    if not maps:
        return {"unit_undersides": [], "perimeter_unserved": []}
    to_ll = airport.frame.transformers()[1]
    many = dem_many(airport.dem)
    recs = []
    for m, (pad, D) in zip(maps, _pad_levels(planar, maps, z), strict=True):
        verdict, det = admit(m, D, np.asarray(many(m.e, m.n), dtype=float))
        air = np.asarray(m.airside, dtype=bool)
        lat, lon = to_ll(float(np.mean(m.e)), float(np.mean(m.n)))
        recs.append({
            "row": str(m.key[0]), "rows": len(m.key), "unit": m.unit,
            "lat": round(float(lat), 7), "lon": round(float(lon), 7),
            "stations": int(len(m.e)), "airside": int(air.sum()),
            "airside_off": int(np.sum(np.abs(m.h[air] - m.t) > MIS_ZEROED_M)),
            "t": round(float(m.t), 3), "t_from": m.t_from,
            "base": None if m.base is None else round(float(m.base), 3),
            "levels": [round(v, 2) for v in m.levels], "relief": round(float(m.relief), 2),
            "interiors": {k: sum(1 for i in m.interiors if i.kind == k)
                          for k in ("open", "roofed")},
            "composite": bool(m.composite), "pad": pad, "D": D, "verdict": verdict, **det})
    return {"unit_undersides": recs, "perimeter_unserved": []}
