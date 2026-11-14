"""THE FENCE YARD STANDS ON THE FENCE-FOOT PLANE (spec
``2068-fence-grade-spec-A2.md`` F3; the yard is ``classify/fence_yard``'s).

A PROJECTION AFTER THE WHOLE SOLVE, on the final ``z``, as the §52 facade
strips are (``solve/project_strip.project_facade_strips``, which calls
this): every vertex of a ``fenceyard:<k>:<pad>`` face takes

    z = L + plane(x, y) - y_p

with ``plane`` the fence-foot plane the upper level's landing record
carries (``planar/group_up``, ``yard_plane``: the fence's authored base
over the frame), ``y_p`` the storey's base and ``L`` the solved level of
the record's own ``<block>/p<k>`` faces.  The yard mints no row and the
level is read, never written.  A vertex an AIRSIDE-side face carries is
never moved (airside is king); a vertex any other standing face carries
YIELDS too, counted in ``yielded`` (expected 0: the yard was cut off every
cell standing with the §52 stand-off)."""
from __future__ import annotations

import typing as _t

from ..geom.capped_plane import plane_at
from ..law import Law
from ..law.tables import role_side
from ..model.planar import PlanarMap, fence_yard_pad

__all__ = ["project_fence_yards"]


def project_fence_yards(planar: PlanarMap, law: Law, z: _t.Sequence[float]
                        ) -> "tuple[tuple[float, ...], dict | None]":
    """The new ``z`` and the report, or ``z`` unchanged and ``None`` when
    the map holds no fence yard."""
    yards = [f for f in planar.faces.values() if fence_yard_pad(f.ref) is not None]
    if not yards:
        return tuple(z), None
    lands = getattr(planar.registries, "landings", None) or {}
    by_pad = {str(r.get("pad")): (lv, r) for lv, r in lands.items() if r.get("yard_plane")}
    out = [float(v) for v in z]
    users: set[int] = set()
    airside: set[int] = set()
    levels: dict[str, list[int]] = {}
    for f in planar.faces.values():
        if fence_yard_pad(f.ref) is not None:
            continue
        vs = _face_vertices(planar, f)
        users |= vs
        if role_side(law, f.role) == "airside":
            airside |= vs
        levels.setdefault(str(f.ref), []).extend(vs)
    rep: dict[str, _t.Any] = {"yards": [], "vertices": 0, "yielded": 0, "airside": 0,
                              "no_level": 0}
    done: set[int] = set()
    for f in sorted(yards, key=lambda f: f.id):
        got = by_pad.get(str(fence_yard_pad(f.ref)))
        lv_vs = [v for v in levels.get(got[0], ()) if v < len(out)] if got else []
        if not lv_vs:
            rep["no_level"] += 1
            continue
        lv, rec = got
        L = sum(out[v] for v in lv_vs) / len(lv_vs)
        pl = tuple(float(c) for c in rec["yard_plane"])
        y_p = float(rec.get("y_p", 0.0))
        lo, hi = float("inf"), float("-inf")
        for v in sorted(_face_vertices(planar, f)):
            if v >= len(out) or v in done:
                continue
            done.add(v)
            if v in users:
                rep["airside" if v in airside else "yielded"] += 1
                continue
            x, y = planar.vertices[v].xy
            out[v] = L + float(plane_at(pl, x, y)) - y_p
            lo, hi = min(lo, out[v]), max(hi, out[v])
            rep["vertices"] += 1
        rep["yards"].append({"face": f.id, "ref": f.ref, "level": lv, "L": round(L, 3),
                             "z": [round(lo, 3), round(hi, 3)] if hi >= lo else None})
    return tuple(out), rep


def _face_vertices(planar: PlanarMap, f) -> set[int]:
    """Every vertex of face ``f``'s rings."""
    return {v for ring in (f.ring, *f.holes) for v in planar.ring_vertices(ring)}
