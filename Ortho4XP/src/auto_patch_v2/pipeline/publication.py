"""The sidecar PUBLICATION — what the solver priced, in the shape the v1
census reads (``check_grade.law_context_from_sidecar``), keyed by the
vertices' canonical lat/lon identity so the census joins exactly.

* ``axes``: every constant-cap centreline axis
  (``constraints.transverse.axes``) as ``[[[lat, lon]…], cL, cT,
  ordinal, is_service]`` — the transverse walk's axes and the
  within-shape spine membership;
* ``stretches``: every taxi centreline STRETCH (RULINGS 2026-09-04t-3,
  ``constraints.stretches``) as ``[[[lat, lon]…], cL, letter, ref]`` —
  the per-stretch pair law v2 verify re-composes (v1's oracle reads the
  stretch caps through ``axes``);
* ``face_holes`` is NOT published here (RULINGS 2026-09-13da residual):
  the emit's shore weld and sub-spacing merge reshape rings AFTER this
  publication, so the patch writer derives the key from the surface it
  writes (``emit/osm_adapter.face_holes_ll``) — the oracle's visibility
  polygon is the face with the holes its EMITTED rings bound;
* ``mesh_edges``: every junction-mesh face's triangle-mesh edges
  (RULINGS 2026-09-04y, ``constraints.junction_mesh``) as
  ``[[lat, lon], [lat, lon]]`` — the v1 oracle's JUNCTION MESH RULE
  consumes them 1:1 (``MeshEdgesExact``) and v2 verify prices exactly
  these edges at the nearest-stretch cap;
* ``crown_drops``: ``[lat, lon, drop]`` per runway-family vertex
  (``constraints.runway_profile.crown_drops``);
* ``airside_no_step_edges``: ``{a, b, budget_m, dist_m}`` per priced
  route pair (``constraints.no_step.no_step_edges``, ``dist_m`` = the
  ROUTE distance, 04o);
* ``pad_pavement_no_step_edges``: the same record per PAD CONTACT↔
  PAVEMENT route pair (RULINGS 2026-09-04r,
  ``constraints.no_step.pad_pavement_edges``: from an attached pad's
  contact vertices along pavement, the pavement list's own pairs not
  repeated) — its own key because the v1 oracle's proximity join
  resolves a pad endpoint to a mixed pad's 0.5 m groundside cut-back
  node (measured SPJC: 70 false 7.2 m rows); v2 verify prices it by
  identity;
* ``taxi_route_pairs``: ``[[lat, lon], [lat, lon], budget_m, dist_m]`` per
  taxi-family within-shape pair priced over the CENTRELINE ROUTE
  (RULINGS 2026-09-05ab, ``constraints.taxi.taxi_pair_routes``; 05ac:
  the solve states the law by the chain, the reader prices every pair
  over its route): the pair's least ``Σ cap·len`` over the routes, and
  ``[a, b, null, null]`` for a pair no route joins (no law edge).
  EVERY routed pair whose route budget differs from ``cap × chord`` by
  more than the elevation materiality is published, in BOTH directions
  — a looser route too, or the reader mints a chord row the chain
  permits.  A z-aware pruning (looser pairs only where the SOLVED
  surface exceeded the chord) was measured at HECA 2026-09-05 and
  withdrawn: one stub pair on the 05C/23C edge sat 0.1 mm inside its
  chord bound at the solve and read 0.035 m over it in the emitted
  patch (the emit quantum and the crown-lifted reading) — the prune
  cannot mirror the reader, so it does not try (HECA: 237k pairs,
  ~10 MB of sidecar beside the 87k the prune kept);
* ``seam_pins``: ``[lat, lon, dem_z]`` per tile-seam DEM pin — EVERY
  one (§38 (1), owner RULINGS 2026-09-13ah: a pin holds exactly, so there
  is no "honoured" subset).  The census skips pin↔pin pairs, prices
  pin↔free pairs at the body cap (user 2026-07-04) and prices the
  EMITTED value against ``dem_z`` as the ``seam_residual`` family;
* ``seam_half_width_m``: the band's own half width, so ``bank_across_seam``
  reads "inside the band" from the law the build ran under;
* ``station_caps``: ``[lat, lon, cap]`` per road station
  (``constraints.contiguity``) — the lateral-contiguity fourth reader
  (2026-08-28 Amendment 2);
* ``lifted_caps`` (§34 (9), owner RULINGS 2026-09-14ak/14am): ``[shapeID,
  corridor, road ref, span m, designed grade]`` per PINCHED RAMP face —
  the report record, never law input.  The LIFT itself rides on the way as
  ``o4_grade_law_cap_lifted`` (:data:`LIFTED_CAP_TAG`) for the v1 census
  and through ``Patch.of(lifted_caps=…)`` for v2 verify;
* ``terrace_joints`` (owner RULINGS 2026-09-08k): one record per shape
  joint (``planar/shapes.py``), v1's record shape — the joint line, the
  emitted step — ``terrace_joints_ll``;
* ``design`` / ``design_target`` (RULINGS 2026-09-08t/v, added by
  ``pipeline/build.py`` where the solve's report lives): the design
  surface's residual per family, and one record per law row the surface
  MISSED (``family``, ``miss_m``, the vertices' ``ll``) — the census
  counts those rows law-true in their families and reports them under the
  ``design_target`` heading;
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
from ..constraints.eat import eat_rects as _eat_rects


def _renode_rows(airport) -> "list | None":
    """§16g (10) (12) (2): the airside nodes the PAD STAGE minted or
    deleted, as ``[lat, lon, kind]``, read verbatim out of the
    arrangement's own publication (``planar/overlay.PAD_AIRSIDE``) and
    converted in the airport's own frame.  Never re-derived: the only
    place the two node sets both exist is inside the arrangement."""
    from ..planar.overlay import PAD_AIRSIDE
    out: list = []
    if "renode_minted" not in PAD_AIRSIDE:
        # THE ARRANGEMENT DID NOT RUN IN THIS PROCESS — a ``v2_solve_replay``
        # arm resumes from a captured planar map, so the pad stage's own
        # reading does not exist here.  Return ``None``, and the caller
        # OMITS the key: an ABSENT key means NOT MEASURED and an empty list
        # means MEASURED ZERO.  Publishing ``[]`` either way would make
        # every replay arm read a perfect ``pad_airside_renode`` — the
        # silent-degradation class this project refuses.
        return None
    if not PAD_AIRSIDE:
        return out
    _to_xy, to_ll = airport.frame.transformers()
    for key, kind in (("renode_deleted_xy", "deleted"),
                      ("renode_minted_xy", "minted")):
        for x, y in (PAD_AIRSIDE.get(key) or ()):
            lat, lon = to_ll(float(x), float(y))
            out.append([round(float(lat), 11), round(float(lon), 11), kind])
    return out

from ..constraints.junction_mesh import mesh_edges_ll
from ..constraints.no_step import no_step_edges, pad_pavement_edges
from ..constraints.roads import road_law_caps
from ..constraints.runway_profile import crown_drops, runway_half_widths
from ..constraints.runway_yield import RunwayCap as _RunwayCap
from ..constraints.seams import seam_pins, seam_vertices_pinned
from ..constraints.stretches import stretches
from ..constraints.taxi import taxi_pair_routes
from ..constraints.transverse import axes
from ..law import Law
from ..constraints.cluster_pad import pad_cluster_mismatch as _pad_cluster_mismatch
from ..constraints.pad_relief import pad_relief_offsets
from ..model.airport import Airport
from ..model.planar import PlanarMap

__all__ = ["publication", "face_tags", "lifted_caps", "LIFTED_CAP_TAG",
           "RAMP_ROLES"]

#: §34 (9) THE PINCHED RAMP (owner RULINGS 2026-09-14ak; the census read
#: RULED in 2026-09-14am): the way tag whose PRESENCE lifts the shape's
#: WITHIN-SHAPE LONGITUDINAL cap, and whose value names the grade the
#: pinched run was DESIGNED at (§34 (9) (3) reports it by name).
#:
#: THE LIFT IS THE PRESENCE, NOT THE VALUE.  The ruling is verbatim
#: "whatever grade the span requires is lawful", and the requirement is
#: not the axis average: OTHH's ``route7`` pinch is 5.1 m of axis at
#: 36.98 %, but its ramp's two long edges are 4.93 m and 3.81 m and its
#: emitted ring carries a 1.12 m chord at 85.8 % — a cap set to the axis
#: grade would leave rows the ruling calls lawful.  The value rides so a
#: report (and an attribution) can name the design; no reader prices it.
LIFTED_CAP_TAG = "o4_grade_law_cap_lifted"

#: The ramp roles a corridor emits (``planar/structure_geometry.
#: ramp_targets``'s own set — one list, two readers).
RAMP_ROLES = ("tunnel_ramp", "door_ramp", "wall_corridor_ramp", "garage_ramp")


def lifted_caps(planar: PlanarMap) -> dict[int, float]:
    """§34 (9): face id -> the DESIGNED grade of the pinched run, for every
    RAMP face of a corridor whose ``Tunnel.pinched`` record the structures
    pass wrote.  An empty map where nothing pinched.

    The face -> corridor join is the SAME one ``planar/structure_geometry.
    ramp_targets`` aims each ramp vertex with — the nearest tunnel AXIS to
    the face's centroid — so the face judged at the lifted cap is exactly
    the face built at the lifted grade.  A ramp face of an unpinched
    corridor, and every neighbour of a pinched one, is absent: the lift
    never leaves the faces the ruling named."""
    pin = {tn.id: tn.pinched for tn in planar.structures if tn.pinched}
    if not pin:
        return {}
    from shapely.geometry import LineString, Point
    axes = {tn.id: LineString(tn.axis) for tn in planar.structures
            if len(tn.axis) >= 2}
    if not axes:
        return {}
    out: dict[int, float] = {}
    for fid, f in planar.faces.items():
        if f.role not in RAMP_ROLES:
            continue
        vs = planar.ring_vertices(f.ring)
        if not vs:
            continue
        cx = sum(planar.vertices[v].xy[0] for v in vs) / len(vs)
        cy = sum(planar.vertices[v].xy[1] for v in vs) / len(vs)
        pt = Point(cx, cy)
        tid = min(axes, key=lambda k: axes[k].distance(pt))
        rec = pin.get(tid)
        if rec is not None:
            out[fid] = float(rec[2])
    return out


def _lifted_records(planar: PlanarMap) -> list[list[_t.Any]]:
    """§34 (9) (3)'s report record per LIFTED ramp face: ``[shapeID,
    corridor id, road ref, span m, designed grade]``, off the SAME
    ``Tunnel.pinched`` record and the SAME face join :func:`lifted_caps`
    uses."""
    pin = {tn.id: tn.pinched for tn in planar.structures if tn.pinched}
    if not pin:
        return []
    caps = lifted_caps(planar)
    if not caps:
        return []
    from shapely.geometry import LineString, Point
    axes = {tn.id: LineString(tn.axis) for tn in planar.structures
            if len(tn.axis) >= 2}
    out: list[list[_t.Any]] = []
    for fid in sorted(caps):
        vs = planar.ring_vertices(planar.faces[fid].ring)
        cx = sum(planar.vertices[v].xy[0] for v in vs) / len(vs)
        cy = sum(planar.vertices[v].xy[1] for v in vs) / len(vs)
        tid = min(axes, key=lambda k: axes[k].distance(Point(cx, cy)))
        road, span, grade = pin[tid]
        out.append([int(fid), str(tid), str(road), round(float(span), 3),
                    round(float(grade), 6)])
    return out


def face_tags(planar: PlanarMap, law: Law, airport: Airport | None = None
              ) -> dict[int, dict[str, str]]:
    """Extra way tags: ``o4_grade_law_cap_t`` on roads bound to a stricter
    contiguous class (the census's way-level lateral-contiguity read), and
    ``o4_edge`` on an adjacent-ground face whose region was ENDED at a
    terrain edge (owner RULINGS 2026-09-10b/10c; spec §19.3 C12).

    §37 (1) (RULINGS 2026-09-13q item 5): the contiguity cap is stamped
    under ``o4_grade_law_cap_t``, NOT ``o4_grade_law_cap``.  The bare tag
    binds a way's whole within-shape reading in both census readers, and
    lateral contiguity binds the TRANSVERSE cap only — a road keeps its
    own longitudinal law.  ``o4_grade_law_cap`` is left to the oracle
    alias (``emit/osm_adapter``) and to v1, whose meaning is unchanged."""
    out: dict[int, dict[str, str]] = {
        fid: {"o4_grade_law_cap_t": f"{cap:g}"}
        for fid, cap in road_law_caps(planar, law, airport).items()}
    # §34 (9) THE PINCHED RAMP (RULINGS 2026-09-14ak/14am): the shape whose
    # within-shape LONGITUDINAL cap is LIFTED, and the designed grade it is
    # lifted for.  The v1 census reads THIS tag (``check_grade.
    # _lifted_cap_tag``); v2 verify reads the same map through
    # ``Patch.of(lifted_caps=…)`` — one derivation, two readers.
    for fid, g in lifted_caps(planar).items():
        out.setdefault(fid, {})[LIFTED_CAP_TAG] = f"{g:g}"
    kinds = getattr(planar, "edge_kind_of_ref", None) or {}
    for fid, f in planar.faces.items():
        kind = kinds.get(f.ref)
        if kind:
            out.setdefault(fid, {})["o4_edge"] = kind
    return out



def cluster_pads(planar: PlanarMap, law: Law, airport: Airport,
                 z: _t.Sequence[float] | None = None) -> list[dict[str, _t.Any]]:
    """§30 (4): one record per TERMINAL CLUSTER — its id, its members, the
    emitted ``building`` faces its footprint union stands on, the LEVEL
    the solve gave that one plane, its footprint-union area, and how many
    apron vertices the reach targeted (with how many of them came within
    the materiality floor of the plane, which is the "apron faces that
    stayed graded" the ruling asks the report to name).

    Read off the SAME derivations the rows were priced from
    (``constraints.cluster_pad``), never a second reading of the law."""
    from ..constraints.cluster_pad import (DERIVED, OFFSET_SPREAD, REFERENCE,
                                           TOUCHING_STEPS, YIELDED,
                                           cluster_apron_faces,
                                           cluster_offsets, cluster_pad_faces,
                                           plane_groups)
    faces = cluster_pad_faces(planar, law, airport)
    if not faces:
        return []
    # §16g (8) as narrowed by (10) (owner RULINGS 2026-09-14x): fill
    # TOUCHING_STEPS (the declared terrace steps between touching
    # clusters' pads) and OFFSET_SPREAD (a cluster whose own bodies
    # disagree about the ground floor — a defect in the split) — the SAME
    # derivation the law states, never a second reading
    cluster_offsets(planar, law, airport)
    reach = cluster_apron_faces(planar, law, airport)
    vs_of = {ref.split("cluster:", 1)[1]: group
             for _f, ref, group, _q in plane_groups(planar, law, airport)
             if ref.startswith("cluster:")}
    by_id = {c.id: c for c in (getattr(airport, "clusters", None) or ())}
    tol = float(law.tables.emit.materiality.elevation_m)
    out: list[dict[str, _t.Any]] = []
    for cid, fids in sorted(faces.items()):
        vs = vs_of.get(cid) or []
        zs = ([float(z[v]) for v in vs if v < len(z)] if z is not None else [])
        lvl = (sorted(zs)[len(zs) // 2] if zs else None)
        ap = reach.get(cid, [])
        flat = (sum(1 for v in ap if v < len(z) and lvl is not None
                    and abs(float(z[v]) - lvl) <= tol)
                if z is not None else 0)
        c = by_id.get(cid)
        out.append({"id": cid,
                    "members": list(getattr(c, "members", ()) or ()),
                    "area_m2": round(float(getattr(c, "area_m2", 0.0)), 1),
                    "pads": sorted({planar.faces[f].ref for f in fids}),
                    "level": (None if lvl is None else round(lvl, 3)),
                    "rim_vertices": len(vs),
                    "apron_vertices_in_reach": len(ap),
                    "apron_vertices_at_the_plane": flat,
                    # §30 (4) (5) (owner RULINGS 2026-09-13ch): the member
                    # pads the gate turned away — they keep their own
                    # plane and the report names them
                    "yielded_pads": sorted(
                        {planar.faces[q].ref for q in YIELDED.get(cid, ())
                         if q in planar.faces}),
                    # §16g (8) (owner RULINGS 2026-09-14u): the pads this
                    # cluster DERIVED from its reference, by the bodies'
                    # authored floor offsets, and the reference itself
                    "reference_pad": (
                        planar.faces[REFERENCE[cid]].ref
                        if cid in REFERENCE and REFERENCE[cid] in planar.faces
                        else None),
                    "derived_pads": {
                        planar.faces[f].ref: d
                        for f, d in sorted(DERIVED.get(cid, {}).items())
                        if f in planar.faces and d},
                    # §16g (10) (1): the cluster's own authored GROUND
                    # FLOOR (the lowest of its member bodies') and the
                    # DECLARED TERRACE STEPS to the clusters it touches
                    "floor": (round(min(getattr(c, "floors", ()) or [0.0]), 3)
                              if getattr(c, "floors", ()) else None),
                    "bodies": int(getattr(c, "bodies", 0) or 0),
                    "footed_bodies": int(getattr(c, "footed", 0) or 0),
                    "touching_steps": {
                        (b if a == cid else a): d
                        for (a, b), d in sorted(TOUCHING_STEPS.items())
                        if cid in (a, b)},
                    # (10) (1): a cluster whose own bodies disagree about
                    # the ground floor cannot exist under the split — a
                    # non-empty reading here is a defect, and is named
                    "pad_offset_spread": (
                        {cid: OFFSET_SPREAD[cid]} if cid in OFFSET_SPREAD
                        else {})})
    return out


def publication(planar: PlanarMap, law: Law, airport: Airport,
                z: _t.Sequence[float] | None = None,
                cs: _t.Any = None) -> dict[str, _t.Any]:
    """The sidecar keys the solve's own pricing publishes; with ``z`` the
    crown drops are the BUILT ones.  The shape joints (owner RULINGS
    2026-09-08k, ``planar.shape_joints``) are declared, and every published
    pair across a joint (``planar.shape_of_vertex``: two shapes) is
    withheld — the solve priced none, so the readers price none (a
    ``taxi_route_pairs`` entry becomes the null record: no law edge)."""
    ll = {vid: [v.key[0], v.key[1]] for vid, v in planar.vertices.items()}
    ax_out = []
    for k, a in enumerate(axes(planar, law)):
        ax_out.append([[ll[v] for v in a.vertices], a.cap_l, a.cap_t, k,
                       bool(a.is_service)])
    st_out = [[[ll[v] for v in s.vertices], s.cap_l, s.code_letter, s.ref]
              for s in stretches(planar, law).items]
    drops = [[ll[v][0], ll[v][1], d] for v, d in
             sorted(crown_drops(planar, law, airport, z).items())]
    tol = law.tables.emit.materiality.elevation_m
    # §38 (1) (owner RULINGS 2026-09-13ah/13am): EVERY seam pin is
    # published — 150 at SPLP, not the 27 the M3a preference happened to
    # honour.  A pin holds exactly, so there is no "honoured" subset to
    # filter by, and the census's ``seam_residual`` family reads exactly
    # this list against the DEM value published beside it.
    seam_all = seam_vertices_pinned(seam_pins(planar, law, airport))
    pins = sorted(seam_all)
    # the pairs the solver priced: a pin↔pin pair was exempt in the solve
    # (constraints.seam_exempt) and is not published — the census prices
    # exactly the published list
    pav = no_step_edges(planar, law, airport)
    edges = [{"a": ll[a], "b": ll[b], "budget_m": round(cap * d, 6),
              "dist_m": round(d, 4)} for a, b, cap, d in pav
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
    pad_edges = [{"a": ll[a], "b": ll[b], "budget_m": round(cap * d, 6),
                  "dist_m": round(d, 4)} for a, b, cap, d in pad_pavement_edges(planar, law, pav, airport)]
    taxi_pairs = taxi_route_pairs(planar, law, airport, ll, tol)
    mesh = mesh_edges_ll(planar, law)
    if planar.shape_joints:
        from ..planar.shapes import straddles
        id_of = {(round(la, 7), round(lo, 7)): vid for vid, (la, lo) in ll.items()}

        def _ids(*pts):
            return [id_of.get((round(float(q[0]), 7), round(float(q[1]), 7))) for q in pts]

        def _cross(*pts) -> bool:
            ids = _ids(*pts)
            return all(i is not None for i in ids) and straddles(planar, ids)
        edges = [e for e in edges if not _cross(e["a"], e["b"])]
        pad_edges = [e for e in pad_edges if not _cross(e["a"], e["b"])]
        mesh = [e for e in mesh if not _cross(e[0], e[1])]
        taxi_pairs = [[e[0], e[1], None, None] if _cross(e[0], e[1]) else e for e in taxi_pairs]
        # a routed pair the prune left unpublished (its route reading equals
        # the chord's) is priced by the reader at the chord: publish it null
        seen = {(tuple(e[0]), tuple(e[1])) for e in taxi_pairs}
        for pp in taxi_pair_routes(planar, law, airport):
            if pp.routed and straddles(planar, (pp.a, pp.b)):
                key = (tuple(ll[pp.a]), tuple(ll[pp.b]))
                if key not in seen and (key[1], key[0]) not in seen:
                    seen.add(key)
                    taxi_pairs.append([ll[pp.a], ll[pp.b], None, None])
    _doc = {"axes": ax_out, "stretches": st_out, "crown_drops": drops,
            # §40 (2) as amended (owner RULINGS 2026-09-13dd): per runway
            # ``[ref, lat_a, lon_a, lat_b, lon_b, half_width_m]`` — the
            # RUNWAY's own geometry (apt.dat ends and width, never a fit
            # to the rings a §40 shoulder fattens), so the v1 census reads
            # the same shoulder line the generator priced at, plus the
            # shoulder cap itself
            "runway_axes": [
                [rw.id, round(rw.ends[0].ll[0], 11), round(rw.ends[0].ll[1], 11),
                 round(rw.ends[1].ll[0], 11), round(rw.ends[1].ll[1], 11),
                 round(runway_half_widths(airport).get(rw.id, 0.0), 4)]
                for rw in airport.runways],
            "shoulder_transverse_max":
                float(law.ruleset.runway.shoulder_transverse_max),
            # §50.1 (4) THE PUBLISHED SIDE of the runway longitudinal cap
            # (owner RULINGS 2026-09-18d (3) / 18f): one record per runway
            # — the code, the ruleset, the TABLE's cap, the EFFECTIVE cap
            # the build priced and the two pins of the governing span —
            # for EVERY runway, yielded or not.  LAW INPUT: without it the
            # census judges a code 1/2 runway at 1.5 % and a yielded one
            # under the un-yielded law (04y's own cause, closed here).  A
            # patch with no key reads exactly as before.
            "runway_caps": [
                rc.as_dict(law.ruleset_key, ll)
                for _r, rc in sorted(
                    (planar.runway_caps or {}).items())
                if isinstance(rc, _RunwayCap)],
            # §30 (4) THE CLUSTER PADS (owner RULINGS 2026-09-13bj item 1):
            # what the object stage's §16g seats a big terminal on, and
            # what the report reads to name the apron faces that stayed
            # graded.  Empty at an airport with no cluster (CYXY's class).
            "cluster_pads": cluster_pads(planar, law, airport, z),
            # §16g (10) (3) `pad_cluster_mismatch` (owner RULINGS
            # 2026-09-14x): CRITICAL — a pad spanning two clusters or a
            # cluster spanning two pads is a misidentified shape.  LAW
            # INPUT: the census cannot recompute a cluster from the patch
            # (the outlines live in the rebake plan), so the DEFECT SET
            # is declared here, over the WHOLE cluster population, and
            # the family prices exactly it.  Empty is the bar.
            "pad_cluster_mismatch": _pad_cluster_mismatch(planar, law,
                                                          airport),
            "apron_tier": apron_tier(law),
            "terrace_joints": terrace_joints_ll(planar, law, z),
            "taxi_route_pairs": taxi_pairs,
            "mesh_edges": mesh,
            "airside_no_step_edges": edges,
            "pad_pavement_no_step_edges": pad_edges,
            # §38 (1)/(5): ``[lat, lon, the vertex's OWN tile's baked DEM
            # sample]``.  The third element is LAW INPUT for the census's
            # ``seam_residual`` family — the pin's value, published where
            # the pin is, so the reader prices the emitted surface against
            # the value the solve held rather than re-sampling a DEM no
            # patch carries.  A patch predating §38 carries 2-element
            # entries and every reader still reads its first two.
            "seam_pins": [[ll[v][0], ll[v][1],
                           round(float(planar.vertices[v].dem_z), 4)]
                          if planar.vertices[v].dem_z is not None else ll[v]
                          for v in pins],
            # the band's own half width, so the census can read "inside the
            # seam band" (``bank_across_seam``) from the law the build ran
            # under and never from a constant of its own
            "seam_half_width_m": float(law.tables.emit.seam.half_width_m),
            "station_caps": stations,
            # §16g (10) (12) (2) THE RE-NODE (Fable 2026-09-16; RULINGS
            # 2026-09-16b): ``[lat, lon, "minted"|"deleted"]`` per airside
            # node the PAD STAGE added to or removed from the arrangement's
            # airside cells.  Published from the ONE derivation site that
            # can know it — ``planar/overlay.build_arrangement`` compares
            # its own pass A (no pad in the line set) with its pass B — so
            # the census family ``pad_airside_renode`` prices exactly what
            # the build did and never re-derives it.  The bar is an EMPTY
            # list; a patch with no key reads exactly as before.
            "pad_airside_renode": _renode_rows(airport),
            # §34 (9) THE PINCHED RAMP (RULINGS 2026-09-14ak/14am):
            # ``[shapeID, corridor, road ref, span m, designed grade]`` per
            # ramp face whose within-shape longitudinal cap is LIFTED — the
            # report record §34 (9) (3) asks for ("the report names each
            # pinched ramp: corridor, road, span, grade").  EVIDENCE, not
            # law input: the census reads the LIFT off the way tag
            # (``check_grade.LIFTED_CAP_TAG``) and prices nothing from this
            # list.
            "lifted_caps": _lifted_records(planar),
            # §37 (7) THE ROAD'S ROUTE FRAME (owner RULINGS 2026-09-13av;
            # ``airport/road_ramp.road_route_frame``, published through
            # ``PlanarMap.road_route_frame``): ``[lat, lon, route id,
            # station s, signed lateral t]`` per road-family ring vertex.
            # A road PAIR is priced along the ROUTE, so the verify reader
            # and the v1 census must pair the way the generator does —
            # they read this and apply ``constraints.roads
            # .road_pair_reading``, the one rule.  Empty on a map whose
            # publisher never ran: every reader keeps the chord law.
            "road_route_frame": [[ll[v][0], ll[v][1], int(r),
                                  round(float(st), 4), round(float(t), 4)]
                                 for v, (r, st, t)
                                 in sorted(planar.road_route_frame.items())],
            # §37 (9) THE COVERAGE-EDGE JOIN (owner RULINGS 2026-09-13be):
            # ``[lat, lon, the CORE ribbon's altitude just outside]`` per
            # pinned road vertex.  LAW INPUT — the census's
            # ``road_coverage_join`` family prices the emitted surface
            # against exactly the value the solve pinned, and the mesh
            # reads the same ribbon.
            "road_coverage_join": [[ll[v][0], ll[v][1], round(float(z), 4)]
                                   for v, z in sorted(
                                       planar.road_coverage_join.items())],
            "basin_facilities": basin_facilities(planar, law, z),
            # THE PAD'S RELIEF TARGET (owner RULINGS 2026-09-11j; spec
            # §11a (2)/(4)): ``[[lat, lon, metres above the pad's level],
            # ...``.  Published because the pad's flatness READER
            # (``verify/pads.pad_flat``) sees only the emitted product: a
            # pad under a body with authored relief is one plane ON ITS
            # LEVEL PLANE, and without this the reader would report every
            # such pad as a plane-residual row.  Empty list = no pad
            # carries a target, which is every airport whose objects are
            # authored flat-footed and the law disarmed.
            "pad_relief": [[ll[v][0], ll[v][1], round(o, 4)]
                           for v, o in sorted(pad_relief_offsets(planar, law,
                                                                 airport).items())],
            # THE END-AROUND TAXIWAY RECTS (spec §36): one record per
            # ACCEPTED rect — its end, its runway, its regulation value and
            # the vertices it pinned, read off the FINAL constraint set so
            # the census prices exactly what the solve pinned.  Empty where
            # the airport has no EAT by recognition, and absent (never
            # invented) when the caller hands no constraint set.
            "eat_rects": ([] if cs is None
                          else _eat_rects(planar, cs)),
            "tunnel_objects": tunnel_objects(planar, airport),
            # THE OPEN CHANNELS (spec §45; owner RULINGS 2026-09-15i):
            # one record per channel the map carries — the FLOOR the
            # record declares per station and the CREST the design
            # surface, in longitude / latitude, so the census can judge
            # the emitted surface against exactly what the generator
            # stated.  Empty at every airport with no channel, which is
            # every airport but the three the class was measured over.
            "channel_facilities": channel_facilities(planar, law, z),
            "object_cuts": object_cuts(planar, airport)}
    # §16g (10) (12) (2): an ABSENT key means NOT MEASURED (the arrangement
    # did not run in this process — a replay arm), an EMPTY list means
    # MEASURED ZERO.  See ``_renode_rows``.
    if _doc.get("pad_airside_renode") is None:
        _doc.pop("pad_airside_renode", None)
    return _doc


def apron_tier(law: Law) -> dict[str, float | None]:
    """THE TIERED APRON LAW the build priced (owner RULINGS 2026-09-06w),
    for the oracle: ``preferred`` (1 %), ``max`` (1.5 %, the hard cap) and
    ``fan`` (the back-edge class, ``common.apron_fan_ramp_max``) as
    fractions — ``check_grade`` reads apron rows against ``max`` and
    counts rows above ``preferred`` as the report figure
    ``apron_over_preference``, never a violation."""
    from ..law.tables import role_cap, role_preferred_cap
    hard = role_cap(law, "apron")
    pref = role_preferred_cap(law, "apron")
    return {"preferred": None if pref is None else pref.longitudinal,
            "max": None if hard is None else hard.longitudinal,
            "fan": law.tables.common.apron_fan_ramp_max}


def taxi_route_pairs(planar: PlanarMap, law: Law, airport: Airport,
                     ll: _t.Mapping[int, _t.Sequence[float]], tol: float
                     ) -> list[list[_t.Any]]:
    """The ``taxi_route_pairs`` publication (module docstring): every
    unrouted pair as ``null``; every routed pair whose route budget
    differs from the chord reading by more than ``tol``."""
    out: list[list[_t.Any]] = []
    seen: set[tuple[int, int]] = set()
    for pp in taxi_pair_routes(planar, law, airport):
        key = (min(pp.a, pp.b), max(pp.a, pp.b))
        if key in seen:
            continue                      # a pair two faces share (a split stub): once
        if not pp.routed:
            seen.add(key)
            out.append([ll[pp.a], ll[pp.b], None, None])
        elif abs(pp.budget - pp.chord_bound_m) > tol:
            seen.add(key)
            out.append([ll[pp.a], ll[pp.b], round(pp.budget, 6), round(pp.dist, 4)])
    return out


def terrace_joints_ll(planar: PlanarMap, law: Law,
                      z: _t.Sequence[float] | None = None) -> list[dict[str, _t.Any]]:
    """Sidecar ``terrace_joints`` (owner RULINGS 2026-09-08k; ``planar/shapes.py``)
    in v1's record shape (``check_grade._terrace_joints_to_m`` /
    ``terrace_joints_sidecar``): one record per SHAPE JOINT — the contour
    (or gap midline) as ``points``, ``step_m`` = the EMITTED step, the
    largest |Δz| over the vertex pairs across it (0 before a solve), which
    is what the oracle forgives across the line and judges the actual step
    against; ``declared_step_m`` the same (a joint has no grade law of its
    own); ``faced`` false (no split copy: the two nodes ARE the step);
    ``kind`` ``apron_terrace`` (never the basin trench-wall kind: no
    ``carried`` flags); ``shapes`` the two shape ids; ``gap`` whether it is
    a gap midline."""
    out: list[dict[str, _t.Any]] = []
    for j in planar.shape_joints:
        pts = [[la, lo] for la, lo in j.points_ll]
        if len(pts) < 2:
            continue
        step = 0.0
        if z is not None and j.pairs:
            step = max(abs(float(z[a]) - float(z[b])) for a, b in j.pairs)
        out.append({"points": pts, "step_m": round(step, 4), "declared_step_m": round(step, 4),
                    "faced": False, "kind": "apron_terrace", "faces": [], "shapes": list(j.shapes),
                    "gap": bool(j.gap), "roles": list(j.roles), "pairs": len(j.pairs),
                    "length_m": round(j.length_m, 2)})
    return out


def tunnel_objects(planar: PlanarMap, airport: Airport) -> list[dict[str, _t.Any]]:
    """The object corridors (RULINGS 2026-09-05k-1 / 05n): id, resource,
    the placements, the floor at the mouth / the ground crest / the
    depth (= the plate height), the walls' length and mean inner width,
    the ends and how the mouth was chosen, the ramp's design grade and
    its length beyond the walls, the re-seat the design implies, the
    05n-2 trench assertion, the OSM bore mouths taken, and the axis in
    lat/lon — a reader's record of which tunnels the pack's objects
    state."""
    _to_xy, to_ll = airport.frame.transformers()
    out: list[dict[str, _t.Any]] = []
    for tn in planar.structures:
        if tn.source == "osm":
            continue
        # ``kind`` (RULINGS 2026-09-08b/c): a tunnel wall object, a door ramp
        # (Law A) or a sunken road (Law B) — the same record, the mouth-law
        # readers exempt every kind alike (the mouth is the object's)
        out.append({
            "id": tn.id, "kind": "wall" if tn.source == "object" else tn.source,
            "resource": tn.resource, "objects": list(tn.objects),
            "floor_m": round(tn.mouth_z, 3), "crest_m": round(float(tn.crest_z or 0.0), 3),
            "depth_m": round(tn.depth_m, 3), "plate_y_m": round(tn.plate_y_m, 3),
            "edge_wall": bool(tn.edge_wall), "length_m": round(tn.hull_length_m, 1),
            "width_m": round(tn.hull_width_m, 1), "ends": tn.ends, "crest_law": tn.crest,
            "replaced_ways": list(tn.replaced_ways), "top_s": round(tn.top_s, 1),
            "wall_length_m": round(tn.wall_length_m, 1),
            "ramp_beyond_walls_m": round(max(0.0, tn.top_s - tn.wall_length_m), 1),
            "design_grade": round(tn.design_grade, 5),
            "mouth": tn.mouth_kind, "ground_end": tn.ground_kind,
            "reseat_expect_m": [round(d, 3) for d in tn.reseat_expect_m],
            "trench_outside_max_m": round(tn.trench_outside_max_m, 3),
            "axis_ll": [[round(la, 8), round(lo, 8)] for la, lo in
                        (to_ll(x, y) for x, y in tn.axis)],
            "profile": [[round(s, 2), round(z, 3)] for s, z in tn.profile],
            "top_ground_m": None if tn.top_ground_z is None else round(tn.top_ground_z, 3),
            "ramp_length_m": round(max(0.0, tn.top_s - tn.climb_from_s), 1),
        })
    return out


def channel_facilities(planar: PlanarMap, law: Law,
                       z: _t.Sequence[float] | None = None) -> list[dict[str, _t.Any]]:
    """THE OPEN CHANNEL RECORDS (spec §45; owner RULINGS 2026-09-15i).

    ``floor_profile`` is ``[[lat, lon, the DECLARED floor], ...]`` — the
    record's own ``floor_z(s)`` per axis station, the SAME call
    ``constraints/channel.channels`` states the pin with, so
    ``channel_floor_at_declaration`` judges the emitted floor against the
    stated row and not against a second arithmetic.  ``emitted_floor_*``
    and ``crest_parts_m`` are what the solve actually produced.
    ``datum_source`` names which of §45 (3)'s three the floor came from,
    so a ``--refresh-data dem`` moving a site from (iii) to (ii) shows up
    in the sidecar with no law change."""
    out: list[dict[str, _t.Any]] = []
    chans = getattr(planar, "channels", ())
    if not chans:
        return out
    from ..constraints.channel import floor_faces_of, wall_faces_of
    floors = floor_faces_of(planar)
    walls = wall_faces_of(planar)
    for c in chans:
        fvs = sorted({v for f in floors.get(c.id, ()) for v in planar.ring_vertices(f.ring)})
        wvs = sorted({v for f in walls.get(c.id, ()) for v in planar.ring_vertices(f.ring)}
                     - set(fvs))
        f_zs = [float(z[v]) for v in fvs] if (z is not None and fvs) else []
        c_zs = [float(z[v]) for v in wvs] if (z is not None and wvs) else []
        out.append({
            "id": c.id,
            "ways": list(c.ways),
            "witnesses": list(c.witnesses),
            "datum_source": c.datum_source,
            "crest": c.crest,
            "bank_slope": round(float(c.bank_slope), 4),
            "floor_profile": [[la, lo, round(float(zz), 3)]
                              for la, lo, zz in c.profile_ll],
            "corridor_longitude_latitude": [[lo, la] for la, lo in c.region_ll],
            "decks": [{"ref": d.ref, "way": d.way, "datum": d.datum,
                       "s0": round(float(d.s0), 2), "s1": round(float(d.s1), 2)}
                      for d in c.decks],
            "walls": [{"side": w.side, "shape": w.shape, "crest": w.crest,
                       "witness": w.witness} for w in c.walls],
            "floor_declared_min_m": round(min((zz for _a, _b, zz in c.profile_ll),
                                              default=0.0), 3),
            "floor_declared_max_m": round(max((zz for _a, _b, zz in c.profile_ll),
                                              default=0.0), 3),
            "emitted_floor_min_m": round(min(f_zs), 3) if f_zs else None,
            "emitted_floor_max_m": round(max(f_zs), 3) if f_zs else None,
            "emitted_floor_count": len(fvs),
            "crest_parts_m": sorted({round(v, 2) for v in c_zs}),
            "crest_count": len(wvs),
            "notes": list(c.notes)})
    return out


def object_cuts(planar: PlanarMap, airport: Airport) -> list[dict[str, _t.Any]]:
    """THE §33 (6) OBJECT CUTS the emitted patch must answer to (spec
    §33 (6); lane `v2objcut`): per SIGNATURE-B corridor its id, the
    object's own WALL LINE as a ring in lat/lon (the outer face of the
    walls ∪ trench — what an emitted ring vertex may not stand outside)
    and the AUTHORED FLOOR the object states (the floor plate's level in
    the seated frame, which overrides ``bore_datum_m``).

    Published so the two census families read the OBJECT'S OWN numbers
    and never re-derive them from the pack: ``object_cut_offset`` prices
    every emitted ramp / rim vertex against ``outline_ll``,
    ``object_cut_depth`` the emitted floor against ``floor_m``.  One
    witness, two instruments — the ``shore_edges`` / ``hairline_pair``
    pattern."""
    _to_xy, to_ll = airport.frame.transformers()
    out: list[dict[str, _t.Any]] = []
    for tn in planar.structures:
        if not tn.id.startswith("object-cut:") or not tn.footprint:
            continue
        out.append({
            "id": tn.id, "signature": "B", "resource": tn.resource,
            "objects": list(tn.objects),
            "floor_m": round(float(tn.mouth_z), 3),
            "depth_m": round(float(tn.depth_m), 3),
            "outline_ll": [[round(la, 8), round(lo, 8)] for la, lo in
                           (to_ll(x, y) for x, y in tn.footprint)],
            "ramp_refs": list(tn.ramp_refs),
            "wall_ref": tn.wall_ref,
        })
    return out


def basin_facilities(planar: PlanarMap, law: Law,
                     z: _t.Sequence[float] | None = None) -> list[dict[str, _t.Any]]:
    """The basin records (see the module docstring)."""
    out: list[dict[str, _t.Any]] = []
    if not planar.basins:
        return out
    by_ref: dict[str, list[int]] = {}
    for f in planar.faces.values():
        # the rim = the void face's EXTERIOR (its holes are the floors)
        by_ref.setdefault(f.ref.split("#")[0], []).extend(planar.ring_vertices(f.ring))
    clearance = float(law.tables.structures.basin.floor_clearance_m)
    for b in planar.basins:
        floor_vs = sorted(set(by_ref.get(b.floor_ref, ())))
        wall_vs = sorted(set(by_ref.get(b.wall_ref, ())) - set(by_ref.get(b.floor_ref, ())))
        rim_parts = sorted({round(float(z[v]), 2) for v in wall_vs}) if z is not None else []
        lat, lon = b.anchor_ll
        # THE FLOOR IS THE SOLVED ONE (owner RULINGS 2026-09-10ba; spec
        # §22.1c): the floor ring stands ``body_depth_m`` under its rim,
        # which follows the pavement — so it is no longer ONE declared
        # number and the record publishes the RANGE the census joins on.
        # ``floor_declared_m`` keeps the object's own reading, and
        # ``rim_law_m`` — the law the rim was held to — is the SOLVED rim
        # where the solve is known (``rim_estimate_m`` stays R_est).
        # ONE DERIVATION (``Basin.floor_below_rim_m``): the body depth plus
        # ``[basin] floor_clearance_m`` (2026-09-11t §24 (2)), the same call
        # ``constraints/structures.basins`` states the row with.
        depth = b.floor_below_rim_m(clearance)
        f_zs = [float(z[v]) for v in floor_vs] if (z is not None and floor_vs) else []
        r_zs = [float(z[v]) for v in wall_vs] if (z is not None and wall_vs) else []
        floor_m = sum(f_zs) / len(f_zs) if f_zs else float(b.floor_z)
        rim_law = sum(r_zs) / len(r_zs) if r_zs else float(b.rim_estimate_m)
        # THE PLATE STANDS floor_clearance_m ABOVE THE TRENCH FLOOR (§24
        # (2)): ``floor_m`` is the terrain's level, the plate's target is
        # that plus the clearance — which is what ``emit/rebake`` seats to
        # (``Member.plate_clearance_m``), so the published expectation and
        # the seat read the same number.
        seat_expect = float(b.seat_expect_m) + (floor_m + clearance - float(b.floor_z))
        out.append({
            "resources": list(b.objects),
            "anchor_longitude_latitude": [lon, lat],
            "rim_estimate_m": round(b.rim_estimate_m, 3),
            "floor_m": round(floor_m, 3),
            "floor_min_m": round(min(f_zs), 3) if f_zs else round(float(b.floor_z), 3),
            "floor_max_m": round(max(f_zs), 3) if f_zs else round(float(b.floor_z), 3),
            "floor_declared_m": round(b.floor_z, 3),
            "floor_below_rim_m": round(depth, 3),
            "floor_clearance_m": round(clearance, 3),
            "rim_law_m": round(rim_law, 3),
            "emitted_rim_min_m": rim_parts[0] if rim_parts else None,
            "emitted_rim_max_m": rim_parts[-1] if rim_parts else None,
            "emitted_rim_part_count": len(rim_parts),
            "emitted_rim_parts_m": rim_parts,
            "solid_minimum_y_m": round(b.solid_min_y_m, 3),
            "body_depth_m": round(-b.solid_min_y_m, 3),
            "rendered_solid_min_m": round(b.solid_min_z, 3),
            "margins_m": 0.0,
            # THE SEAT (RULINGS 2026-09-06b (3)): the family's plate y, the
            # anchor's place and the delta the design implies
            "plate_y_m": round(b.plate_y_m, 3),
            "anchor_inside_floor": bool(b.anchor_inside_floor),
            "seat_expect_m": round(seat_expect, 3),
            "member_ids": list(b.member_ids),
            "witness_id": b.witness_id,
            "covered_fraction": round(b.covered_fraction, 4),
            "area_m2": round(b.area_m2, 1),
            "floor_ref": b.floor_ref,
            "wall_ref": b.wall_ref,
            "floor_plates": len(planar_faces_of_ref(planar, b.floor_ref)),
            "shell_count": len(b.objects),
            # THE RAMP CORRIDORS (spec §24 (5), owner RULINGS 2026-09-13g),
            # in LONGITUDE / LATITUDE — the coordinate system the patch and
            # the sidecar share (the planar frame's metres are NOT the
            # patch's), so ``verify`` re-derives the expectation from the
            # object's own authored deck instead of reading it back.
            "ramp_corridors": len(b.ramp_rings),
            "ramp_rings_ll": [[[round(x, 9), round(y, 9)] for x, y in r]
                              for r in b.ramp_rings_ll],
            "ramp_faces_ll": [[[round(q[0], 9), round(q[1], 9), round(q[2], 3)] for q in t]
                              for t in b.ramp_faces_ll],
        })
    return out


def planar_faces_of_ref(planar: PlanarMap, ref: str) -> list[int]:
    return [f.id for f in planar.faces.values() if f.ref.split("#")[0] == ref]
