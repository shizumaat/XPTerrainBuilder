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
  direct-distance pair (``constraints.no_step.no_step_edges``);
* ``seam_pins``: ``[lat, lon]`` per tile-seam DEM pin the solve honoured
  (``constraints.seams``) — the census skips pin↔pin pairs and prices
  pin↔free pairs at the body cap (user 2026-07-04);
* ``station_caps``: ``[lat, lon, cap]`` per road station
  (``constraints.contiguity``) — the lateral-contiguity fourth reader
  (2026-08-28 Amendment 2).
"""
from __future__ import annotations

import typing as _t

from ..constraints.contiguity import road_station_caps
from ..constraints.no_step import no_step_edges
from ..constraints.roads import road_law_caps
from ..constraints.runway_profile import crown_drops
from ..constraints.seams import seam_pins, seam_vertices_pinned
from ..constraints.transverse import axes
from ..law import Law
from ..model.airport import Airport
from ..model.planar import PlanarMap

__all__ = ["publication", "face_tags"]


def face_tags(planar: PlanarMap, law: Law, airport: Airport | None = None
              ) -> dict[int, dict[str, str]]:
    """Extra way tags: ``o4_grade_law_cap`` on roads bound to a stricter
    contiguous class (the census's way-level lateral-contiguity read)."""
    return {fid: {"o4_grade_law_cap": f"{cap:g}"}
            for fid, cap in road_law_caps(planar, law, airport).items()}


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
    tol = law.tables.emit.materiality.elevation_m
    seam_all = seam_vertices_pinned(seam_pins(planar, law, airport))
    pins = sorted(seam_all)
    if z is not None:
        pins = [v for v in pins if abs(z[v] - planar.vertices[v].dem_z) <= tol]
    # the pairs the solver priced: a pin↔pin pair was exempt in the solve
    # (constraints.seam_exempt) and is not published — the census prices
    # exactly the published list
    edges = [{"a": ll[a], "b": ll[b], "budget_m": round(cap * d, 6),
              "dist_m": round(d, 4)} for a, b, cap, d in no_step_edges(planar, law)
             if not (a in seam_all and b in seam_all)]
    # THE FOURTH READER'S VECTOR (2026-08-28 Amendment 2): every road
    # station with a verdict, ``[lat, lon, cap]`` in the frame's own
    # inverse — the census joins by nearest station
    _to_xy, to_ll = airport.frame.transformers()
    stations = []
    for fid, sts in sorted(road_station_caps(planar, law, airport).items()):
        for st in sts:
            if st.cap is None:
                continue
            la, lo = to_ll(*st.xy)
            stations.append([round(la, 8), round(lo, 8), st.cap])
    return {"axes": ax_out, "crown_drops": drops,
            "airside_no_step_edges": edges,
            "seam_pins": [ll[v] for v in pins],
            "station_caps": stations}
