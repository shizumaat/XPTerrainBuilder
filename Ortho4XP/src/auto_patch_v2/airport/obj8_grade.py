"""THE AT-GRADE READ, MEMOISED PER RESOURCE (owner RULINGS 2026-09-13bp).

``obj8.at_grade_geometry`` / ``above_grade_footprint`` clipped and unioned
the same pack resource ONCE PER PLACEMENT.  VHHH: 5,078 custom objects over
785 resources and 74 basin rings — 2,626 s of a 3,800 s build inside
``unary_union`` and ``obj8_clip._clip_both``, ~25 MB retained per placement
(2.2 -> 10.0 GB in 7 minutes; the app's worker 34.9 GB), and untimed, so it
read as a hang.  The clip and the union depend only on ``(resource, the
components' clip planes)``: the placement affine is RIGID and commutes with
both, so it is applied afterwards and only IT is paid per placement.

Split from ``obj8.py`` under the 1,000-line file law, exactly as
``obj8_clip.py`` is; the laws and the readers stay there and nothing
numeric lives here but the plane quantum the ruling names.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import os
import time
import typing as _t

import numpy as np
from shapely.ops import unary_union

from .obj8_clip import _clip_both, _clip_component

if _t.TYPE_CHECKING:  # annotations only — obj8 imports this module
    from .obj8 import Component, ObjGeometry, PlacedObject, ResourceCache

__all__ = ["GradeStats", "planes", "memo_union", "both_clip", "above_clip"]


@_dc.dataclass
class GradeStats:
    """THE AT-GRADE READ, TIMED (owner RULINGS 2026-09-13bp (iii)).  The
    clip + union behind ``at_grade_geometry`` / ``above_grade_footprint``
    was UNTIMED, so VHHH's 2,626 s planar stage read as a hang: 5,078
    custom placements re-clipped and re-unioned FIVE pack resources once
    each, ~0.9 s and ~25 MB a placement.  ``calls`` is the placements
    asked, ``unions`` the clip+union actually run (one per distinct
    ``(resource, planes)`` key — (i)), ``vertices`` what those unions
    consumed and ``seconds`` what they cost.  ``vertex_budget`` (law
    ``[basin] rim_read_vertex_budget``, 0 = unbounded) is the REFUSAL: a
    pack past it stops being read and is named, instead of a silent 44
    minutes."""

    calls: int = 0
    unions: int = 0
    vertices: int = 0
    seconds: float = 0.0
    vertex_budget: int = 0
    over_budget: bool = False
    resources: set = _dc.field(default_factory=set)

    def charge(self, resource: str, vertices: int, seconds: float) -> None:
        self.unions += 1
        self.vertices += vertices
        self.seconds += seconds
        self.resources.add(resource)
        if self.vertex_budget and self.vertices > self.vertex_budget:
            self.over_budget = True

    def pack(self) -> str:
        """The pack the read is charged to — the resources' common root."""
        if not self.resources:
            return "(no resource)"
        paths = sorted(self.resources)
        try:
            return os.path.commonpath(paths)
        except ValueError:
            return os.path.dirname(paths[0])



#: The plane QUANTUM (metres) of the memo key.  The clip plane is the DEM
#: under a component's centroid minus the placement's render datum: a
#: continuous number that would make every placement its own key.  It is
#: rounded to the centimetre — the ONE rounding this memo introduces, and
#: the reason LEMD's and OTHH's basin rims are replayed for byte-identity.
_PLANE_QUANTUM = 2

#: the sentinel a memoised ``None`` clip must not be mistaken for
_MISS = object()


def planes(o: "PlacedObject", comps: list[tuple[int, "Component"]],
           dem_z: _t.Callable[[float, float], float], base: float, band: float,
           above: bool, to_frame) -> tuple[tuple[int, float], ...]:
    """``(component index, clip plane)`` for the components the read
    keeps, the plane quantised — the memo key's second half.  ``to_frame``
    is ``obj8``'s own authored-to-frame map (passed, not imported: this
    module must not import back into ``obj8``)."""
    out = []
    for ci, comp in comps:
        cx, cy = to_frame(o.xy, o.heading_deg, comp.cx, comp.cz)
        local = float(dem_z(cx, cy))
        if math.isnan(local):
            local = o.anchor_z
        plane = round(local - base + band if above else local - base - band, _PLANE_QUANTUM)
        if comp.max_y < plane:
            continue
        out.append((ci, plane))
    return tuple(out)


def above_clip(v: np.ndarray, comp: "Component", plane: float):
    """One component's above-plane geometry as the cover reader wants it."""
    return _clip_component(v, comp, plane, False)


def both_clip(v: np.ndarray, comp: "Component", plane: float):
    return _clip_both(v, comp, plane)


def memo_union(cache: "ResourceCache", memo: dict, o: "PlacedObject", g: "ObjGeometry",
               comps: list[tuple[int, "Component"]], keyed: tuple[tuple[int, float], ...],
               clip):
    """The resource's clipped geometry in ITS OWN frame for ``planes``,
    computed once and retained per ``(resource, planes)``.  ``clip`` is
    ``both_clip`` (linework + polygons) or ``above_clip`` (polygons).
    Past the vertex budget the read REFUSES — the pack is named by the
    caller and nothing further is clipped (RULINGS 2026-09-13bp (iii))."""
    st = cache.grade
    st.calls += 1
    key = (o.resolved, keyed)
    if key in memo:
        return memo[key]
    if st.over_budget:
        return None
    by_index = dict(comps)
    t0 = time.perf_counter()
    lines, polys, nv = [], [], 0
    # THE COMPONENT CLIP IS THE SECOND LEVEL.  A resource's components sit
    # at different planes (the DEM under each centroid), so two placements
    # rarely agree on ALL of them — but they agree on most, and the clip
    # (with ``_clip_both``'s own union inside it) is where the seconds are.
    cmemo = cache.clip_memo
    for ci, plane in keyed:
        comp = by_index.get(ci)
        if comp is None:
            continue
        ck = (o.resolved, ci, plane, clip is both_clip)
        out = cmemo.get(ck, _MISS)
        if out is _MISS:
            nv += int(comp.tris.shape[0]) * 3
            out = clip(g.vertices, comp, plane)
            cmemo[ck] = out
        if clip is both_clip:
            ln, pg = out
            if ln is not None:
                lines.append(ln)
            if pg is not None:
                polys.append(pg)
        elif out is not None:
            polys.append(out)
    pu = unary_union(polys) if polys else None
    if pu is not None and pu.is_empty:
        pu = None
    if clip is both_clip:
        lu = unary_union(lines) if lines else None
        if lu is not None and lu.is_empty:
            lu = None
        val = (lu, pu)
    else:
        val = pu
    memo[key] = val
    st.charge(o.resolved, nv, time.perf_counter() - t0)
    return val
