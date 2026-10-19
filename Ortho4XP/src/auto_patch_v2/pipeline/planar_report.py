"""THE PLANAR STAGE'S REPORT LINES: what the build says about the map the
planar stage made — the shore, the faces and seams, the shapes, the
structures, the objects and the basins.  A READ of pm / pstats; it
derives nothing (pipeline/prefix.run_prefix says it for the main pass
only — the prefix re-runs are silent)."""
from __future__ import annotations

import typing as _t

__all__ = ["say_planar", "shore_decision_lines"]


def say_planar(icao: str, pm, pstats, airport, lrep, planar_s: float,
               out: _t.Callable[[str], None]) -> None:
    """Say the planar stage's lines for pm (built in planar_s
    seconds) through out; lrep is the load report (the objects
    restored for the read)."""
    # §37 (11) (7) (issue #72): the shore the zones were cut against —
    # quay faces stand on a DECLARED shore (or a pavement edge that IS
    # the coast), natural faces slope to the water.
    out(f"  [planar] shore (§37 (11) (7)): "
         f"{len(getattr(pm, 'quay_refs', ()) or ())} quay face(s), "
         f"{len(getattr(pm, 'natural_shore_refs', ()) or ())} natural")
    for _ln in shore_decision_lines(pm, airport):
        out(_ln)
    out(f"[{icao}] planar {planar_s:.2f} s  faces {pstats.faces}  "
         f"edges {pstats.edges}  vertices {pstats.vertices}  "
         f"breaklines {pstats.breaklines}  T-vertices {pstats.t_vertices}"
         f"  seam bands {pstats.seam_bands}  seam vertices {pstats.seam_vertices}"
         f"  seam-band faces dropped {pstats.dropped_seam_faces}"
         f"  slivers merged {pstats.slivers_merged} (08d-4a)")
    # §41 (4) (owner RULINGS 2026-09-14c item 4): the sliver ZONE strips
    if pstats.zone_slivers_dissolved or pstats.zone_slivers_dropped:
        out(f"[{icao}] zone slivers (41-4): "
             f"{pstats.zone_slivers_dissolved} dissolved into their host, "
             f"{pstats.zone_slivers_dropped} host-less dropped, "
             f"{pstats.zone_sliver_area_m2:,.1f} m2")
    sh = pstats.shapes
    if sh.faces:
        # THE TERRAIN EDGE (owner RULINGS 2026-09-10b/10c; spec §19)
        out(f"[{icao}] " + pstats.terrain_edge.line())
        # THE SHAPES (owner RULINGS 2026-09-08k; ``planar/shapes.py``)
        out(f"[{icao}] network (08p): {sh.network_faces} of {sh.faces} pavement faces "
             f"({', '.join(f'{k} {n}' for k, n in sorted(sh.network_by_role.items()))}), "
             f"{sh.network_vertices} vertices, {sh.connected_stations} connected stations, "
             f"{sh.unconnected_station_edges} unconnected centreline edges; bodies {sh.body_faces} faces "
             f"({sh.faces_unlabelled} welded whole)")
        out(f"[{icao}] shapes (08k): {sh.body_faces} body faces -> {sh.components} components, "
             f"{sh.bodies} bodies, {sh.shapes} shapes (strip welds {sh.welded_strip_pairs}, route welds {sh.welded_route_pairs}); "
             f"vertices {sh.vertices_labelled} (roads {sh.road_vertices_labelled} labelled / "
             f"{sh.road_vertices_relabelled} relabelled / {sh.road_vertices_unlabelled} freed; road faces "
             f"{sh.roads_along} along, {sh.roads_crossing} crossing -> {sh.road_ramps} ramps, 08r-2; pads relabelled "
             f"{sh.pads_relabelled}); joints {sh.contours} contours ({sh.contour_length_m:,.0f} m, "
             f"dangling faces {sh.dangling_faces}) + {sh.gap_joints} gap ({sh.gap_length_m:,.0f} m); "
             f"joint edges {sh.joint_edges}; {sh.wall_s:.2f} s")
        for sid, nf, a, nv, roles in sh.by_shape[:8]:
            out(f"    shape {sid}: {nf} faces, {a:,} m2, {nv} vertices, {'/'.join(roles)}")
    ss = pstats.structures
    ts = pstats.tunnel_objects
    ds, rs = pstats.door_wells, pstats.sunken_roads
    ws = pstats.wall_corridors
    if ws.corridors or ws.refused:
        out(f"[{icao}] wall corridors (09-08m/n Law C): {ws.corridors} corridors "
             f"({', '.join(f'{k} {n}' for k, n in sorted(ws.by_class.items()))}) from {ws.pairs} "
             f"pairs of {ws.bands} bands in {ws.families} families ({ws.read_s:.2f} s)  "
             + (f"field read ({ws.field_cells} cells)" if ws.field_read else "FIELD NOT READ")
             + f"  refused {len(ws.refused)}")
        for r in ws.refused[:40]:
            out(f"    refused wall corridor {r}")
    if ds.wells or ds.refused or rs.roads or rs.refused:
        out(f"[{icao}] door wells (09-08b/c Law A): {ds.wells} of {ds.regions} regions in "
             f"{ds.families} families ({ds.sill_witnesses} sill witnesses over {ds.screened} "
             f"screened placements, {ds.basin_gate_components} basin-gate components left to the "
             f"basin pass; {ds.read_s:.2f} s)  sunken roads (Law B): {rs.roads} of {rs.plates} "
             f"plates in {rs.families} families ({rs.read_s:.2f} s)  refused {len(ds.refused)} / "
             f"{len(rs.refused)}")
        for r in ds.refused[:40]:
            out(f"    refused door {r}")
        for r in rs.refused[:40]:
            out(f"    refused sunken road {r}")
    if ss.bores or ss.object_corridors or ss.door_ramps or ss.sunken_roads or ss.wall_corridors \
            or ts.refused:
        out(f"[{icao}] structures: bores {ss.bores} (no on-field mouth {ss.bores_no_mouth}, "
             f"mouth-only built {ss.bores_mouth_only}, replaced by "
             f"objects {ss.bores_replaced_by_object})  mouths {ss.mouths} (off-field "
             f"{ss.mouths_off_field}, on approach {ss.mouths_on_approach} of "
             f"{ss.approach_corridors} corridors, "
             f"{ss.runway_bands} runway bands)  duals merged "
             f"{ss.duals_merged}  object corridors {ss.object_corridors} (signatures "
             f"{ts.signatures} of {ts.resources} resources screened, {ts.not_screened} "
             f"not screened, thin plates {ts.plates}, object cuts {ts.shells} B "
             f"(basin placements claimed {len(ts.shell_claimed)}), merged {ts.merged}, "
             f"{ts.signature_s:.2f} s)  plate mouths {len(ss.plate_mouths)}  "
             f"crest from approach {len(ss.crest_from_approach)}  "
             f"underpasses {len(ss.underpasses)}  "
             f"object-decked trenches {ss.decked_outlines} (§33 (6) B (3) (c): "
             f"{ss.decked_pavement_m2:,.0f} m2 pavement, {ss.decked_centreline_m:,.0f} m "
             f"centreline, {ss.decked_road_m:,.0f} m road excluded)  "
             f"door ramps {ss.door_ramps}  sunken roads "
             f"{ss.sunken_roads}  wall corridors {ss.wall_corridors}  tunnels {ss.tunnels}  "
             f"decks {ss.decks}  "
             f"cells cut {ss.cells_cut}  mouth roads {len(ss.mouth_roads)}  "
             f"refused {len(ss.refused) + len(ts.refused)}")
    # §34 (13) (4): every MOUTH ROAD named — the class is meant to be a
    # handful (LEMD 4, KCLT 3, OTHH 0), so a rising count is visible
    for _mr in ss.mouth_roads:
        out(f"    [{icao}]     {_mr}")
    # the structure report is printed ONCE, mouth roads or none (it stood
    # inside the loop above since 81a61794: a field with no mouth road
    # printed no refusal and no per-tunnel line — KCLT, sweep sww)
    for r in ts.refused:
        out(f"    refused object {r}")
    for r in ss.refused:
        out(f"    refused {r}")
    if ss.mouth_only_bores:
        out(f"    mouth-only bores BUILT (owner 2026-09-12ab, no cover): "
             f"{', '.join(ss.mouth_only_bores)}")
    for r in ss.plate_mouths:
        out(f"    {r}")
    for r in ss.underpasses:
        out(f"    {r}")
    for r in ss.decked_excluded:
        out(f"    {r}")
    for r in ss.decked_runway_family:
        out(f"    {r}")
    for r in ss.crest_from_approach:
        out(f"    {r}")
    for r in ss.mouths_on_approach_named:
        out(f"    {r}")
    for r in ss.mouths_off_field_nearest:
        out(f"    {r}")
    for r in ss.bore_precedence:
        out(f"    {r}")
    for tn in pm.structures:
        if tn.source == "object":
            # round-2 spec §3.6: the per-corridor line
            inside = min(tn.top_s, tn.wall_length_m)
            out(f"    {tn.id}: floor@mouth {tn.mouth_z:.2f} ground {tn.mouth_dem_z:.2f} "
                 f"depth {tn.depth_m:.2f} m ramp {tn.top_s:.1f} m (inside walls {inside:.1f} m, "
                 f"beyond {max(0.0, tn.top_s - tn.wall_length_m):.1f} m) grade "
                 f"{100.0 * tn.design_grade:.2f} % ends mouth={tn.mouth_kind} "
                 f"ground={tn.ground_kind} walls {tn.ends} width {tn.hull_width_m:.1f} m "
                 f"reseat expect {', '.join(f'{d:+.2f}' for d in tn.reseat_expect_m)} "
                 f"trench-outside {tn.trench_outside_max_m:.3f} m replaced mouths of "
                 f"[{', '.join(str(w) for w in tn.replaced_ways)}]  decks {len(tn.decks)}  "
                 f"{'; '.join(tn.notes)}")
            continue
        if tn.source == "wall_corridor":
            # RULINGS 2026-09-08m/n Law C: the per-site line the report quotes
            inside = [z for s, z in tn.profile if s <= tn.wall_length_m + 1e-6]
            out(f"    {tn.id}: floor@mouth {tn.mouth_z:.2f} ground {tn.mouth_dem_z:.2f} "
                 f"floor {min(inside) if inside else tn.mouth_z:.2f}..{max(inside) if inside else tn.mouth_z:.2f} "
                 f"depth {tn.depth_m:.2f} m width {tn.hull_width_m:.1f} m walls "
                 f"{tn.wall_length_m:.1f} m ramp {max(0.0, tn.top_s - tn.climb_from_s):.1f} m at "
                 f"{100.0 * tn.design_grade:.2f} % top s {tn.top_s:.1f} ends {tn.ends} "
                 f"trench-outside {tn.trench_outside_max_m:.3f} m clipped '{tn.clipped_by}'  "
                 f"{'; '.join(tn.notes)}")
            continue
        if tn.source in ("door", "sunken_road"):
            # RULINGS 2026-09-08b/c: the per-site line the report quotes
            out(f"    {tn.id}: {'sill' if tn.source == 'door' else 'cut'} {tn.mouth_z:.2f} "
                 f"ground {tn.mouth_dem_z:.2f} depth {tn.depth_m:.2f} m width "
                 f"{tn.hull_width_m:.1f} m well/plate {tn.wall_length_m:.1f} m ramp "
                 f"{max(0.0, tn.top_s - tn.climb_from_s):.1f} m at {100.0 * tn.design_grade:.2f} % "
                 f"top s {tn.top_s:.1f} ground {tn.top_ground_z if tn.top_ground_z is not None else float('nan'):.2f} "
                 f"trench-outside {tn.trench_outside_max_m:.3f} m clipped '{tn.clipped_by}'  "
                 f"{'; '.join(tn.notes)}")
            continue
        out(f"    {tn.id}: mouth {tn.mouth_z:.2f} (DEM {tn.mouth_dem_z:.2f}) top {tn.top_s:.0f} m"
             f"  half {tn.half_width_m:.1f} m  decks {len(tn.decks)}  {'; '.join(tn.notes)}")
    bs = pstats.basins
    if bs.objects is not None:
        o = bs.objects
        out(f"[{icao}] objects: {o.placements} placements, {o.resolved} resolved "
             f"({o.unresolved} unresolved, {o.stock_placements} stock), "
             f"{o.resources_parsed} resources parsed in {bs.object_read_s:.2f} s, "
             f"{o.below_grade_objects} below grade, {o.hard_deck_objects} hard-deck, "
             f"{lrep.objects_restored_for_read} restored-for-read (.anchor_bak)")
        for up in o.unresolved_paths[:10]:
            out(f"    unresolved {up}")
    # THE AT-GRADE READ, TIMED (owner RULINGS 2026-09-13bp (iii)): it was
    # untimed beside object_read_s and burned VHHH's 2,626 s planar stage
    out(f"[{icao}] at-grade read: {bs.grade_geometry_s:.2f} s, {bs.grade_calls} placements, "
         f"{bs.grade_unions} clip+union (one per distinct resource/plane), "
         f"{bs.grade_vertices} vertices")
    if bs.union_s:
        out("[%s] basin unions: " % icao + "  ".join(
            f"{k} {v:.1f}s/{bs.union_n.get(k, 0)}"
            for k, v in sorted(bs.union_s.items(), key=lambda kv: -kv[1])))
    if bs.regions or bs.refused:
        out(f"[{icao}] basins: regions {bs.regions}  basins {bs.basins}  cells cut {bs.cells_cut}  "
             f"refused {len(bs.refused)}  under min area {len(bs.small_regions)}")
        for r in bs.refused:
            out(f"    refused {r}")
        for b in pm.basins:
            out(f"    {b.id}: floor {b.floor_z:.2f}  R_est {b.rim_estimate_m:.2f}  deepest solid "
                 f"{b.solid_min_y_m:+.2f} (rendered {b.solid_min_z:.2f})  floor area {b.area_m2:.0f} m2  "
                 f"seat expect {b.seat_expect_m:+.2f} (anchor "
                 f"{'inside' if b.anchor_inside_floor else 'outside'} the floor, plate y "
                 f"{b.plate_y_m:+.2f})  at {b.anchor_ll[0]:.6f},{b.anchor_ll[1]:.6f}  "
                 f"{'; '.join(b.notes)}")


def shore_decision_lines(pm, airport, every: bool = False) -> list[str]:
    """§37 (11) THE SHORE DECISION (owner RULINGS 2026-09-29a): one summary
    line — the verdicts per witness — and one ``shore_undeclared`` row per
    contact no witness spoke for (29a (5)), with its ``lat, lon``.
    ``every`` lists every contact's verdict (the replay's read)."""
    vs = getattr(pm, "shore_verdicts", ()) or ()
    if not vs:
        return []
    from collections import Counter
    c = Counter((v[1], v[2]) for v in vs)
    parts = [f"{k} by {w} {n}" for (k, w), n in sorted(c.items())]
    lines = [f"  [planar] shore decision (29a): {len(vs)} contact(s): "
             + ", ".join(parts)]
    try:
        to_ll = airport.frame.transformers()[1]
    except Exception:                                   # pragma: no cover
        to_ll = None
    for v in vs:
        if v[2] != "default" and not every:
            continue
        ll = ""
        if to_ll is not None and v[4] == v[4]:
            la, lo = to_ll(v[4], v[5])
            ll = f" at {la:.6f}, {lo:.6f}"
        tail = (f"contact {v[6]:.0f} m, profile stations {v[7]} built {v[8]} "
                f"gentle {v[9]}")
        if v[2] == "default":
            lines.append(f"  [planar] shore_undeclared {v[0]}{ll}: {tail} "
                         f"— natural by default")
        else:
            h = "" if v[3] is None else f" height {v[3]:.2f} m"
            lines.append(f"  [planar] shore {v[1]} by {v[2]}{h} {v[0]}{ll}: "
                         f"{tail}")
    return lines
