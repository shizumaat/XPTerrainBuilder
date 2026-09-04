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
  (2026-08-28 Amendment 2);
* ``basin_facilities`` (M4b): one record per basin the map carries, in
  the v1 emitter's key shape (``check_grade._basin_facilities_declared``
  reads ``floor_m`` / ``rim_law_m`` / ``body_depth_m`` /
  ``solid_minimum_y_m`` / ``anchor_longitude_latitude`` /
  ``emitted_rim_parts_m``): the floor and the rim estimate the planar
  builder keyed, the wall crest values the SOLVE gave (with ``z``), the
  deepest solid relative to ``R_est`` and its negation as the body depth
  (one instrument read once — the disagreement gate is vacuous by
  construction, RULINGS 2026-08-26 §2.2).
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
            "station_caps": stations,
            "basin_facilities": basin_facilities(planar, law, z)}


def basin_facilities(planar: PlanarMap, law: Law,
                     z: _t.Sequence[float] | None = None) -> list[dict[str, _t.Any]]:
    """The basin records (see the module docstring)."""
    out: list[dict[str, _t.Any]] = []
    if not planar.basins:
        return out
    br = law.tables.structures.bridge
    bl = law.tables.structures.basin
    by_ref: dict[str, list[int]] = {}
    for f in planar.faces.values():
        for cyc in (f.ring, *f.holes):
            by_ref.setdefault(f.ref.split("#")[0], []).extend(planar.ring_vertices(cyc))
    for b in planar.basins:
        wall_vs = sorted(set(by_ref.get(b.wall_ref, ())))
        rim_parts = sorted({round(float(z[v]), 2) for v in wall_vs}) if z is not None else []
        lat, lon = b.anchor_ll
        out.append({
            "resources": list(b.objects),
            "anchor_longitude_latitude": [lon, lat],
            "rim_estimate_m": round(b.rim_estimate_m, 3),
            "floor_m": round(b.floor_z, 3),
            "rim_law_m": round(b.rim_estimate_m, 3),
            "emitted_rim_min_m": rim_parts[0] if rim_parts else None,
            "emitted_rim_max_m": rim_parts[-1] if rim_parts else None,
            "emitted_rim_part_count": len(rim_parts),
            "emitted_rim_parts_m": rim_parts,
            "solid_minimum_y_m": round(b.solid_min_y_m, 3),
            "body_depth_m": round(-b.solid_min_y_m, 3),
            "rendered_solid_min_m": round(b.solid_min_z, 3),
            "margins_m": round(br.floor_below_object_deck_m + bl.seat_margin_m, 3),
            "covered_fraction": round(b.covered_fraction, 4),
            "area_m2": round(b.area_m2, 1),
            "floor_ref": b.floor_ref,
            "wall_ref": b.wall_ref,
            "floor_plates": len(planar_faces_of_ref(planar, b.floor_ref)),
            "shell_count": len(b.objects),
        })
    return out


def planar_faces_of_ref(planar: PlanarMap, ref: str) -> list[int]:
    return [f.id for f in planar.faces.values() if f.ref.split("#")[0] == ref]
