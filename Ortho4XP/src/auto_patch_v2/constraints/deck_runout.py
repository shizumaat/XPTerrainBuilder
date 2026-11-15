"""THE AIRSIDE RUN-OUT'S ROWS (#2062 spec R5; master ruling 2026-11-15 on
the owner's 13:50Z / 13:52Z reads; ``planar/deck_runout`` mints it).

A kept deck end whose ground route runs on over airside pavement
(``StackEnd.airside_run``) carries its road past the end line: on every
ground vertex of the end's corridor beyond the slab, the road's profile
``P(s)`` -- the deck end's top coming down at the road ramp grade
(``StackEnd.profile``) -- as a band ``[P - deck_flush_m, P]``
(:func:`runout_rows`, under the stack's ruling head).

THE AIRSIDE DOES NOT MOVE: between the stages (:func:`runout_rewrite`,
bound in ``road_ramp.reach_seed_rewrite``) each such row reads the airside
stage 1 solved beside it -- ``A``, the inverse-distance mean of the nearest
stage-1 levels -- and holds ``max(P, A)``: the road comes down until it
meets the airside, then lies on it.  Its bank to the apron is free ground.

Nothing here names a pack, a resource or an airport."""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

import numpy as np

from ..geom import exact as _exact
from ..model.constraints import Band, Row, Source

__all__ = ["RUN_TAG", "REPORT_KEY", "runout_rows", "runout_rewrite"]

#: the part tag of a run-out row (``Source.inputs[2]``)
RUN_TAG = "airside run-out"
#: the stage-2 report's key
REPORT_KEY = "deck_runout"
#: how many stage-1 neighbours the airside level beside a vertex is read on
_NEAR = 6


def runout_rows(planar, law, st, gen: str, ruling: str, skip: _t.AbstractSet[int]
                ) -> list[Row]:
    """A stack's run-out rows (module doc), on the vertices not in ``skip``
    (the road / hard vertices, the R1 / R3 rows)."""
    import shapely
    from shapely.geometry import Point

    from ..geom.deck_ground import end_corridor, path_line
    br = law.tables.structures.bridge
    flush, step = float(br.deck_flush_m), float(br.abutment_sample_step_m)
    grid = float(law.tables.emit.identity.min_distinct_spacing_m)
    ends = [e for e in st.ends if getattr(e, "airside_run", 0.0)]
    if not ends:
        return []
    allv = list(planar.vertices)
    axy = np.array([planar.vertices[v].xy for v in allv], float).reshape(-1, 2)
    rows: list[Row] = []
    z0 = float(st.zero_z)
    for e in ends:
        line = path_line(e, e.run)
        if line is None:
            continue
        zone = end_corridor(e, line, e.half_width).buffer(grid, join_style="mitre")
        for k in np.flatnonzero(shapely.contains_xy(zone, axy[:, 0], axy[:, 1])).tolist():
            v = allv[k]
            if v in skip:
                continue
            s = line.project(Point(axy[k]))
            if s <= step + 1e-9:
                continue                    # the slab: R1's
            p = e.profile(z0, s, step)
            rows.append(Band(v, p - flush, p, Source(
                gen, ruling, (st.id, e.object_id, f"{e.object_id} end {e.side} {RUN_TAG}"))))
    return rows


def _is_run(r) -> bool:
    ins = getattr(r.source, "inputs", ()) or ()
    return len(ins) >= 3 and str(ins[2]).endswith(RUN_TAG)


def runout_rewrite(planar, law, cs, levels: _t.Mapping[int, float]
                   ) -> "tuple[_t.Any, dict]":
    """``(cs with every run-out row held at max(P, A), report)`` (module
    doc).  The report lists per end the rows moved onto the airside and the
    station where the road meets it."""
    runs = [(i, r) for i, r in enumerate(cs.bands) if _is_run(r)]
    if not runs or not levels:
        return cs, {}
    flush = float(law.tables.structures.bridge.deck_flush_m)
    ids = np.array(list(levels), int)
    lxy = np.array([planar.vertices[int(v)].xy for v in ids], float).reshape(-1, 2)
    lz = np.array([float(levels[int(v)]) for v in ids], float)
    rep: dict[str, dict] = {}
    new: dict[int, Band] = {}
    for i, r in runs:
        xy = np.asarray(planar.vertices[r.v].xy, float)
        d = _exact.hypot_array(lxy[:, 0] - xy[0], lxy[:, 1] - xy[1])
        near = np.argsort(d)[:_NEAR]
        w = 1.0 / np.maximum(d[near], 0.5)
        a = float((w * lz[near]).sum() / w.sum())
        key = str(r.source.inputs[2])
        rec = rep.setdefault(key, {"rows": 0, "on_airside": 0, "max_over_airside_m": 0.0})
        rec["rows"] += 1
        p = float(r.hi)
        rec["max_over_airside_m"] = round(max(rec["max_over_airside_m"], p - a), 3)
        if a > p:
            rec["on_airside"] += 1
            new[i] = _dc.replace(r, lo=a - flush, hi=a)
    if not new:
        return cs, {"ends": rep}
    return (_dc.replace(cs, bands=tuple(new.get(i, r) for i, r in enumerate(cs.bands))),
            {"ends": rep})
