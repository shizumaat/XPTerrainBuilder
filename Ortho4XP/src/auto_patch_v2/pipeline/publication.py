"""The sidecar PUBLICATION — what the solver priced, in the shape the v1
census reads (``check_grade.law_context_from_sidecar``), keyed by the
vertices' canonical lat/lon identity so the census joins exactly.

* ``axes``: every constant-cap centreline axis
  (``constraints.transverse.axes``) as ``[[[lat, lon]…], cL, cT,
  ordinal, is_service]`` — the transverse walk's axes and the
  within-shape spine membership;
* ``crown_drops``: ``[lat, lon, drop]`` per runway-family vertex
  (``constraints.runway_profile.crown_drops``);
* ``airside_no_step_edges``: ``{a, b, budget_m, dist_m}`` per priced
  direct-distance pair (``constraints.no_step.no_step_edges``).
"""
from __future__ import annotations

import typing as _t

from ..constraints.no_step import no_step_edges
from ..constraints.roads import road_law_caps
from ..constraints.runway_profile import crown_drops
from ..constraints.transverse import axes
from ..law import Law
from ..model.airport import Airport
from ..model.planar import PlanarMap

__all__ = ["publication", "face_tags"]


def face_tags(planar: PlanarMap, law: Law) -> dict[int, dict[str, str]]:
    """Extra way tags: ``o4_grade_law_cap`` on roads bound to a stricter
    contiguous class (the census's way-level lateral-contiguity read)."""
    return {fid: {"o4_grade_law_cap": f"{cap:g}"}
            for fid, cap in road_law_caps(planar, law).items()}


def publication(planar: PlanarMap, law: Law, airport: Airport,
                z: _t.Sequence[float] | None = None) -> dict[str, _t.Any]:
    """The sidecar keys the solve's own pricing publishes; with ``z`` the
    crown drops are the BUILT ones."""
    ll = {vid: [v.key[0], v.key[1]] for vid, v in planar.vertices.items()}
    ax_out = []
    for k, a in enumerate(axes(planar, law)):
        ax_out.append([[ll[v] for v in a.vertices], a.cap_l, a.cap_t, k,
                       bool(a.is_service)])
    drops = [[ll[v][0], ll[v][1], d] for v, d in
             sorted(crown_drops(planar, law, airport, z).items())]
    edges = [{"a": ll[a], "b": ll[b], "budget_m": round(cap * d, 6),
              "dist_m": round(d, 4)} for a, b, cap, d in no_step_edges(planar, law)]
    return {"axes": ax_out, "crown_drops": drops,
            "airside_no_step_edges": edges}
